"""Parity check: the Python backend must answer exactly like the TypeScript API it replaces.

Usage (both APIs running, both get RESET):
    uv run python tests/parity.py [--ts http://localhost:4000] [--py http://localhost:4010] [-v]

1. Reads: resets both, then GETs every route of the contract with representative params and diffs
   the JSON.
2. Writes: runs the same business flow on both (orders, purchasing, payments, history, tags,
   pricing, routing, context, error cases) and diffs every response, then the resulting state.

Normalised before comparing: random line ids (lin_…, pol_…) and write-time timestamps.
Deliberate difference: context entries use `entityType` here vs `scope` in the TS API (renamed).
Exit code 1 if anything differs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# ───────── HTTP ─────────


def call(base: str, method: str, path: str, body: Any = None, actor: str | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        req.add_header("content-type", "application/json")
    if actor:
        req.add_header("x-actor", actor)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw.decode(errors="replace")


# ───────── Normalisation & diff ─────────

LINE_ID = re.compile(r"^(lin|pol)_[0-9a-f]{8}$")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def normalize(x: Any, write_time: str | None = None) -> Any:
    """Mask values that legitimately differ between two runs (random line ids, write timestamps)."""
    if isinstance(x, dict):
        return {k: normalize(v, write_time) for k, v in x.items()}
    if isinstance(x, list):
        return [normalize(v, write_time) for v in x]
    if isinstance(x, str):
        if LINE_ID.match(x):
            return f"{x[:3]}_<random>"
        if write_time and TIMESTAMP.match(x) and x.startswith(write_time):
            return "<write-time>"
    return x


def ts_context(x: Any) -> Any:
    """TS context entries say `scope`; the Python backend says `entityType` (deliberate rename)."""
    if isinstance(x, list):
        return [ts_context(v) for v in x]
    if isinstance(x, dict):
        is_context = ("kind" in x and "body" in x) or "entries" in x
        return {("entityType" if k == "scope" and is_context else k): ts_context(v) for k, v in x.items()}
    return x


def diff(a: Any, b: Any, path: str = "") -> list[str]:
    """Differences between two JSON values (ints and floats compare by value)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}/{k}: missing in TS, py={short(b[k])}")
            elif k not in b:
                out.append(f"{path}/{k}: missing in py, ts={short(a[k])}")
            else:
                out += diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length ts={len(a)} py={len(b)}"] + diff(a[: min(len(a), len(b))], b[: min(len(a), len(b))], path)
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]")
        return out
    if isinstance(a, bool) or isinstance(b, bool):
        return [] if a is b else [f"{path}: ts={short(a)} py={short(b)}"]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return [] if a == b else [f"{path}: ts={a} py={b}"]
    return [] if a == b else [f"{path}: ts={short(a)} py={short(b)}"]


def short(v: Any) -> str:
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) < 140 else s[:137] + "..."


class Report:
    def __init__(self, verbose: bool):
        self.verbose = verbose
        self.checked = 0
        self.failed: list[tuple[str, list[str]]] = []

    def compare(self, label: str, ts: tuple[int, Any], py: tuple[int, Any], write_time: str | None = None,
                context: bool = False) -> Any:  # fmt: skip
        self.checked += 1
        (ts_status, ts_body), (py_status, py_body) = ts, py
        if context:
            ts_body = ts_context(ts_body)
        problems = [] if ts_status == py_status else [f"status ts={ts_status} py={py_status}"]
        problems += diff(normalize(ts_body, write_time), normalize(py_body, write_time))
        if problems:
            self.failed.append((label, problems))
            print(f"  DIFF {label}  ({len(problems)})")
            for p in problems[: 8 if not self.verbose else 50]:
                print(f"       {p}")
        elif self.verbose:
            print(f"  ok   {label}")
        return ts_body


# ───────── 1. Reads ─────────


def q(path: str, **params: Any) -> str:
    params = {k: v for k, v in params.items() if v is not None}
    return f"{path}?{urllib.parse.urlencode(params)}" if params else path


