"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus } from "lucide-react";

import { useCreateStudent } from "@/lib/hooks/use-teacher-mutations";
import type {
  GraduateMode,
  StudentCreateBody,
  StudentCreateResult,
  Track,
} from "@/lib/types/teacher";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const TRACK_OPTIONS: Array<{ value: Track; label: string }> = [
  { value: "sayisal", label: "Sayısal" },
  { value: "ea", label: "Eşit Ağırlık" },
  { value: "sozel", label: "Sözel" },
  { value: "dil", label: "Dil" },
];

const GRADUATE_MODE_OPTIONS: Array<{ value: GraduateMode; label: string }> = [
  { value: "full_time", label: "Tam zamanlı" },
  { value: "dershane", label: "Dershane" },
];

/**
 * Yeni öğrenci ekleme modalı — başarıda backend'in dönen `temp_password`'unu
 * tek seferlik gösterir; kullanıcı manuel kopyalar.
 */
export function StudentCreateButton() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [result, setResult] = React.useState<StudentCreateResult | null>(null);
  const mut = useCreateStudent();

  function handleClose(o: boolean) {
    if (mut.isPending) return;
    setOpen(o);
    if (!o) {
      setResult(null);
      if (result) router.refresh();
    }
  }

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <Plus className="size-4" aria-hidden />
        Yeni öğrenci
      </Button>
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {result ? "Öğrenci eklendi" : "Yeni öğrenci"}
            </DialogTitle>
          </DialogHeader>
          {result ? (
            <TempPasswordPanel
              result={result}
              onDone={() => handleClose(false)}
            />
          ) : (
            <CreateForm
              isPending={mut.isPending}
              onCancel={() => handleClose(false)}
              onSubmit={(body) =>
                mut.mutate(
                  { body },
                  {
                    onSuccess: (res) => setResult(res.data),
                  },
                )
              }
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function CreateForm({
  onSubmit,
  onCancel,
  isPending,
}: {
  onSubmit: (body: StudentCreateBody) => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [grade, setGrade] = React.useState<string>("8");
  const [isGraduate, setIsGraduate] = React.useState(false);
  const [track, setTrack] = React.useState<Track | "">("");
  const [graduateMode, setGraduateMode] = React.useState<GraduateMode | "">("");
  const [error, setError] = React.useState<string | null>(null);

  const trackRequired = isGraduate || Number(grade) >= 11;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const fn = fullName.trim();
    const em = email.trim().toLowerCase();
    if (!fn) {
      setError("Ad Soyad zorunlu.");
      return;
    }
    if (!em.includes("@")) {
      setError("Geçerli bir e-posta girin.");
      return;
    }
    const gradeNum = isGraduate ? null : Number(grade);
    if (!isGraduate && (!Number.isFinite(gradeNum) || gradeNum! < 5 || gradeNum! > 12)) {
      setError("Sınıf 5-12 aralığında olmalı.");
      return;
    }
    if (trackRequired && !track) {
      setError("11. sınıf, 12. sınıf ve mezunlar için alan zorunlu.");
      return;
    }
    if (isGraduate && !graduateMode) {
      setError("Mezun öğrenciler için çalışma şekli zorunlu.");
      return;
    }
    onSubmit({
      full_name: fn,
      email: em,
      grade_level: gradeNum,
      is_graduate: isGraduate,
      track: track || null,
      graduate_mode: isGraduate ? graduateMode || null : null,
    });
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor="cs-name">Ad Soyad</Label>
        <Input
          id="cs-name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="cs-email">E-posta</Label>
        <Input
          id="cs-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="cs-grade">Sınıf</Label>
          <select
            id="cs-grade"
            value={isGraduate ? "graduate" : grade}
            onChange={(e) => {
              const v = e.target.value;
              if (v === "graduate") {
                setIsGraduate(true);
              } else {
                setIsGraduate(false);
                setGrade(v);
              }
            }}
            className={cn(
              "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            {[5, 6, 7, 8, 9, 10, 11, 12].map((g) => (
              <option key={g} value={String(g)}>
                {g}. sınıf
              </option>
            ))}
            <option value="graduate">Mezun</option>
          </select>
        </div>
        {trackRequired ? (
          <div className="space-y-1">
            <Label htmlFor="cs-track">Alan</Label>
            <select
              id="cs-track"
              value={track}
              onChange={(e) => setTrack(e.target.value as Track | "")}
              className={cn(
                "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
              required
            >
              <option value="">— Seç —</option>
              {TRACK_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        ) : null}
      </div>
      {isGraduate ? (
        <div className="space-y-1">
          <Label htmlFor="cs-gmode">Çalışma şekli</Label>
          <select
            id="cs-gmode"
            value={graduateMode}
            onChange={(e) => setGraduateMode(e.target.value as GraduateMode | "")}
            className={cn(
              "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
            required
          >
            <option value="">— Seç —</option>
            {GRADUATE_MODE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex items-center justify-end gap-2 pt-2">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={isPending}>
          İptal
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          Ekle
        </Button>
      </div>
    </form>
  );
}

function TempPasswordPanel({
  result,
  onDone,
}: {
  result: StudentCreateResult;
  onDone: () => void;
}) {
  return (
    <div className="space-y-4">
      <p className="text-sm">
        <strong>{result.full_name}</strong> başarıyla eklendi. Aşağıdaki geçici
        parolayı öğrenciye iletin — bu kez bir daha gösterilmeyecek.
      </p>
      <div className="rounded-md border border-border bg-muted p-3 font-mono text-sm break-all">
        {result.temp_password}
      </div>
      <p className="text-xs text-muted-foreground">
        Öğrenci ilk girişte parolasını değiştirmelidir. E-posta: {result.email}
      </p>
      <div className="flex items-center justify-end pt-2">
        <Button onClick={onDone}>Tamam</Button>
      </div>
    </div>
  );
}
