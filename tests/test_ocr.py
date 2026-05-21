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
import tempfile  # noqa: E402

from refunds.ocr import (  # noqa: E402
    AnthropicVisionOcr,
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


def test_anthropic_factory_aliases():
    assert isinstance(get_ocr_adapter("anthropic"), AnthropicVisionOcr)
    assert isinstance(get_ocr_adapter("claude"), AnthropicVisionOcr)


def test_anthropic_without_key_raises():
    try:
        AnthropicVisionOcr(api_key="").extract_text("scan.pdf")
    except OcrDependencyError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("expected OcrDependencyError without an API key")


def test_anthropic_rejects_unsupported_extension():
    try:
        AnthropicVisionOcr(api_key="test-key").extract_text("contract.docx")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for an unsupported file type")


def test_anthropic_builds_pdf_and_image_blocks():
    ocr = AnthropicVisionOcr(api_key="test-key")
    with tempfile.TemporaryDirectory() as folder:
        pdf_path = os.path.join(folder, "c.pdf")
        png_path = os.path.join(folder, "c.png")
        with open(pdf_path, "wb") as handle:
            handle.write(b"%PDF-1.4 fake")
        with open(png_path, "wb") as handle:
            handle.write(b"\x89PNG fake")
        pdf_block = ocr._build_payload(pdf_path, "read")["messages"][0][
            "content"
        ][0]
        png_block = ocr._build_payload(png_path, "read")["messages"][0][
            "content"
        ][0]
    assert pdf_block["type"] == "document"
    assert pdf_block["source"]["media_type"] == "application/pdf"
    assert png_block["type"] == "image"
    assert png_block["source"]["media_type"] == "image/png"


def test_anthropic_extract_text_parses_the_response():
    class FakeAnthropic(AnthropicVisionOcr):
        def _post(self, payload: dict) -> dict:
            self.sent = payload
            return {
                "content": [
                    {"type": "text", "text": "GAP Waiver -- Zurich -- $400.00"}
                ]
            }

    ocr = FakeAnthropic(api_key="test-key")
    with tempfile.TemporaryDirectory() as folder:
        png_path = os.path.join(folder, "c.png")
        with open(png_path, "wb") as handle:
            handle.write(b"\x89PNG fake")
        text = ocr.extract_text(png_path)
    assert "GAP Waiver" in text
    assert ocr.sent["model"]
    assert ocr.sent["messages"][0]["content"][0]["type"] == "image"


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
