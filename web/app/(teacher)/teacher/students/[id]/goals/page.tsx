import { GoalsTree } from "@/components/teacher/goals-tree";

interface PageProps {
  params: Promise<{ id: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Hedefler · Öğrenci #${id}` };
}

export default async function GoalsPage({ params }: PageProps) {
  const { id } = await params;
  return <GoalsTree studentId={Number(id)} />;
}
