/** Navigation model: sidebar groups + ⌘K "Aller à" commands. Add a page here AND in app/routes.tsx. */
import {
  Activity, AudioLines, Boxes, Building2, FileText, Home, Package, ShoppingCart, Sparkles, Truck, Users, Wallet, Warehouse,
  type LucideIcon,
} from "lucide-react";
import { History } from "lucide-react";
import { BadgeEuro, Tags } from "lucide-react";
import { Scale } from "lucide-react";
import { BookOpen } from "lucide-react";

export interface NavItem { to: string; label: string; icon: LucideIcon; keywords?: string }
export interface NavGroup { label?: string; items: NavItem[] }

export const NAV: NavGroup[] = [
  { items: [{ to: "/", label: "Accueil", icon: Home, keywords: "dashboard tableau de bord" }] },
  {
    label: "Ventes",
    items: [
      { to: "/orders", label: "Commandes", icon: ShoppingCart, keywords: "ventes commande" },
      { to: "/clients", label: "Clients", icon: Users, keywords: "client restaurant" },
      { to: "/prices", label: "Prix", icon: BadgeEuro, keywords: "tarifs règles remise prix négocié grille simulateur marge" },
      { to: "/history", label: "Historique", icon: History, keywords: "historique réclamation litige retour avoir relation événements fournisseur" },
    ],
  },
  {
    label: "Achats & stock",
    items: [
      { to: "/products", label: "Produits", icon: Package, keywords: "catalogue article" },
      { to: "/stock", label: "Stocks", icon: Warehouse, keywords: "lots inventaire" },
      { to: "/purchase-orders", label: "Achats", icon: Boxes, keywords: "commande fournisseur" },
      { to: "/suppliers", label: "Fournisseurs", icon: Building2, keywords: "fournisseur" },
    ],
  },
  {
    label: "Finance",
    items: [
      { to: "/receivables", label: "Encours", icon: Scale, keywords: "encours balance âgée retard relance créances dso impayés" },
      { to: "/invoices", label: "Factures", icon: FileText, keywords: "facture impayé" },
      { to: "/payments", label: "Paiements", icon: Wallet, keywords: "règlement encaissement" },
    ],
  },
  { label: "Logistique", items: [{ to: "/routes", label: "Tournées", icon: Truck, keywords: "livraison route" }] },
  {
    label: "IA",
    items: [
      { to: "#assistant", label: "Assistant", icon: Sparkles, keywords: "chat ia" },
      { to: "/voice", label: "Voix", icon: AudioLines, keywords: "agent vocal appel" },
      { to: "/context", label: "Contexte", icon: BookOpen, keywords: "contexte ia fiches connaissances mémoire règles procédures préférences" },
    ],
  },
  { items: [{ to: "/activity", label: "Activité", icon: Activity, keywords: "journal événements" }, { to: "/groups", label: "Groupes", icon: Tags, keywords: "groupes tags étiquettes segments clients produits fournisseurs" }] },
];

export const NAV_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);
