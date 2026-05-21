"""Tests for the redundant extraction ensemble and its reconciliation.

The model calls cannot run here (no keys, restricted network), so the
reconciliation logic -- the part that actually reduces errors -- is
tested with fake extractors, models, and resolvers.

Runs under pytest, or standalone:  python tests/test_extraction.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from refunds.extraction import (  # noqa: E402
    ConflictResolver,
    DocumentExtraction,
    DocumentExtractor,
    EnsembleExtractor,
    GeminiVisionModel,
    LLMDocumentExtractor,
    NullConflictResolver,
    ProductFields,
    ResolverVerdict,
    build_default_ensemble,
    reconcile,
)
from refunds.ocr import OcrDependencyError  # noqa: E402


def _vsc(price=2695.0, contract="VSC-1", admin="Zurich", months=72, miles=75000):
    return ProductFields(
        product_type="Vehicle Service Contract",
        administrator=admin,
        contract_number=contract,
        price=price,
        term_months=months,
        term_miles=miles,
    )


def _doc(source, products, vin=None, error=None):
    return DocumentExtraction(
        source=source, products=products, vin=vin, error=error
    )


class FakeExtractor(DocumentExtractor):
    def __init__(self, name, extraction):
        self.name = name
        self._extraction = extraction

    def extract(self, path):
        return self._extraction


class FakeResolver(ConflictResolver):
    def __init__(self, value, confident=True):
        self.value = value
        self.confident = confident
        self.calls = []

    def resolve(self, path, product_type, field_name, candidates):
        self.calls.append((field_name, candidates))
        return ResolverVerdict(self.value, self.confident)


class FakeModel:
    name = "fake"

    def __init__(self, reply):
        self.reply = reply

    def complete(self, path, prompt):
        return self.reply


# -- reconciliation ----------------------------------------------------


def test_unanimous_fields_are_high_confidence():
    docs = [_doc(f"r{i}", [_vsc()]) for i in range(3)]
    result = reconcile("d.pdf", docs, NullConflictResolver())
    assert len(result.products) == 1
    product = result.products[0]
    assert product.product.price == 2695.0
    assert all(level == "high" for level in product.confidence.values())
    assert product.review_fields == []


def test_majority_wins_with_medium_confidence():
    docs = [
        _doc("r1", [_vsc(price=2695.0)]),
        _doc("r2", [_vsc(price=2695.0)]),
        _doc("r3", [_vsc(price=2999.0)]),
    ]
    result = reconcile("d.pdf", docs, NullConflictResolver())
    product = result.products[0]
    assert product.product.price == 2695.0
    assert product.confidence["price"] == "medium"
    assert "price" not in product.review_fields


def test_conflict_is_sent_to_the_resolver():
    docs = [
        _doc("r1", [_vsc(price=2695.0)]),
        _doc("r2", [_vsc(price=2999.0)]),
    ]
    resolver = FakeResolver(2750.0, confident=True)
    result = reconcile("d.pdf", docs, resolver)
    product = result.products[0]
    assert product.product.price == 2750.0
    assert product.confidence["price"] == "medium"
    assert any(field == "price" for field, _ in resolver.calls)


def test_unresolved_conflict_is_flagged_for_review():
    docs = [
        _doc("r1", [_vsc(price=2695.0)]),
        _doc("r2", [_vsc(price=2999.0)]),
    ]
    result = reconcile("d.pdf", docs, NullConflictResolver())
    product = result.products[0]
    assert product.confidence["price"] == "low"
    assert "price" in product.review_fields


def test_failed_extractor_is_dropped_with_a_warning():
    docs = [
        _doc("r1", [_vsc()]),
        _doc("r2", [_vsc()]),
        _doc("broken", [], error="API timeout"),
    ]
    result = reconcile("d.pdf", docs, NullConflictResolver())
    assert "broken" not in result.extractor_names
    assert any("broken" in w for w in result.warnings)
    assert result.products[0].confidence["price"] == "high"


def test_single_reader_is_all_low_confidence():
    result = reconcile("d.pdf", [_doc("solo", [_vsc()])], NullConflictResolver())
    product = result.products[0]
    assert all(level == "low" for level in product.confidence.values())
    assert any("Only one reader" in w for w in result.warnings)


def test_product_seen_by_a_minority_is_warned():
    gap = ProductFields(
        product_type="GAP Waiver",
        administrator="Zurich",
        contract_number="GAP-1",
        price=900.0,
        term_months=72,
    )
    docs = [
        _doc("r1", [_vsc(), gap]),
        _doc("r2", [_vsc()]),
        _doc("r3", [_vsc()]),
    ]
    result = reconcile("d.pdf", docs, NullConflictResolver())
    assert len(result.products) == 2
    assert any("GAP Waiver" in w and "1 of 3" in w for w in result.warnings)


def test_vin_is_voted_across_readers():
    docs = [
        _doc("r1", [_vsc()], vin="1HGCM82633A004352"),
        _doc("r2", [_vsc()], vin="1HGCM82633A004352"),
        _doc("r3", [_vsc()], vin="WRONGVIN0000000AA"),
    ]
    result = reconcile("d.pdf", docs, NullConflictResolver())
    assert result.vin == "1HGCM82633A004352"


# -- ensemble + extractors --------------------------------------------


def test_ensemble_runs_every_extractor_and_reconciles():
    ensemble = EnsembleExtractor(
        [
            FakeExtractor("a", _doc("a", [_vsc()])),
            FakeExtractor("b", _doc("b", [_vsc()])),
        ]
    )
    result = ensemble.extract("d.pdf")
    assert set(result.extractor_names) == {"a", "b"}
    assert result.products[0].confidence["price"] == "high"


def test_llm_extractor_parses_json():
    reply = (
        '{"vin":"V1","purchase_date":"2023-03-15","products":['
        '{"product_type":"GAP","administrator":"Zurich","contract_number":'
        '"G1","price":900,"term_months":72,"term_miles":null}]}'
    )
    doc = LLMDocumentExtractor(FakeModel(reply), name="fake").extract("d.pdf")
    assert doc.error is None
    assert len(doc.products) == 1
    assert doc.products[0].price == 900.0
    assert doc.vin == "V1"


def test_llm_extractor_handles_fenced_json():
    reply = 'Sure:\n```json\n{"products":[{"product_type":"GAP","price":900}]}\n```'
    doc = LLMDocumentExtractor(FakeModel(reply), name="fake").extract("d.pdf")
    assert doc.error is None
    assert len(doc.products) == 1


def test_llm_extractor_captures_model_errors():
    class Boom:
        name = "boom"

        def complete(self, path, prompt):
            raise RuntimeError("rate limited")

    doc = LLMDocumentExtractor(Boom(), name="boom").extract("d.pdf")
    assert doc.error is not None
    assert doc.products == []


# -- gemini model ------------------------------------------------------


def test_gemini_without_key_raises():
    try:
        GeminiVisionModel(api_key="").complete("scan.pdf", "transcribe")
    except OcrDependencyError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("expected OcrDependencyError without an API key")


def test_gemini_rejects_unsupported_extension():
    try:
        GeminiVisionModel(api_key="key")._media_type("contract.docx")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for an unsupported file type")


def test_build_default_ensemble_without_keys_is_none():
    saved_anthropic = os.environ.pop("ANTHROPIC_API_KEY", None)
    saved_gemini = os.environ.pop("GEMINI_API_KEY", None)
    try:
        assert build_default_ensemble() is None
    finally:
        if saved_anthropic:
            os.environ["ANTHROPIC_API_KEY"] = saved_anthropic
        if saved_gemini:
            os.environ["GEMINI_API_KEY"] = saved_gemini


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