def read_routes(ts: str) -> list[tuple[str, str] | str]:
    """Every GET of the contract, with representative params (ids discovered from the TS API).
    An entry is a path, or (ts_path, py_path) when the query differs (context: scope → entityType)."""
    get = lambda p: call(ts, "GET", p)[1]  # noqa: E731
    clients = get("/api/clients")
    products = get("/api/products")
    suppliers = get("/api/suppliers")
    orders = get("/api/orders")
    pos = get("/api/purchase-orders")
    invoices = get("/api/invoices")
    payments = get("/api/payments")
    runs = get("/api/route-runs")
    tags = get("/api/tags")
    rules = get("/api/price-rules")
    contexts = get("/api/context")
    meta = get("/api/meta")
    today = meta["today"]

    def every(xs: list, n: int) -> list:
        step = max(1, len(xs) // n)
        return xs[::step][:n]

    blocked = next((c["id"] for c in clients if c["status"] == "blocked"), clients[0]["id"])
    client_tags = sorted({t for c in clients for t in c.get("tags", [])})
    product_tags = sorted({t for p in products for t in p.get("tags", [])})
    zones = sorted({c["zone"] for c in clients})
    reps = sorted({c["salesRep"] for c in clients})
    phones = [ct["phone"] for c in clients[:5] for ct in c["contacts"] if ct.get("phone")]
    statuses = sorted({o["status"] for o in orders})

    routes: list[tuple[str, str] | str] = [
        "/api/health", "/api/meta", "/api/dashboard", "/api/routes", "/api/suppliers", "/api/stock", "/api/events",
        "/api/clients", "/api/products", "/api/orders", "/api/purchase-orders", "/api/invoices", "/api/payments",
        "/api/receivables", "/api/tags", "/api/price-rules", "/api/route-runs", "/api/client-events", "/api/supplier-events",
    ]  # fmt: skip
    # Filters
    routes += [q("/api/clients", q=x) for x in ["bistrot", "lemoine", "C0012", "paris", "marc"]]
    routes += [q("/api/clients", type=t) for t in ["restaurant", "fishmonger", "canteen"]]
    routes += [q("/api/clients", zone=z) for z in zones] + [q("/api/clients", status=s) for s in ["active", "blocked", "prospect"]]
    routes += [q("/api/clients", tag=t) for t in client_tags[:5]]
    routes += [q("/api/products", q=x) for x in ["bar", "saint", "loup", "BAR-LIG", "ecosse", "citron"]]
    routes += [q("/api/products", category=c) for c in ["whole_fish", "shellfish", "crustacean", "produce", "dry"]]
    routes += [q("/api/products", tag=t) for t in product_tags[:5]]
    routes += [q("/api/suppliers", tag=t["id"]) for t in tags if t["scope"] == "supplier"][:4]
    routes += [q("/api/orders", status=s) for s in statuses] + [q("/api/orders", status="confirmed,prepared")]
    routes += [q("/api/orders", clientId=c["id"]) for c in every(clients, 6)]
    routes += [q("/api/orders", date=d) for d in [today, orders[0]["deliveryDate"], orders[-1]["deliveryDate"]]]
    routes += [q("/api/orders", q=x) for x in ["CMD-2026-0001", "bistrot", "lemoine"]] + [q("/api/orders", limit=n) for n in [1, 25, "abc"]]
    routes += [q("/api/purchase-orders", status=s) for s in ["draft", "sent", "partially_received", "received", "cancelled", "sent,draft"]]
    routes += [q("/api/purchase-orders", supplierId=s["id"]) for s in suppliers[:4]]
    routes += [q("/api/invoices", status=s) for s in ["issued", "paid", "overdue", "partially_paid", "open", "cancelled"]]
    routes += [q("/api/invoices", clientId=c["id"]) for c in every(clients, 5)]
    routes += [q("/api/payments", clientId=c["id"]) for c in every(clients, 5)]
    routes += [q("/api/receivables", onlyOverdue="true"), q("/api/receivables", onlyOverdue="1"), q("/api/receivables", q="bistrot")]
    routes += [q("/api/receivables", tag=t) for t in client_tags[:4]] + [q("/api/receivables", zone=z) for z in zones[:3]]
    routes += [q("/api/receivables", rep=r) for r in reps[:3]]
    routes += [q("/api/stock/movements", productId=p["id"], limit=20) for p in every(products, 6)] + ["/api/stock/movements", q("/api/stock/movements", limit=5)]
    routes += [q("/api/events", limit=5)]
    routes += [q("/api/route-runs", date=r["date"]) for r in every(runs, 6)] + [q("/api/route-runs", date=today)]
    routes += [q("/api/tags", scope=s) for s in ["client", "supplier", "product"]]
    routes += [q("/api/price-rules", active=a) for a in ["true", "false", ""]]
    routes += [q("/api/price-rules", clientId=c["id"]) for c in every(clients, 5)]
    routes += [q("/api/price-rules", productId=p["id"]) for p in every(products, 5)]
    # Client events / supplier events
    routes += [q("/api/client-events", type=t) for t in ["complaint", "dispute,late_payment", "call"]]
    routes += [q("/api/client-events", status=s) for s in ["open", "resolved"]]
    routes += [q("/api/client-events", clientId=c["id"]) for c in every(clients, 4)]
    routes += [q("/api/client-events", q=x) for x in ["langoustine", "retard livraison", "avoir"]]
    routes += [q("/api/client-events", **{"from": "2026-01-01", "to": "2026-06-30"}), q("/api/client-events", **{"from": "bad"})]
    routes += [q("/api/supplier-events", type=t) for t in ["shortage", "quality_issue,price_change"]]
    routes += [q("/api/supplier-events", status="open"), q("/api/supplier-events", supplierId=suppliers[0]["id"], q="prix")]
    # Search
    searches = [
        "bar", "lemoine", "bonjour c'est Lemoine", "loup", "saint jacques", "st jacques", "dorade", "daurade", "dorad",
        "bistrot du port", "poissonerie", "C0012", "c12", "CMD-2026-000123", "123", "000123", "le loup pour le bistrot",
        "je voudrais 4 kg de bar", "huitres", "crevettes", "saumon ecosse", "", "   ", "zzzzzz", "rungis", "marée",
    ] + phones[:3]
    routes += [q("/api/search", q=s) for s in searches]
    routes += [q("/api/search", q="bar", types="product"), q("/api/search", q="lemoine", types="client,supplier"), q("/api/search", q="bar", limit=3)]
    routes += [q("/api/search", q=s, types="context") for s in ["substitution", "credit", "livraison", "lemoine"]]
    # Details (every client / supplier / product, a sample of the rest)
    for c in clients:
        routes += [f"/api/clients/{c['id']}", f"/api/clients/{c['id']}/usual", f"/api/clients/{c['id']}/events"]
    routes += [q(f"/api/clients/{blocked}/events", type="complaint", limit=3), q(f"/api/clients/{blocked}/events", status="open")]
    for s in suppliers:
        routes += [f"/api/suppliers/{s['id']}", f"/api/suppliers/{s['id']}/usual", f"/api/suppliers/{s['id']}/events"]
    for p in products:
        routes += [f"/api/products/{p['id']}", f"/api/products/{p['id']}/alternatives"]
    routes += [f"/api/orders/{o['id']}" for o in every(orders, 120)]
    routes += [f"/api/orders/{o['id']}" for o in orders if o["status"] in ("draft", "confirmed", "prepared")]
    routes += [f"/api/purchase-orders/{p['id']}" for p in every(pos, 60)]
    routes += [f"/api/purchase-orders/{p['id']}" for p in pos if p["status"] in ("draft", "sent", "partially_received")]
    routes += [f"/api/invoices/{i['id']}" for i in every(invoices, 80)]
    _ = payments
    # Pricing
    for c in every(clients, 12):
        routes += [q("/api/prices/grid", clientId=c["id"])]
        for p in every(products, 8):
            routes += [q("/api/prices/resolve", clientId=c["id"], productId=p["id"])]
    for r in rules:
        cs, ps = r["clientScope"], r["productScope"]
        cid = cs.get("clientId") or next((c["id"] for c in clients if cs.get("tag") in c.get("tags", [])), clients[0]["id"])
        pid = ps.get("productId") or next(
            (p["id"] for p in products if ps.get("tag") in p.get("tags", []) or ps.get("category") == p["category"]), products[0]["id"]
        )
        routes += [q("/api/prices/resolve", clientId=cid, productId=pid, qty=qty) for qty in [1, 10, 50]]
        routes += [q("/api/prices/resolve", clientId=cid, productId=pid, date=d) for d in ["2026-01-15", "2026-12-24"]]
    routes += [q("/api/prices/grid", clientTag=t) for t in client_tags]
    routes += [q("/api/prices/grid", clientId=clients[0]["id"], productTag=product_tags[0] if product_tags else None, q="bar")]
    routes += [q("/api/prices/grid", clientId=clients[1]["id"], category="shellfish")]
    # Errors
    routes += [
        "/api/clients/cli_9999", "/api/orders/nope", "/api/nope", q("/api/prices/resolve", clientId=clients[0]["id"]),
        q("/api/prices/resolve", clientId=clients[0]["id"], productId=products[0]["id"], qty="abc"),
        q("/api/prices/resolve", clientId=clients[0]["id"], productId=products[0]["id"], date="24/11"),
        "/api/prices/grid", "/api/invoices/inv_x", "/api/products/x/alternatives", "/api/suppliers/x/usual",
        q("/api/price-rules", clientId="cli_9999"),
    ]  # fmt: skip
    # Context (scope → entityType)
    ctx_routes: list[tuple[str, str]] = [("/api/context", "/api/context")]
    for ts_key, py_key in [("scope", "entityType")]:
        for v in ["company", "client", "supplier,product", "category"]:
            ctx_routes.append((q("/api/context", **{ts_key: v}), q("/api/context", **{py_key: v})))
    ctx_routes += [(q("/api/context", q=x), q("/api/context", q=x)) for x in ["substitution", "crédit", "livraison le matin", "lemoine", "zzz"]]
    ctx_routes += [(q("/api/context", kind=k), q("/api/context", kind=k)) for k in ["policy", "risk,pricing"]]
    ctx_routes += [(q("/api/context", source="seed", limit=5), q("/api/context", source="seed", limit=5))]
    ctx_routes += [(q("/api/context", entityId=c["id"]), q("/api/context", entityId=c["id"])) for c in clients[:3]]
    tag0 = next((t for e in contexts for t in e.get("tags", [])), "x")
    ctx_routes += [(q("/api/context", tag=tag0), q("/api/context", tag=tag0))]
    ctx_routes += [(f"/api/context/{e['id']}", f"/api/context/{e['id']}") for e in every(contexts, 15)]
    targets = [("company", "")] + [("client", c["id"]) for c in every(clients, 6)] + [("supplier", s["id"]) for s in suppliers[:4]]
    targets += [("product", p["id"]) for p in every(products, 5)] + [("category", "crustacean"), ("category", "produce")]
    ctx_routes += [(q("/api/context/for", scope=s, id=i), q("/api/context/for", entityType=s, id=i)) for s, i in targets]
    return routes + ctx_routes


def check_reads(rep: Report, ts: str, py: str, label: str) -> None:
    routes = read_routes(ts)
    print(f"[reads/{label}] {len(routes)} GETs")
    for r in routes:
        if isinstance(r, tuple):
            rep.compare(f"GET {r[1]}", call(ts, "GET", r[0]), call(py, "GET", r[1]), context=True)
        else:
            rep.compare(f"GET {r}", call(ts, "GET", r), call(py, "GET", r))


# ───────── 2. Writes ─────────


def write_flow(rep: Report, ts: str, py: str) -> None:
    """Same business flow on both APIs, step by step; every response compared."""
    today = call(ts, "GET", "/api/meta")[1]["today"]
    clients = call(ts, "GET", "/api/clients")[1]
    products = call(ts, "GET", "/api/products")[1]
    suppliers = call(ts, "GET", "/api/suppliers")[1]
    active = [c for c in clients if c["status"] == "active"]
    client = active[0]
    blocked = next((c for c in clients if c["status"] == "blocked"), clients[-1])
    in_stock = [p for p in products if p["available"] > 5 and p["active"]]
    fish, shell, other = in_stock[0], in_stock[1], in_stock[2]
    scarce = min((p for p in products if p["active"]), key=lambda p: p["available"])
    steps = 0

    def both(method: str, ts_path: str, body: Any = None, actor: str | None = "voice_agent", py_path: str | None = None,
             py_body: Any = None, context: bool = False, by_id: bool = False) -> Any:  # fmt: skip
        nonlocal steps
        steps += 1
        a = call(ts, method, ts_path, body, actor)
        b = call(py, method, py_path or ts_path, py_body if py_body is not None else body, actor)
        if by_id:  # rows written in the same millisecond have no defined order: compare as sets
            a, b = (a[0], sorted(a[1], key=lambda x: x["id"])), (b[0], sorted(b[1], key=lambda x: x["id"]))
        return rep.compare(f"{method} {py_path or ts_path}", a, b, write_time=today, context=context)

    print("[writes] orders")
    order = both("POST", "/api/orders", {"clientId": client["id"], "lines": [{"productId": fish["id"], "qty": 3.5}, {"productId": shell["id"], "qty": 2, "note": "bien frais"}]})
    oid = order["id"]
    line_ids = [l["id"] for l in order["lines"]]  # random: differ per API → fetch each side's own ids
    order_py = call(py, "GET", f"/api/orders/{oid}")[1]
    py_line_ids = [l["id"] for l in order_py["lines"]]
    both("POST", f"/api/orders/{oid}/lines", {"productId": other["id"], "qty": 1})
    order_ts, order_py = call(ts, "GET", f"/api/orders/{oid}")[1], call(py, "GET", f"/api/orders/{oid}")[1]
    added_ts, added_py = order_ts["lines"][-1]["id"], order_py["lines"][-1]["id"]
    both("PATCH", f"/api/orders/{oid}/lines/{line_ids[0]}", {"qty": 4}, py_path=f"/api/orders/{oid}/lines/{py_line_ids[0]}")
    both("PATCH", f"/api/orders/{oid}/lines/{line_ids[1]}", {"productId": scarce["id"]}, py_path=f"/api/orders/{oid}/lines/{py_line_ids[1]}")
    both("DELETE", f"/api/orders/{oid}/lines/{added_ts}", py_path=f"/api/orders/{oid}/lines/{added_py}")
    both("PATCH", f"/api/orders/{oid}", {"note": "Livrer avant 7h"})
    both("PATCH", f"/api/orders/{oid}/lines/nope", {"qty": 1})
    both("POST", f"/api/orders/{oid}/confirm")
    both("POST", f"/api/orders/{oid}/confirm")  # 409
    both("PATCH", f"/api/orders/{oid}", {"deliveryDate": order["deliveryDate"]})
    both("POST", f"/api/orders/{oid}/prepare", {"lines": [{"lineId": line_ids[0], "preparedQty": 3.85}]}, py_body={"lines": [{"lineId": py_line_ids[0], "preparedQty": 3.85}]})
    both("POST", f"/api/orders/{oid}/invoice")  # 409: not delivered
    both("POST", f"/api/orders/{oid}/deliver")
    inv = both("POST", f"/api/orders/{oid}/invoice")
    both("POST", "/api/payments", {"clientId": client["id"], "amount": 50, "method": "transfer", "reference": "VIR-1"})
    both("POST", "/api/payments", {"clientId": client["id"], "amount": 10, "method": "card", "allocations": [{"invoiceId": inv["id"], "amount": 10}]})
    both("POST", "/api/payments", {"clientId": client["id"], "amount": 5, "method": "card", "allocations": [{"invoiceId": inv["id"], "amount": 9}]})  # 400
    both("POST", "/api/payments", {"clientId": client["id"], "amount": -5, "method": "card"})  # 400
    both("GET", f"/api/invoices/{inv['id']}")
    # Second order: blocked client, then cancel
    o2 = both("POST", "/api/orders", {"clientId": blocked["id"], "deliveryDate": today, "source": "phone", "lines": [{"productId": scarce["id"], "qty": 999}]}, actor="user")
    both("POST", f"/api/orders/{o2['id']}/confirm", actor="user")
    both("POST", f"/api/orders/{o2['id']}/cancel")
    both("POST", f"/api/orders/{o2['id']}/cancel")  # 409
    o3 = both("POST", "/api/orders", {"clientId": active[1]["id"], "lines": [{"productId": fish["id"], "qty": 2, "unitPrice": 0.5}]}, actor="ai_chat")
    both("POST", f"/api/orders/{o3['id']}/confirm")
    both("POST", "/api/orders", {"clientId": "cli_9999"})  # 404
    both("POST", "/api/orders", {"clientId": client["id"], "lines": [{"productId": fish["id"], "qty": 0}]})  # 400
    both("POST", "/api/orders", {"lines": "x"})  # 400

    print("[writes] purchasing & stock")
    sup = suppliers[0]
    sup_prices = call(ts, "GET", f"/api/suppliers/{sup['id']}")[1]["prices"]
    p1, p2 = sup_prices[0]["productId"], sup_prices[1]["productId"]
    po = both("POST", "/api/purchase-orders", {"supplierId": sup["id"], "lines": [{"productId": p1, "qty": 10}]})
    pid = po["id"]
    both("POST", f"/api/purchase-orders/{pid}/lines", {"productId": p2, "qty": 5, "unitPrice": sup_prices[1]["price"] * 1.5})
    both("POST", f"/api/purchase-orders/{pid}/lines", {"productId": fish["id"] if fish["id"] not in (p1, p2) else other["id"], "qty": 1})
    po_ts, po_py = call(ts, "GET", f"/api/purchase-orders/{pid}")[1], call(py, "GET", f"/api/purchase-orders/{pid}")[1]
    lt, lp = [l["id"] for l in po_ts["lines"]], [l["id"] for l in po_py["lines"]]
    both("PATCH", f"/api/purchase-orders/{pid}/lines/{lt[0]}", {"qty": 12}, py_path=f"/api/purchase-orders/{pid}/lines/{lp[0]}")
    both("DELETE", f"/api/purchase-orders/{pid}/lines/{lt[2]}", py_path=f"/api/purchase-orders/{pid}/lines/{lp[2]}")
    both("PATCH", f"/api/purchase-orders/{pid}", {"note": "Appeler avant", "expectedDate": today})
    both("POST", f"/api/purchase-orders/{pid}/receive")  # 409 draft
    both("POST", f"/api/purchase-orders/{pid}/send")
    both("POST", f"/api/purchase-orders/{pid}/receive", {"lines": [{"lineId": lt[0], "receivedQty": 4}]}, py_body={"lines": [{"lineId": lp[0], "receivedQty": 4}]})
    both("POST", f"/api/purchase-orders/{pid}/receive")
    both("GET", f"/api/products/{p1}")
    empty = both("POST", "/api/purchase-orders", {"supplierId": sup["id"], "lines": []})
    both("POST", f"/api/purchase-orders/{empty['id']}/send")  # 409 empty
    both("POST", f"/api/purchase-orders/{empty['id']}/cancel")
    both("POST", "/api/stock/adjust", {"productId": fish["id"], "qty": 2, "reason": "waste", "note": "abîmé"})
    both("POST", "/api/stock/adjust", {"productId": fish["id"], "qty": 1.5, "reason": "adjustment"})
    both("POST", "/api/stock/adjust", {"productId": fish["id"], "qty": -0.5, "reason": "adjustment"})
    both("POST", "/api/stock/adjust", {"productId": fish["id"], "qty": 0, "reason": "adjustment"})  # 400

    print("[writes] history, clients, tags, pricing")
    ev = both("POST", f"/api/clients/{client['id']}/events", {"type": "complaint", "title": "Bar pas frais", "description": "Odeur", "severity": "high", "orderId": oid})
    both("PATCH", f"/api/client-events/{ev['id']}", {"status": "resolved", "resolution": "Avoir de 20 €"})
    both("PATCH", f"/api/client-events/{ev['id']}", {"status": "open"})
    both("POST", f"/api/clients/{client['id']}/events", {"type": "call", "title": "Appel", "at": "2026-11-20"}, actor="user")
    both("POST", f"/api/clients/{client['id']}/events", {"type": "note", "title": "x", "orderId": o2["id"]})  # 400 mismatch
    sev = both("POST", f"/api/suppliers/{sup['id']}/events", {"type": "shortage", "title": "Pas de bar", "purchaseOrderId": pid})
    both("PATCH", f"/api/supplier-events/{sev['id']}", {"status": "resolved"})
    both("PATCH", f"/api/supplier-events/{sev['id']}", {"title": "Pas de bar (tempête)"})
    new_client = both("POST", "/api/clients", {"name": "Le Nouveau Bistrot", "type": "restaurant", "zone": client["zone"]})
    both("PATCH", f"/api/clients/{new_client['id']}", {"status": "blocked"})
    both("PATCH", f"/api/clients/{new_client['id']}", {"preferences": "Pas de surgelé", "creditLimit": 1500})
    both("POST", f"/api/clients/{new_client['id']}/notes", {"text": "Rappeler lundi"})
    both("POST", "/api/clients", {"name": "", "type": "nope"})  # 400
    both("POST", "/api/tags", {"id": "vip", "scope": "client", "label": "VIP", "color": "amber"})
    both("POST", "/api/tags", {"id": "vip", "scope": "client", "label": "VIP"})  # 409
    both("POST", "/api/tags", {"id": "Bad Slug", "scope": "client", "label": "x"})  # 400
    both("PATCH", f"/api/clients/{client['id']}", {"tags": [*client.get("tags", []), "vip"]})
    both("PATCH", f"/api/clients/{client['id']}", {"tags": ["unknown-tag"]})  # 400
    both("PATCH", "/api/tags/client/vip", {"label": "Clients VIP"})
    rule = both("POST", "/api/price-rules", {"name": "VIP -10 % poisson", "clientScope": {"kind": "tag", "tag": "vip"}, "productScope": {"kind": "category", "category": fish["category"]}, "method": {"kind": "discount_pct", "pct": 10}, "priority": 5})
    both("GET", q("/api/prices/resolve", clientId=client["id"], productId=fish["id"]))
    both("PATCH", f"/api/price-rules/{rule['id']}", {"active": False})
    both("PATCH", f"/api/price-rules/{rule['id']}", {"active": True})
    both("PATCH", f"/api/price-rules/{rule['id']}", {"minQty": 20, "note": "volume"})
    both("GET", q("/api/prices/resolve", clientId=client["id"], productId=fish["id"], qty=25))
    both("POST", "/api/price-rules", {"name": "bad", "clientScope": {"kind": "all"}, "productScope": {"kind": "all"}, "method": {"kind": "discount_pct", "pct": 150}})  # 400
    both("PUT", f"/api/clients/{client['id']}/prices/{fish['id']}", {"price": 12.345})
    both("GET", q("/api/prices/resolve", clientId=client["id"], productId=fish["id"]))
    both("DELETE", f"/api/clients/{client['id']}/prices/{fish['id']}")
    both("DELETE", f"/api/clients/{client['id']}/prices/{fish['id']}")  # 404
    both("DELETE", f"/api/price-rules/{rule['id']}")
    both("PATCH", f"/api/products/{fish['id']}", {"price": fish["price"] + 1})
    both("PATCH", f"/api/products/{other['id']}", {"tags": [], "aliases": ["test"]})
    both("PATCH", f"/api/suppliers/{sup['id']}", {"leadTimeDays": 2, "notes": "ok"})
    both("DELETE", "/api/tags/client/vip")
    both("DELETE", "/api/tags/client/vip")  # 404

    print("[writes] routing")
    tomorrow_orders = [o for o in call(ts, "GET", q("/api/orders", status="confirmed,prepared"))[1]]
    plan_date = tomorrow_orders[0]["deliveryDate"] if tomorrow_orders else today
    runs = both("POST", "/api/route-runs/plan", {"date": plan_date})
    if runs and len(runs[0]["stops"]) > 1:
        ids = [s["orderId"] for s in runs[0]["stops"]][::-1]
        both("PATCH", f"/api/route-runs/{runs[0]['id']}/stops", {"orderIds": ids[:2]})
    both("PATCH", f"/api/route-runs/{runs[0]['id'] if runs else 'x'}/stops", {"orderIds": ["nope"]})  # 400
    both("POST", "/api/route-runs/plan")

    print("[writes] context")
    c1 = both("POST", "/api/context", {"scope": "client", "entityId": client["id"], "kind": "preference", "title": "  Aime le bar  ", "body": "Toujours du bar de ligne.", "tags": ["bar", " bar ", ""]},
              py_body={"entityType": "client", "entityId": client["id"], "kind": "preference", "title": "  Aime le bar  ", "body": "Toujours du bar de ligne.", "tags": ["bar", " bar ", ""]}, context=True)
    both("PATCH", f"/api/context/{c1['id']}", {"title": "Aime le bar de ligne", "tags": []}, context=True)
    both("PATCH", f"/api/context/{c1['id']}", {"scope": "company"}, py_body={"entityType": "company"}, context=True)
    both("POST", "/api/context", {"scope": "company", "entityId": client["id"], "kind": "policy", "title": "x", "body": "y"},
         py_body={"entityType": "company", "entityId": client["id"], "kind": "policy", "title": "x", "body": "y"}, context=True)  # 400
    both("DELETE", f"/api/context/{c1['id']}", context=True)
    both("GET", f"/api/context/{c1['id']}", context=True)  # 404

    print(f"[writes] {steps} steps; comparing resulting state")
    for path in ["/api/dashboard", "/api/receivables", "/api/stock", "/api/orders", "/api/purchase-orders", "/api/invoices",
                 "/api/payments", "/api/clients", "/api/tags", "/api/price-rules", q("/api/events", limit=200),
                 "/api/client-events", "/api/supplier-events", "/api/route-runs",
                 f"/api/clients/{client['id']}", f"/api/suppliers/{sup['id']}", f"/api/orders/{oid}", f"/api/purchase-orders/{pid}"]:  # fmt: skip
        both("GET", path)
    both("GET", q("/api/stock/movements", limit=50), by_id=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ts", default="http://localhost:4000")
    ap.add_argument("--py", default="http://localhost:4010")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--reads-only", action="store_true")
    args = ap.parse_args()
    rep = Report(args.verbose)
    for base in (args.ts, args.py):
        assert call(base, "POST", "/api/admin/reset")[1] == {"ok": True}, f"reset failed on {base}"
    check_reads(rep, args.ts, args.py, "after reset")
    if not args.reads_only:
        write_flow(rep, args.ts, args.py)
        for base in (args.ts, args.py):
            call(base, "POST", "/api/admin/reset")
    print(f"\n{rep.checked} comparisons, {len(rep.failed)} with differences")
    sys.exit(1 if rep.failed else 0)


if __name__ == "__main__":
    main()
