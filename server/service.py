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
import zipfile
from datetime import date
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
    text_to_pdf,
    total_estimated_refund,
)

_SAFE_NAME_RE = re.compile(r"[A-Za-z0-9._-]+")
_TEXT_EXTENSIONS = (".txt", ".text", ".md")


class ServiceError(Exception):
    """A client-correctable error (maps to HTTP 400)."""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "").strip()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    return cleaned or "file"


def _money(value: float | None) -> str:
    return f"${value:,.2f}" if value is not None else "$0.00"


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
        return path

    def _meta_path(self, case_id: str) -> str:
        return os.path.join(self._case_dir(case_id), "_meta.json")

    def _load_meta(self, case_id: str) -> dict:
        path = self._meta_path(case_id)
        if not os.path.isfile(path):
            return {"documents": [], "generated": [], "parse_warnings": []}
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def _save_meta(self, case_id: str, meta: dict) -> None:
        with open(self._meta_path(case_id), "w", encoding="utf-8") as handle:
            json.dump(meta, handle, indent=2)

    def _store_file(self, case_id: str, name: str, data: bytes) -> None:
        with open(os.path.join(self._case_dir(case_id), name), "wb") as handle:
            handle.write(data)

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
        self._save_meta(
            case.case_id,
            {"documents": [], "generated": [], "parse_warnings": []},
        )
        return self._view(case)

    # -- step 2: ingest documents ----------------------------------------

    def add_document(
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
        method = (
            "cross-checked by " + ", ".join(result.extractor_names)
            if result.extractor_names
            else "ensemble"
        )
        return {"warnings": warnings, "review": review, "method": method}

    # -- step 3: confirm services ----------------------------------------

    def confirm_services(self, case_id: str, keep_indices: list[int]) -> dict:
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

        for letter in letters:
            base = f"letter-{_slug(letter.recipient_name)}"
            pdf_name = f"{base}.pdf"
            pdf_bytes = text_to_pdf(letter.body)
            self._store_file(case_id, pdf_name, pdf_bytes)
            generated.append(
                {
                    "name": pdf_name,
                    "kind": "letter",
                    "description": f"Certified-mail letter to {letter.recipient_name}",
                }
            )

            admin = lookup(letter.product.administrator_name)
            if admin.email and admin.cancellation_route != CancellationRoute.DEALER:
                eml_name = f"{base}.eml"
                self._store_file(
                    case_id,
                    eml_name,
                    self._email_draft(case, letter, admin, pdf_name, pdf_bytes),
                )
                generated.append(
                    {
                        "name": eml_name,
                        "kind": "email",
                        "description": f"Email draft to {admin.email}",
                    }
                )

        auth_name = "authorization.pdf"
        auth_text = generate_authorization(
            case, service_name=self.service_name, service_contact=self.service_contact
        )
        self._store_file(case_id, auth_name, text_to_pdf(auth_text))
        generated.append(
            {
                "name": auth_name,
                "kind": "authorization",
                "description": "Limited authorization for you to sign",
            }
        )

        checklist_name = "mailing-checklist.txt"
        checklist = self._checklist(case, letters)
        self._store_file(case_id, checklist_name, checklist.encode("utf-8"))
        generated.append(
            {
                "name": checklist_name,
                "kind": "checklist",
                "description": "Step-by-step certified-mail checklist",
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
                "description": "Everything above, zipped",
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
            + "\n\nAttached: the cancellation request (PDF). Please also see "
            "the enclosed bill of sale and signed authorization.\n"
        )
        message.add_attachment(
            pdf_bytes, maintype="application", subtype="pdf", filename=pdf_name
        )
        return message.as_bytes()

    def _checklist(self, case: RefundCase, letters: list) -> str:
        lines = [
            f"MAILING CHECKLIST -- Case {case.case_id}",
            "",
            f"Seller: {case.seller.legal_name}",
            f"Vehicle: {case.vehicle.description}  (VIN {case.vehicle.vin})",
            f"Sold: {case.sale_date.isoformat()}",
            "",
            f"You have {len(letters)} cancellation request(s) to send.",
            "For EACH letter below:",
            "",
            "  [ ] Print the letter (PDF).",
            "  [ ] Sign and date the authorization document. Have it notarized",
            "      if the administrator requires it.",
            "  [ ] Enclose: a copy of the bill of sale, the signed",
            "      authorization, and a copy of the product contract.",
            "  [ ] Mail it from USPS as Certified Mail, Return Receipt",
            "      Requested. Keep the receipt and tracking number.",
            "",
            "LETTERS",
            "-------",
        ]
        for index, letter in enumerate(letters, start=1):
            lines.append(
                f"{index}. {letter.recipient_name} -- "
                f"{letter.product.product_type.value} "
                f"(Contract {letter.product.contract_number or 'unknown'})"
            )
            for addr_line in letter.recipient_address_lines:
                lines.append(f"     {addr_line}")
            admin = lookup(letter.product.administrator_name)
            if admin.email and admin.cancellation_route != CancellationRoute.DEALER:
                lines.append(f"     A pre-filled email draft is also included.")
            for warning in letter.warnings:
                lines.append(f"     ! {warning}")
            lines.append("")
        lines.append(
            "Keep every Certified Mail receipt and return card -- they are your"
        )
        lines.append("proof the request was sent and received.")
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

    def _question(self, product: AddOnProduct, estimate) -> str:
        label = product.product_type.value
        admin = product.administrator_name or "the administrator"
        text = (
            f"It appears you purchased {label} from {admin} for "
            f"{_money(product.price)}."
        )
        if estimate.can_estimate:
            text += (
                f" Because you sold the vehicle, you appear to be entitled to a "
                f"pro-rata refund of approximately {_money(estimate.net_refund)}, "
                f"based on {estimate.basis}."
            )
        else:
            text += (
                " Because you sold the vehicle, you appear to be entitled to a "
                "pro-rata refund of the unearned portion you paid; the "
                "administrator will calculate the exact amount."
            )
        if product.product_type == ProductType.GAP:
            text += (
                " GAP refunds on early payoff or sale are also required by law "
                "in many states."
            )
        return text

    def _view(self, case: RefundCase) -> dict:
        meta = self._load_meta(case.case_id)
        review = meta.get("review", {})
        estimates = estimate_case(case)
        products = []
        for index, (product, estimate) in enumerate(zip(case.products, estimates)):
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
                    "question": self._question(product, estimate),
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
            "products": products,
            "total_estimated_refund": total_estimated_refund(case),
            "parse_warnings": meta.get("parse_warnings", []),
            "extraction_method": meta.get("extraction_method", ""),
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
