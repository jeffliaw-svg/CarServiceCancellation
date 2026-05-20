"""Tests for the administrator registry and its maintenance tooling.

Runs under pytest, or standalone:  python tests/test_registry.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from refunds import load_registry, lookup, save_registry  # noqa: E402
from refunds.models import CancellationRoute  # noqa: E402
from refunds.registry_tool import set_administrator  # noqa: E402


def test_default_registry_loads_known_administrators():
    registry = load_registry()
    for name in ("zurich", "gwc warranty", "easycare (apco)"):
        assert name in registry


def test_seeded_addresses_are_present_but_unverified():
    registry = load_registry()
    for admin in registry.values():
        assert admin.address_lines, f"{admin.name} has no address"
        # Web-sourced data must not claim to be human-verified.
        assert admin.address_verified is False
        assert admin.source


def test_registry_round_trips_through_json():
    registry = load_registry()
    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w"
    ) as handle:
        path = handle.name
    try:
        save_registry(registry, path)
        reloaded = load_registry(path)
        assert reloaded == registry
    finally:
        os.unlink(path)


def test_set_administrator_updates_fields():
    registry = load_registry()
    set_administrator(
        registry,
        "Zurich",
        address=["123 New Street", "Somewhere, KS 66000"],
        route="administrator",
    )
    zurich = registry["zurich"]
    assert zurich.address_lines == ["123 New Street", "Somewhere, KS 66000"]
    assert zurich.cancellation_route == CancellationRoute.ADMINISTRATOR


def test_marking_verified_stamps_the_date():
    registry = load_registry()
    set_administrator(
        registry, "Zurich", verified=True, today=date(2026, 5, 20)
    )
    zurich = registry["zurich"]
    assert zurich.address_verified is True
    assert zurich.verified_on == "2026-05-20"


def test_cannot_verify_without_an_address():
    registry = load_registry()
    set_administrator(registry, "Brand New Co.")  # created with no address
    try:
        set_administrator(registry, "Brand New Co.", verified=True)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError verifying an addressless entry")


def test_set_administrator_creates_new_entry():
    registry = load_registry()
    before = len(registry)
    set_administrator(
        registry, "Regional Warranty Co.", address=["PO Box 1", "Town, ST 00000"]
    )
    assert len(registry) == before + 1
    assert lookup("Regional Warranty Co.", registry).address_lines


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
