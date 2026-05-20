"""Tests for the cancellation letter generator.

Runs under pytest, or standalone:  python tests/test_letters.py
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
    generate_letter,
    generate_letters_for_case,
)

TODAY = date(2026, 5, 20)


def _case(product: AddOnProduct, *, authorization_signed: bool = True) -> RefundCase:
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
            selling_dealer="Springfield Honda",
            dealer_address_lines=["4500 Auto Mall Drive", "Springfield, IL 62711"],
            purchase_date=date(2023, 3, 15),
            odometer_at_purchase=12,
            odometer_at_sale=31_400,
        ),
        sale_date=date(2025, 11, 1),
        products=[product],
        authorization_signed=authorization_signed,
    )


def _vsc() -> AddOnProduct:
    return AddOnProduct(
        product_type=ProductType.VEHICLE_SERVICE_CONTRACT,
        administrator_name="Zurich",
        contract_number="VSC-7781234",
        price=2_695.00,
        term_months=72,
        term_miles=75_000,
        start_date=date(2023, 3, 15),
        start_odometer=12,
        cancellation_fee=50.00,
    )


def test_letter_addressed_to_administrator():
    product = _vsc()
    case = _case(product)
    letter = generate_letter(case, product, today=TODAY)
    assert letter.recipient_name == "Zurich"


def test_letter_body_contains_key_identifiers():
    product = _vsc()
    case = _case(product)
    body = generate_letter(case, product, today=TODAY).body
    assert case.vehicle.vin in body
    assert product.contract_number in body
    assert "pro-rata" in body.lower()
    assert case.seller.legal_name in body
    assert "$" in body  # an estimated refund figure is quoted


def test_dealer_route_addresses_the_selling_dealer():
    # JM&A Group is seeded with a DEALER cancellation route.
    product = AddOnProduct(
        product_type=ProductType.GAP,
        administrator_name="JM&A Group",
        contract_number="GAP-553021",
        price=895.00,
        term_months=72,
        start_date=date(2023, 3, 15),
    )
    case = _case(product)
    letter = generate_letter(case, product, today=TODAY)
    assert letter.recipient_name == "Springfield Honda"
    assert "4500 Auto Mall Drive" in letter.recipient_address_lines


def test_unverified_administrator_address_raises_warning():
    product = _vsc()
    case = _case(product)
    letter = generate_letter(case, product, today=TODAY)
    assert any("verified" in w.lower() for w in letter.warnings)


def test_missing_authorization_raises_warning():
    product = _vsc()
    case = _case(product, authorization_signed=False)
    letter = generate_letter(case, product, today=TODAY)
    assert any("authorization" in w.lower() for w in letter.warnings)


def test_unknown_administrator_still_drafts_a_letter():
    product = AddOnProduct(
        product_type=ProductType.OTHER,
        administrator_name="Obscure Regional Warranty Co.",
        contract_number="OBS-1",
        price=400.00,
        term_months=36,
        start_date=date(2023, 3, 15),
    )
    case = _case(product)
    letter = generate_letter(case, product, today=TODAY)
    assert letter.recipient_name == "Obscure Regional Warranty Co."
    assert any("registry" in w.lower() for w in letter.warnings)


def test_generate_letters_for_case_one_per_product():
    products = [
        _vsc(),
        AddOnProduct(
            product_type=ProductType.TIRE_AND_WHEEL,
            administrator_name="Safe-Guard Products International",
            contract_number="TW-2210045",
            price=799.00,
            term_months=60,
            start_date=date(2023, 3, 15),
        ),
    ]
    case = RefundCase(
        seller=Seller(legal_name="Jordan A. Rivera", address_lines=["123 Maple St"]),
        vehicle=Vehicle(vin="1HGCM82633A004352", purchase_date=date(2023, 3, 15)),
        sale_date=date(2025, 11, 1),
        products=products,
        authorization_signed=True,
    )
    letters = generate_letters_for_case(case, today=TODAY)
    assert len(letters) == 2
    assert all(letter.filename.endswith(".txt") for letter in letters)


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
