import { TopicPerformancePanel } from "@/components/shared/topic-performance-panel";

export const metadata = { title: "Konu Performansı" };
export const dynamic = "force-dynamic";

export default function StudentTopicsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <h1 className="mb-1 text-lg font-bold text-foreground">Konu Performansım</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Hangi derste, hangi konuda ne kadar test çözdün ve doğruluğun ne — bir bakışta gör.
      </p>
      <TopicPerformancePanel source="student" />
    </div>
  );
}
