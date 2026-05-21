import { FocusBoard } from "@/components/teacher/focus-board";

interface PageProps {
  params: Promise<{ id: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Odak · Öğrenci #${id}` };
}

export default async function FocusPage({ params }: PageProps) {
  const { id } = await params;
  return <FocusBoard studentId={Number(id)} />;
}
