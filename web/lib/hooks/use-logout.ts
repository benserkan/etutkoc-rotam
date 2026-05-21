"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";

/**
 * Logout mutation hook'u — POST /api/v2/auth/logout sonra cache temizle +
 * /login'e yönlendir.
 *
 * Hata olsa bile yönlendirme yapılır (cookie eskimişse de kullanıcı çıkmış
 * sayılır). qc.clear() çağırdığı için ESLint missing-invalidate susturulur.
 */
export function useLogout() {
  const router = useRouter();
  const qc = useQueryClient();

  return useMutation({
    mutationFn: () => api<{ ok: boolean }>("/api/v2/auth/logout", { method: "POST" }),
    onSuccess: () => {
      qc.clear();
      toast.success("Oturum kapatıldı");
      router.refresh();
      router.push("/login");
    },
    onError: () => {
      qc.clear();
      toast.error("Çıkış sırasında hata — yine de yönlendiriliyorsunuz.");
      router.push("/login");
    },
  });
}
