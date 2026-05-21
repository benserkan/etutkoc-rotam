"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

type State = "verifying" | "success" | "error";

interface Props {
  token: string;
}

export function VerifyEmailClient({ token }: Props) {
  const [state, setState] = React.useState<State>("verifying");
  const [message, setMessage] = React.useState<string>("");
  const startedRef = React.useRef(false);

  React.useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    (async () => {
      try {
        const res = await api<{ ok: boolean; message: string }>(
          `/api/v2/auth/verify-email/${token}`,
          { method: "POST" },
        );
        setMessage(res.message);
        setState("success");
      } catch (e) {
        setMessage(
          e instanceof ApiError
            ? e.detail?.message ?? "Doğrulama bağlantısı geçersiz veya süresi dolmuş."
            : "Sunucuya ulaşılamadı.",
        );
        setState("error");
      }
    })();
  }, [token]);

  if (state === "verifying") {
    return (
      <div className="flex flex-col items-center gap-3 py-4 text-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" aria-hidden />
        <p className="text-sm text-muted-foreground">Doğrulanıyor…</p>
      </div>
    );
  }

  if (state === "success") {
    return (
      <div className="space-y-4 text-center">
        <CheckCircle2 className="mx-auto size-10 text-emerald-600" aria-hidden />
        <p className="text-sm text-muted-foreground">{message}</p>
        <Button asChild className="w-full">
          <Link href="/login">Girişe dön</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 text-center">
      <XCircle className="mx-auto size-10 text-rose-600" aria-hidden />
      <p className="text-sm text-muted-foreground">{message}</p>
      <Button asChild variant="outline" className="w-full">
        <Link href="/login">Girişe dön</Link>
      </Button>
    </div>
  );
}
