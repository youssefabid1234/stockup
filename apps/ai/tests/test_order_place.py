"""place_order: a whole order step in one tool call (day, products, units, write, read-back), never writing when unclear."""

import importlib

import pytest

from app.tools import registry
from app.tools.registry import ToolContext

CATALOGUE = [
    {"id": "prd_0001", "name": "Farine de blé T55 tradition française (sac 25 kg)", "aliases": ["tradi"], "unit": "piece", "caliber": "sac 25 kg", "active": True},
    {"id": "prd_0006", "name": "Farine de seigle T130 (sac 25 kg)", "aliases": ["seigle"], "unit": "piece", "caliber": "sac 25 kg", "active": True},
    {"id": "prd_0026", "name": "Beurre de tourage 82 % (plaque 2 kg)", "aliases": ["tourage standard", "tourage"], "unit": "kg", "caliber": "carton 5 plaques de 2 kg", "active": True},
    {"id": "prd_0025", "name": "Beurre de tourage AOP 84 % (plaque 2 kg)", "aliases": ["tourage AOP", "tourage"], "unit": "kg", "caliber": "carton 5 plaques de 2 kg", "active": True},
]


class FakeErp:
    def __init__(self, status="active"):
        self.client = {"id": "cli_0001", "name": "Maison Sarrailh", "status": status, "deliveryDays": ["tue", "thu", "sat"],
                       "zone": "Toulouse centre & faubourgs"}
        self.orders: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []
        self.stock = {p["id"]: 999 for p in CATALOGUE}  # available, in the product's unit

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
        if path.startswith("/api/products/") and path.endswith("/alternatives"):
            pid = path.split("/")[3]
            return [{"id": p["id"], "name": p["name"], "unit": p["unit"], "available": self.stock[p["id"]]}
                    for p in CATALOGUE if p["id"] != pid and p["unit"] == next(c["unit"] for c in CATALOGUE if c["id"] == pid)]
        if path.startswith("/api/products/"):
            p = next(c for c in CATALOGUE if c["id"] == path.split("/")[3])
            return {**p, "available": self.stock[p["id"]], "stock": {}}
        if path == "/api/prices/resolve":
            return {"price": 10.0, "listPrice": 10.0, "explanation": "catalogue"}
        if path == "/api/price-rules":
            return []
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
    assert r["written"] and r["daySay"] == "jeudi 26 novembre"
    assert r["readback"].startswith("10 sacs de Farine de blé T55 tradition française")
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
    assert not r["written"] and "jeudi 26 novembre" in r["next"] and erp.orders == {}


async def test_ambiguous_product_asks_instead_of_guessing(place):
    erp = FakeErp()
    r = await place(ToolContext(erp=erp, actor="voice_agent"), "cli_0001", [line(said="tourage", qty=40, said_unit="kilos")], "jeudi", None)
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


async def test_short_stock_writes_nothing_and_brings_the_substitute(place):
    erp = FakeErp()
    erp.stock["prd_0025"] = 4  # AOP: 4 kg left, 3 cartons = 30 kg asked
    r = await place(ToolContext(erp=erp, actor="voice_agent"), "cli_0001",
                    [line(said="tradi", qty=10), line(said="tourage AOP", qty=3, said_unit="cartons")], "jeudi", None)
    assert r["written"] is False and not erp.orders and not any(m != "GET" for m, _ in erp.calls)
    (short,) = r["short"]
    assert short["productId"] == "prd_0025" and short["wanted"] == 30 and short["available"] == 4
    assert short["alternatives"][0]["id"] == "prd_0026" and "remplaçant" in r["next"]


async def test_short_stock_taken_anyway_when_the_caller_says_so(place):
    erp = FakeErp()
    erp.stock["prd_0025"] = 4
    r = await place(ToolContext(erp=erp, actor="voice_agent"), "cli_0001", [line(said="tourage AOP", qty=3, said_unit="cartons")],
                    "jeudi", None, True)
    assert r["written"] is True and len(erp.orders) == 1


async def test_only_the_increase_of_a_line_is_checked(place):
    erp = FakeErp()
    ctx = ToolContext(erp=erp, actor="voice_agent")
    first = await place(ctx, "cli_0001", [line(said="tradi", qty=10)], "jeudi", None)
    erp.stock["prd_0001"] = 3  # 10 already in the order: 12 = +2 → fine; then 16 = +4 > 3 → short
    assert (await place(ctx, "cli_0001", [line(said="tradi", qty=12)], None, first["orderId"]))["written"] is True
    r = await place(ctx, "cli_0001", [line(said="tradi", qty=16)], None, first["orderId"])
    assert r["written"] is False and r["short"][0]["wanted"] == 4
