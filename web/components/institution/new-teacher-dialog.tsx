"use client";

import * as React from "react";
import { Check, Copy, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateInstitutionTeacher } from "@/lib/hooks/use-institution-mutations";
import type { TeacherCreateResult } from "@/lib/types/institution";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Yeni öğretmen dialog'u — Jinja `teachers_list.html:127-163` ile birebir.
 *
 * Akış:
 *   1) Ad + email gir → POST
 *   2) Yanıtta `temp_password` döner (tek seferlik)
 *   3) Dialog bu evrede başarı kartına geçer: şifre + "Kopyala" + güvenlik notu
 *   4) "Tamam" ile dialog kapanır; tekrar açıldığında temiz form
 */
export function NewTeacherDialog({ open, onOpenChange }: Props) {
  const mut = useCreateInstitutionTeacher();
  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [createdResult, setCreatedResult] =
    React.useState<TeacherCreateResult | null>(null);

  // Dialog kapandığında state'i sıfırla — bir sonraki açılışta temiz başla
  React.useEffect(() => {
    if (!open) {
      const t = setTimeout(() => {
        setFullName("");
        setEmail("");
        setCreatedResult(null);
        mut.reset();
      }, 200);
      return () => clearTimeout(t);
    }
  }, [open, mut]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!fullName.trim() || !email.trim()) return;
    mut.mutate(
      { full_name: fullName.trim(), email: email.trim().toLowerCase() },
      {
        onSuccess: (res) => {
          setCreatedResult(res.data);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {createdResult ? "Öğretmen oluşturuldu" : "Yeni Öğretmen"}
          </DialogTitle>
        </DialogHeader>

        {createdResult ? (
          <CreatedTeacherSuccess
            result={createdResult}
            onClose={() => onOpenChange(false)}
          />
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="ntn-name">
                Ad Soyad <span className="text-rose-500">*</span>
              </Label>
              <Input
                id="ntn-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                autoFocus
                placeholder="Öğretmenin tam adı"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ntn-email">
                E-posta <span className="text-rose-500">*</span>
              </Label>
              <Input
                id="ntn-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="ornek@okul.tr"
              />
            </div>

            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-900">
              <strong>🔐 Şifre güvenliği:</strong> Sistem güçlü geçici şifre
              üretecek. Öğretmen{" "}
              <strong>ilk girişte kendi şifresini belirlemek zorundadır</strong>
              . Geçici şifreyi öğretmene güvenli bir kanaldan iletin.
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
              <Button
                type="button"
                variant="ghost"
                onClick={() => onOpenChange(false)}
                disabled={mut.isPending}
              >
                İptal
              </Button>
              <Button type="submit" disabled={mut.isPending}>
                {mut.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : null}
                Oluştur
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function CreatedTeacherSuccess({
  result,
  onClose,
}: {
  result: TeacherCreateResult;
  onClose: () => void;
}) {
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(result.temp_password);
      setCopied(true);
      toast.success("Geçici şifre panoya kopyalandı.");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Kopyalama başarısız", {
        description: "Şifreyi manuel olarak seçip kopyalayın.",
      });
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-sm text-emerald-900">
        <strong>{result.full_name}</strong> başarıyla eklendi.
        <div className="text-xs text-emerald-800 mt-0.5 font-mono break-all">
          {result.email}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs uppercase tracking-wider text-muted-foreground">
          Geçici şifre (sadece bir kez görünür)
        </Label>
        <div className="flex items-center gap-2">
          <code className="flex-1 px-3 py-2 rounded-md border border-border bg-muted/50 font-mono text-sm break-all select-all">
            {result.temp_password}
          </code>
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={copy}
            aria-label="Şifreyi kopyala"
            title="Kopyala"
          >
            {copied ? (
              <Check className="size-4 text-emerald-600" aria-hidden />
            ) : (
              <Copy className="size-4" aria-hidden />
            )}
          </Button>
        </div>
      </div>

      <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-900">
        Geçici şifreyi öğretmene <strong>güvenli bir kanaldan</strong> iletin.
        Öğretmen <strong>ilk girişte kendi şifresini belirleyecek</strong>.
        Bu şifre bir daha gösterilmez.
      </div>

      <div className="flex items-center justify-end pt-2 border-t border-border">
        <Button onClick={onClose}>Tamam</Button>
      </div>
    </div>
  );
}
