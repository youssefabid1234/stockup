"""
Team 12 · Daycem (T4) · who should get a clearing promotion on a substitute, from the order history.

Real life: when a product is out of stock, a promotion on its substitute is meant for the clients who USED TO BUY the
missing product and accept a substitute (they are the ones who would switch). Giving it to every client of the group is
a windfall for those who buy the substitute anyway, and wasted on those who refuse any substitute.

Generic on purpose: no client, product or group is written here; everything comes from the arguments. The demo values
and the resulting FROZEN list live in scripts/setup_demo_data.py and apps/backend/app/core/team_demo.py (DECISIONS §5);
tests/test_promo_target.py checks that the frozen list still matches this computation on the data.

    PYTHONPATH=apps/ai python scripts/promo_target.py --tag <client group> --product <out-of-stock product id> \\
        --min-orders 2 --months 12 [--seed-dir DATA_DIR/seed] [--today YYYY-MM-DD]

Refusal = the card's substitution_policy (apps/ai, keywords in French and English) says « refuse » for that product.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path

IGNORED_STATUSES = {"cancelled", "draft"}  # an order that was not really placed says nothing about a habit


def months_before(today: date, months: int) -> date:
    """Same day `months` months earlier (end of month when that day does not exist)."""
    y, m = divmod(today.year * 12 + today.month - 1 - months, 12)
    return date(y, m + 1, min(today.day, calendar.monthrange(y, m + 1)[1]))


def select_targets(
    clients: Iterable[dict],
    orders: Iterable[dict],
    *,
    client_tag: str,
    product_id: str,
    min_orders: int,
    months: int,
    today: date,
    refuses: Callable[[dict], bool],
) -> list[str]:
    """Ids (sorted) of the clients in `client_tag`, active, with at least `min_orders` orders containing `product_id`
    delivered over the last `months` months (up to `today`), and for whom `refuses(client)` is False."""
    since = months_before(today, months)
    counts: dict[str, int] = {}
    for o in orders:
        if o.get("status") in IGNORED_STATUSES:
            continue
        day = date.fromisoformat(str(o.get("deliveryDate") or o.get("createdAt") or "")[:10] or "1900-01-01")
        if not since <= day <= today or not any(line.get("productId") == product_id for line in o.get("lines") or []):
            continue
        counts[o.get("clientId")] = counts.get(o.get("clientId"), 0) + 1  # one order counts once, whatever its lines
    return sorted(
        c["id"]
        for c in clients
        if client_tag in (c.get("tags") or [])
        and c.get("status", "active") == "active"
        and counts.get(c["id"], 0) >= min_orders
        and not refuses(c)
    )


def _rows(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("items", [])


def targets_from_pack(seed_dir: Path, *, client_tag: str, product_id: str, min_orders: int, months: int,
                      today: date | None = None) -> list[str]:  # fmt: skip
    """select_targets on a data pack folder (clients.json, orders.json, products.json, meta.json), refusal read with
    the agent's own substitution_policy. `today` defaults to the pack's business date."""
    from app.agent.rules_sales import substitution_policy  # apps/ai on PYTHONPATH

    seed_dir = Path(seed_dir)
    meta = json.loads((seed_dir / "meta.json").read_text(encoding="utf-8"))
    today = today or date.fromisoformat(str(meta["today"])[:10])
    name = next((p.get("name") or "" for p in _rows(seed_dir / "products.json") if p.get("id") == product_id), "")

    def refuses(c: dict) -> bool:
        notes = [n.get("text") or "" if isinstance(n, dict) else str(n) for n in c.get("notes") or []]
        return substitution_policy(name, c.get("preferences") or "", notes) == "refuse"

    return select_targets(_rows(seed_dir / "clients.json"), _rows(seed_dir / "orders.json"), client_tag=client_tag,
                          product_id=product_id, min_orders=min_orders, months=months, today=today, refuses=refuses)  # fmt: skip


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clients who should get a clearing promotion on a substitute.")
    parser.add_argument("--tag", required=True, help="client group")
    parser.add_argument("--product", required=True, help="id of the product that is out of stock")
    parser.add_argument("--min-orders", type=int, default=2)
    parser.add_argument("--months", type=int, default=12)
    default_seed = Path(os.environ.get("DATA_DIR", "data")) / (os.environ.get("SEED_DIR_NAME") or "seed")
    parser.add_argument("--seed-dir", type=Path, default=default_seed)
    parser.add_argument("--today", type=date.fromisoformat, default=None, help="default: the pack's business date")
    a = parser.parse_args()
    print(json.dumps(targets_from_pack(a.seed_dir, client_tag=a.tag, product_id=a.product, min_orders=a.min_orders,
                                       months=a.months, today=a.today)))  # fmt: skip
