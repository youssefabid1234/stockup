"""
The tools the model can call, grouped by domain. Each one wraps ERP API endpoints.

    registry.py  @tool decorator, Tool, ToolContext (start here to add a tool)
    erp.py       the HTTP client for the ERP API
    catalog.py   search, get_client, get_product_stock, find_alternatives, get_price
    context.py   search_context, get_context, save_context
    history.py   get_client_history, log_client_event, get_supplier_history, log_supplier_event
    orders.py    create_draft_order, add_order_line, confirm_order, get_order
    new_client.py register_new_client (team 12, TEAM_PRELOAD)

A new file needs one more line: import it below so its @tool functions get registered.
"""

from app import team_flags

from . import catalog, context, history, orders  # noqa: F401  (importing registers the tools)
from .erp import ErpClient

if team_flags.product_insight():  # team 12 (Youssef): composite tool, registered only when its switch is on
    from . import product_insight  # noqa: F401
if team_flags.order_rules():  # team 12 (Amine K.): delivery-day tool, registered only when its switch is on
    from . import after_sales, delivery, order_edit, order_jev, order_place, order_review  # noqa: F401
if team_flags.preload():  # team 12 (Youssef): a new client on the phone becomes a real prospect in the ERP
    from . import new_client  # noqa: F401
from .registry import TOOLS, Tool, ToolContext, tool


def all_tools() -> list[Tool]:
    return list(TOOLS.values())


__all__ = ["TOOLS", "ErpClient", "Tool", "ToolContext", "all_tools", "tool"]
