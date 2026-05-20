"""Tests for the minimal PDF renderer.

Runs under pytest, or standalone:  python tests/test_pdf.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from refunds.pdf import LINES_PER_PAGE, text_to_pdf, write_pdf  # noqa: E402


def test_produces_a_pdf_document():
    data = text_to_pdf("Hello, world.")
    assert data.startswith(b"%PDF-")
    assert b"%%EOF" in data
    assert b"/BaseFont /Courier" in data


def test_single_page_for_short_text():
    data = text_to_pdf("one\ntwo\nthree")
    assert b"/Count 1" in data


def test_long_text_paginates():
    text = "\n".join(f"line {i}" for i in range(LINES_PER_PAGE * 2))
    data = text_to_pdf(text)
    assert b"/Count 2" in data


def test_parentheses_and_backslashes_are_escaped():
    data = text_to_pdf("a (parenthetical) and a back\\slash")
    assert b"\\(" in data
    assert b"\\)" in data
    assert b"\\\\" in data


def test_xref_count_matches_objects():
    # 3 fixed objects + 2 per page; one page here -> 5 objects, xref size 6.
    data = text_to_pdf("short")
    assert b"/Size 6" in data


def test_write_pdf_creates_a_file():
    with tempfile.TemporaryDirectory() as root:
        path = os.path.join(root, "letter.pdf")
        write_pdf("A test letter.", path)
        assert os.path.isfile(path)
        with open(path, "rb") as handle:
            assert handle.read(5) == b"%PDF-"


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
