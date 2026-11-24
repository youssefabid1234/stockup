"""One CRUD object per stored entity. Usage: `from app import crud` then `crud.clients.require(id)`.

Keys: most tables use the document id; client/supplier prices use "clientId|productId",
tags use "scope|id".
"""

from app.core.db import JsonTable
from app.crud.base import CRUDBase, NumberedCRUD

products = CRUDBase(JsonTable("products"), "Product")
clients = CRUDBase(JsonTable("clients"), "Customer")
client_prices = CRUDBase(JsonTable("client_prices", lambda d: f"{d['clientId']}|{d['productId']}"), "Customer price")
suppliers = CRUDBase(JsonTable("suppliers"), "Supplier")
supplier_prices = CRUDBase(JsonTable("supplier_prices", lambda d: f"{d['supplierId']}|{d['productId']}"), "Supplier price")
lots = CRUDBase(JsonTable("lots"), "Lot")
stock_movements = CRUDBase(JsonTable("stock_movements"), "Movement")
orders = NumberedCRUD(JsonTable("orders"), "Order")
purchase_orders = NumberedCRUD(JsonTable("purchase_orders"), "Supplier order")
invoices = NumberedCRUD(JsonTable("invoices"), "Invoice")
payments = CRUDBase(JsonTable("payments"), "Payment")
routes = CRUDBase(JsonTable("routes"), "Delivery route")
route_runs = CRUDBase(JsonTable("route_runs"), "Day tour")
client_events = CRUDBase(JsonTable("client_events"), "Customer event")
supplier_events = CRUDBase(JsonTable("supplier_events"), "Supplier event")
tags = CRUDBase(JsonTable("tags", lambda d: f"{d['scope']}|{d['id']}"), "Group")
price_rules = CRUDBase(JsonTable("price_rules"), "Price rule")
context_entries = CRUDBase(JsonTable("context_entries"), "Background sheet")
events = CRUDBase(JsonTable("events"), "Event")  # the activity log

# Data pack file name (seed/<key>.json) → CRUD. Missing files load as [].
PACK: dict[str, CRUDBase] = {
    "products": products,
    "clients": clients,
    "clientPrices": client_prices,
    "suppliers": suppliers,
    "supplierPrices": supplier_prices,
    "lots": lots,
    "stockMovements": stock_movements,
    "orders": orders,
    "purchaseOrders": purchase_orders,
    "invoices": invoices,
    "payments": payments,
    "routes": routes,
    "routeRuns": route_runs,
    "clientEvents": client_events,
    "supplierEvents": supplier_events,
    "tags": tags,
    "priceRules": price_rules,
    "contextEntries": context_entries,
}
