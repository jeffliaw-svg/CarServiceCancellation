"""Registry of add-on product administrators.

This is a starter set of real, well-known F&I product administrators.
Mailing addresses and cancellation routes are intentionally left
UNVERIFIED -- confirming them is manual research and is the core
proprietary asset of the service. The letter engine surfaces a warning
on any letter built from an unverified entry.
"""

from __future__ import annotations

from .models import Administrator, CancellationRoute


def _unverified_address() -> list[str]:
    return ["<<VERIFY: mailing address required>>"]


def _seed() -> dict[str, Administrator]:
    admins = [
        Administrator(
            name="Zurich",
            address_lines=_unverified_address(),
            cancellation_route=CancellationRoute.EITHER,
            notes="Zurich-administered VSC/GAP cancellations are often processed "
            "through the selling dealer; confirm the route for this contract.",
        ),
        Administrator(
            name="Fidelity Warranty Services",
            address_lines=_unverified_address(),
            cancellation_route=CancellationRoute.DEALER,
            notes="FWS typically requires the selling dealer to submit cancellations.",
        ),
        Administrator(
            name="JM&A Group",
            address_lines=_unverified_address(),
            cancellation_route=CancellationRoute.DEALER,
        ),
        Administrator(
            name="Safe-Guard Products International",
            address_lines=_unverified_address(),
            cancellation_route=CancellationRoute.ADMINISTRATOR,
        ),
        Administrator(
            name="EasyCare (APCO)",
            address_lines=_unverified_address(),
            cancellation_route=CancellationRoute.ADMINISTRATOR,
        ),
        Administrator(
            name="Assurant",
            address_lines=_unverified_address(),
            cancellation_route=CancellationRoute.EITHER,
        ),
        Administrator(
            name="GWC Warranty",
            address_lines=_unverified_address(),
            cancellation_route=CancellationRoute.ADMINISTRATOR,
        ),
    ]
    return {a.name.lower(): a for a in admins}


DEFAULT_REGISTRY: dict[str, Administrator] = _seed()


def lookup(
    name: str, registry: dict[str, Administrator] | None = None
) -> Administrator:
    """Resolve an administrator by name.

    Always returns an Administrator. An unknown name yields an unverified
    placeholder so a draft letter can still be produced (flagged for
    research) rather than failing the case outright.
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
        address_lines=["<<VERIFY: administrator not in registry -- research address>>"],
        cancellation_route=CancellationRoute.EITHER,
        notes="Administrator is not in the registry; verify the name, mailing "
        "address, and cancellation procedure before mailing.",
    )
