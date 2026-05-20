"""Parse a retail installment sales contract into AddOnProduct entries.

The contract is the one document that itemizes every add-on product, its
price, term, administrator, and contract number. This parser works on
the *text* of the contract: a structured-text path is implemented now,
and `extract_text` exposes a documented seam for plugging in an OCR
engine for scanned PDFs or images later.

Output is always a starting point for human review -- contracts vary
widely in layout, so any field the parser cannot find is reported as a
warning rather than guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .models import AddOnProduct, ProductType

_MONEY_RE = re.compile(r"\$?\s?(\d[\d,]*\.\d{2})\b")
_MONTHS_RE = re.compile(r"(\d[\d,]*)\s*(?:months?|mos?)\b", re.IGNORECASE)
_MILES_RE = re.compile(r"(\d[\d,]*)\s*miles?\b", re.IGNORECASE)
_CONTRACT_RE = re.compile(
    r"(?:contract|agreement|policy|plan|certificate)\s*"
    r"(?:no\.?|number|num\.?|#)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-]{2,})",
    re.IGNORECASE,
)
_VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")

# Distinctive substrings -> canonical administrator name (matches the registry).
_ADMIN_ALIASES: dict[str, str] = {
    "zurich": "Zurich",
    "fidelity": "Fidelity Warranty Services",
    "jm&a": "JM&A Group",
    "jm & a": "JM&A Group",
    "safe-guard": "Safe-Guard Products International",
    "safeguard": "Safe-Guard Products International",
    "easycare": "EasyCare (APCO)",
    "apco": "EasyCare (APCO)",
    "assurant": "Assurant",
    "gwc": "GWC Warranty",
}

_PRODUCT_KEYWORDS: list[tuple[tuple[str, ...], ProductType]] = [
    (("gap",), ProductType.GAP),
    (("tire", "wheel"), ProductType.TIRE_AND_WHEEL),
    (
        ("prepaid maintenance", "maintenance plan", "maintenance contract"),
        ProductType.PREPAID_MAINTENANCE,
    ),
    (
        ("paint", "fabric", "appearance protection", "appearance package"),
        ProductType.APPEARANCE_PROTECTION,
    ),
    (("key replacement", "key & remote", "key protection"), ProductType.KEY_REPLACEMENT),
    (("theft", "vin etch", "etch"), ProductType.THEFT_PROTECTION),
    (
        ("service contract", "vehicle service", "extended service", "extended warranty", "vsc"),
        ProductType.VEHICLE_SERVICE_CONTRACT,
    ),
]

_PRODUCT_PATTERNS: list[tuple[re.Pattern[str], ProductType]] = [
    (
        re.compile(
            r"\b(?:" + "|".join(re.escape(kw) for kw in keywords) + r")\b",
            re.IGNORECASE,
        ),
        product_type,
    )
    for keywords, product_type in _PRODUCT_KEYWORDS
]


@dataclass
class ParsedContract:
    products: list[AddOnProduct]
    detected_vin: str | None = None
    warnings: list[str] = field(default_factory=list)


def _match_product_type(line: str) -> ProductType | None:
    for pattern, product_type in _PRODUCT_PATTERNS:
        if pattern.search(line):
            return product_type
    return None


def _match_administrator(text: str) -> str:
    lowered = text.lower()
    for alias, name in _ADMIN_ALIASES.items():
        if alias in lowered:
            return name
    return ""


def _to_int(value: str) -> int:
    return int(value.replace(",", ""))


def _build_product(
    product_type: ProductType, block_text: str
) -> tuple[AddOnProduct | None, list[str]]:
    prices = _MONEY_RE.findall(block_text)
    contract_match = _CONTRACT_RE.search(block_text)
    contract_number = contract_match.group(1) if contract_match else ""

    # A block with neither a price nor a contract number is almost certainly a
    # section header rather than a real line item -- skip it silently.
    if not prices and not contract_number:
        return None, []

    warnings: list[str] = []
    label = product_type.value

    price = float(prices[-1].replace(",", "")) if prices else 0.0
    if not prices:
        warnings.append(f"{label}: no price found; defaulted to $0.00 -- verify.")

    administrator = _match_administrator(block_text)
    if not administrator:
        warnings.append(
            f"{label}: administrator not identified -- fill in before generating letters."
        )

    if not contract_number:
        warnings.append(f"{label}: contract/agreement number not found -- verify.")

    months_match = _MONTHS_RE.search(block_text)
    miles_match = _MILES_RE.search(block_text)

    product = AddOnProduct(
        product_type=product_type,
        administrator_name=administrator,
        contract_number=contract_number,
        price=price,
        term_months=_to_int(months_match.group(1)) if months_match else None,
        term_miles=_to_int(miles_match.group(1)) if miles_match else None,
    )
    return product, warnings


def parse_contract_text(text: str) -> ParsedContract:
    """Parse the plain text of a retail installment contract."""

    lines = text.splitlines()
    warnings: list[str] = []

    detected_vin: str | None = None
    vin_match = _VIN_RE.search(text.upper())
    if vin_match and any(ch.isalpha() for ch in vin_match.group(1)):
        detected_vin = vin_match.group(1)

    matched_lines: dict[int, ProductType] = {}
    for index, line in enumerate(lines):
        product_type = _match_product_type(line)
        if product_type is not None:
            matched_lines[index] = product_type

    products: list[AddOnProduct] = []
    for index in sorted(matched_lines):
        # A "block" is the keyword line plus following lines, up to a blank
        # line or the next product -- price and term often sit on the next row.
        block = [lines[index]]
        cursor = index + 1
        while cursor < len(lines):
            if not lines[cursor].strip() or cursor in matched_lines:
                break
            block.append(lines[cursor])
            cursor += 1

        product, block_warnings = _build_product(
            matched_lines[index], " ".join(block)
        )
        if product is not None:
            products.append(product)
            warnings.extend(block_warnings)

    if not products:
        warnings.append("No add-on products were recognized in the document.")

    return ParsedContract(
        products=products, detected_vin=detected_vin, warnings=warnings
    )


def extract_text(path: str, *, ocr: Callable[[str], str] | None = None) -> str:
    """Read the text of a contract file.

    Plain-text files are read directly. For scanned PDFs or images, pass
    `ocr` -- a callable mapping a file path to its extracted text (e.g. a
    wrapper around an external OCR/PDF service). This is the seam where a
    real OCR engine plugs in.
    """
    if path.lower().endswith((".txt", ".text")):
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    if ocr is not None:
        return ocr(path)
    raise NotImplementedError(
        f"Cannot extract text from {path!r}: only .txt is supported natively. "
        "Pass ocr=<callable> to plug in an OCR engine that maps a file path "
        "to its text."
    )


def parse_contract_file(
    path: str, *, ocr: Callable[[str], str] | None = None
) -> ParsedContract:
    return parse_contract_text(extract_text(path, ocr=ocr))
