/** English labels for domain enums. Add new enum values here (and a tone in ui/status.ts if it's a status). */
import type { Actor, ClientType, ContextKind, ContextScope, ContextSource, OrderSource, PaymentMethod, ProductCategory, StockMovementReason, Weekday } from "@kit/shared";

export const CLIENT_TYPE_LABEL: Record<ClientType, string> = {
  restaurant: "Restaurant",
  brasserie: "Brasserie",
  fishmonger: "Fishmonger",
  canteen: "Institutional catering",
  supermarket: "Supermarket",
  caterer: "Caterer",
  hotel: "Hotel",
};

/** Product category labels: per company, filled from meta.categories at boot (see clock.ts). Legacy ids as fallback. */
export const CATEGORY_LABEL: Record<ProductCategory, string> = {
  whole_fish: "Whole fish",
  fillet: "Fillets",
  shellfish: "Shellfish",
  crustacean: "Crustaceans",
  frozen: "Frozen goods",
  produce: "Fruit & vegetables",
  dairy: "Dairy",
  dry: "Dry goods",
};
let categoryOrder: ProductCategory[] = Object.keys(CATEGORY_LABEL);
/** Replace the labels with the data pack's categories (id → label). */
export function setCategories(cats: { id: string; label: string }[] | undefined) {
  if (!cats?.length) return;
  for (const k of Object.keys(CATEGORY_LABEL)) delete CATEGORY_LABEL[k];
  for (const c of cats) CATEGORY_LABEL[c.id] = c.label;
  categoryOrder = cats.map((c) => c.id);
}
/** Label of a category id (raw id if unknown). */
export const categoryLabel = (id: string | undefined | null): string => (id ? CATEGORY_LABEL[id] ?? id : "");
/** Category ids of the company, in pack order. */
export const categoryIds = (): ProductCategory[] => categoryOrder;
/** {value, label} options for selects. */
export const categoryOptions = () => categoryOrder.map((value) => ({ value, label: categoryLabel(value) }));

export const SOURCE_LABEL: Record<OrderSource, string> = {
  phone: "Phone",
  voice_agent: "Voice agent",
  email: "E-mail",
  whatsapp: "WhatsApp",
  manual: "Manual entry",
  web: "Web",
};

export const PAYMENT_METHOD_LABEL: Record<PaymentMethod, string> = {
  transfer: "Bank transfer",
  card: "Card",
  cheque: "Cheque",
  cash: "Cash",
  direct_debit: "Direct debit",
};

export const MOVEMENT_REASON_LABEL: Record<StockMovementReason, string> = {
  receipt: "Receipt",
  sale: "Sale",
  adjustment: "Adjustment",
  waste: "Waste",
  return: "Return",
};

export const WEEKDAY_LABEL: Record<Weekday, string> = {
  mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun",
};
export const WEEKDAYS: Weekday[] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export const ACTOR_LABEL: Record<Actor, string> = {
  user: "User",
  ai_chat: "AI assistant",
  voice_agent: "Voice agent",
  system: "System",
};

// ── Context table ──
export const CONTEXT_SCOPE_LABEL: Record<ContextScope, string> = {
  company: "Company",
  client: "Customer",
  supplier: "Supplier",
  product: "Product",
  category: "Department",
};
export const CONTEXT_KIND_LABEL: Record<ContextKind, string> = {
  policy: "Policy",
  procedure: "Procedure",
  preference: "Preference",
  fact: "Fact",
  relationship: "Relationship",
  pricing: "Price",
  logistics: "Logistics",
  risk: "Risk",
};
export const CONTEXT_SOURCE_LABEL: Record<ContextSource, string> = {
  seed: "Data pack",
  user: "User",
  ai_chat: "AI assistant",
  voice_agent: "Voice agent",
};
