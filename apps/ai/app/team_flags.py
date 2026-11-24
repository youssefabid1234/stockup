"""
Team 12 switches: each brick of our voice agent is OFF by default, so the kit's original behaviour stays until the
brick works. Turn one on in the repo-root `.env` (e.g. `TEAM_FILLERS=1`), then restart the AI service.

Read at call time (not import time) so tests can flip them with monkeypatch.setenv; the exception is
TEAM_PRODUCT_INSIGHT, read when tools are registered (restart needed). See docs/team/interfaces.md.

| Switch                 | Owner          | Brick                                                        |
|------------------------|----------------|--------------------------------------------------------------|
| TEAM_FILLERS           | Mohamed Amine  | services/fillers.py: classic (1), fast restatement (2), combined (3) |
| TEAM_ORCHESTRATOR      | Youssef        | agent/orchestrator.py: fast "speaker" agent + "brain" agent  |
| TEAM_PRELOAD           | Youssef        | agent/call_context.py: client sheet loaded once, in parallel |
| TEAM_PRODUCT_INSIGHT   | Youssef        | tools/product_insight.py: stock + price + substitutes + promo |
| TEAM_ORDER_RULES       | Amine Khalil   | agent/rules_order.py: jargon, usual, readback, checks         |
| TEAM_SALES_RULES       | Daycem         | agent/rules_sales.py: preferences, consent, persuasion, tone  |
"""

import os

from app import config  # noqa: F401  (loads the repo-root .env into os.environ before we read the switches)

_TRUE = {"1", "true", "yes", "on"}


def _on(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE


def fillers_mode() -> int:
    value = os.environ.get("TEAM_FILLERS", "").strip().lower()
    if value in {"2", "3"}:
        return int(value)
    return int(value in _TRUE)


def fillers() -> bool:
    return fillers_mode() != 0


def fast_fillers() -> bool:
    return fillers_mode() in {2, 3}


def orchestrator() -> bool:
    return _on("TEAM_ORCHESTRATOR")


def preload() -> bool:
    return _on("TEAM_PRELOAD")


def product_insight() -> bool:
    return _on("TEAM_PRODUCT_INSIGHT")


def order_rules() -> bool:
    return _on("TEAM_ORDER_RULES")


def sales_rules() -> bool:
    return _on("TEAM_SALES_RULES")


def fast_model() -> str:
    """Model of the fast "speaker" agent (orchestrator). Haiku = fastest Anthropic model."""
    return os.environ.get("TEAM_FAST_MODEL", "").strip() or "claude-haiku-5-5"


def all_flags() -> dict[str, bool]:
    """For /health-style debugging and the scenario runner's report."""
    return {
        "fillers": fillers(),
        "orchestrator": orchestrator(),
        "preload": preload(),
        "product_insight": product_insight(),
        "order_rules": order_rules(),
        "sales_rules": sales_rules(),
    }
