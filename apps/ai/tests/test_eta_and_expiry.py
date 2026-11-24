"""Idée 2 (heure du camion) and idée 3 (date courte dite au client)."""

import importlib

import pytest

from app.agent.rules_order import expiry_alert, review
from app.tools import registry
from app.tools.registry import ToolContext

LEVURE = "Levure fraîche boulangère (pain de 500 g)"


def test_expiry_alert_says_the_date_and_asks():
    w = {"code": "expiring_soon", "productId": "p1", "message": f"{LEVURE} : le lot lot_014289 expire le ven. 27 nov."}
    o = {"deliveryDate": "2026-11-26", "lines": [{"productId": "p1", "productName": LEVURE}]}
    said = expiry_alert(w, o)
    assert "levure fraîche boulangère" in said and "vendredi 27 novembre" in said and "juste après la livraison" in said
    assert expiry_alert({**w, "message": "illisible"}, o) is None


def test_the_short_date_becomes_an_alert_in_the_readback_without_blocking():
    order = {"id": "o1", "deliveryDate": "2026-11-26", "totalHt": 2.7,
             "lines": [{"productId": "p1", "qty": 2, "unit": "piece", "productName": LEVURE, "available": 100}],
             "warnings": [{"code": "expiring_soon", "productId": "p1", "message": f"{LEVURE} : le lot l1 expire le ven. 27 nov."}]}
    r = review(order, {"p1": {"id": "p1", "name": LEVURE, "unit": "piece", "caliber": "pain 500 g"}}, [])
    assert any("vendredi 27 novembre" in a for a in r["alerts"]) and r["canConfirm"] is True


class EtaErp:
    def __init__(self, planned=True):
        self.planned = planned

    async def get(self, path, query=None):
        if path == "/api/meta":
            return {"today": "2026-11-24", "generatedAt": "2026-11-24T05:30:00.000Z"}
        if path.startswith("/api/clients/"):
            return {"id": "cli_0003", "deliveryDays": ["mon", "tue", "wed", "thu", "fri", "sat"]}
        if path == "/api/orders":
            return [{"id": "o_today", "status": "prepared", "deliveryDate": "2026-11-24"},
                    {"id": "o1", "status": "delivered", "deliveryDate": "2026-11-21"},
                    {"id": "o2", "status": "delivered", "deliveryDate": "2026-11-20"}]
        if path == "/api/route-runs":
            stop = {"clientId": "cli_0003", "seq": 1, "eta": "07:05", "status": "pending"}
            if query["date"] == "2026-11-24" and not self.planned:
                return []
            return [{"route": {"driver": "Yohan Ferrié", "departureTime": "06:30"},
                     "stops": [{**stop, "eta": {"2026-11-21": "07:17", "2026-11-20": "07:08"}.get(query["date"], "07:05")}]}]
        raise AssertionError(path)


@pytest.fixture
def eta():
    saved = dict(registry.TOOLS)
    registry.TOOLS.pop("delivery_eta", None)
    from app.tools import delivery_eta

    importlib.reload(delivery_eta)
    yield registry.TOOLS["delivery_eta"].fn
    registry.TOOLS.clear()
    registry.TOOLS.update(saved)


async def test_planned_round_gives_the_stop_and_the_time(eta):
    r = await eta(ToolContext(erp=EtaErp(), actor="voice_agent"), "cli_0003", None)
    assert r["planned"] and r["seq"] == 1 and "Yohan part à 6 h 30" in r["say"] and "vers 7 h 05" in r["say"]


async def test_not_planned_yet_gives_the_usual_time_without_promise(eta):
    r = await eta(ToolContext(erp=EtaErp(planned=False), actor="voice_agent"), "cli_0003", None)
    assert not r["planned"] and r["usualEta"] == "7 h 10" and "en général" in r["say"] and "fixée la veille" in r["say"]
