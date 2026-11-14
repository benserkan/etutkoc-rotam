import { MessageSuggestionsClient } from "@/components/teacher/message-suggestions-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Bugünün mesajları — Koç",
};

export default async function TeacherMessagesPage({
  searchParams,
}: {
  searchParams: Promise<{ student?: string }>;
}) {
  const sp = await searchParams;
  const sid = sp.student ? Number(sp.student) : null;
  return <MessageSuggestionsClient studentId={Number.isFinite(sid) && sid ? sid : null} />;
}
