/** French labels for domain enums. Add new enum values here (and a tone in ui/status.ts if it's a status). */
import type { Actor, ClientType, ContextKind, ContextScope, ContextSource, OrderSource, PaymentMethod, ProductCategory, StockMovementReason, Weekday } from "@kit/shared";

export const CLIENT_TYPE_LABEL: Record<ClientType, string> = {
  restaurant: "Restaurant",
  brasserie: "Brasserie",
  fishmonger: "Poissonnerie",
  canteen: "Restauration collective",
  supermarket: "Grande surface",
  caterer: "Traiteur",
  hotel: "Hôtel",
};

/** Product category labels: per company, filled from meta.categories at boot (see clock.ts). Legacy ids as fallback. */
export const CATEGORY_LABEL: Record<ProductCategory, string> = {
  whole_fish: "Poisson entier",
  fillet: "Filets",
  shellfish: "Coquillages",
  crustacean: "Crustacés",
  frozen: "Surgelés",
  produce: "Fruits & légumes",
  dairy: "Crèmerie",
  dry: "Épicerie",
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
  phone: "Téléphone",
  voice_agent: "Agent vocal",
  email: "E-mail",
  whatsapp: "WhatsApp",
  manual: "Saisie",
  web: "Web",
};

export const PAYMENT_METHOD_LABEL: Record<PaymentMethod, string> = {
  transfer: "Virement",
  card: "Carte",
  cheque: "Chèque",
  cash: "Espèces",
  direct_debit: "Prélèvement",
};

export const MOVEMENT_REASON_LABEL: Record<StockMovementReason, string> = {
  receipt: "Réception",
  sale: "Vente",
  adjustment: "Ajustement",
  waste: "Perte",
  return: "Retour",
};

export const WEEKDAY_LABEL: Record<Weekday, string> = {
  mon: "lun.", tue: "mar.", wed: "mer.", thu: "jeu.", fri: "ven.", sat: "sam.", sun: "dim.",
};
export const WEEKDAYS: Weekday[] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export const ACTOR_LABEL: Record<Actor, string> = {
  user: "Utilisateur",
  ai_chat: "Assistant IA",
  voice_agent: "Agent vocal",
  system: "Système",
};

// ── Context table ──
export const CONTEXT_SCOPE_LABEL: Record<ContextScope, string> = {
  company: "Entreprise",
  client: "Client",
  supplier: "Fournisseur",
  product: "Produit",
  category: "Rayon",
};
export const CONTEXT_KIND_LABEL: Record<ContextKind, string> = {
  policy: "Règle",
  procedure: "Procédure",
  preference: "Préférence",
  fact: "Fait",
  relationship: "Relation",
  pricing: "Prix",
  logistics: "Logistique",
  risk: "Vigilance",
};
export const CONTEXT_SOURCE_LABEL: Record<ContextSource, string> = {
  seed: "Data pack",
  user: "Utilisateur",
  ai_chat: "Assistant IA",
  voice_agent: "Agent vocal",
};
