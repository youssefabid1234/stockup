"""place_order: a whole order step in one tool call (day, products, units, write, read-back), never writing when unclear."""

import importlib

import pytest

from app.tools import registry
from app.tools.registry import ToolContext

CATALOGUE = [
    {"id": "prd_0001", "name": "Traditional T55 wheat flour (25 kg sack)", "aliases": ["tradi"], "unit": "piece", "caliber": "25 kg sack", "active": True},
    {"id": "prd_0006", "name": "Rye flour T130 (25 kg sack)", "aliases": ["seigle"], "unit": "piece", "caliber": "25 kg sack", "active": True},
    {"id": "prd_0026", "name": "Touring butter 82 % (plate 2 kg)", "aliases": ["tourage standard", "laminating butter"], "unit": "kg", "caliber": "carton 5 plates of 2 kg", "active": True},
    {"id": "prd_0025", "name": "Butter AOP 84 % (plate 2 kg)", "aliases": ["laminating butter AOP", "laminating butter"], "unit": "kg", "caliber": "carton 5 plates of 2 kg", "active": True},
]


class FakeErp:
    def __init__(self, status="active"):
        self.client = {"id": "cli_0001", "name": "Maison Sarrailh", "status": status, "deliveryDays": ["tue", "thu", "sat"],
                       "zone": "Toulouse center & suburbs"}
        self.orders: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []

    def _detail(self, oid):
        o = self.orders[oid]
        names = {p["id"]: p for p in CATALOGUE}
        lines = [{**li, "productName": names[li["productId"]]["name"], "unit": names[li["productId"]]["unit"], "available": 999}
                 for li in o["lines"]]
        return {**o, "lines": lines, "warnings": [], "totalHt": 189.0}

    async def get(self, path, query=None):
        self.calls.append(("GET", path))
        if path == "/api/meta":
            return {"today": "2026-11-24", "generatedAt": "2026-11-24T05:30:00.000Z"}
        if path == "/api/products":
            return CATALOGUE
        if path.endswith("/usual"):
            return []
        if path == "/api/search":  # « tourage » alone: both tourages (ambiguous on purpose)
            q = (query or {}).get("q", "")
            return [{"type": "product", "id": p["id"], "label": p["name"]} for p in CATALOGUE if q.split()[-1] in p["name"].lower()]
        if path == "/api/clients/cli_0001":
            return self.client
        if path == "/api/orders":
            return [{"id": k, "status": v["status"], "source": "voice_agent", "deliveryDate": v["deliveryDate"]} for k, v in self.orders.items()]
        if path.startswith("/api/orders/"):
            return self._detail(path.split("/")[3])
        raise AssertionError(f"unexpected GET {path}")

    async def post(self, path, body=None):
        self.calls.append(("POST", path))
        if path == "/api/orders":
            oid = f"ord_{len(self.orders) + 1}"
            lines = [{"id": f"lin_{i}", **li} for i, li in enumerate(body["lines"])]
            self.orders[oid] = {"id": oid, "number": "CMD-1", "clientId": body["clientId"], "status": "draft",
                                "deliveryDate": body["deliveryDate"], "source": body["source"], "lines": lines}
            return self._detail(oid)
        oid = path.split("/")[3]
        self.orders[oid]["lines"].append({"id": f"lin_{len(self.orders[oid]['lines']) + 10}", **body})
        return self._detail(oid)

    async def patch(self, path, body=None):
        self.calls.append(("PATCH", path))
        parts = path.split("/")
        o = self.orders[parts[3]]
        if "lines" in parts:
            next(li for li in o["lines"] if li["id"] == parts[5]).update(body)
        else:
            o.update(body)
        return self._detail(parts[3])

    async def delete(self, path, query=None):
        self.calls.append(("DELETE", path))
        parts = path.split("/")
        o = self.orders[parts[3]]
        o["lines"] = [li for li in o["lines"] if li["id"] != parts[5]]
        return self._detail(parts[3])


