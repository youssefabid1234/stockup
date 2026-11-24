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
  { items: [{ to: "/", label: "Home", icon: Home, keywords: "dashboard tableau de bord" }] },
  {
    label: "Sales",
    items: [
      { to: "/orders", label: "Orders", icon: ShoppingCart, keywords: "sales order" },
      { to: "/clients", label: "Customers", icon: Users, keywords: "client restaurant" },
      { to: "/prices", label: "Pricing", icon: BadgeEuro, keywords: "prices rules discount price negotiated grid simulator margin" },
      { to: "/history", label: "Account history", icon: History, keywords: "historical claim dispute back to have relation events supplier" },
    ],
  },
  {
    label: "Purchasing and stock",
    items: [
      { to: "/products", label: "Products", icon: Package, keywords: "catalogue article" },
      { to: "/stock", label: "Stocks", icon: Warehouse, keywords: "inventory lots" },
      { to: "/purchase-orders", label: "Purchases", icon: Boxes, keywords: "order supplier" },
      { to: "/suppliers", label: "Suppliers", icon: Building2, keywords: "supplier" },
    ],
  },
  {
    label: "Finance",
    items: [
      { to: "/receivables", label: "Outstanding balance", icon: Scale, keywords: "outstanding old-age balance delay recovery unpaid debt" },
      { to: "/invoices", label: "Invoices", icon: FileText, keywords: "unpaid invoice" },
      { to: "/payments", label: "Payments", icon: Wallet, keywords: "settlement" },
    ],
  },
  { label: "Logistics", items: [{ to: "/routes", label: "Delivery routes", icon: Truck, keywords: "Road delivery" }] },
  {
    label: "AI",
    items: [
      { to: "#assistant", label: "Assistant", icon: Sparkles, keywords: "chat ia" },
      { to: "/voice", label: "Voice", icon: AudioLines, keywords: "Voice call agent" },
      { to: "/context", label: "Context", icon: BookOpen, keywords: "context ia factsheets knowledge memory rules procedures preferences" },
    ],
  },
  { items: [{ to: "/activity", label: "Activity", icon: Activity, keywords: "Newspaper events" }, { to: "/groups", label: "Groups", icon: Tags, keywords: "groups tags labels segments customers products suppliers" }] },
];

export const NAV_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);
