import { AnalyticsView } from "./analytics-view";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Site Analitiği — Süper Admin",
};

export default function AdminAnalyticsPage() {
  // Runtime env (next container). Boşsa kurulum rehberi gösterilir.
  const sharedUrl = process.env.PLAUSIBLE_SHARED_URL || "";
  const dashboardUrl = process.env.PLAUSIBLE_DASHBOARD_URL || "";
  return <AnalyticsView sharedUrl={sharedUrl} dashboardUrl={dashboardUrl} />;
}
