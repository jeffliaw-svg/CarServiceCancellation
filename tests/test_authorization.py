"""Tests for the authorization-document generator.

Runs under pytest, or standalone:  python tests/test_authorization.py
"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from refunds import (  # noqa: E402
    AddOnProduct,
    ProductType,
    RefundCase,
    Seller,
    Vehicle,
)
from refunds.authorization import generate_authorization  # noqa: E402

TODAY = date(2026, 5, 20)


def _case(products: list[AddOnProduct]) -> RefundCase:
    return RefundCase(
        seller=Seller(
            legal_name="Jordan A. Rivera",
            address_lines=["123 Maple Street", "Springfield, IL 62704"],
        ),
        vehicle=Vehicle(
            vin="1HGCM82633A004352",
            year=2023,
            make="Honda",
            model="Accord",
        ),
        sale_date=date(2025, 11, 1),
        products=products,
    )


def _products() -> list[AddOnProduct]:
    return [
        AddOnProduct(
            product_type=ProductType.VEHICLE_SERVICE_CONTRACT,
            administrator_name="Zurich",
            contract_number="VSC-7781234",
            price=2_695.00,
        ),
        AddOnProduct(
            product_type=ProductType.GAP,
            administrator_name="Fidelity Warranty Services",
            contract_number="GAP-553021",
            price=895.00,
        ),
    ]


def test_authorization_contains_principal_and_vehicle():
    doc = generate_authorization(_case(_products()), today=TODAY)
    assert "POWER OF ATTORNEY" in doc
    assert "Jordan A. Rivera" in doc
    assert "1HGCM82633A004352" in doc
    assert "pro-rata" in doc


def test_authorization_lists_every_product():
    doc = generate_authorization(_case(_products()), today=TODAY)
    assert "VSC-7781234" in doc
    assert "GAP-553021" in doc


def test_authorization_handles_no_products_yet():
    doc = generate_authorization(_case([]), today=TODAY)
    assert "No add-on products have been individually identified" in doc


def test_notary_block_is_optional():
    with_notary = generate_authorization(_case(_products()), today=TODAY)
    without_notary = generate_authorization(
        _case(_products()), today=TODAY, include_notary=False
    )
    assert "NOTARY ACKNOWLEDGMENT" in with_notary
    assert "NOTARY ACKNOWLEDGMENT" not in without_notary


def test_signature_block_present():
    doc = generate_authorization(_case(_products()), today=TODAY)
    assert "PRINCIPAL SIGNATURE" in doc
    assert "Signature:" in doc


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
