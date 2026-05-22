"""Orchestration layer for the refund web service.

`RefundService` wraps the `refunds` engine into the steps the front-end
drives: create a case, ingest documents, pose the per-service
confirmation, and generate the certified-mail letter packet. It has no
HTTP knowledge -- `app.py` is the thin HTTP shell over this.
"""

from __future__ import annotations

import io
import json
import os
import re
import secrets
import threading
import zipfile
from datetime import date, datetime, timezone
from email.message import EmailMessage

from refunds import (
    AddOnProduct,
    CancellationRoute,
    CaseStatus,
    CaseStore,
    ProductType,
    RefundCase,
    Seller,
    Vehicle,
    estimate_case,
    generate_authorization,
    generate_letters_for_case,
    lookup,
    parse_contract_text,
    state_notes,
    text_to_pdf,
    total_estimated_refund,
)

_SAFE_NAME_RE = re.compile(r"[A-Za-z0-9._-]+")
_TEXT_EXTENSIONS = (".txt", ".text", ".md")


class ServiceError(Exception):
    """A client-correctable error (maps to HTTP 400)."""


class AccessDenied(Exception):
    """A missing or wrong case access token (maps to HTTP 403)."""


def _atomic_write(path: str, data: bytes) -> None:
    """Write a file atomically and privately (0600), so concurrent readers
    never see a partial file."""
    tmp = f"{path}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "").strip()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    return cleaned or "file"


def _money(value: float | None) -> str:
    return f"${value:,.2f}" if value is not None else "$0.00"


def _state_from_address(address_lines: list[str]) -> str | None:
    """Pull a 2-letter state code from a "City, ST ZIP" style address."""
    match = re.search(
        r"\b([A-Z]{2})\s+\d{5}(?:-\d{4})?\b", " ".join(address_lines)
    )
    return match.group(1) if match else None


