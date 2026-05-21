import { Loader2 } from "lucide-react";

export default function TeacherLoading() {
  return (
    <div
      className="flex items-center justify-center py-20 text-muted-foreground gap-2"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="size-5 animate-spin" aria-hidden />
      <span className="text-sm">Yükleniyor…</span>
    </div>
  );
}
