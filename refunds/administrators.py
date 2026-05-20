"""Registry of add-on product administrators, loaded from a data file.

The registry lives in `data/administrators.json` so it can be maintained
without code changes (see `registry_tool`). Every seeded address was
collected by web research and is NOT human-verified -- `address_verified`
is false until a person confirms it. The letter engine surfaces a
warning on any letter built from an unverified or missing address.
"""

from __future__ import annotations

import json
import os

from .models import Administrator, CancellationRoute

_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "administrators.json")


def _administrator_from_dict(data: dict) -> Administrator:
    return Administrator(
        name=data["name"],
        address_lines=list(data.get("address_lines") or []),
        attn=data.get("attn", "Cancellations Department"),
        cancellation_route=CancellationRoute(
            data.get("cancellation_route", CancellationRoute.ADMINISTRATOR.value)
        ),
        phone=data.get("phone", ""),
        address_verified=bool(data.get("address_verified", False)),
        source=data.get("source", ""),
        verified_on=data.get("verified_on", ""),
        notes=data.get("notes", ""),
    )


def _administrator_to_dict(admin: Administrator) -> dict:
    return {
        "name": admin.name,
        "address_lines": list(admin.address_lines),
        "attn": admin.attn,
        "cancellation_route": admin.cancellation_route.value,
        "phone": admin.phone,
        "address_verified": admin.address_verified,
        "source": admin.source,
        "verified_on": admin.verified_on,
        "notes": admin.notes,
    }


def load_registry(path: str = _DATA_PATH) -> dict[str, Administrator]:
    """Load the administrator registry from a JSON data file."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    admins = [
        _administrator_from_dict(item) for item in data.get("administrators", [])
    ]
    return {admin.name.lower(): admin for admin in admins}


def save_registry(
    registry: dict[str, Administrator], path: str = _DATA_PATH
) -> str:
    """Write the registry back to its JSON data file, sorted by name."""
    payload = {
        "_comment": (
            "Administrator registry. Confirm each address against the "
            "administrator's current cancellation instructions before mailing. "
            "Use 'python -m refunds.registry_tool' to maintain this file."
        ),
        "administrators": [
            _administrator_to_dict(registry[key]) for key in sorted(registry)
        ],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return path


DEFAULT_REGISTRY: dict[str, Administrator] = load_registry()


def lookup(
    name: str, registry: dict[str, Administrator] | None = None
) -> Administrator:
    """Resolve an administrator by name.

    Always returns an Administrator. An unknown name yields a placeholder
    with no address (flagged for research) so a draft letter can still be
    produced rather than failing the case outright.
    """
    reg = DEFAULT_REGISTRY if registry is None else registry
    key = (name or "").strip().lower()
    if key in reg:
        return reg[key]
    for registered_key, admin in reg.items():
        if key and (key in registered_key or registered_key in key):
            return admin
    return Administrator(
        name=name or "[Unknown Administrator]",
        address_lines=[],
        cancellation_route=CancellationRoute.EITHER,
        notes="Administrator is not in the registry; verify the name, mailing "
        "address, and cancellation procedure before mailing.",
    )
