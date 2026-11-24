/** Where an entity lives in the app. Use for any cross-link (activity feed, search, assistant). */
import type { ActivityEvent, Id } from "@kit/shared";

export function entityPath(entity: ActivityEvent["entity"], id: Id): string | undefined {
  switch (entity) {
    case "client": return `/clients/${id}`;
    case "supplier": return `/suppliers/${id}`;
    case "product": return `/products/${id}`;
    case "stock": return `/products/${id}`; // stock events carry the productId
    case "order": return `/orders/${id}`;
    case "purchase_order": return `/purchase-orders/${id}`;
    case "invoice": return `/invoices/${id}`;
    case "payment": return `/payments`;
    case "route_run": return `/routes`;
    case "context": return `/context?e=${id}`;
    default: return undefined;
  }
}

export const ENTITY_LABEL: Record<ActivityEvent["entity"], string> = {
  client: "Customer", supplier: "Supplier", product: "Product", stock: "Stock", order: "Order",
  purchase_order: "Purchase", invoice: "Invoice", payment: "Payment", route_run: "Delivery route", context: "Context",
};
