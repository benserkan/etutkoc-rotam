import { PromoteForm } from "@/components/teacher/promote-form";

interface PageProps {
  params: Promise<{ id: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Sınıf Yükselt · Öğrenci #${id}` };
}

export default async function PromotePage({ params }: PageProps) {
  const { id } = await params;
  return <PromoteForm studentId={Number(id)} />;
}
