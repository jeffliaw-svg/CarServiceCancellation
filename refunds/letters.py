"""Cancellation + pro-rata refund letter generation.

One letter is produced per add-on product. The recipient is the product
administrator, unless the administrator's cancellation route requires the
selling dealer to submit the cancellation, in which case the letter is
addressed to the dealer instead.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date

from .administrators import lookup
from .models import AddOnProduct, Administrator, CancellationRoute, RefundCase
from .pdf import write_pdf
from .prorata import estimate_refund

DEFAULT_SERVICE_NAME = "[Your Service Name]"
DEFAULT_SERVICE_CONTACT = "[service phone / email]"


@dataclass
class Letter:
    case_id: str
    product: AddOnProduct
    recipient_name: str
    recipient_address_lines: list[str]
    subject: str
    body: str
    warnings: list[str] = field(default_factory=list)

    @property
    def filename(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.recipient_name.lower()).strip("-")
        return f"{self.case_id}_{slug}.txt"


def fmt_money(value: float | None) -> str:
    return f"${value:,.2f}" if value is not None else "$0.00"


def _date_str(value: date) -> str:
    return f"{value:%B} {value.day}, {value.year}"


def _term_str(product: AddOnProduct) -> str:
    parts: list[str] = []
    if product.term_months:
        parts.append(f"{product.term_months} months")
    if product.term_miles:
        parts.append(f"{product.term_miles:,} miles")
    return " / ".join(parts) if parts else "the term stated in the Contract"


def _resolve_recipient(
    case: RefundCase, admin: Administrator
) -> tuple[str, list[str], str, list[str]]:
    """Return (recipient_name, address_lines, attn, warnings)."""
    warnings: list[str] = []

    if admin.cancellation_route == CancellationRoute.DEALER:
        recipient_name = case.vehicle.selling_dealer or "[Selling Dealer]"
        address_lines = list(case.vehicle.dealer_address_lines)
        if not case.vehicle.selling_dealer:
            warnings.append(
                "Cancellation routes through the selling dealer, but the dealer "
                "is not yet identified."
            )
        if not address_lines:
            address_lines = ["<<VERIFY: selling dealer mailing address required>>"]
            warnings.append("Selling dealer mailing address is not on file.")
        return recipient_name, address_lines, "Finance & Insurance (F&I) Department", warnings

    if not admin.address_verified:
        warnings.append(
            "Administrator mailing address is not verified -- confirm before mailing."
        )
    if admin.cancellation_route == CancellationRoute.EITHER:
        warnings.append(
            "Cancellation route is uncertain; some administrators require the "
            "selling dealer to submit the cancellation."
        )
    return admin.name, list(admin.address_lines), admin.attn, warnings


def generate_letter(
    case: RefundCase,
    product: AddOnProduct,
    *,
    today: date | None = None,
    service_name: str = DEFAULT_SERVICE_NAME,
    service_contact: str = DEFAULT_SERVICE_CONTACT,
    registry: dict[str, Administrator] | None = None,
) -> Letter:
    today = today or date.today()
    admin = lookup(product.administrator_name, registry)
    recipient_name, recipient_address, attn, warnings = _resolve_recipient(case, admin)
    routes_through_dealer = admin.cancellation_route == CancellationRoute.DEALER

    if admin.notes:
        warnings.append(f"Administrator note: {admin.notes}")
    if not product.contract_number:
        warnings.append("Contract / agreement number is missing.")
    if not case.authorization_signed:
        warnings.append(
            "Signed customer authorization is not yet on file -- required before mailing."
        )

    estimate = estimate_refund(product, case)
    warnings.extend(estimate.warnings)

    seller = case.seller
    vehicle = case.vehicle
    product_name = product.product_type.value

    subject = (
        f"Cancellation and Pro-Rata Refund Request -- {product_name}, "
        f"Contract No. {product.contract_number or '[unknown]'}"
    )

    if routes_through_dealer:
        opening = (
            f"I am writing on behalf of {seller.legal_name}, the original purchaser "
            f"and contract holder of the above-referenced {product_name} (the "
            f'"Contract"), which was sold by your dealership. The Contract is '
            f"administered by {admin.name}, whose cancellation procedure requires "
            f"the selling dealer to submit the request."
        )
        action_intro = (
            "Accordingly, please treat this letter as a formal request that your "
            "dealership:"
        )
    else:
        opening = (
            f"I am writing on behalf of {seller.legal_name}, the original purchaser "
            f"and contract holder of the above-referenced {product_name} (the "
            f'"Contract").'
        )
        action_intro = "Accordingly, please treat this letter as a formal request to:"

    if estimate.can_estimate:
        estimate_paragraph = (
            f"Based on a purchase price of {fmt_money(product.price)}, a term of "
            f"{_term_str(product)}, and {estimate.basis}, the estimated unearned "
            f"refund is approximately {fmt_money(estimate.net_refund)}"
        )
        if product.cancellation_fee:
            estimate_paragraph += (
                f" (after a stated cancellation fee of "
                f"{fmt_money(product.cancellation_fee)})"
            )
        estimate_paragraph += (
            ". This figure is an estimate only; please calculate the exact "
            "unearned amount in accordance with the cancellation provisions of "
            "the Contract."
        )
    else:
        estimate_paragraph = (
            "Please calculate the unearned amount due in accordance with the "
            "cancellation provisions of the Contract and issue the pro-rata "
            "refund accordingly."
        )

    lines: list[str] = []
    lines.append(_date_str(today))
    lines.append("")
    lines.append(recipient_name)
    if attn:
        lines.append(f"Attn: {attn}")
    lines.extend(recipient_address)
    lines.append("")
    lines.append("Re: " + subject)
    lines.append(f"    Vehicle: {vehicle.description}")
    lines.append(f"    VIN: {vehicle.vin}")
    lines.append(f"    Date of sale: {_date_str(case.sale_date)}")
    lines.append("")
    lines.append("To Whom It May Concern:")
    lines.append("")
    lines.append(opening)
    lines.append("")
    lines.append(
        f"{seller.legal_name} sold the above vehicle on {_date_str(case.sale_date)} "
        f"and no longer owns it. The contract holder is therefore entitled to "
        f"cancel the Contract and to receive a pro-rata refund of the unearned "
        f"portion of the amount paid."
    )
    lines.append("")
    lines.append(action_intro)
    lines.append("")
    lines.append(f"  1. Cancel the Contract effective {_date_str(case.sale_date)}; and")
    lines.append(
        f"  2. Issue a pro-rata refund of all unearned amounts payable to "
        f"{seller.legal_name} at the address shown below."
    )
    lines.append("")
    lines.append(estimate_paragraph)
    lines.append("")
    lines.append("Enclosed please find:")
    lines.append("")
    lines.append("  - A copy of the bill of sale evidencing the sale of the vehicle;")
    lines.append(
        f"  - A signed authorization permitting {service_name} to act on behalf "
        f"of {seller.legal_name} in this matter; and"
    )
    lines.append("  - A copy of the Contract.")
    lines.append("")
    lines.append("Please send the refund and written confirmation of cancellation to:")
    lines.append("")
    lines.append(f"  {seller.legal_name}")
    for addr_line in seller.address_lines:
        lines.append(f"  {addr_line}")
    lines.append("")
    lines.append(
        f"If you require any additional information, please contact {service_name} "
        f"at {service_contact}."
    )
    lines.append("")
    lines.append("Sincerely,")
    lines.append("")
    lines.append("")
    lines.append("_______________________________")
    lines.append(seller.legal_name)
    lines.append(f"(by {service_name}, as authorized agent)")

    return Letter(
        case_id=case.case_id,
        product=product,
        recipient_name=recipient_name,
        recipient_address_lines=recipient_address,
        subject=subject,
        body="\n".join(lines) + "\n",
        warnings=warnings,
    )


def generate_letters_for_case(
    case: RefundCase,
    *,
    today: date | None = None,
    service_name: str = DEFAULT_SERVICE_NAME,
    service_contact: str = DEFAULT_SERVICE_CONTACT,
    registry: dict[str, Administrator] | None = None,
) -> list[Letter]:
    return [
        generate_letter(
            case,
            product,
            today=today,
            service_name=service_name,
            service_contact=service_contact,
            registry=registry,
        )
        for product in case.products
    ]


def write_letters(letters: list[Letter], out_dir: str) -> list[str]:
    """Write each letter body to a .txt file; return the written paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths: list[str] = []
    for letter in letters:
        path = os.path.join(out_dir, letter.filename)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(letter.body)
        paths.append(path)
    return paths


def write_letters_pdf(letters: list[Letter], out_dir: str) -> list[str]:
    """Render each letter to a printable .pdf file; return the written paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths: list[str] = []
    for letter in letters:
        name = letter.filename
        if name.endswith(".txt"):
            name = name[:-4]
        path = os.path.join(out_dir, f"{name}.pdf")
        write_pdf(letter.body, path)
        paths.append(path)
    return paths
