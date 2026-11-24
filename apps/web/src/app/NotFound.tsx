import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { EmptyState, Page, PageBody, PageHeader } from "@/ui";

export function NotFound() {
  return (
    <Page>
      <PageHeader title="Page introuvable" />
      <PageBody>
        <EmptyState icon={Compass} title="Cette page n'existe pas" action={<Link to="/" className="text-[12.5px] font-medium text-primary hover:underline">Retour à l'accueil</Link>} />
      </PageBody>
    </Page>
  );
}
