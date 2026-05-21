"use client";

import * as React from "react";
import { Eye, EyeOff, KeyRound, Loader2, ShieldCheck } from "lucide-react";

import { usePasswordChange } from "@/lib/hooks/use-me-mutations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SectionPanel } from "@/components/section-panel";
import { cn } from "@/lib/utils";

interface Props {
  /**
   * `true` ise alan boş bırakılabilir (must_change_password ilk giriş senaryosu).
   * Varsayılan: mevcut şifre ister.
   */
  allowEmptyCurrent?: boolean;
  /** Başlık kısayolu (settings tabında "Hesap şifresi" vs.). */
  title?: string;
  description?: string;
}

/**
 * Şifre değiştirme kartı — /me/account + /teacher/settings (Profil) ortak.
 *
 * Backend kodları (POST /api/v2/me/password-change) toast'lar use-me-mutations
 * tarafında ele alınır; bu component yalnızca form alanlarını + min kontrolü
 * sağlar (eşleşme + 8 karakter eşiği). Politika reddi (zayıf/breached) toast.
 */
export function PasswordChangeCard({
  allowEmptyCurrent = false,
  title = "Hesap şifresi",
  description = "Mevcut şifreni doğrula, ardından yeni bir şifre belirle. Yeni şifre tüm açık oturumları geçersiz kılmaz; güvenli kabul edilmek için son sızıntı veritabanlarına karşı kontrol edilir.",
}: Props) {
  const mut = usePasswordChange();
  const [current, setCurrent] = React.useState("");
  const [next, setNext] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [showCurrent, setShowCurrent] = React.useState(false);
  const [showNext, setShowNext] = React.useState(false);
  const [localError, setLocalError] = React.useState<string | null>(null);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLocalError(null);
    if (!allowEmptyCurrent && current.length === 0) {
      setLocalError("Mevcut şifreni gir.");
      return;
    }
    if (next.length < 8) {
      setLocalError("Yeni şifre en az 8 karakter olmalı.");
      return;
    }
    if (next !== confirm) {
      setLocalError("Yeni şifreler birbiriyle eşleşmiyor.");
      return;
    }
    mut.mutate(
      {
        body: {
          current_password: allowEmptyCurrent ? null : current,
          new_password: next,
          confirm_password: confirm,
        },
      },
      {
        onSuccess: () => {
          setCurrent("");
          setNext("");
          setConfirm("");
        },
      },
    );
  }

  return (
    <SectionPanel
      title={title}
      description={description}
      accent="lacivert"
    >
      <form onSubmit={onSubmit} className="space-y-4 max-w-md">
        {!allowEmptyCurrent ? (
          <div className="space-y-1.5">
            <Label htmlFor="pwd-current">Mevcut şifre</Label>
            <PasswordInput
              id="pwd-current"
              value={current}
              onChange={setCurrent}
              show={showCurrent}
              onToggleShow={() => setShowCurrent((v) => !v)}
              autoComplete="current-password"
              required
            />
          </div>
        ) : null}

        <div className="space-y-1.5">
          <Label htmlFor="pwd-new">Yeni şifre</Label>
          <PasswordInput
            id="pwd-new"
            value={next}
            onChange={setNext}
            show={showNext}
            onToggleShow={() => setShowNext((v) => !v)}
            autoComplete="new-password"
            required
          />
          <PasswordPolicyHint value={next} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="pwd-confirm">Yeni şifre (tekrar)</Label>
          <PasswordInput
            id="pwd-confirm"
            value={confirm}
            onChange={setConfirm}
            show={showNext}
            autoComplete="new-password"
            required
            // tekrar alanını ayrı show toggle ile karmaşıklaştırmıyoruz
            onToggleShow={() => setShowNext((v) => !v)}
          />
        </div>

        {localError ? (
          <p className="text-sm text-destructive" role="alert">
            {localError}
          </p>
        ) : null}

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={mut.isPending}>
            {mut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <KeyRound className="size-4" aria-hidden />
            )}
            Şifreyi güncelle
          </Button>
          {mut.isSuccess && !mut.isPending ? (
            <span className="inline-flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="size-4" aria-hidden /> Güncellendi
            </span>
          ) : null}
        </div>
      </form>
    </SectionPanel>
  );
}

function PasswordInput({
  id,
  value,
  onChange,
  show,
  onToggleShow,
  autoComplete,
  required,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  show: boolean;
  onToggleShow: () => void;
  autoComplete?: string;
  required?: boolean;
}) {
  return (
    <div className="relative">
      <Input
        id={id}
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        required={required}
        className="pr-10"
      />
      <button
        type="button"
        onClick={onToggleShow}
        className="absolute inset-y-0 right-0 px-3 text-muted-foreground hover:text-foreground"
        aria-label={show ? "Şifreyi gizle" : "Şifreyi göster"}
        tabIndex={-1}
      >
        {show ? (
          <EyeOff className="size-4" aria-hidden />
        ) : (
          <Eye className="size-4" aria-hidden />
        )}
      </button>
    </div>
  );
}

function PasswordPolicyHint({ value }: { value: string }) {
  const rules: Array<{ test: boolean; label: string }> = [
    { test: value.length >= 8, label: "En az 8 karakter" },
    { test: /[A-Za-z]/.test(value), label: "Harf içeriyor" },
    { test: /\d/.test(value), label: "Rakam içeriyor" },
  ];
  return (
    <ul className="flex flex-wrap gap-2 text-xs">
      {rules.map((r, i) => (
        <li
          key={i}
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5",
            r.test
              ? "border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
              : "border-border text-muted-foreground",
          )}
        >
          <span
            className={cn(
              "inline-block size-1.5 rounded-full",
              r.test ? "bg-emerald-500" : "bg-muted-foreground/40",
            )}
          />
          {r.label}
        </li>
      ))}
    </ul>
  );
}
