import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { TopicPerformancePanel } from "@/components/shared/topic-performance-panel";

export const dynamic = "force-dynamic";
export const metadata = { title: "Konu Performansı — Veli Paneli" };

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ParentTopicsPage({ params }: PageProps) {
  const { id } = await params;
  const sid = Number(id);
  if (!Number.isFinite(sid) || sid <= 0) notFound();

  return (
    <div className="space-y-4">
      <div>
        <Link
          href={`/parent/students/${sid}`}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" aria-hidden />
          Geri
        </Link>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight font-display">Konu Performansı</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Çocuğunuzun her dersin konularında çözdüğü test ve doğru/yanlış performansı.
        </p>
      </div>
      <TopicPerformancePanel source="parent" studentId={sid} />
    </div>
  );
}
