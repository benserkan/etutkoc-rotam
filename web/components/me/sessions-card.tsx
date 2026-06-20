"use client";

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Monitor, Smartphone } from "lucide-react";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface SessionItem {
  session_token: string;
  ip: string | null;
  user_agent: string | null;
  login_at: string | null;
  last_seen_at: string | null;
  idle_seconds: number;
  is_current: boolean;
}

interface SessionsResponse {
  sessions: SessionItem[];
}

const SESSIONS_KEY = ["me", "sessions"] as const;

function humanizeAgo(seconds: number): string {
  if (seconds < 60) return "az önce";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} dk önce`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} saat önce`;
  return `${Math.floor(seconds / 86400)} gün önce`;
}

function deviceLabel(ua: string | null): string {
  if (!ua) return "Bilinmeyen cihaz";
  const s = ua.toLowerCase();
  let os = "Cihaz";
  if (s.includes("windows")) os = "Windows";
  else if (s.includes("android")) os = "Android";
  else if (s.includes("iphone") || s.includes("ipad") || s.includes("ios")) os = "iOS";
  else if (s.includes("mac")) os = "Mac";
  else if (s.includes("linux")) os = "Linux";
  let browser = "";
  if (s.includes("edg")) browser = "Edge";
  else if (s.includes("chrome")) browser = "Chrome";
  else if (s.includes("firefox")) browser = "Firefox";
  else if (s.includes("safari")) browser = "Safari";
  return browser ? `${os} · ${browser}` : os;
}

function isMobile(ua: string | null): boolean {
  if (!ua) return false;
  const s = ua.toLowerCase();
  return s.includes("android") || s.includes("iphone") || s.includes("mobile");
}

export function SessionsCard() {
  const qc = useQueryClient();
  const q = useQuery<SessionsResponse>({
    queryKey: SESSIONS_KEY,
    queryFn: () => api<SessionsResponse>("/api/v2/me/sessions"),
    staleTime: 10_000,
  });
  const [revoking, setRevoking] = React.useState<string | null>(null);

  const sessions = q.data?.sessions ?? [];

  async function revoke(token: string) {
    setRevoking(token);
    try {
      const res = await api<MutationResponse<{ message: string }>>(
        `/api/v2/me/sessions/${encodeURIComponent(token)}/revoke`,
        { method: "POST" },
      );
      toast.success(res.data.message);
      qc.invalidateQueries({ queryKey: SESSIONS_KEY });
    } catch (e) {
      toast.error("Kapatılamadı", {
        description: e instanceof ApiError ? e.detail?.message : undefined,
      });
    } finally {
      setRevoking(null);
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-1 flex items-center gap-2">
        <Monitor className="size-5 text-muted-foreground" aria-hidden />
        <h2 className="font-display text-lg font-semibold">Aktif oturumlar</h2>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Hesabınıza giriş yapılmış cihazlar (son 24 saat). Tanımadığınız bir cihaz
        görürseniz oturumu kapatın; o cihazda yeniden giriş gerekir.
      </p>

      {q.isLoading ? (
        <p className="text-sm text-muted-foreground">Yükleniyor…</p>
      ) : sessions.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aktif oturum bulunamadı.</p>
      ) : (
        <ul className="divide-y divide-border">
          {sessions.map((s) => {
            const Icon = isMobile(s.user_agent) ? Smartphone : Monitor;
            return (
              <li key={s.session_token} className="flex items-center justify-between gap-3 py-3">
                <div className="flex min-w-0 items-start gap-3">
                  <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{deviceLabel(s.user_agent)}</span>
                      {s.is_current ? (
                        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200">
                          Bu cihaz
                        </span>
                      ) : null}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {s.ip ? <span className="font-mono">{s.ip}</span> : "IP yok"} · son aktivite {humanizeAgo(s.idle_seconds)}
                    </div>
                  </div>
                </div>
                {s.is_current ? (
                  <span className="shrink-0 text-[11px] text-muted-foreground">aktif</span>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={revoking === s.session_token}
                    onClick={() => revoke(s.session_token)}
                    className="shrink-0"
                  >
                    {revoking === s.session_token ? <Loader2 className="animate-spin" /> : null}
                    Oturumu kapat
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
