"""Refund-rules reference, loaded from a human-maintained data file.

`data/refund_rules.json` records the typical pro-rata method for each
product type and per-state statutory notes. It is deliberately NOT
auto-refreshed: statutory cancellation law changes on a legislative
cadence and should be reviewed by a person with legal input, not polled
nightly. The binding refund is always the administrator's calculation
under the actual contract and applicable law -- these notes inform the
estimate and the customer.

`state_notes` returns only entries a human has reviewed (a non-empty
`reviewed_on`), so unconfirmed placeholders are never shown to customers.
"""

from __future__ import annotations

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "refund_rules.json")


def load_rules(path: str = _DATA_PATH) -> dict:
    """Load the refund-rules reference from its JSON data file."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


DEFAULT_RULES: dict = load_rules()


def method_note(product_type: str, rules: dict | None = None) -> dict:
    """Return {method, note} describing how `product_type` is refunded."""
    source = DEFAULT_RULES if rules is None else rules
    return source.get("methods", {}).get(product_type, {})


def state_notes(state: str, rules: dict | None = None) -> list[dict]:
    """Return the reviewed statutory notes for a 2-letter state code.

    Unreviewed placeholder entries (empty `reviewed_on`) are excluded.
    """
    source = DEFAULT_RULES if rules is None else rules
    if not state:
        return []
    entries = source.get("states", {}).get(state.strip().upper(), [])
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if entry.get("reviewed_on")]
