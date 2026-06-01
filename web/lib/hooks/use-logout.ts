"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

/**
 * Logout mutation hook'u — POST /api/v2/auth/logout (cookie temizler + ActiveSession
 * sonlandırır), ardından TAM SAYFA YENİLEME ile /login'e gider.
 *
 * KRİTİK GÜVENLİK: `router.push("/login")` KULLANILMAZ. Next.js App Router'ın
 * client-side router cache'i, çıkıştan önce gezilen korumalı sayfaların (örn.
 * /admin) RSC payload'ını tutar; `router.push` bu cache'i boşaltmaz → kullanıcı
 * çıkış yaptıktan sonra logo/geri ile cache'li authenticated sayfaya geri
 * dönebiliyordu (çıkış yaptım ama /admin hâlâ açılıyor açığı). `window.location.
 * replace` tam sayfa yükleme yapar → TÜM client cache silinir + history'ye authed
 * sayfa bırakmaz (replace). Sonraki her gezinme sunucudan taze gelir; cookie
 * temizlendiği için korumalı sayfalar /login'e düşer.
 *
 * onSettled: POST başarılı da olsa hata da verse (cookie eskimişse de) çıkış
 * tamamlanmış sayılır ve hard-nav yapılır.
 */
export function useLogout() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: () => api<{ ok: boolean }>("/api/v2/auth/logout", { method: "POST" }),
    onSettled: () => {
      qc.clear();
      window.location.replace("/login");
    },
  });
}
