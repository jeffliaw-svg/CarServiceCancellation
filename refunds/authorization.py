"""Limited authorization / power-of-attorney document generator.

Administrators and dealers will not discuss or cancel a contract for a
third party without written authorization from the contract holder. This
module drafts that document for the seller to sign; it is referenced as
an enclosure by the cancellation letters.

This is a plain-language template, not legal advice. Power-of-attorney
and notarization requirements vary by state and by administrator -- have
the final wording reviewed by counsel before using it in production.
"""

from __future__ import annotations

from datetime import date

from .letters import DEFAULT_SERVICE_CONTACT, DEFAULT_SERVICE_NAME
from .models import RefundCase


def _date_str(value: date) -> str:
    return f"{value:%B} {value.day}, {value.year}"


def generate_authorization(
    case: RefundCase,
    *,
    today: date | None = None,
    service_name: str = DEFAULT_SERVICE_NAME,
    service_contact: str = DEFAULT_SERVICE_CONTACT,
    include_notary: bool = True,
) -> str:
    """Draft the limited authorization document for `case.seller` to sign."""

    today = today or date.today()
    seller = case.seller
    vehicle = case.vehicle

    lines: list[str] = []
    lines.append("LIMITED AUTHORIZATION AND POWER OF ATTORNEY")
    lines.append("")
    lines.append("In plain English:")
    lines.append(
        f"   This one-page form lets {service_name} ask the companies on your"
    )
    lines.append(
        "   behalf to cancel your add-on products and issue the pro-rata refunds"
    )
    lines.append(
        "   you are owed. It does not let us touch your money -- every refund"
    )
    lines.append(
        "   goes directly to you, at the address you list below. You may"
    )
    lines.append("   revoke this authorization in writing at any time.")
    lines.append("")
    lines.append(f"Date: {_date_str(today)}")
    lines.append("")
    lines.append(
        f'1. PRINCIPAL. I, {seller.legal_name} ("Principal"), residing at:'
    )
    lines.append("")
    for addr_line in seller.address_lines:
        lines.append(f"       {addr_line}")
    lines.append("")
    lines.append("   am the seller of the vehicle described below.")
    lines.append("")
    lines.append("2. VEHICLE.")
    lines.append(f"       Description: {vehicle.description}")
    lines.append(f"       VIN: {vehicle.vin}")
    lines.append(f"       Date of sale: {_date_str(case.sale_date)}")
    lines.append("")
    lines.append(
        f'3. AGENT. I appoint {service_name} ("Agent") as my limited agent and'
    )
    lines.append(
        "   attorney-in-fact for the limited purposes stated in Section 4."
    )
    lines.append("")
    lines.append("4. GRANT OF AUTHORITY. I authorize the Agent, on my behalf, to:")
    lines.append("")
    lines.append(
        "   (a) request cancellation of the add-on products listed in Section 5,"
    )
    lines.append(
        "       and of any other add-on, ancillary, service, or F&I product sold"
    )
    lines.append("       in connection with my purchase of the Vehicle;")
    lines.append(
        "   (b) request and pursue pro-rata refunds of all unearned amounts paid"
    )
    lines.append("       for those products;")
    lines.append(
        "   (c) communicate with product administrators, the selling dealer, and"
    )
    lines.append(
        "       any lienholder regarding those cancellations and refunds; and"
    )
    lines.append(
        "   (d) request and receive records and information concerning those"
    )
    lines.append("       products and contracts.")
    lines.append("")
    lines.append("5. PRODUCTS COVERED.")
    lines.append("")
    if case.products:
        for product in case.products:
            contract = product.contract_number or "[contract number not provided]"
            lines.append(
                f"       - {product.product_type.value} -- administered by "
                f"{product.administrator_name}, Contract No. {contract}"
            )
    else:
        lines.append(
            "       (No add-on products have been individually identified yet;"
        )
        lines.append(
            "       this authorization extends to all such products per Section 4.)"
        )
    lines.append("")
    lines.append(
        "6. REFUNDS. All refunds shall be made payable to the Principal and sent"
    )
    lines.append("   to the Principal's address shown in Section 1.")
    lines.append("")
    lines.append(
        "7. LIMITATIONS. This authorization is limited to the purposes in"
    )
    lines.append(
        "   Section 4. It does not authorize the Agent to receive funds on my"
    )
    lines.append(
        "   behalf, to incur debt in my name, or to act for any other purpose."
    )
    lines.append("")
    lines.append(
        "8. REVOCATION. I may revoke this authorization at any time by written"
    )
    lines.append(
        "   notice to the Agent. It otherwise remains in effect until the"
    )
    lines.append(
        "   cancellations and refunds described above are complete."
    )
    lines.append("")
    lines.append(f"9. CONTACT. The Agent may be contacted at {service_contact}.")
    lines.append("")
    lines.append("")
    lines.append("PRINCIPAL SIGNATURE")
    lines.append("")
    lines.append(
        "   Signature: _______________________________   Date: ____________"
    )
    lines.append("")
    lines.append(f"   Printed name: {seller.legal_name}")

    if include_notary:
        lines.append("")
        lines.append("")
        lines.append(
            "NOTARY ACKNOWLEDGMENT (complete only if required by the administrator)"
        )
        lines.append("")
        lines.append("State of __________________")
        lines.append("County of _________________")
        lines.append("")
        lines.append(
            f"On __________________ before me personally appeared "
            f"{seller.legal_name},"
        )
        lines.append(
            "who proved to me on the basis of satisfactory evidence to be the"
        )
        lines.append(
            "person whose name is subscribed above, and acknowledged signing it."
        )
        lines.append("")
        lines.append("   Notary signature: _______________________________")
        lines.append("")
        lines.append("   My commission expires: ____________            [SEAL]")

    return "\n".join(lines) + "\n"
