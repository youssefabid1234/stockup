import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { EmptyState, Page, PageBody, PageHeader } from "@/ui";

export function NotFound() {
  return (
    <Page>
      <PageHeader title="Page not found" />
      <PageBody>
        <EmptyState icon={Compass} title="This page does not exist" action={<Link to="/" className="text-[12.5px] font-medium text-primary hover:underline">Back to the reception</Link>} />
      </PageBody>
    </Page>
  );
}
