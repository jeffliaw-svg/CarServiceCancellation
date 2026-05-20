"""Tests for the retail installment contract parser.

Runs under pytest, or standalone:  python tests/test_contract_parser.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from refunds import ProductType  # noqa: E402
from refunds.contract_parser import (  # noqa: E402
    parse_contract_file,
    parse_contract_text,
)

SAMPLE = """\
RETAIL INSTALLMENT SALE CONTRACT

VEHICLE
New 2023 Honda Accord EX-L
VIN: 1HGCM82633A004352

OPTIONAL PRODUCTS AND SERVICES

  Vehicle Service Contract -- Zurich -- Contract No. VSC-7781234
      Term: 72 months / 75,000 miles ................. $2,695.00

  GAP Waiver -- Fidelity Warranty Services -- Agreement No. GAP-553021
      Term: 72 months ............................... $895.00

  Tire & Wheel Protection -- Safe-Guard -- Contract No. TW-2210045
      Term: 60 months ............................... $799.00
"""


def test_parses_every_product():
    result = parse_contract_text(SAMPLE)
    types = {p.product_type for p in result.products}
    assert types == {
        ProductType.VEHICLE_SERVICE_CONTRACT,
        ProductType.GAP,
        ProductType.TIRE_AND_WHEEL,
    }


def test_extracts_price_term_and_contract_number():
    result = parse_contract_text(SAMPLE)
    vsc = next(
        p for p in result.products
        if p.product_type == ProductType.VEHICLE_SERVICE_CONTRACT
    )
    assert vsc.price == 2_695.00
    assert vsc.term_months == 72
    assert vsc.term_miles == 75_000
    assert vsc.contract_number == "VSC-7781234"
    assert vsc.administrator_name == "Zurich"


def test_detects_vin():
    result = parse_contract_text(SAMPLE)
    assert result.detected_vin == "1HGCM82633A004352"


def test_section_headers_do_not_become_products():
    # "OPTIONAL PRODUCTS AND SERVICES" must not be parsed as a product.
    result = parse_contract_text(SAMPLE)
    assert len(result.products) == 3


def test_missing_fields_produce_warnings():
    text = "GAP Waiver enrolled at signing. Contract No. GAP-1\n"
    result = parse_contract_text(text)
    assert len(result.products) == 1
    assert result.products[0].price == 0.0
    assert any("no price" in w for w in result.warnings)
    assert any("administrator" in w for w in result.warnings)


def test_empty_document_warns():
    result = parse_contract_text("Just some unrelated text.\n")
    assert result.products == []
    assert any("No add-on products" in w for w in result.warnings)


def test_parse_sample_contract_file():
    fixture = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "examples",
        "sample_contract.txt",
    )
    result = parse_contract_file(fixture)
    assert len(result.products) == 4  # VSC, GAP, Tire & Wheel, Prepaid Maintenance
    assert result.detected_vin == "1HGCM82633A004352"


def test_non_text_file_without_ocr_raises():
    try:
        parse_contract_file("scan.pdf")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("expected NotImplementedError without an OCR callable")


def test_ocr_callable_is_used_for_non_text_files():
    result = parse_contract_file(
        "scan.pdf",
        ocr=lambda _path: "GAP Waiver -- Zurich -- Contract No. GAP-9 $500.00\n",
    )
    assert len(result.products) == 1
    assert result.products[0].product_type == ProductType.GAP


def _run_standalone() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
