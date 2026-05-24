import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { MyAccountResponse } from "@/lib/types/me";
import { TeacherShell } from "@/components/teacher/teacher-shell";

/**
 * /(teacher)/* — öğretmen paneli korumalı layout.
 *
 * Defense-in-depth:
 *   - Backend zaten `_require_teacher` ile 403 atar
 *   - Bu layout boş sayfa yerine kullanıcıyı doğru hedefe yönlendirir:
 *       401/403  → /login?returnUrl=...
 *       student  → /student/day
 *       parent   → /me/account (Dalga 6'da /parent/* olacak)
 *       admin    → /me/account (Dalga 4/5'te kendi paneline)
 *
 * R-007: cache: "no-store" + dynamic = "force-dynamic" — App Router cache yok.
 */
export const dynamic = "force-dynamic";

export default async function TeacherLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let data: MyAccountResponse;
  try {
    data = await apiServer<MyAccountResponse>("/api/v2/me");
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect("/login?returnUrl=" + encodeURIComponent("/teacher/dashboard"));
    }
    throw e;
  }

  const role = data.user.role;
  if (role !== "teacher") {
    if (role === "student") {
      redirect("/student/day");
    }
    redirect("/me/account");
  }

  return (
    <TeacherShell user={data.user} institution={data.institution}>
      {children}
    </TeacherShell>
  );
}
