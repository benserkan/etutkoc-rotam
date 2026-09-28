import Link from "next/link";

import { apiServer } from "@/lib/api-server";
import type { SupportListResponse } from "@/lib/types/support";
import { SupportCenter } from "@/components/support/support-center";
import { DemoHint } from "@/components/demos/demo-hint";
import { cn } from "@/lib/utils";

/**
 * /institution/support-inbox — Talepler (birleşik, 2026-09-28).
 *
 * İki akış tek sayfada, iki sekme:
 *   - "Öğretmenlerden gelen": kurumdaki öğretmenlerin kurum yöneticisine talepleri
 *   - "Sistem yöneticisiyle": kurum yöneticisinin platforma (süper yönetici) talepleri
 * Tenant izolasyonu backend'de: yalnız kendi kurumunun talepleri görünür.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Talepler" };

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function InstitutionSupportInboxPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const tab = sp.tab === "sistem" ? "sistem" : "ogretmen";
  const [inbox, mine] = await Promise.all([
    apiServer<SupportListResponse>("/api/v2/support/inbox"),
    apiServer<SupportListResponse>("/api/v2/support/requests"),
  ]);
  const inboxOpen = inbox.pending_count ?? 0;
  const mineAnswered = mine.items.filter((i) => i.status === "answered").length;

  return (
    <div className="space-y-4">
      <nav className="flex flex-wrap gap-2 border-b border-border" aria-label="Talep türü">
        <TabLink href="/institution/support-inbox" active={tab === "ogretmen"} count={inboxOpen}>
          Öğretmenlerden gelen
        </TabLink>
        <TabLink href="/institution/support-inbox?tab=sistem" active={tab === "sistem"} count={mineAnswered}>
          Sistem yöneticisiyle
        </TabLink>
      </nav>
      <DemoHint contextKey="requests" role="institution_admin" />
      {tab === "ogretmen" ? (
        <SupportCenter
          view="inbox"
          initial={inbox}
          title="Öğretmenlerden gelen talepler"
          description="Kurumundaki öğretmenlerin sana ilettiği talepler. İnceleyip yanıtla, çözümle; çözemediğini sistem yöneticisine yönlendirebilirsin."
        />
      ) : (
        <SupportCenter
          view="mine"
          initial={mine}
          canCreate
          title="Sistem yöneticisiyle yazışmalar"
          description="Platformla ilgili (paket, teknik sorun, hesap) sistem yöneticisine ilettiğin talepler ve yanıtları."
        />
      )}
    </div>
  );
}

function TabLink({
  href,
  active,
  count,
  children,
}: {
  href: string;
  active: boolean;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm",
        active
          ? "border-foreground font-medium text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
      {count > 0 ? (
        <span className="rounded-full bg-rose-600 px-1.5 text-[11px] font-semibold text-white">
          {count}
        </span>
      ) : null}
    </Link>
  );
}
