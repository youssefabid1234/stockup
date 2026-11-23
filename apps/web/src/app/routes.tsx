/** All routes. One page = one folder in src/pages/<name>/index.tsx (default export). */
import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "./AppShell";
import { NotFound } from "./NotFound";
import DashboardPage from "@/pages/dashboard";
import OrdersPage from "@/pages/orders";
import OrderDetailPage from "@/pages/order-detail";
import ClientsPage from "@/pages/clients";
import ClientDetailPage from "@/pages/client-detail";
import ProductsPage from "@/pages/products";
import ProductDetailPage from "@/pages/product-detail";
import StockPage from "@/pages/stock";
import PurchaseOrdersPage from "@/pages/purchase-orders";
import PurchaseOrderDetailPage from "@/pages/purchase-order-detail";
import SuppliersPage from "@/pages/suppliers";
import SupplierDetailPage from "@/pages/supplier-detail";
import InvoicesPage from "@/pages/invoices";
import ReceivablesPage from "@/pages/receivables";
import InvoiceDetailPage from "@/pages/invoice-detail";
import PaymentsPage from "@/pages/payments";
import RoutesPage from "@/pages/routes";
import ActivityPage from "@/pages/activity";
import VoicePage from "@/pages/voice";
import HistoryPage from "@/pages/history";
import PricesPage from "@/pages/prices";
import GroupsPage from "@/pages/groups";
import ContextPage from "@/pages/context";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "orders", element: <OrdersPage /> },
      { path: "orders/:id", element: <OrderDetailPage /> },
      { path: "clients", element: <ClientsPage /> },
      { path: "clients/:id", element: <ClientDetailPage /> },
      { path: "products", element: <ProductsPage /> },
      { path: "products/:id", element: <ProductDetailPage /> },
      { path: "stock", element: <StockPage /> },
      { path: "purchase-orders", element: <PurchaseOrdersPage /> },
      { path: "purchase-orders/:id", element: <PurchaseOrderDetailPage /> },
      { path: "suppliers", element: <SuppliersPage /> },
      { path: "suppliers/:id", element: <SupplierDetailPage /> },
      { path: "receivables", element: <ReceivablesPage /> },
      { path: "invoices", element: <InvoicesPage /> },
      { path: "invoices/:id", element: <InvoiceDetailPage /> },
      { path: "payments", element: <PaymentsPage /> },
      { path: "routes", element: <RoutesPage /> },
      { path: "activity", element: <ActivityPage /> },
      { path: "voice", element: <VoicePage /> },
      { path: "history", element: <HistoryPage /> },
      { path: "prices", element: <PricesPage /> },
      { path: "groups", element: <GroupsPage /> },
      { path: "context", element: <ContextPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);
