"""End-to-end tests for the RefundService orchestration layer.

Runs under pytest, or standalone:  python tests/test_server.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.service import RefundService, ServiceError  # noqa: E402

_CONTRACT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "examples",
    "sample_contract.txt",
)

_INTAKE = {
    "legal_name": "Jordan A. Rivera",
    "address_lines": ["123 Maple Street", "Springfield, IL 62704"],
    "email": "jordan.rivera@example.com",
    "phone": "(555) 010-2345",
    "vin": "1HGCM82633A004352",
    "sale_date": "2025-11-01",
}


def _service() -> RefundService:
    return RefundService(tempfile.mkdtemp())


def _with_contract(service: RefundService) -> str:
    case_id = service.create_case(_INTAKE)["case_id"]
    with open(_CONTRACT, "rb") as handle:
        service.add_document(
            case_id, filename="contract.txt", data=handle.read(), kind="contract"
        )
    return case_id


def test_create_case_requires_core_fields():
    service = _service()
    try:
        service.create_case({"vin": "X", "sale_date": "2025-01-01"})
    except ServiceError:
        pass
    else:
        raise AssertionError("expected ServiceError without a legal name")


def test_ingesting_a_contract_parses_products_and_estimates():
    service = _service()
    case_id = _with_contract(service)
    view = service.get_case(case_id)
    assert len(view["products"]) == 4
    assert view["vehicle"]["purchase_date"] == "2023-03-15"
    # A coverage start date was detected, so refunds can be estimated.
    assert view["total_estimated_refund"] > 0
    assert all(p["question"] for p in view["products"])


def test_confirmation_drops_unconfirmed_services():
    service = _service()
    case_id = _with_contract(service)
    view = service.confirm_services(case_id, [0, 2])
    assert len(view["products"]) == 2
    assert view["status"] == "ready_to_send"


def test_generate_produces_letters_authorization_and_bundle():
    service = _service()
    case_id = _with_contract(service)
    service.confirm_services(case_id, [0, 1, 2, 3])
    view = service.generate(case_id)

    kinds = {item["kind"] for item in view["generated"]}
    assert {"letter", "authorization", "checklist", "bundle"} <= kinds

    letters = [i for i in view["generated"] if i["kind"] == "letter"]
    assert len(letters) == 4

    pdf_bytes, content_type = service.get_file(case_id, letters[0]["name"])
    assert pdf_bytes.startswith(b"%PDF-")
    assert content_type == "application/pdf"


def test_generate_creates_email_drafts_when_an_admin_email_is_known():
    # EasyCare (APCO) has a cancellations email in the registry.
    service = _service()
    case_id = _with_contract(service)
    service.confirm_services(case_id, [0, 1, 2, 3])
    view = service.generate(case_id)
    emails = [i for i in view["generated"] if i["kind"] == "email"]
    assert emails, "expected at least one .eml draft"
    eml_bytes, content_type = service.get_file(case_id, emails[0]["name"])
    assert content_type == "message/rfc822"
    assert b"Subject:" in eml_bytes


def test_generate_requires_confirmed_services():
    service = _service()
    case_id = _with_contract(service)
    service.confirm_services(case_id, [])
    try:
        service.generate(case_id)
    except ServiceError:
        pass
    else:
        raise AssertionError("expected ServiceError generating with no services")


class _FakeOcr:
    """A stand-in OCR backend that returns canned contract text."""

    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self, path: str) -> str:
        return self.text


def test_pdf_contract_is_read_through_the_configured_ocr():
    with open(_CONTRACT, encoding="utf-8") as handle:
        contract_text = handle.read()
    service = RefundService(tempfile.mkdtemp(), ocr=_FakeOcr(contract_text))
    case_id = service.create_case(_INTAKE)["case_id"]
    service.add_document(
        case_id, filename="scan.pdf", data=b"%PDF-1.4 fake", kind="contract"
    )
    view = service.get_case(case_id)
    assert len(view["products"]) == 4


def test_pdf_contract_without_ocr_returns_a_warning():
    os.environ.pop("ANTHROPIC_API_KEY", None)
    service = RefundService(tempfile.mkdtemp())
    case_id = service.create_case(_INTAKE)["case_id"]
    service.add_document(
        case_id, filename="scan.pdf", data=b"%PDF-1.4 fake", kind="contract"
    )
    view = service.get_case(case_id)
    assert view["products"] == []
    assert any("not configured" in w for w in view["parse_warnings"])


def test_pdf_contract_uses_the_ensemble_when_configured():
    from refunds.extraction import (
        DocumentExtraction,
        DocumentExtractor,
        EnsembleExtractor,
        ProductFields,
    )

    class _StubExtractor(DocumentExtractor):
        def __init__(self, name):
            self.name = name

        def extract(self, path):
            return DocumentExtraction(
                source=self.name,
                products=[
                    ProductFields(
                        product_type="Vehicle Service Contract",
                        administrator="Zurich",
                        contract_number="VSC-1",
                        price=2695.0,
                        term_months=72,
                        term_miles=75000,
                    )
                ],
                purchase_date="2023-03-15",
            )

    ensemble = EnsembleExtractor([_StubExtractor("a"), _StubExtractor("b")])
    service = RefundService(tempfile.mkdtemp(), ensemble=ensemble)
    case_id = service.create_case(_INTAKE)["case_id"]
    service.add_document(
        case_id, filename="scan.pdf", data=b"%PDF-1.4 fake", kind="contract"
    )
    view = service.get_case(case_id)
    assert len(view["products"]) == 1
    assert "cross-checked" in view["extraction_method"]
    # Both readers agreed on every field, so nothing is flagged for review.
    assert view["products"][0]["review_fields"] == []


def test_get_file_rejects_unsafe_names():
    service = _service()
    case_id = _with_contract(service)
    try:
        service.get_file(case_id, "../secret")
    except ServiceError:
        pass
    else:
        raise AssertionError("expected ServiceError for a path-traversal name")


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
