"use client";

import * as React from "react";
import { QRCodeSVG } from "qrcode.react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, ShieldCheck, ShieldOff } from "lucide-react";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";

interface Status {
  available: boolean;
  enabled: boolean;
  pending_setup: boolean;
  remaining_backup_codes: number;
}

interface SetupResult {
  secret: string;
  provisioning_uri: string;
  backup_codes: string[];
}

interface MutResult {
  message: string;
  enabled: boolean;
}

const STATUS_KEY = ["me", "2fa", "status"] as const;

export function TwoFactorCard() {
  const qc = useQueryClient();
  const statusQ = useQuery<Status>({
    queryKey: STATUS_KEY,
    queryFn: () => api<Status>("/api/v2/me/2fa/status"),
    staleTime: 10_000,
  });

  const [setup, setSetup] = React.useState<SetupResult | null>(null);
  const [code, setCode] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const status = statusQ.data;
  // Rol uygun değilse kart hiç gösterilmez (öğretmen/öğrenci/veli)
  if (!status || !status.available) return null;

  async function startSetup() {
    setBusy(true);
    try {
      const res = await api<SetupResult>("/api/v2/me/2fa/setup", { method: "POST" });
      setSetup(res);
      setCode("");
    } catch (e) {
      toast.error("Kurulum başlatılamadı", {
        description: e instanceof ApiError ? e.detail?.message : undefined,
      });
    } finally {
      setBusy(false);
    }
  }

  async function confirmEnable() {
    setBusy(true);
    try {
      const res = await api<MutationResponse<MutResult>>("/api/v2/me/2fa/enable", {
        method: "POST",
        body: JSON.stringify({ code: code.trim() }),
      });
      toast.success(res.data.message);
      setSetup(null);
      setCode("");
      qc.invalidateQueries({ queryKey: STATUS_KEY });
      qc.invalidateQueries({ queryKey: ["me", "account"] });
    } catch (e) {
      toast.error("Etkinleştirilemedi", {
        description: e instanceof ApiError ? e.detail?.message : undefined,
      });
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setBusy(true);
    try {
      const res = await api<MutationResponse<MutResult>>("/api/v2/me/2fa/disable", {
        method: "POST",
        body: JSON.stringify({ code: code.trim() }),
      });
      toast.success(res.data.message);
      setCode("");
      qc.invalidateQueries({ queryKey: STATUS_KEY });
      qc.invalidateQueries({ queryKey: ["me", "account"] });
    } catch (e) {
      toast.error("Kapatılamadı", {
        description: e instanceof ApiError ? e.detail?.message : undefined,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-1 flex items-center gap-2">
        {status.enabled ? (
          <ShieldCheck className="size-5 text-emerald-600" aria-hidden />
        ) : (
          <ShieldOff className="size-5 text-muted-foreground" aria-hidden />
        )}
        <h2 className="font-display text-lg font-semibold">İki faktörlü doğrulama</h2>
        {status.enabled ? (
          <span className="ml-auto rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
            Aktif
          </span>
        ) : (
          <span className="ml-auto rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
            Kapalı
          </span>
        )}
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Yönetici hesabınız için ekstra güvenlik. Girişte şifreye ek olarak
        authenticator uygulamasındaki (Google Authenticator, Authy vb.) 6 haneli kod istenir.
      </p>

      {/* AKTİF */}
      {status.enabled ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Kalan yedek kod: <strong>{status.remaining_backup_codes}</strong>
          </p>
          <div className="space-y-2">
            <Label htmlFor="disable_code">Kapatmak için doğrulama kodu</Label>
            <Input id="disable_code" inputMode="numeric" autoComplete="one-time-code"
                   placeholder="123456 veya yedek kod" value={code} disabled={busy}
                   onChange={(e) => setCode(e.target.value)} className="max-w-xs" />
          </div>
          <Button variant="destructive" disabled={busy || !code.trim()} onClick={disable}>
            {busy ? <Loader2 className="animate-spin" /> : null}
            2FA&apos;yı kapat
          </Button>
        </div>
      ) : setup ? (
        /* KURULUM — QR + backup + kod doğrulama */
        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-muted/30 p-4 text-center">
            <div className="inline-block rounded-md bg-white p-3">
              <QRCodeSVG value={setup.provisioning_uri} size={160} />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Authenticator uygulamanızla bu kodu tarayın. Tarayamıyorsanız gizli anahtarı elle girin:
            </p>
            <code className="mt-1 block break-all text-xs font-mono">{setup.secret}</code>
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
            <p className="text-xs font-medium text-amber-900">
              Yedek kodlarınızı güvenli bir yere kaydedin (bir kez gösterilir):
            </p>
            <div className="mt-2 grid grid-cols-2 gap-1 font-mono text-xs text-amber-900">
              {setup.backup_codes.map((c) => (
                <span key={c}>{c}</span>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="enable_code">Uygulamadaki 6 haneli kodu girin</Label>
            <Input id="enable_code" inputMode="numeric" autoComplete="one-time-code"
                   placeholder="123456" value={code} disabled={busy}
                   onChange={(e) => setCode(e.target.value)} className="max-w-xs" />
          </div>
          <div className="flex gap-2">
            <Button disabled={busy || !code.trim()} onClick={confirmEnable}>
              {busy ? <Loader2 className="animate-spin" /> : null}
              Etkinleştir
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => { setSetup(null); setCode(""); }}>
              Vazgeç
            </Button>
          </div>
        </div>
      ) : (
        /* KAPALI — kurulum başlat */
        <Button disabled={busy} onClick={startSetup}>
          {busy ? <Loader2 className="animate-spin" /> : null}
          İki faktörlü doğrulamayı kur
        </Button>
      )}
    </Card>
  );
}
