"""Minimal, dependency-free PDF rendering for letters and authorizations.

Letters and the authorization document are plain monospaced text. This
module renders that text into a printable PDF using the standard Courier
font (one of the 14 base fonts, so nothing needs embedding). It paginates
long documents and word-wraps over-long lines.

It is deliberately small -- enough to produce a clean, printable page,
not a general-purpose PDF library.
"""

from __future__ import annotations

PAGE_WIDTH = 612   # US Letter, points
PAGE_HEIGHT = 792
MARGIN_X = 54      # 0.75 inch
TOP_Y = 738        # baseline of the first line
FONT_SIZE = 10
LEADING = 12       # line height
# Courier glyphs are 0.6 em wide; keep a little slack inside the right margin.
MAX_CHARS = 84
LINES_PER_PAGE = 55


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
    lines: list[str] = []
    for raw_line in text.split("\n"):
        lines.extend(_wrap_line(raw_line, MAX_CHARS))
    pages = [
        lines[start : start + LINES_PER_PAGE]
        for start in range(0, len(lines), LINES_PER_PAGE)
    ]
    return pages or [[]]


def _content_stream(page_lines: list[str]) -> bytes:
    parts = [
        "BT",
        f"/F1 {FONT_SIZE} Tf",
        f"{LEADING} TL",
        f"{MARGIN_X} {TOP_Y} Td",
    ]
    for line in page_lines:
        parts.append(f"({_escape(line)}) Tj")
        parts.append("T*")
    parts.append("ET")
    return ("\n".join(parts)).encode("latin-1", errors="replace")


def text_to_pdf(text: str) -> bytes:
    """Render `text` into the bytes of a printable PDF document."""

    pages = _paginate(text)

    # Object ids: 1 catalog, 2 pages, 3 font, then (page, content) pairs.
    page_object_ids = [4 + 2 * i for i in range(len(pages))]
    content_object_ids = [5 + 2 * i for i in range(len(pages))]
    total_objects = 3 + 2 * len(pages)

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
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("latin-1"),
    )

    add_object(
        3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"
    )

    for page_lines, page_id, content_id in zip(
        pages, page_object_ids, content_object_ids
    ):
        page_body = (
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        add_object(page_id, page_body.encode("latin-1"))

        stream = _content_stream(page_lines)
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


def write_pdf(text: str, path: str) -> str:
    """Render `text` to a PDF file at `path`; return the path."""
    with open(path, "wb") as handle:
        handle.write(text_to_pdf(text))
    return path
