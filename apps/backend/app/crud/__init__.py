"""One CRUD object per stored entity. Usage: `from app import crud` then `crud.clients.require(id)`.

Keys: most tables use the document id; client/supplier prices use "clientId|productId",
tags use "scope|id".
"""

from app.core.db import JsonTable
from app.crud.base import CRUDBase, NumberedCRUD

products = CRUDBase(JsonTable("products"), "Produit")
clients = CRUDBase(JsonTable("clients"), "Client")
client_prices = CRUDBase(JsonTable("client_prices", lambda d: f"{d['clientId']}|{d['productId']}"), "Prix client")
suppliers = CRUDBase(JsonTable("suppliers"), "Fournisseur")
supplier_prices = CRUDBase(JsonTable("supplier_prices", lambda d: f"{d['supplierId']}|{d['productId']}"), "Prix fournisseur")
lots = CRUDBase(JsonTable("lots"), "Lot")
stock_movements = CRUDBase(JsonTable("stock_movements"), "Mouvement")
orders = NumberedCRUD(JsonTable("orders"), "Commande")
purchase_orders = NumberedCRUD(JsonTable("purchase_orders"), "Commande fournisseur")
invoices = NumberedCRUD(JsonTable("invoices"), "Facture")
payments = CRUDBase(JsonTable("payments"), "Paiement")
routes = CRUDBase(JsonTable("routes"), "Tournée")
route_runs = CRUDBase(JsonTable("route_runs"), "Tournée du jour")
client_events = CRUDBase(JsonTable("client_events"), "Événement client")
supplier_events = CRUDBase(JsonTable("supplier_events"), "Événement fournisseur")
tags = CRUDBase(JsonTable("tags", lambda d: f"{d['scope']}|{d['id']}"), "Groupe")
price_rules = CRUDBase(JsonTable("price_rules"), "Règle de prix")
context_entries = CRUDBase(JsonTable("context_entries"), "Fiche de contexte")
events = CRUDBase(JsonTable("events"), "Événement")  # the activity log

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
