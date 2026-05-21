import { ReviewBoard } from "@/components/teacher/review-board";

interface PageProps {
  params: Promise<{ id: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Tekrar · Öğrenci #${id}` };
}

export default async function ReviewPage({ params }: PageProps) {
  const { id } = await params;
  return <ReviewBoard studentId={Number(id)} />;
}
