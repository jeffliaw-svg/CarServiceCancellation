"""OCR backend for extracting text from scanned contracts.

`contract_parser` parses the *text* of a contract. For scanned PDFs and
photos, this module supplies that text. An `OcrAdapter` is a pluggable
backend; two concrete ones ship:

  - `AnthropicVisionOcr` -- Claude reads the document image. Most
    reliable on visually dense F&I paperwork. Needs an API key; uses
    only the standard library (no SDK install).
  - `TesseractOcr` -- classical open-source OCR via `pytesseract`.

Every adapter is callable, so an adapter instance drops directly into
the `ocr=` seam of `parse_contract_file`:

    from refunds.contract_parser import parse_contract_file
    parse_contract_file("scan.pdf", ocr="anthropic")
    parse_contract_file("scan.pdf", ocr=TesseractOcr(dpi=400))

Optional dependencies (and, for the vision backend, the API key) are
resolved lazily; a missing one raises `OcrDependencyError` with
instructions rather than failing at import time.
"""

from __future__ import annotations

import abc
import base64
import importlib
import json
import os
import urllib.error
import urllib.request
from typing import Any


class OcrDependencyError(RuntimeError):
    """Raised when an OCR backend's optional dependency is unavailable."""


_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif")


def _require(module_name: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise OcrDependencyError(
            f"The '{module_name.split('.')[0]}' package is required for OCR but "
            f"is not installed. Install the OCR extra:  pip install '.[ocr]'  "
            f"(PDF support also needs the system Poppler binaries, and Tesseract "
            f"OCR must be installed and on PATH)."
        ) from exc


class OcrAdapter(abc.ABC):
    """A backend that extracts plain text from a scanned document."""

    @abc.abstractmethod
    def extract_text(self, path: str) -> str:
        """Return the text content of the document at `path`."""

    def __call__(self, path: str) -> str:
        return self.extract_text(path)


class TesseractOcr(OcrAdapter):
    """OCR via Tesseract (through `pytesseract`).

    Images are read directly; PDFs are rasterized page by page with
    `pdf2image` before being passed to Tesseract.
    """

    def __init__(self, *, dpi: int = 300, lang: str = "eng") -> None:
        self.dpi = dpi
        self.lang = lang

    def extract_text(self, path: str) -> str:
        lower = path.lower()
        if lower.endswith(".pdf"):
            return self._extract_pdf(path)
        if lower.endswith(_IMAGE_EXTENSIONS):
            return self._extract_image(path)
        raise ValueError(
            f"TesseractOcr cannot handle {path!r}; expected a PDF or an image "
            f"file ({', '.join(_IMAGE_EXTENSIONS)})."
        )

    def _ocr_image(self, image: Any) -> str:
        pytesseract = _require("pytesseract")
        try:
            return pytesseract.image_to_string(image, lang=self.lang)
        except pytesseract.TesseractNotFoundError as exc:
            raise OcrDependencyError(
                "The Tesseract OCR engine is not installed or not on PATH. "
                "Install it (e.g. 'apt-get install tesseract-ocr' or "
                "'brew install tesseract')."
            ) from exc

    def _extract_image(self, path: str) -> str:
        image_module = _require("PIL.Image")
        with image_module.open(path) as image:
            return self._ocr_image(image)

    def _extract_pdf(self, path: str) -> str:
        pdf2image = _require("pdf2image")
        pages = pdf2image.convert_from_path(path, dpi=self.dpi)
        return "\n\f\n".join(self._ocr_image(page) for page in pages)


_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"

_VISION_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

_TRANSCRIBE_PROMPT = (
    "You are transcribing a vehicle purchase document -- a retail installment "
    "sales contract or buyer's order. Transcribe ALL text exactly as it "
    "appears, preserving line breaks and the layout of any itemized sections. "
    "Be sure every add-on product line is captured with its product name, the "
    "administrator or provider, any contract or agreement numbers, the price, "
    "and the term (months and miles). Do not summarize and do not add "
    "commentary. Output only the transcribed text."
)


class AnthropicVisionOcr(OcrAdapter):
    """OCR via Claude's vision API -- reads scanned PDFs and photos.

    Far more reliable than classical OCR on visually dense F&I paperwork.
    The Anthropic API is a plain HTTPS request, so this needs no SDK --
    only an API key (the `ANTHROPIC_API_KEY` environment variable, or the
    `api_key` argument).

    Beyond `extract_text`, the `complete(path, prompt)` method runs an
    arbitrary vision prompt, which lets this double as a vision model for
    the structured-extraction ensemble in `refunds.extraction`.
    """

    name = "claude"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 8000,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get(
            "ANTHROPIC_API_KEY", ""
        )
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _source_block(self, path: str) -> dict:
        lower = path.lower()
        if lower.endswith(".pdf"):
            block_type, media_type = "document", "application/pdf"
        else:
            media_type = next(
                (mt for ext, mt in _VISION_MEDIA_TYPES.items() if lower.endswith(ext)),
                None,
            )
            if media_type is None:
                raise ValueError(
                    f"AnthropicVisionOcr cannot handle {path!r}; expected a PDF "
                    f"or a PNG/JPEG/GIF/WebP image."
                )
            block_type = "image"
        with open(path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("ascii")
        return {
            "type": block_type,
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": encoded,
            },
        }

    def _build_payload(self, path: str, prompt: str) -> dict:
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        self._source_block(path),
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }

    def _post(self, payload: dict) -> dict:
        request = urllib.request.Request(
            _ANTHROPIC_URL,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OcrDependencyError(
                f"Anthropic API request failed ({exc.code}): {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise OcrDependencyError(
                f"Could not reach the Anthropic API: {exc.reason}"
            ) from exc

    def complete(self, path: str, prompt: str) -> str:
        """Run `prompt` against the document at `path`; return the reply text."""
        if not self.api_key:
            raise OcrDependencyError(
                "AnthropicVisionOcr needs an API key. Set the "
                "ANTHROPIC_API_KEY environment variable, or pass api_key=..."
            )
        payload = self._build_payload(path, prompt)  # also validates the file
        response = self._post(payload)
        text = "\n".join(
            block.get("text", "")
            for block in response.get("content", [])
            if block.get("type") == "text"
        ).strip()
        if not text:
            raise OcrDependencyError(
                "The Anthropic API returned no text for this document."
            )
        return text

    def extract_text(self, path: str) -> str:
        return self.complete(path, _TRANSCRIBE_PROMPT)


_ADAPTERS: dict[str, type[OcrAdapter]] = {
    "tesseract": TesseractOcr,
    "anthropic": AnthropicVisionOcr,
    "claude": AnthropicVisionOcr,
}


def get_ocr_adapter(name: str = "tesseract", **kwargs: Any) -> OcrAdapter:
    """Construct an OCR adapter by name.

    Construction is cheap and never imports the optional dependencies --
    those load lazily on the first `extract_text` call.
    """
    key = name.strip().lower()
    if key not in _ADAPTERS:
        raise ValueError(
            f"Unknown OCR adapter {name!r}; available: {sorted(_ADAPTERS)}"
        )
    return _ADAPTERS[key](**kwargs)
