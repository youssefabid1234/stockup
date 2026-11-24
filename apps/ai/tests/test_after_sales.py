"""T6: a complaint in an order call: the real delivery, the amount, recorded with the order; redelivery at 0 € or credit."""

import importlib

import pytest

from app.tools import registry
from app.tools.registry import ToolContext

from test_order_place import FakeErp  # tests/ is on the path (rootdir conftest)


class SavErp(FakeErp):
    """Sarrailh was delivered on Saturday 21/11 (21 sacks of tradi at 18.89), nothing this morning (Tue 24/11)."""

    def __init__(self):
        super().__init__()
        self.orders["ord_9"] = {"id": "ord_9", "number": "CMD-9", "clientId": "cli_0001", "status": "delivered",
                                "deliveryDate": "2026-11-21", "source": "email",
                                "lines": [{"id": "lin_a", "productId": "prd_0001", "qty": 21, "unitPrice": 18.89},
                                          {"id": "lin_b", "productId": "prd_0006", "qty": 3, "unitPrice": 21.5}]}
        self.events: dict[str, dict] = {}

    async def post(self, path, body=None):
        if path.endswith("/events"):
            self.calls.append(("POST", path))
            eid = f"cev_{len(self.events) + 1}"
            self.events[eid] = {"id": eid, **body}
            return self.events[eid]
        return await super().post(path, body)

    async def patch(self, path, body=None):
        if path.startswith("/api/client-events/"):
            self.calls.append(("PATCH", path))
            self.events[path.split("/")[3]].update(body)
            return self.events[path.split("/")[3]]
        return await super().patch(path, body)


@pytest.fixture
def sav(monkeypatch):
    saved = dict(registry.TOOLS)
    from app.tools import order_jev, order_review

    order_review._products = None
    for name in ("resolve_product", "place_order", "report_delivery_issue", "settle_delivery_issue"):
        registry.TOOLS.pop(name, None)
    importlib.reload(order_jev)
    from app.tools import after_sales, order_place

    importlib.reload(order_place)
    importlib.reload(after_sales)
    import app.clients as clients

    monkeypatch.setattr(clients, "get_jev_client", lambda: None)
    yield registry.TOOLS
    registry.TOOLS.clear()
    registry.TOOLS.update(saved)
    order_review._products = None


def test_the_model_can_read_the_tools(sav):
    for name in ("report_delivery_issue", "settle_delivery_issue"):
        assert sav[name].info.parameters["properties"]  # the schema builds (no lazy annotations)


async def test_this_morning_is_checked_never_invented(sav):
    erp = SavErp()
    r = await sav["report_delivery_issue"].fn(ToolContext(erp=erp, actor="voice_agent"), "cli_0001", "tradi", "manquant",
                                              2, "sacs", "ce matin", "il manquait deux sacs", None)
    assert r["logged"] is False and "samedi 21 novembre" in r["next"] and not erp.events


async def test_complaint_recorded_with_the_order_and_the_amount(sav):
    erp = SavErp()
    r = await sav["report_delivery_issue"].fn(ToolContext(erp=erp, actor="voice_agent"), "cli_0001", "tradi", "manquant",
                                              2, "sacs", "samedi", "il manquait deux sacs", None)
    assert r["logged"] and r["orderId"] == "ord_9" and r["qty"] == 2 and r["amountHt"] == 37.78
    assert r["options"] == ["relivraison", "avoir"] and r["redeliverySay"] == "jeudi 26 novembre"
    ev = erp.events[r["eventId"]]
    assert ev["type"] == "delivery_issue" and ev["orderId"] == "ord_9" and ev["productIds"] == ["prd_0001"] and ev["amount"] == 37.78


async def test_above_150_euros_the_management_decides(sav):
    erp = SavErp()
    r = await sav["report_delivery_issue"].fn(ToolContext(erp=erp, actor="voice_agent"), "cli_0001", "tradi", "abime",
                                              None, None, "samedi", None, None)  # the whole line: 21 × 18.89
    assert r["logged"] and r["amountHt"] == 396.69 and r["options"] == [] and "direction" in r["next"]
    assert erp.events[r["eventId"]]["type"] == "quality_issue" and erp.events[r["eventId"]]["severity"] == "high"
    s = await sav["settle_delivery_issue"].fn(ToolContext(erp=erp, actor="voice_agent"), "cli_0001", "avoir", r["eventId"],
                                              "prd_0001", 21, 396.69, None)
    assert s["done"] is False


async def test_free_redelivery_goes_into_the_order_of_the_call_and_stays_apart(sav):
    erp = SavErp()
    ctx = ToolContext(erp=erp, actor="voice_agent")
    from app.tools.order_place import PlaceLine

    placed = await sav["place_order"].fn(ctx, "cli_0001", [PlaceLine(said="tradi", qty=10)], "jeudi", None)
    r = await sav["report_delivery_issue"].fn(ctx, "cli_0001", "tradi", "manquant", 2, "sacs", "samedi", None, None)
    s = await sav["settle_delivery_issue"].fn(ctx, "cli_0001", "relivraison", r["eventId"], "prd_0001", 2, 37.78, placed["orderId"])
    lines = erp.orders[placed["orderId"]]["lines"]
    assert s["done"] and len(erp.orders) == 2  # the delivered one + this call's order, no extra order
    assert sorted((li["qty"], li.get("unitPrice")) for li in lines) == [(2, 0), (10, None)]
    assert "offerts (réclamation)" in s["readback"] and "Relivraison gratuite" in erp.events[r["eventId"]]["resolution"]
    # the caller then changes the paid line: the free one is untouched
    await sav["place_order"].fn(ctx, "cli_0001", [PlaceLine(said="tradi", qty=12)], None, placed["orderId"])
    assert sorted((li["qty"], li.get("unitPrice")) for li in erp.orders[placed["orderId"]]["lines"]) == [(2, 0), (12, None)]


async def test_credit_note_written_on_the_complaint(sav):
    erp = SavErp()
    ctx = ToolContext(erp=erp, actor="voice_agent")
    r = await sav["report_delivery_issue"].fn(ctx, "cli_0001", "tradi", "manquant", 2, "sacs", None, None, None)
    s = await sav["settle_delivery_issue"].fn(ctx, "cli_0001", "avoir", r["eventId"], "prd_0001", 2, 37.78, None)
    assert s["done"] and "37 euros 78" in s["say"] and "Avoir de 37.78" in erp.events[r["eventId"]]["resolution"]
    assert len(erp.orders) == 1  # no order written for a credit note


async def test_confirming_an_order_already_confirmed_is_a_success(sav):
    """24/11 at the mic: lines added to a confirmed order, then « Oui. » → confirm_order failed and retried for 12.5 s."""
    erp = SavErp()
    erp.orders["ord_9"]["status"] = "confirmed"
    r = await sav["confirm_order"].fn(ToolContext(erp=erp, actor="voice_agent"), "ord_9", "Oui.", "Je vous la valide ?")
    assert r["confirmed"] is True and r["alreadyConfirmed"] is True and not any(m == "POST" for m, _ in erp.calls)
