import { DnaBoard } from "@/components/teacher/dna-board";

interface PageProps {
  params: Promise<{ id: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `DNA · Öğrenci #${id}` };
}

export default async function DnaPage({ params }: PageProps) {
  const { id } = await params;
  return <DnaBoard studentId={Number(id)} />;
}
