"""Tests for JSON persistence and the CaseStore.

Runs under pytest, or standalone:  python tests/test_persistence.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from refunds import (  # noqa: E402
    AddOnProduct,
    CaseStatus,
    ProductType,
    RefundCase,
    Seller,
    Vehicle,
)
from refunds.persistence import CaseStore, case_from_dict, case_to_dict  # noqa: E402


def _sample_case() -> RefundCase:
    return RefundCase(
        seller=Seller(
            legal_name="Jordan A. Rivera",
            address_lines=["123 Maple Street", "Springfield, IL 62704"],
            email="jordan.rivera@example.com",
            phone="(555) 010-2345",
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
        products=[
            AddOnProduct(
                product_type=ProductType.VEHICLE_SERVICE_CONTRACT,
                administrator_name="Zurich",
                contract_number="VSC-7781234",
                price=2_695.00,
                term_months=72,
                term_miles=75_000,
                start_date=date(2023, 3, 15),
                start_odometer=12,
                cancellation_fee=50.00,
            ),
            AddOnProduct(
                product_type=ProductType.GAP,
                administrator_name="Fidelity Warranty Services",
                contract_number="GAP-553021",
                price=895.00,
                term_months=72,
                start_date=date(2023, 3, 15),
            ),
        ],
        authorization_signed=True,
        status=CaseStatus.READY_TO_SEND,
    )


def test_round_trip_preserves_the_case():
    case = _sample_case()
    restored = case_from_dict(case_to_dict(case))
    assert restored == case


def test_save_and_load_round_trip():
    case = _sample_case()
    with tempfile.TemporaryDirectory() as root:
        store = CaseStore(root)
        store.save(case)
        assert store.exists(case.case_id)
        assert store.load(case.case_id) == case


def test_list_ids_and_cases():
    with tempfile.TemporaryDirectory() as root:
        store = CaseStore(root)
        first = _sample_case()
        second = _sample_case()
        store.save(first)
        store.save(second)
        assert set(store.list_ids()) == {first.case_id, second.case_id}
        assert len(store.list_cases()) == 2


def test_delete_removes_the_case():
    case = _sample_case()
    with tempfile.TemporaryDirectory() as root:
        store = CaseStore(root)
        store.save(case)
        assert store.delete(case.case_id) is True
        assert not store.exists(case.case_id)
        assert store.delete(case.case_id) is False


def test_load_missing_case_raises():
    with tempfile.TemporaryDirectory() as root:
        store = CaseStore(root)
        try:
            store.load("doesnotexist")
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for a missing case")


def test_invalid_case_id_is_rejected():
    with tempfile.TemporaryDirectory() as root:
        store = CaseStore(root)
        try:
            store.path_for("../escape")
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for a path-traversal id")


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
