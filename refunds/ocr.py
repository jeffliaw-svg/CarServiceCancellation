"""OCR backend for extracting text from scanned contracts.

`contract_parser` parses the *text* of a contract. For scanned PDFs and
photos, this module supplies that text. An `OcrAdapter` is a pluggable
backend; `TesseractOcr` is the concrete, open-source implementation.

Every adapter is callable, so an adapter instance drops directly into
the `ocr=` seam of `parse_contract_file`:

    from refunds.contract_parser import parse_contract_file
    parse_contract_file("scan.pdf", ocr="tesseract")
    parse_contract_file("scan.pdf", ocr=TesseractOcr(dpi=400))

The third-party packages (`pytesseract`, `Pillow`, `pdf2image`) and the
system Tesseract/Poppler binaries are optional -- they are imported
lazily, and a missing dependency raises `OcrDependencyError` with
install instructions rather than failing at import time. A vision-LLM or
cloud-OCR backend can be added later as another `OcrAdapter` subclass.
"""

from __future__ import annotations

import abc
import importlib
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


_ADAPTERS: dict[str, type[OcrAdapter]] = {
    "tesseract": TesseractOcr,
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