class RefundService:
    def __init__(
        self,
        data_dir: str,
        *,
        service_name: str = "RefundRoute",
        service_contact: str = "support@refundroute.example",
        ocr: object | None = None,
        ensemble: object | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.cases = CaseStore(os.path.join(data_dir, "cases"))
        self.files_root = os.path.join(data_dir, "files")
        os.makedirs(self.files_root, exist_ok=True)
        self.service_name = service_name
        self.service_contact = service_contact
        # Serializes the read-modify-write of a case's files so concurrent
        # requests on one case cannot lose each other's updates.
        self._lock = threading.Lock()
        # Reading scanned (non-text) contracts. A redundant, cross-checked
        # ensemble is preferred; `ocr` is the single-reader fallback. With
        # neither supplied, an ensemble is built from any configured model
        # API keys (ANTHROPIC_API_KEY / GEMINI_API_KEY).
        self.ocr = ocr
        self.ensemble = ensemble
        if self.ocr is None and self.ensemble is None:
            from refunds import build_default_ensemble

            self.ensemble = build_default_ensemble()

    # -- file storage -----------------------------------------------------

    def _case_dir(self, case_id: str) -> str:
        path = os.path.join(self.files_root, case_id)
        os.makedirs(path, exist_ok=True)
        os.chmod(path, 0o700)
        return path

    def _meta_path(self, case_id: str) -> str:
        return os.path.join(self._case_dir(case_id), "_meta.json")

    def _load_meta(self, case_id: str) -> dict:
        path = self._meta_path(case_id)
        if not os.path.isfile(path):
            return {
                "documents": [],
                "generated": [],
                "parse_warnings": [],
                "access_token": "",
            }
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def _save_meta(self, case_id: str, meta: dict) -> None:
        _atomic_write(
            self._meta_path(case_id),
            json.dumps(meta, indent=2).encode("utf-8"),
        )

    def _store_file(self, case_id: str, name: str, data: bytes) -> None:
        _atomic_write(os.path.join(self._case_dir(case_id), name), data)

    def get_file(self, case_id: str, name: str) -> tuple[bytes, str]:
        if not _SAFE_NAME_RE.fullmatch(name):
            raise ServiceError(f"Invalid file name: {name!r}")
        path = os.path.join(self._case_dir(case_id), name)
        if not os.path.isfile(path):
            raise KeyError(name)
        with open(path, "rb") as handle:
            return handle.read(), _content_type(name)

    # -- step 1: create a case -------------------------------------------

    def create_case(self, intake: dict) -> dict:
        legal_name = (intake.get("legal_name") or "").strip()
        vin = (intake.get("vin") or "").strip().upper()
        sale_date_raw = (intake.get("sale_date") or "").strip()
        if not legal_name:
            raise ServiceError("Your legal name is required.")
        if not vin:
            raise ServiceError("The vehicle VIN (or plate) is required.")
        try:
            sale_date = date.fromisoformat(sale_date_raw)
        except ValueError:
            raise ServiceError("Sale date must be a valid date (YYYY-MM-DD).")

        address_lines = [
            line.strip()
            for line in (intake.get("address_lines") or [])
            if line and line.strip()
        ]
        seller = Seller(
            legal_name=legal_name,
            address_lines=address_lines,
            email=(intake.get("email") or "").strip(),
            phone=(intake.get("phone") or "").strip(),
        )
        case = RefundCase(
            seller=seller,
            vehicle=Vehicle(vin=vin),
            sale_date=sale_date,
            status=CaseStatus.INTAKE,
        )
        self.cases.save(case)
        access_token = secrets.token_urlsafe(24)
        self._save_meta(
            case.case_id,
            {
                "documents": [],
                "generated": [],
                "parse_warnings": [],
                "access_token": access_token,
            },
        )
        # The token is returned exactly once, here -- the client must keep
        # it. Every later request for this case must present it.
        return {**self._view(case), "access_token": access_token}

    def authorize(self, case_id: str, token: str | None) -> None:
        """Raise AccessDenied unless `token` matches the case's token.

        Returns nothing on success. Used to gate every case-scoped
        request; a wrong token and an unknown case are indistinguishable,
        so case ids do not have to be secret.
        """
        expected = self._load_meta(case_id).get("access_token", "")
        if (
            not expected
            or not token
            or not secrets.compare_digest(str(token), expected)
        ):
            raise AccessDenied("Invalid or missing case access token.")

    # -- step 2: ingest documents ----------------------------------------

    def add_document(
        self, case_id: str, *, filename: str, data: bytes, kind: str
    ) -> dict:
        with self._lock:
            return self._add_document(
                case_id, filename=filename, data=data, kind=kind
            )

    def _add_document(
        self, case_id: str, *, filename: str, data: bytes, kind: str
    ) -> dict:
        case = self.cases.load(case_id)
        stored_name = f"doc-{_slug(kind)}-{_safe_filename(filename)}"
        self._store_file(case_id, stored_name, data)

        meta = self._load_meta(case_id)
        meta["documents"] = [
            doc for doc in meta["documents"] if doc["name"] != stored_name
        ]
        meta["documents"].append(
            {
                "name": stored_name,
                "original_name": filename,
                "kind": kind,
                "size": len(data),
            }
        )

        if kind == "contract":
            stored_path = os.path.join(self._case_dir(case_id), stored_name)
            ingest = self._ingest_contract(case, stored_path, filename, data)
            meta["parse_warnings"] = ingest["warnings"]
            meta["review"] = ingest["review"]
            meta["review_detail"] = ingest.get("review_detail", {})
            meta["extraction_method"] = ingest["method"]
            self.cases.save(case)

        self._save_meta(case_id, meta)
        return self._view(case)

    def _ingest_contract(
        self, case: RefundCase, path: str, filename: str, data: bytes
    ) -> dict:
        """Read a contract into case.products; return warnings/review/method."""
        if filename.lower().endswith(_TEXT_EXTENSIONS):
            parsed = parse_contract_text(data.decode("utf-8", errors="replace"))
            self._apply_parsed(case, parsed)
            return {
                "warnings": list(parsed.warnings),
                "review": {},
                "method": "text contract (rule-based parser)",
            }

        if self.ensemble is not None:
            try:
                result = self.ensemble.extract(path)  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                return {
                    "warnings": [f"Could not read this contract: {exc}"],
                    "review": {},
                    "method": "ensemble (failed)",
                }
            return self._apply_ensemble(case, result)

        if self.ocr is not None:
            try:
                text = self.ocr.extract_text(path)  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                return {
                    "warnings": [f"Could not read this contract: {exc}"],
                    "review": {},
                    "method": "single reader (failed)",
                }
            parsed = parse_contract_text(text)
            self._apply_parsed(case, parsed)
            return {
                "warnings": list(parsed.warnings),
                "review": {},
                "method": "single reader",
            }

        return {
            "warnings": [
                "This contract is a PDF or image, and document reading is not "
                "configured on this server. Upload a text version, paste the "
                "contract text, or set ANTHROPIC_API_KEY (and optionally "
                "GEMINI_API_KEY) to enable automatic reading."
            ],
            "review": {},
            "method": "none",
        }

    def _apply_parsed(self, case: RefundCase, parsed) -> None:
        case.products = parsed.products
        if parsed.detected_purchase_date is not None:
            case.vehicle.purchase_date = parsed.detected_purchase_date
            for product in case.products:
                if product.start_date is None:
                    product.start_date = parsed.detected_purchase_date
        if parsed.detected_vin and not case.vehicle.vin:
            case.vehicle.vin = parsed.detected_vin
        case.status = CaseStatus.AWAITING_AUTHORIZATION

    def _apply_ensemble(self, case: RefundCase, result) -> dict:
        case.products = [item.product for item in result.products]
        purchase_date = None
        if result.purchase_date:
            try:
                purchase_date = date.fromisoformat(result.purchase_date[:10])
            except ValueError:
                purchase_date = None
        if purchase_date is not None:
            case.vehicle.purchase_date = purchase_date
            for product in case.products:
                if product.start_date is None:
                    product.start_date = purchase_date
        if result.vin and not case.vehicle.vin:
            case.vehicle.vin = result.vin
        case.status = CaseStatus.AWAITING_AUTHORIZATION

        warnings = list(result.warnings)
        if purchase_date is None and case.products:
            warnings.append(
                "Contract date not found -- refund estimates need a coverage "
                "start date."
            )
        review = {
            item.product.product_type.value: item.review_fields
            for item in result.products
            if item.review_fields
        }
        review_detail = {
            item.product.product_type.value: item.field_candidates
            for item in result.products
            if item.field_candidates
        }
        method = (
            "cross-checked by " + ", ".join(result.extractor_names)
            if result.extractor_names
            else "ensemble"
        )
        return {
            "warnings": warnings,
            "review": review,
            "review_detail": review_detail,
            "method": method,
        }

    # -- step 3: confirm services ----------------------------------------

    def confirm_services(self, case_id: str, keep_indices: list[int]) -> dict:
        with self._lock:
            return self._confirm_services(case_id, keep_indices)

    def _confirm_services(
        self, case_id: str, keep_indices: list[int]
    ) -> dict:
        case = self.cases.load(case_id)
        kept = set(keep_indices)
        for index in kept:
            if not 0 <= index < len(case.products):
                raise ServiceError(f"No service at position {index}.")
        case.products = [
            product for i, product in enumerate(case.products) if i in kept
        ]
        case.status = (
            CaseStatus.READY_TO_SEND if case.products else CaseStatus.INTAKE
        )
        self.cases.save(case)
        return self._view(case)

    # -- step 4: generate the packet -------------------------------------

    def generate(self, case_id: str) -> dict:
        with self._lock:
            return self._generate(case_id)

    def _generate(self, case_id: str) -> dict:
        case = self.cases.load(case_id)
        if not case.products:
            raise ServiceError("Confirm at least one service before generating.")

        meta = self._load_meta(case_id)
        generated: list[dict] = []
        letters = generate_letters_for_case(
            case,
            service_name=self.service_name,
            service_contact=self.service_contact,
        )
        authorization = generate_authorization(
            case,
            service_name=self.service_name,
            service_contact=self.service_contact,
        )
        total = len(letters)

        # One self-contained, print-ready packet per outbound mailing:
        # an instruction sheet on top, then the letter, then the
        # authorization -- page-numbered, with a running header.
        for number, letter in enumerate(letters, start=1):
            product = letter.product
            cover = self._instruction_sheet(case, letter, number, total)
            packet_text = cover + "\f" + letter.body + "\f" + authorization
            contract = product.contract_number or "no contract number"
            header = (
                f"Re: {product.product_type.value} -- Contract {contract} "
                f"(mailing {number} of {total})"
            )
            packet_pdf = text_to_pdf(packet_text, header=header)

            slug = _slug(letter.recipient_name)
            packet_name = f"mailing-{number}-{slug}.pdf"
            self._store_file(case_id, packet_name, packet_pdf)
            generated.append(
                {
                    "name": packet_name,
                    "kind": "packet",
                    "description": (
                        f"Mailing {number} of {total}: "
                        f"{product.product_type.value} to {letter.recipient_name}"
                    ),
                }
            )

            admin = lookup(product.administrator_name)
            if admin.email and admin.cancellation_route != CancellationRoute.DEALER:
                eml_name = f"mailing-{number}-{slug}.eml"
                self._store_file(
                    case_id,
                    eml_name,
                    self._email_draft(case, letter, admin, packet_name, packet_pdf),
                )
                generated.append(
                    {
                        "name": eml_name,
                        "kind": "email",
                        "description": (
                            f"Email draft to {admin.email} -- send in parallel "
                            f"with mailing {number}"
                        ),
                    }
                )

        zip_name = "refund-packet.zip"
        self._store_file(
            case_id, zip_name, self._zip(case_id, meta["documents"], generated)
        )
        generated.append(
            {
                "name": zip_name,
                "kind": "bundle",
                "description": "Every mailing packet, zipped",
            }
        )

        meta["generated"] = generated
        self._save_meta(case_id, meta)
        case.status = CaseStatus.READY_TO_SEND
        self.cases.save(case)
        return self._view(case)

    def _email_draft(
        self, case: RefundCase, letter, admin, pdf_name: str, pdf_bytes: bytes
    ) -> bytes:
        message = EmailMessage()
        message["To"] = admin.email
        message["From"] = case.seller.email or "[your email address]"
        message["Subject"] = letter.subject
        message.set_content(
            letter.body
            + "\n\nAttached is my cancellation request and authorization (PDF). "
            "I am also sending this request by USPS Certified Mail, with a copy "
            "of the bill of sale enclosed.\n"
        )
        message.add_attachment(
            pdf_bytes, maintype="application", subtype="pdf", filename=pdf_name
        )
        return message.as_bytes()

    def _instruction_sheet(
        self, case: RefundCase, letter, number: int, total: int
    ) -> str:
        """The cover page that sits on top of one outbound mailing."""
        product = letter.product
        zip_match = re.search(
            r"\b\d{5}(?:-\d{4})?\b", " ".join(case.seller.address_lines)
        )

        lines = [
            f"MAILING {number} OF {total}",
            "INSTRUCTION SHEET -- keep this page on top of the envelope",
            "",
            "WHAT THIS IS",
            "  Your request to cancel one vehicle add-on product and claim a",
            "  pro-rata refund, now that you have sold the vehicle.",
            "",
            f"    Product:   {product.product_type.value}",
            f"    Provider:  {letter.recipient_name}",
            f"    Contract:  {product.contract_number or '(not found -- see the letter)'}",
            "",
            "SEND THIS PACKET TO",
        ]
        for addr_line in [letter.recipient_name, *letter.recipient_address_lines]:
            lines.append(f"    {addr_line}")
        lines += [
            "",
            "HOW TO SEND IT",
            "  Send it by USPS Certified Mail, Return Receipt Requested. That",
            "  gives you dated proof that the provider received it.",
            "",
            "  Find your nearest Post Office at:",
            "    https://tools.usps.com/find-location.htm",
        ]
        if zip_match:
            lines.append(f"  (search your ZIP code: {zip_match.group(0)})")
        lines += [
            "",
            "BEFORE YOU SEAL THE ENVELOPE",
            "  [ ] Sign and date the authorization page in this packet.",
            "  [ ] Enclose a copy of your bill of sale.",
            f"  [ ] Enclose a copy of your {product.product_type.value} contract.",
            "  [ ] Keep your Certified Mail receipt and the green return card.",
            "",
            "WHAT'S IN THIS PACKET",
            "  1. This instruction sheet.",
            "  2. The cancellation and pro-rata refund letter.",
            "  3. The authorization for you to sign.",
        ]

        admin = lookup(product.administrator_name)
        if admin.email and admin.cancellation_route != CancellationRoute.DEALER:
            lines += [
                "",
                f"  Optional: a pre-filled email to {admin.email} is also",
                "  included, so you can submit this request electronically in",
                "  parallel. The certified mailing remains your proof of record.",
            ]

        if letter.warnings:
            lines.append("")
            lines.append("PLEASE CHECK")
            for warning in letter.warnings:
                lines.append(f"  ! {warning}")
        return "\n".join(lines) + "\n"

    def _zip(
        self, case_id: str, documents: list[dict], generated: list[dict]
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry in generated:
                data, _ = self.get_file(case_id, entry["name"])
                archive.writestr(entry["name"], data)
            for doc in documents:
                data, _ = self.get_file(case_id, doc["name"])
                archive.writestr(f"your-documents/{doc['original_name']}", data)
        return buffer.getvalue()

    # -- views ------------------------------------------------------------

    def get_case(self, case_id: str) -> dict:
        return self._view(self.cases.load(case_id))

    # -- operator console -------------------------------------------------

    _STAGES = (
        "Started",
        "Documents read",
        "Services confirmed",
        "Letters generated",
    )

    def _stage(self, case: RefundCase, meta: dict) -> int:
        """How far a case got: 1 Started .. 4 Letters generated."""
        if meta.get("generated"):
            return 4
        if case.status == CaseStatus.READY_TO_SEND:
            return 3
        if case.products:
            return 2
        return 1

    def operator_case(self, case_id: str) -> dict:
        """Full case detail for the operator (same shape as the customer view)."""
        return self._view(self.cases.load(case_id))

    def operator_overview(self) -> dict:
        """Aggregate every case into the operator dashboard payload."""
        rows: list[dict] = []
        for case in self.cases.list_cases():
            meta = self._load_meta(case.case_id)
            stage = self._stage(case, meta)
            packets = [
                g for g in meta.get("generated", []) if g.get("kind") == "packet"
            ]
            rows.append(
                {
                    "case_id": case.case_id,
                    "seller": case.seller.legal_name,
                    "vehicle": case.vehicle.description,
                    "vin": case.vehicle.vin,
                    "stage": self._STAGES[stage - 1],
                    "stage_num": stage,
                    "products": len(case.products),
                    "estimated_total": total_estimated_refund(case),
                    "review": meta.get("review", {}),
                    "packets": len(packets),
                    "created_at": case.created_at,
                    "updated_at": case.updated_at,
                }
            )

        reached = [0, 0, 0, 0]
        stalled = [0, 0, 0, 0]
        for row in rows:
            for index in range(row["stage_num"]):
                reached[index] += 1
            stalled[row["stage_num"] - 1] += 1

        funnel = [
            {
                "stage": self._STAGES[index],
                "reached": reached[index],
                # cases sitting at this stage with nowhere further (an
                # abandonment); the final stage is a completion, not a stall.
                "stalled_here": stalled[index] if index < 3 else 0,
            }
            for index in range(4)
        ]

        needs_review = [
            {
                "case_id": row["case_id"],
                "seller": row["seller"],
                "stage": row["stage"],
                "review": row["review"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
            if row["review"]
        ]

        recent = sorted(rows, key=lambda r: r["created_at"], reverse=True)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "totals": {
                "started": reached[0],
                "documents_read": reached[1],
                "services_confirmed": reached[2],
                "letters_generated": reached[3],
                "packets_generated": sum(row["packets"] for row in rows),
                "needs_review": len(needs_review),
            },
            "funnel": funnel,
            "needs_review": needs_review,
            "recent": recent[:50],
        }

    _FIELD_ATTR = {"administrator": "administrator_name"}

    @staticmethod
    def _coerce_field(field: str, value: object) -> object:
        """Coerce an operator-entered correction to the field's type."""
        if field in ("price", "cancellation_fee"):
            try:
                text = str(value).replace("$", "").replace(",", "").strip()
                return round(float(text), 2)
            except (ValueError, TypeError):
                return 0.0
        if field in ("term_months", "term_miles"):
            try:
                return int(float(str(value).replace(",", "").strip()))
            except (ValueError, TypeError):
                return None
        return str(value).strip()

    def resolve_case(self, case_id: str, corrections: list[dict]) -> dict:
        """Apply operator corrections to a flagged case and clear its review.

        Each correction: {product_type, field, value}.
        """
        with self._lock:
            case = self.cases.load(case_id)
            by_type = {p.product_type.value: p for p in case.products}
            for correction in corrections:
                product = by_type.get(correction.get("product_type"))
                field = correction.get("field")
                if product is None or not field:
                    continue
                attr = self._FIELD_ATTR.get(field, field)
                if not hasattr(product, attr):
                    continue
                setattr(product, attr, self._coerce_field(field, correction.get("value")))
            self.cases.save(case)

            meta = self._load_meta(case_id)
            meta["review"] = {}
            meta["review_detail"] = {}
            meta["resolution"] = {
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "fields_corrected": len(corrections),
            }
            self._save_meta(case_id, meta)
            return self._view(case)

    def _confirmation_text(
        self, product: AddOnProduct, estimate
    ) -> tuple[str, str]:
        """Return (plain headline, collapsible detail) for the confirm step."""
        label = product.product_type.value
        admin = product.administrator_name or "the provider"
        if product.price and product.price > 0:
            headline = (
                f"You appear to have bought {label} from {admin} for "
                f"{_money(product.price)}."
            )
        else:
            headline = (
                f"You appear to have bought {label} from {admin}. We could not "
                f"read the price from your contract."
            )

        detail: list[str] = []
        if estimate.can_estimate and estimate.net_refund > 0:
            detail.append(
                f"Because you sold the vehicle, you appear to be owed a "
                f"pro-rata refund of roughly {_money(estimate.net_refund)} -- "
                f"the unused part of what you paid, based on {estimate.basis}."
            )
            if product.cancellation_fee and product.cancellation_fee > 0:
                detail.append(
                    f"This already reflects the contract's "
                    f"{_money(product.cancellation_fee)} cancellation fee. It "
                    f"is an estimate; the provider sets the binding amount."
                )
            else:
                detail.append(
                    "This is an estimate, before any cancellation fee the "
                    "provider may deduct. The provider sets the binding amount."
                )
        else:
            detail.append(
                "Because you sold the vehicle, you appear to be owed a pro-rata "
                "refund of the unused part of what you paid. The provider will "
                "calculate the exact amount."
            )
        if product.product_type == ProductType.GAP:
            detail.append(
                "GAP refunds are also required by law in many states, though "
                "the exact method varies."
            )
        return headline, " ".join(detail)

    def _view(self, case: RefundCase) -> dict:
        meta = self._load_meta(case.case_id)
        review = meta.get("review", {})
        estimates = estimate_case(case)
        products = []
        for index, (product, estimate) in enumerate(zip(case.products, estimates)):
            headline, detail = self._confirmation_text(product, estimate)
            products.append(
                {
                    "index": index,
                    "product_type": product.product_type.value,
                    "administrator": product.administrator_name or "(unknown)",
                    "contract_number": product.contract_number,
                    "price": product.price,
                    "term_months": product.term_months,
                    "term_miles": product.term_miles,
                    "estimate": {
                        "can_estimate": estimate.can_estimate,
                        "net_refund": estimate.net_refund,
                        "gross_refund": estimate.gross_refund,
                        "basis": estimate.basis,
                    },
                    "headline": headline,
                    "detail": detail,
                    "review_fields": review.get(product.product_type.value, []),
                }
            )
        prefix = f"/api/cases/{case.case_id}/files/"
        return {
            "case_id": case.case_id,
            "status": case.status.value,
            "seller": {
                "legal_name": case.seller.legal_name,
                "address_lines": case.seller.address_lines,
                "email": case.seller.email,
                "phone": case.seller.phone,
            },
            "vehicle": {
                "vin": case.vehicle.vin,
                "description": case.vehicle.description,
                "purchase_date": (
                    case.vehicle.purchase_date.isoformat()
                    if case.vehicle.purchase_date
                    else None
                ),
            },
            "sale_date": case.sale_date.isoformat(),
            "created_at": case.created_at,
            "updated_at": case.updated_at,
            "products": products,
            "total_estimated_refund": total_estimated_refund(case),
            "parse_warnings": meta.get("parse_warnings", []),
            "extraction_method": meta.get("extraction_method", ""),
            "review_detail": meta.get("review_detail", {}),
            "resolution": meta.get("resolution"),
            "rules_notes": state_notes(
                _state_from_address(case.seller.address_lines) or ""
            ),
            "documents": [
                {**doc, "download_url": prefix + doc["name"]}
                for doc in meta.get("documents", [])
            ],
            "generated": [
                {**item, "download_url": prefix + item["name"]}
                for item in meta.get("generated", [])
            ],
        }


def _content_type(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith(".pdf"):
        return "application/pdf"
    if lowered.endswith(".zip"):
        return "application/zip"
    if lowered.endswith(".eml"):
        return "message/rfc822"
    if lowered.endswith((".txt", ".text")):
        return "text/plain; charset=utf-8"
    if lowered.endswith(".json"):
        return "application/json"
    return "application/octet-stream"
