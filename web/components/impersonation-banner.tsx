"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Drama, Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface ImpersonationStatus {
  active: boolean;
  impersonator_name: string | null;
  target_name: string | null;
}

/**
 * Sahte oturum (impersonation) üst bandı.
 *
 * Aktif istek bir süper admin tarafından "sahte oturum" için üretilmiş bir BFF
 * token'ıysa (`imp_by` claim'i), `/api/v2/auth/impersonation-status` active=True
 * döner → kapatılamaz mor banner + "Admin'e dön". Tıklanınca
 * `/api/v2/admin/impersonate/end` admin'in normal cookie'sini geri basar ve
 * `/admin`'e yönlendirir. Normal kullanıcıda hiç görünmez (active=False → null).
 */
export function ImpersonationBanner() {
  const q = useQuery<ImpersonationStatus>({
    queryKey: ["impersonation-status"],
    queryFn: () => api<ImpersonationStatus>("/api/v2/auth/impersonation-status"),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
  const [ending, setEnding] = React.useState(false);

  if (!q.data?.active) return null;

  async function endImpersonation() {
    setEnding(true);
    try {
      const r = await api<{ redirect_url: string }>(
        "/api/v2/admin/impersonate/end",
        { method: "POST" },
      );
      window.location.href = r.redirect_url || "/admin";
    } catch {
      // Yine de admin'e dönmeyi dene
      window.location.href = "/admin";
    }
  }

  return (
    <div className="bg-violet-700 text-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-2 text-sm">
        <Drama className="size-4 shrink-0" aria-hidden />
        <span className="min-w-[200px] flex-1">
          <strong>Sahte oturum</strong> —{" "}
          {q.data.target_name ?? "kullanıcı"} olarak görüntülüyorsunuz
          {q.data.impersonator_name ? ` (${q.data.impersonator_name})` : ""}.
          Yaptığınız işlemler audit&apos;e bu kullanıcı adına yazılır.
        </span>
        <Button
          onClick={endImpersonation}
          disabled={ending}
          size="sm"
          className="shrink-0 bg-white text-violet-800 hover:bg-violet-50 hover:text-violet-900"
        >
          {ending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <Drama className="size-3.5" aria-hidden />
          )}
          Admin&apos;e dön
        </Button>
      </div>
    </div>
  );
}
