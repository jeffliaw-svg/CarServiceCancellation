"""Minimal, dependency-free PDF rendering for letters and packets.

Letters, the authorization, and the assembled mailing packets are plain
monospaced text. This module renders that text into a printable PDF
using the standard Courier font (no embedding). It paginates long text,
word-wraps over-long lines, honours an explicit page break (the form
feed character "\\f"), and stamps every page with an optional running
header and a "Page N of X" footer.

It is deliberately small -- enough to produce a clean, printable page,
not a general-purpose PDF library.
"""

from __future__ import annotations

PAGE_WIDTH = 612   # US Letter, points
PAGE_HEIGHT = 792
MARGIN_X = 54      # 0.75 inch
HEADER_Y = 754     # baseline of the running header
RULE_Y = 746       # the thin line under the header
BODY_TOP = 728     # baseline of the first body line
FOOTER_Y = 44      # baseline of the page-number footer
FONT_SIZE = 10
SMALL_SIZE = 9     # header and footer
LEADING = 12       # body line height
# Courier glyphs are 0.6 em wide; keep a little slack inside the right margin.
MAX_CHARS = 84
LINES_PER_PAGE = 54


def _wrap_line(line: str, width: int) -> list[str]:
    if len(line) <= width:
        return [line]
    indent_len = len(line) - len(line.lstrip(" "))
    prefix = " " * indent_len
    wrapped: list[str] = []
    current = prefix
    for word in line.split():
        if current.strip() == "":
            current = prefix + word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            wrapped.append(current)
            current = prefix + word
    wrapped.append(current)
    return wrapped


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _paginate(text: str) -> list[list[str]]:
    """Split text into pages. A form feed ("\\f") forces a page break, so
    each section of an assembled packet starts on a fresh page."""
    pages: list[list[str]] = []
    for block in text.split("\f"):
        lines: list[str] = []
        for raw_line in block.split("\n"):
            lines.extend(_wrap_line(raw_line, MAX_CHARS))
        for start in range(0, max(len(lines), 1), LINES_PER_PAGE):
            pages.append(lines[start : start + LINES_PER_PAGE])
    return pages or [[]]


def _page_stream(
    page_lines: list[str], page_num: int, total: int, header: str | None
) -> bytes:
    parts: list[str] = []

    if header:
        parts.append("BT")
        parts.append(f"/F1 {SMALL_SIZE} Tf")
        parts.append(f"{MARGIN_X} {HEADER_Y} Td")
        parts.append(f"({_escape(header[:MAX_CHARS])}) Tj")
        parts.append("ET")
        parts.append("0.6 0.6 0.6 RG 0.6 w")
        parts.append(
            f"{MARGIN_X} {RULE_Y} m {PAGE_WIDTH - MARGIN_X} {RULE_Y} l S"
        )

    parts.append("BT")
    parts.append(f"/F1 {FONT_SIZE} Tf")
    parts.append(f"{LEADING} TL")
    parts.append(f"{MARGIN_X} {BODY_TOP} Td")
    for line in page_lines:
        parts.append(f"({_escape(line)}) Tj")
        parts.append("T*")
    parts.append("ET")

    footer = f"Page {page_num} of {total}"
    parts.append("BT")
    parts.append(f"/F1 {SMALL_SIZE} Tf")
    parts.append(f"{MARGIN_X} {FOOTER_Y} Td")
    parts.append(f"({_escape(footer)}) Tj")
    parts.append("ET")

    return ("\n".join(parts)).encode("latin-1", errors="replace")


def text_to_pdf(text: str, *, header: str | None = None) -> bytes:
    """Render `text` into the bytes of a printable PDF document.

    A "\\f" in the text forces a page break. Every page carries the
    optional running `header` and a "Page N of X" footer.
    """

    pages = _paginate(text)
    total = len(pages)

    # Object ids: 1 catalog, 2 pages, 3 font, then (page, content) pairs.
    page_object_ids = [4 + 2 * i for i in range(total)]
    content_object_ids = [5 + 2 * i for i in range(total)]
    total_objects = 3 + 2 * total

    buffer = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}

    def add_object(object_id: int, body: bytes) -> None:
        offsets[object_id] = len(buffer)
        buffer.extend(f"{object_id} 0 obj\n".encode("latin-1"))
        buffer.extend(body)
        buffer.extend(b"\nendobj\n")

    add_object(1, b"<< /Type /Catalog /Pages 2 0 R >>")

    kids = " ".join(f"{pid} 0 R" for pid in page_object_ids)
    add_object(
        2,
        f"<< /Type /Pages /Kids [{kids}] /Count {total} >>".encode("latin-1"),
    )

    add_object(3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    for index, (page_lines, page_id, content_id) in enumerate(
        zip(pages, page_object_ids, content_object_ids)
    ):
        page_body = (
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        add_object(page_id, page_body.encode("latin-1"))

        stream = _page_stream(page_lines, index + 1, total, header)
        content_body = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )
        add_object(content_id, content_body)

    xref_offset = len(buffer)
    buffer.extend(f"xref\n0 {total_objects + 1}\n".encode("latin-1"))
    buffer.extend(b"0000000000 65535 f \n")
    for object_id in range(1, total_objects + 1):
        buffer.extend(f"{offsets[object_id]:010d} 00000 n \n".encode("latin-1"))
    buffer.extend(
        f"trailer\n<< /Size {total_objects + 1} /Root 1 0 R >>\n".encode("latin-1")
    )
    buffer.extend(f"startxref\n{xref_offset}\n%%EOF\n".encode("latin-1"))

    return bytes(buffer)


def write_pdf(text: str, path: str, *, header: str | None = None) -> str:
    """Render `text` to a PDF file at `path`; return the path."""
    with open(path, "wb") as handle:
        handle.write(text_to_pdf(text, header=header))
    return path
