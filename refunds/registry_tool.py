"""CLI for maintaining the administrator registry.

Examples (run from the repository root):

  python -m refunds.registry_tool list
  python -m refunds.registry_tool show "Zurich"
  python -m refunds.registry_tool set "Zurich" \\
      --address "P.O. Box 7922" --address "Shawnee Mission, KS 66207" \\
      --attn "Zurich F&I Customer Service" --route either \\
      --phone "888-835-5063" --source "confirmed by phone" --verified

`--verified` records that a human has confirmed the address and stamps
today's date. Without it, an address is treated as unverified and the
letter engine will warn before mailing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from .administrators import load_registry, save_registry
from .models import Administrator, CancellationRoute


def set_administrator(
    registry: dict[str, Administrator],
    name: str,
    *,
    address: list[str] | None = None,
    attn: str | None = None,
    route: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    source: str | None = None,
    notes: str | None = None,
    verified: bool | None = None,
    today: date | None = None,
) -> Administrator:
    """Create or update an administrator in `registry`; return the entry.

    Raises ValueError if `verified` is set true without an address on file.
    """
    key = name.strip().lower()
    admin = registry.get(key) or Administrator(name=name, address_lines=[])

    if address is not None:
        admin.address_lines = list(address)
    if attn is not None:
        admin.attn = attn
    if route is not None:
        admin.cancellation_route = CancellationRoute(route)
    if phone is not None:
        admin.phone = phone
    if email is not None:
        admin.email = email
    if source is not None:
        admin.source = source
    if notes is not None:
        admin.notes = notes

    if verified is True:
        if not admin.address_lines:
            raise ValueError(
                f"Cannot mark {name!r} verified: no address on file."
            )
        admin.address_verified = True
        admin.verified_on = (today or date.today()).isoformat()
    elif verified is False:
        admin.address_verified = False
        admin.verified_on = ""

    registry[key] = admin
    return admin


def _format_admin(admin: Administrator) -> str:
    if admin.address_verified:
        status = f"VERIFIED {admin.verified_on}".strip()
    elif admin.address_lines:
        status = "unverified"
    else:
        status = "NO ADDRESS"
    lines = [
        f"{admin.name}",
        f"  status:  {status}",
        f"  route:   {admin.cancellation_route.value}",
        f"  attn:    {admin.attn}",
        f"  phone:   {admin.phone or '(none)'}",
        f"  email:   {admin.email or '(none)'}",
        "  address: " + (
            "\n           ".join(admin.address_lines)
            if admin.address_lines
            else "(none)"
        ),
        f"  source:  {admin.source or '(none)'}",
    ]
    if admin.notes:
        lines.append(f"  notes:   {admin.notes}")
    return "\n".join(lines)


def _cmd_list(registry: dict[str, Administrator]) -> int:
    for key in sorted(registry):
        admin = registry[key]
        if admin.address_verified:
            flag = f"[verified {admin.verified_on}]"
        elif admin.address_lines:
            flag = "[unverified]"
        else:
            flag = "[no address]"
        first_line = admin.address_lines[0] if admin.address_lines else "--"
        print(f"  {flag:<22} {admin.name:<34} {first_line}")
    return 0


def _cmd_show(registry: dict[str, Administrator], name: str) -> int:
    admin = registry.get(name.strip().lower())
    if admin is None:
        print(f"No administrator named {name!r} in the registry.", file=sys.stderr)
        return 1
    print(_format_admin(admin))
    return 0


def _cmd_set(registry: dict[str, Administrator], args: argparse.Namespace) -> int:
    verified: bool | None = None
    if args.verified:
        verified = True
    elif args.unverify:
        verified = False

    try:
        admin = set_administrator(
            registry,
            args.name,
            address=args.address if args.address else None,
            attn=args.attn,
            route=args.route,
            phone=args.phone,
            email=args.email,
            source=args.source,
            notes=args.notes,
            verified=verified,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    save_registry(registry)
    print(f"Saved. Updated entry:\n")
    print(_format_admin(admin))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="registry_tool", description="Maintain the administrator registry."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list every administrator")

    show = sub.add_parser("show", help="show one administrator in detail")
    show.add_argument("name")

    set_cmd = sub.add_parser("set", help="create or update an administrator")
    set_cmd.add_argument("name")
    set_cmd.add_argument(
        "--address",
        action="append",
        metavar="LINE",
        help="an address line (repeat for each line; replaces all lines)",
    )
    set_cmd.add_argument("--attn")
    set_cmd.add_argument(
        "--route", choices=[route.value for route in CancellationRoute]
    )
    set_cmd.add_argument("--phone")
    set_cmd.add_argument("--email", help="cancellations email address")
    set_cmd.add_argument("--source", help="provenance of the address")
    set_cmd.add_argument("--notes")
    set_cmd.add_argument(
        "--verified",
        action="store_true",
        help="mark the address human-verified (stamps today's date)",
    )
    set_cmd.add_argument(
        "--unverify", action="store_true", help="clear the verified flag"
    )

    args = parser.parse_args(argv)
    registry = load_registry()

    if args.command == "list":
        return _cmd_list(registry)
    if args.command == "show":
        return _cmd_show(registry, args.name)
    if args.command == "set":
        return _cmd_set(registry, args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