@pytest.fixture
def place(monkeypatch):
    """The tool's function, without leaving the order tools registered for the other tests."""
    saved = dict(registry.TOOLS)
    from app.tools import order_jev, order_review

    order_review._products = None  # catalogue cache
    for name in ("resolve_product", "place_order"):
        registry.TOOLS.pop(name, None)
    importlib.reload(order_jev)
    from app.tools import order_place

    registry.TOOLS.pop("place_order", None)
    importlib.reload(order_place)
    fn = registry.TOOLS["place_order"].fn
    import app.clients as clients

    monkeypatch.setattr(clients, "get_jev_client", lambda: None)  # deterministic: aliases only
    yield fn
    registry.TOOLS.clear()
    registry.TOOLS.update(saved)
    order_review._products = None


def line(**kw):
    from app.tools.order_place import PlaceLine

    return PlaceLine(**kw)


def test_the_model_can_read_the_tool(place):
    info = registry.TOOLS["place_order"].info  # what the LLM receives: must build (it failed with lazy annotations)
    props = info.parameters["properties"]
    assert {"clientId", "lines", "deliveryDay", "orderId"} <= set(props)
    assert {"said", "productId", "qty", "saidUnit"} <= set(props["lines"]["items"]["properties"])


async def test_new_order_in_one_call(place):
    erp = FakeErp()
    r = await place(ToolContext(erp=erp, actor="voice_agent"), "cli_0001", [line(said="tradi", qty=10)], "jeudi", None)
    assert r["written"] and r["daySay"] == "Thursday 26 November"
    assert r["readback"].startswith("10 sacks of Traditional T55 wheat flour")
    o = next(iter(erp.orders.values()))
    assert o["deliveryDate"] == "2026-11-26" and o["lines"][0]["qty"] == 10 and o["source"] == "voice_agent"


async def test_change_of_mind_edits_the_order_in_progress(place):
    erp = FakeErp()
    ctx = ToolContext(erp=erp, actor="voice_agent")
    first = await place(ctx, "cli_0001", [line(said="tradi", qty=10), line(said="seigle", qty=3)], "jeudi", None)
    oid = first["orderId"]
    r = await place(ctx, "cli_0001", [line(product_id="prd_0001", qty=12), line(said="seigle", qty=0)], None, oid)
    assert r["written"] and len(erp.orders) == 1  # never a second order
    assert [(li["productId"], li["qty"]) for li in erp.orders[oid]["lines"]] == [("prd_0001", 12)]
    await place(ctx, "cli_0001", [], "samedi", oid)
    assert erp.orders[oid]["deliveryDate"] == "2026-11-28"


async def test_impossible_day_writes_nothing(place):
    erp = FakeErp()
    r = await place(ToolContext(erp=erp, actor="voice_agent"), "cli_0001", [line(said="tradi", qty=10)], "mercredi", None)
    assert not r["written"] and "Thursday 26 November" in r["next"] and erp.orders == {}


async def test_ambiguous_product_asks_instead_of_guessing(place):
    erp = FakeErp()
    r = await place(ToolContext(erp=erp, actor="voice_agent"), "cli_0001", [line(said="laminating butter", qty=40, said_unit="kilos")], "jeudi", None)
    assert not r["written"] and r["next"] and erp.orders == {}


async def test_units_are_converted_and_odd_sacks_are_asked(place):
    erp = FakeErp()
    ctx = ToolContext(erp=erp, actor="voice_agent")
    r = await place(ctx, "cli_0001", [line(said="tourage standard", qty=3, said_unit="cartons")], "jeudi", None)
    assert r["written"] and next(iter(erp.orders.values()))["lines"][0]["qty"] == 30  # 3 cartons of 5 × 2 kg
    erp2 = FakeErp()
    r = await place(ToolContext(erp=erp2, actor="voice_agent"), "cli_0001", [line(said="tradi", qty=40, said_unit="kilos")], "jeudi", None)
    assert not r["written"] and "sac" in r["next"] and erp2.orders == {}  # 1.6 sacks: asked, never rounded


async def test_blocked_client_gets_no_order(place):
    erp = FakeErp(status="blocked")
    r = await place(ToolContext(erp=erp, actor="voice_agent"), "cli_0001", [line(said="tradi", qty=5)], "jeudi", None)
    assert r["blocked"] and not r["written"] and erp.orders == {}
