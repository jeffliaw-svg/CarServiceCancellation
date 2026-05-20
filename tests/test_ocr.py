"""Tests for the OCR backend.

The optional OCR dependencies are not installed in the test environment,
so these tests exercise the adapter contract, the factory, and the
documented failure modes -- not a live Tesseract run.

Runs under pytest, or standalone:  python tests/test_ocr.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from refunds.contract_parser import parse_contract_file  # noqa: E402
from refunds.ocr import (  # noqa: E402
    OcrAdapter,
    OcrDependencyError,
    TesseractOcr,
    get_ocr_adapter,
)


class FakeOcr(OcrAdapter):
    """A test adapter that returns canned contract text."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[str] = []

    def extract_text(self, path: str) -> str:
        self.calls.append(path)
        return self.text


def test_adapter_is_callable():
    adapter = FakeOcr("hello")
    assert adapter("scan.pdf") == "hello"
    assert adapter.calls == ["scan.pdf"]


def test_factory_returns_requested_adapter():
    adapter = get_ocr_adapter("tesseract")
    assert isinstance(adapter, TesseractOcr)


def test_factory_rejects_unknown_adapter():
    try:
        get_ocr_adapter("does-not-exist")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for an unknown adapter name")


def test_tesseract_rejects_unsupported_extension():
    try:
        TesseractOcr().extract_text("contract.docx")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for a non-image, non-PDF file")


def test_missing_dependency_raises_clear_error():
    # pytesseract / Pillow are not installed in the test environment, so the
    # dependency check fires before any file access.
    try:
        TesseractOcr().extract_text("scan.png")
    except OcrDependencyError as exc:
        assert "pip install" in str(exc)
    else:
        raise AssertionError("expected OcrDependencyError without OCR packages")


def test_parse_contract_file_uses_an_adapter_instance():
    adapter = FakeOcr(
        "GAP Waiver -- Zurich -- Contract No. GAP-9 ... $500.00\n"
    )
    result = parse_contract_file("scan.png", ocr=adapter)
    assert len(result.products) == 1
    assert adapter.calls == ["scan.png"]


def test_parse_contract_file_resolves_adapter_by_name():
    # The string "tesseract" must resolve to TesseractOcr, which then fails
    # only because the optional dependency is absent -- proving the wiring.
    try:
        parse_contract_file("scan.png", ocr="tesseract")
    except OcrDependencyError:
        pass
    else:
        raise AssertionError("expected OcrDependencyError from the resolved adapter")


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
