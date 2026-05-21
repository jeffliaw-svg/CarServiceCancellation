"""Tests for the refund-rules reference.

Runs under pytest, or standalone:  python tests/test_refund_rules.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from refunds import ProductType  # noqa: E402
from refunds.refund_rules import load_rules, method_note, state_notes  # noqa: E402


def test_every_product_type_has_a_method_note():
    rules = load_rules()
    for product_type in ProductType:
        note = method_note(product_type.value, rules)
        assert note.get("method"), f"no method note for {product_type.value}"


def test_state_notes_excludes_unreviewed_placeholders():
    # The seeded IL entry has an empty reviewed_on and must not surface.
    assert state_notes("IL") == []


def test_state_notes_returns_only_reviewed_entries():
    rules = {
        "states": {
            "CA": [
                {
                    "topic": "GAP refund",
                    "rule": "a confirmed rule",
                    "source": "Cal. statute",
                    "reviewed_on": "2026-01-15",
                },
                {
                    "topic": "VSC refund",
                    "rule": "<<RESEARCH>>",
                    "source": "",
                    "reviewed_on": "",
                },
            ]
        }
    }
    notes = state_notes("CA", rules)
    assert len(notes) == 1
    assert notes[0]["topic"] == "GAP refund"


def test_state_notes_handles_unknown_or_empty_state():
    assert state_notes("ZZ") == []
    assert state_notes("") == []


def test_state_notes_is_case_insensitive():
    rules = {
        "states": {
            "TX": [
                {
                    "topic": "x",
                    "rule": "y",
                    "source": "z",
                    "reviewed_on": "2026-02-01",
                }
            ]
        }
    }
    assert len(state_notes("tx", rules)) == 1


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
