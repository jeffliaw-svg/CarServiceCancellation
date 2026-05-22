"""Tests for the operator console aggregation.

Runs under pytest, or standalone:  python tests/test_operator.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.service import RefundService  # noqa: E402

_CONTRACT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "examples",
    "sample_contract.txt",
)
_INTAKE = {
    "legal_name": "Jordan A. Rivera",
    "address_lines": ["123 Maple Street", "Springfield, IL 62704"],
    "vin": "1HGCM82633A004352",
    "sale_date": "2025-11-01",
}


def _service() -> RefundService:
    return RefundService(tempfile.mkdtemp())


def _started(service: RefundService) -> str:
    return service.create_case(_INTAKE)["case_id"]


def _with_documents(service: RefundService) -> str:
    case_id = _started(service)
    with open(_CONTRACT, "rb") as handle:
        service.add_document(
            case_id, filename="c.txt", data=handle.read(), kind="contract"
        )
    return case_id


def test_funnel_and_totals_count_each_stage():
    service = _service()
    _started(service)                                    # stalls at Started
    _with_documents(service)                             # stalls at Documents
    confirmed = _with_documents(service)
    service.confirm_services(confirmed, [0, 1, 2, 3])    # stalls at Confirmed
    generated = _with_documents(service)
    service.confirm_services(generated, [0, 1, 2, 3])
    service.generate(generated)                          # reaches the end

    overview = service.operator_overview()
    totals = overview["totals"]
    assert totals["started"] == 4
    assert totals["documents_read"] == 3
    assert totals["services_confirmed"] == 2
    assert totals["letters_generated"] == 1
    assert totals["packets_generated"] == 4  # the generated case had 4 products

    funnel = {stage["stage"]: stage for stage in overview["funnel"]}
    assert funnel["Started"]["reached"] == 4
    assert funnel["Started"]["stalled_here"] == 1
    assert funnel["Documents read"]["stalled_here"] == 1
    assert funnel["Services confirmed"]["stalled_here"] == 1
    assert funnel["Letters generated"]["reached"] == 1


def test_recent_lists_newest_first():
    service = _service()
    first = _started(service)
    second = _started(service)
    recent = service.operator_overview()["recent"]
    assert recent[0]["case_id"] == second
    assert recent[-1]["case_id"] == first


def test_needs_review_surfaces_flagged_cases():
    from refunds.extraction import (
        DocumentExtraction,
        DocumentExtractor,
        EnsembleExtractor,
        ProductFields,
    )

    class _Stub(DocumentExtractor):
        def __init__(self, name, price):
            self.name = name
            self.price = price

        def extract(self, path):
            return DocumentExtraction(
                source=self.name,
                products=[
                    ProductFields(
                        product_type="GAP Waiver",
                        administrator="Zurich",
                        contract_number="G1",
                        price=self.price,
                        term_months=72,
                    )
                ],
                purchase_date="2023-03-15",
            )

    # Two readers disagree on the price -> reconciliation flags it.
    ensemble = EnsembleExtractor([_Stub("a", 900.0), _Stub("b", 950.0)])
    service = RefundService(tempfile.mkdtemp(), ensemble=ensemble)
    case_id = service.create_case(_INTAKE)["case_id"]
    service.add_document(
        case_id, filename="scan.pdf", data=b"%PDF-1.4 fake", kind="contract"
    )

    overview = service.operator_overview()
    assert overview["totals"]["needs_review"] == 1
    assert overview["needs_review"][0]["case_id"] == case_id
    assert "price" in overview["needs_review"][0]["review"]["GAP Waiver"]


def test_operator_case_returns_full_detail():
    service = _service()
    case_id = _with_documents(service)
    detail = service.operator_case(case_id)
    assert detail["case_id"] == case_id
    assert len(detail["products"]) == 4
    assert detail["created_at"]


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
