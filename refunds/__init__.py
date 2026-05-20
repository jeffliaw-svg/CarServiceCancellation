"""Pro-rata refund request generator for cancelled vehicle F&I add-on products.

A car seller provides minimal intake (legal name, VIN, sale date) plus one
document -- the retail installment sales contract -- which itemizes the
add-on products that were sold. This package models that case, estimates
the pro-rata refund owed on each product, and drafts the cancellation
letters to send.
"""

from .administrators import DEFAULT_REGISTRY, lookup
from .authorization import generate_authorization
from .contract_parser import (
    ParsedContract,
    parse_contract_file,
    parse_contract_text,
)
from .letters import (
    Letter,
    generate_letter,
    generate_letters_for_case,
    write_letters,
    write_letters_pdf,
)
from .pdf import text_to_pdf, write_pdf
from .models import (
    AddOnProduct,
    Administrator,
    CancellationRoute,
    CaseStatus,
    ProductType,
    RefundCase,
    Seller,
    Vehicle,
)
from .persistence import CaseStore, case_from_dict, case_to_dict
from .prorata import (
    RefundEstimate,
    estimate_case,
    estimate_refund,
    total_estimated_refund,
)

__all__ = [
    "AddOnProduct",
    "Administrator",
    "CancellationRoute",
    "CaseStatus",
    "ProductType",
    "RefundCase",
    "Seller",
    "Vehicle",
    "RefundEstimate",
    "estimate_refund",
    "estimate_case",
    "total_estimated_refund",
    "Letter",
    "generate_letter",
    "generate_letters_for_case",
    "write_letters",
    "write_letters_pdf",
    "text_to_pdf",
    "write_pdf",
    "DEFAULT_REGISTRY",
    "lookup",
    "CaseStore",
    "case_to_dict",
    "case_from_dict",
    "generate_authorization",
    "ParsedContract",
    "parse_contract_text",
    "parse_contract_file",
]
