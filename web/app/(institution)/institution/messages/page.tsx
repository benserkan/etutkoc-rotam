import { InstitutionMessagesClient } from "@/components/institution/institution-messages-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Koçlara mesajlar — Kurum",
};

export default function InstitutionMessagesPage() {
  return <InstitutionMessagesClient />;
}
