"""Tests for the pro-rata refund estimator.

Runs under pytest, or standalone:  python tests/test_prorata.py
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
    estimate_refund,
)


def _case(
    *,
    sale_date: date,
    odometer_at_purchase: int | None = None,
    odometer_at_sale: int | None = None,
    purchase_date: date | None = None,
) -> RefundCase:
    return RefundCase(
        seller=Seller(legal_name="Test Seller", address_lines=["1 Test St"]),
        vehicle=Vehicle(
            vin="TESTVIN0000000001",
            purchase_date=purchase_date,
            odometer_at_purchase=odometer_at_purchase,
            odometer_at_sale=odometer_at_sale,
        ),
        sale_date=sale_date,
    )


def test_mileage_based_refund_is_exact():
    product = AddOnProduct(
        product_type=ProductType.VEHICLE_SERVICE_CONTRACT,
        administrator_name="Zurich",
        contract_number="VSC-1",
        price=2_000.00,
        term_months=120,  # long term so time fraction stays tiny
        term_miles=100_000,
        start_date=date(2024, 1, 1),
        start_odometer=10_000,
    )
    case = _case(
        sale_date=date(2024, 2, 1),
        odometer_at_sale=60_000,  # 50,000 of 100,000 miles used -> 0.5 elapsed
    )
    est = estimate_refund(product, case)
    assert est.can_estimate
    assert abs(est.remaining_fraction - 0.5) < 1e-9
    assert est.gross_refund == 1_000.00
    assert est.net_refund == 1_000.00


def test_time_based_refund_when_no_mileage_data():
    product = AddOnProduct(
        product_type=ProductType.GAP,
        administrator_name="Zurich",
        contract_number="GAP-1",
        price=2_400.00,
        term_months=24,
        start_date=date(2024, 1, 1),
        cancellation_fee=50.00,
    )
    case = _case(sale_date=date(2025, 1, 1))  # ~12 months of 24 elapsed
    est = estimate_refund(product, case)
    assert est.can_estimate
    assert abs(est.remaining_fraction - 0.5) < 0.01
    # gross ~1200, minus the $50 cancellation fee
    assert abs(est.net_refund - 1_150.00) < 12.0


def test_greater_elapsed_fraction_wins():
    # Time elapsed 0.75, mileage elapsed 0.10 -> earned portion uses time.
    product = AddOnProduct(
        product_type=ProductType.TIRE_AND_WHEEL,
        administrator_name="Safe-Guard Products International",
        contract_number="TW-1",
        price=1_000.00,
        term_months=24,
        term_miles=100_000,
        start_date=date(2024, 1, 1),
        start_odometer=0,
    )
    case = _case(sale_date=date(2025, 7, 1), odometer_at_sale=10_000)
    est = estimate_refund(product, case)
    assert est.can_estimate
    assert abs(est.remaining_fraction - 0.25) < 0.02
    assert "time" in est.basis


def test_no_term_cannot_estimate():
    product = AddOnProduct(
        product_type=ProductType.OTHER,
        administrator_name="Zurich",
        contract_number="X-1",
        price=500.00,
        start_date=date(2024, 1, 1),
    )
    case = _case(sale_date=date(2025, 1, 1))
    est = estimate_refund(product, case)
    assert not est.can_estimate
    assert est.net_refund == 0.0
    assert est.warnings


def test_missing_start_date_cannot_estimate():
    product = AddOnProduct(
        product_type=ProductType.GAP,
        administrator_name="Zurich",
        contract_number="GAP-2",
        price=900.00,
        term_months=72,
    )
    case = _case(sale_date=date(2025, 1, 1))  # no purchase_date on the vehicle either
    est = estimate_refund(product, case)
    assert not est.can_estimate


def test_fully_elapsed_term_refunds_nothing():
    product = AddOnProduct(
        product_type=ProductType.PREPAID_MAINTENANCE,
        administrator_name="Zurich",
        contract_number="PM-1",
        price=600.00,
        term_months=12,
        start_date=date(2020, 1, 1),
    )
    case = _case(sale_date=date(2025, 1, 1))  # long past the 12-month term
    est = estimate_refund(product, case)
    assert est.can_estimate
    assert est.remaining_fraction == 0.0
    assert est.net_refund == 0.0


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
