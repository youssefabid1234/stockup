"""Exercise the real recommendation and outbound APIs against a disposable SQLite database."""

import copy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from uuid import uuid4

from fastapi.testclient import TestClient

# The database module connects at import time. Always give this test its own database.
database = TemporaryDirectory()
with mock.patch.dict(os.environ, {"DB_PATH": str(Path(database.name) / "test.sqlite")}):
    from app import crud
    from app.core.datapack import DEV_FIXTURE, write_pack
    from app.core.db import load_all
    from app.main import app
    from app.services import outbound_calls

CLIENT = "cli_0001"
PRODUCT = "prd_0001"
OTHER = "prd_0003"
RULE = {
    "id": "prl_test", "name": "Promo vérifiable", "clientScope": {"kind": "all"},
    "productScope": {"kind": "product", "productId": PRODUCT}, "method": {"kind": "discount_pct", "pct": 10},
    "active": True, "priority": 0, "validFrom": "2026-11-23", "validTo": "2026-11-30",
    "createdAt": "2026-11-23T06:00:00.000Z",
}


class RecommendationTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        database.cleanup()

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"TEAM_RECOMMENDATIONS": "1", "TEAM_OUTBOUND_DEMO": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        fixture = json.loads(DEV_FIXTURE.read_text())
        sale = fixture["orders"][0]
        fixture["orders"] = [sale, {**copy.deepcopy(sale), "id": "ord_000099", "number": "CMD-2026-000099", "deliveryDate": "2026-11-10"}]
        fixture["clientPrices"] = []
        fixture["priceRules"] = [RULE]
        write_pack(fixture)
        self.http = TestClient(app)
        self.addCleanup(self.http.close)

    def offers(self, **filters):
        response = self.http.get("/api/recommendations", params={"clientId": CLIENT, **filters})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def start(self):
        response = self.http.post("/api/outbound-demo/attempts", json={"requestId": str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_only_applied_promotions_are_offered(self):
        offer, = self.offers()
        self.assertEqual((offer["productId"], offer["unitPrice"], offer["purchaseCount"]), (PRODUCT, 25.65, 2))
        crud.client_prices.put({"clientId": CLIENT, "productId": PRODUCT, "price": 26.90})
        self.assertEqual(self.offers(), [])
        crud.client_prices.table.remove(f"{CLIENT}|{PRODUCT}")
        crud.price_rules.put({**RULE, "validTo": "2026-11-22"})
        self.assertEqual(self.offers(), [])

    def test_launch_date_and_purchase_category(self):
        product_id = "prd_0002"
        response = self.http.patch(f"/api/products/{product_id}", json={"launchedOn": "2026-11-20"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(("new", product_id), {(o["kind"], o["productId"]) for o in self.offers()})
        self.http.patch(f"/api/products/{product_id}", json={"launchedOn": None})
        self.assertNotIn(product_id, {o["productId"] for o in self.offers()})
        self.assertEqual(self.http.patch(f"/api/products/{product_id}", json={"launchedOn": "2026-02-30"}).status_code, 400)

    def test_offer_adds_one_line_to_the_same_draft_and_retries_are_idempotent(self):
        order = self.http.post("/api/orders", json={"clientId": CLIENT, "lines": [{"productId": OTHER, "qty": 1}]}).json()
        offer, = self.offers(orderId=order["id"])
        body = {"orderId": order["id"], "quantity": 2, "offer": offer, "requestId": str(uuid4())}
        path = f"/api/recommendations/{CLIENT}/accept"
        for _ in range(2):
            reply = self.http.post(path, json=body)
            self.assertEqual(reply.status_code, 200, reply.text)
            order_after = reply.json()
            self.assertEqual(order_after["id"], order["id"])
            self.assertEqual(order_after["status"], "draft")
            self.assertEqual([(l["productId"], l["qty"]) for l in order_after["lines"]], [(OTHER, 1), (PRODUCT, 2)])
        self.assertFalse(self.offers(orderId=order["id"]))
        self.assertEqual(self.http.post(path, json={**body, "quantity": 3}).status_code, 409)

    def test_acceptance_rechecks_tariff_and_available_quantity(self):
        offer, = self.offers()
        path = f"/api/recommendations/{CLIENT}/accept"
        body = {"quantity": 200, "offer": offer, "requestId": str(uuid4())}
        self.assertEqual(self.http.post(path, json=body).status_code, 409)
        crud.price_rules.put({**RULE, "method": {"kind": "discount_pct", "pct": 5}})
        self.assertEqual(self.http.post(path, json={**body, "quantity": 1}).status_code, 409)
        self.assertEqual(self.http.get("/api/orders", params={"clientId": CLIENT, "status": "draft"}).json(), [])

    def test_refusal_suppresses_later_offers(self):
        offer, = self.offers()
        for _ in range(2):
            self.assertEqual(self.http.post(f"/api/recommendations/{CLIENT}/decline", json=offer).status_code, 200)
        self.assertFalse(self.offers())
        self.assertFalse(self.http.get("/api/outbound-demo/candidates").json())

    def test_missed_attempt_reloads_from_sqlite_and_cannot_send_twice(self):
        attempt = self.start()
        load_all()
        for _ in range(2):
            outbound_calls._expire_attempt(attempt["id"], attempt["deadline"])
        attempt_path = f"/api/outbound-demo/attempts/{attempt['id']}/answer"
        missed = self.http.post(attempt_path, json={"sessionId": "too-late"}).json()
        self.assertEqual(missed["status"], "missed")
        self.assertIn("30/11", missed["sms"])
        events = self.http.get(f"/api/clients/{CLIENT}/events").json()
        self.assertEqual(sum(e.get("channel") == "sms" for e in events), 1)

    def test_answered_attempt_does_not_send_a_message(self):
        attempt = self.start()
        attempt_path = f"/api/outbound-demo/attempts/{attempt['id']}"
        answered = self.http.post(attempt_path + "/answer", json={"sessionId": "speak"}).json()
        self.assertEqual(answered["status"], "answered")
        self.assertEqual(answered["sessionId"], "speak")
        outbound_calls._expire_attempt(attempt["id"], attempt["deadline"] + 1)
        self.http.post(attempt_path + "/complete", json={"sessionId": "speak"})
        completed, = self.http.get("/api/outbound-demo/attempts").json()
        self.assertEqual(completed["status"], "completed")
        self.assertNotIn("sms", completed)

    def test_expired_offer_does_not_send_a_message(self):
        attempt = self.start()
        crud.price_rules.put({**RULE, "active": False})
        outbound_calls._expire_attempt(attempt["id"], attempt["deadline"])
        missed, = self.http.get("/api/outbound-demo/attempts").json()
        self.assertEqual(missed["status"], "missed")
        self.assertIn("reason", missed)
        self.assertNotIn("sms", missed)

    def test_dismiss_after_a_lost_browser_session_does_not_send_a_message(self):
        attempt = self.start()
        path = f"/api/outbound-demo/attempts/{attempt['id']}"
        self.http.post(path + "/answer", json={"sessionId": "lost-browser"})
        self.assertEqual(self.http.post(path + "/dismiss").status_code, 200)
        completed, = self.http.get("/api/outbound-demo/attempts").json()
        self.assertEqual(completed["status"], "completed")
        self.assertNotIn("sms", completed)
