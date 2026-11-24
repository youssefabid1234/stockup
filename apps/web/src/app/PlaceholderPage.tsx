import type { ReactNode } from "react";
import { Hammer } from "lucide-react";
import { EmptyState, Page, PageBody, PageHeader, type Crumb } from "@/ui";

/** Temporary body for pages not built yet. Page agents: delete its usage when you implement your page. */
export function PlaceholderPage({ title, breadcrumb, description }: { title: ReactNode; breadcrumb?: Crumb[]; description?: string }) {
  return (
    <Page>
      <PageHeader title={title} breadcrumb={breadcrumb} />
      <PageBody>
        <EmptyState icon={Hammer} title="Page under construction" description={description ?? "This page will be built on the Clients model."} />
      </PageBody>
    </Page>
  );
}
