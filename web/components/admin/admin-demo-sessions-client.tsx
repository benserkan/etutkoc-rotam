"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  FlaskConical,
  GraduationCap,
  Loader2,
  Tag,
  Trash2,
  User as UserIcon,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { adminKeys, getAdminDemoSessions } from "@/lib/api/admin";
import {
  useCreateDemoUniverse,
  useDeleteDemoSession,
} from "@/lib/hooks/use-admin-mutations";
import type {
  DemoKind,
  DemoSessionListItem,
  DemoSessionListResponse,
  DemoUniverseResult,
} from "@/lib/types/admin";
import { cn } from "@/lib/utils";

const KIND_LABEL: Record<DemoKind, string> = {
  institution: "Kurum",
  solo_coach: "Bağımsız Koç",
  institution_teacher: "Kuruma Bağlı Öğretmen",
};

const KIND_TONE: Record<DemoKind, string> = {
  institution: "border-indigo-200 bg-indigo-50 text-indigo-800 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200",
  solo_coach: "border-violet-200 bg-violet-50 text-violet-800 dark:bg-violet-500/10 dark:border-violet-500/30 dark:text-violet-200",
  institution_teacher: "border-sky-200 bg-sky-50 text-sky-800 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
};

function fmtRelative(iso: string): string {
  const d = new Date(iso);
  const now = Date.now();
  const diffMs = now - d.getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "az önce";
  if (minutes < 60) return `${minutes} dk önce`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} saat önce`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} gün önce`;
  // Tam tarih
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}.${d.getFullYear()}`;
}

interface Props {
  initial: DemoSessionListResponse;
}

export function AdminDemoSessionsClient({ initial }: Props) {
  const q = useQuery({
    queryKey: adminKeys.demoSessions(),
    queryFn: () => getAdminDemoSessions(),
    initialData: initial,
    staleTime: 30_000,
  });

  const items = q.data?.items ?? [];

  return (
    <div className="px-3 sm:px-6 py-4 max-w-5xl mx-auto">
      <header className="mb-5">
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <FlaskConical className="size-6 text-amber-700" aria-hidden />
          Demo Hesaplar
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Tanıtım için oluşturduğun demo ekosistemler. Her satır bir görüşme
          için yaratılmış kullanıcı grubudur. Görüşme bitince &quot;Sil&quot; tıkla —
          tüm bağlı kullanıcı + kurum + örnek veri cascade temizlenir.
        </p>
      </header>

      <UniverseCreator />

      {items.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center">
            <FlaskConical
              className="size-12 text-muted-foreground mx-auto mb-3"
              aria-hidden
            />
            <p className="text-sm text-muted-foreground">
              Henüz demo ekosistem oluşturmadın.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              <code className="bg-muted px-1 py-0.5 rounded">/admin/users</code>{" "}
              sayfasındaki <b>&quot;Demo Aç&quot;</b> butonuyla oluşturabilirsin.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <DemoSessionCard key={item.seed_id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}

function UniverseCreator() {
  const [label, setLabel] = React.useState("");
  const [coachCount, setCoachCount] = React.useState(3);
  const [studentsPerCoach, setStudentsPerCoach] = React.useState(5);
  const [withAudio, setWithAudio] = React.useState(false);
  const [result, setResult] = React.useState<DemoUniverseResult | null>(null);
  const create = useCreateDemoUniverse();

  function handleCreate() {
    create.mutate(
      {
        label: label.trim(),
        coach_count: coachCount,
        students_per_coach: studentsPerCoach,
        with_audio: withAudio,
      },
      { onSuccess: (res) => setResult(res) },
    );
  }

  function copyAll() {
    if (!result) return;
    const lines = [
      `${result.label} — demo hesaplar (şifre tümü: ${result.password})`,
      ...result.accounts.map(
        (a) =>
          `${a.role_label}${a.group ? ` [${a.group}]` : ""}: ${a.full_name} · ${a.email}`,
      ),
    ];
    void navigator.clipboard.writeText(lines.join("\n"));
  }

  const totalAccounts = 1 + coachCount + coachCount * studentsPerCoach * 2;

  return (
    <>
      <Card className="mb-5 border-cyan-200 dark:border-cyan-500/30">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-1">
            <Building2 className="size-4 text-cyan-700" aria-hidden />
            <h2 className="text-sm font-semibold">
              Dolu Kurumsal Evren Oluştur
            </h2>
          </div>
          <p className="text-xs text-muted-foreground mb-3">
            &quot;Aylardır kullanılıyor&quot; hissi veren tam demo: 10 haftalık görev
            geçmişi + gerçek karne kopyaları + yanlış soru arşivi + anket
            analizleri + seans raporları + yapay zekâ içgörüleri + Rota veli
            yorumları. Tüm hesaplar birbirine bağlı kurulur.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
            <label className="block sm:col-span-2">
              <span className="text-xs font-medium">Kurum / hesap adı</span>
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Örn. Marhan Akademi"
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium">Koç sayısı</span>
              <select
                value={coachCount}
                onChange={(e) => setCoachCount(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
              >
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium">Öğrenci / koç</span>
              <select
                value={studentsPerCoach}
                onChange={(e) => setStudentsPerCoach(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
              >
                {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="mt-3 flex items-center justify-between gap-3 flex-wrap">
            <label className="inline-flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={withAudio}
                onChange={(e) => setWithAudio(e.target.checked)}
                className="size-3.5"
              />
              <span>
                Rota veli yorumlarına <b>gerçek ses</b> üret (kurulum uzar,
                yapay zekâ seslendirme kullanır)
              </span>
            </label>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">
                Toplam {totalAccounts} hesap (her öğrenciye 1 veli)
              </span>
              <Button
                size="sm"
                onClick={handleCreate}
                disabled={create.isPending || label.trim().length < 3}
                className="bg-cyan-700 hover:bg-cyan-800 text-white"
              >
                {create.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <FlaskConical className="size-4" aria-hidden />
                )}
                Evreni Kur
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Sonuç dialogu — hesaplar anında, kurulum arka planda */}
      <Dialog open={result !== null} onOpenChange={(o) => !o && setResult(null)}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FlaskConical className="size-4 text-cyan-700" aria-hidden />
              {result?.label} — hesaplar hazırlanıyor
            </DialogTitle>
          </DialogHeader>
          {result ? (
            <div className="space-y-3 py-1">
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
                {result.note}
              </p>
              <p className="text-sm">
                Şifre (tüm hesaplar):{" "}
                <code className="bg-muted px-1.5 py-0.5 rounded font-semibold">
                  {result.password}
                </code>
              </p>
              <div className="border rounded-md overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b bg-muted/50 text-left">
                      <th className="px-2 py-1.5 font-medium">Rol</th>
                      <th className="px-2 py-1.5 font-medium">Ad</th>
                      <th className="px-2 py-1.5 font-medium">E-posta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.accounts.map((a) => (
                      <tr key={a.email} className="border-b last:border-0">
                        <td className="px-2 py-1 whitespace-nowrap">
                          {a.role_label}
                          {a.group ? (
                            <span className="ml-1 text-muted-foreground">
                              [{a.group}]
                            </span>
                          ) : null}
                        </td>
                        <td className="px-2 py-1 whitespace-nowrap">{a.full_name}</td>
                        <td className="px-2 py-1 font-mono">{a.email}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={copyAll}>
              Tümünü kopyala
            </Button>
            <Button onClick={() => setResult(null)}>Kapat</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function DemoSessionCard({ item }: { item: DemoSessionListItem }) {
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const del = useDeleteDemoSession();

  function handleDelete() {
    del.mutate(
      { seedId: item.seed_id },
      {
        onSuccess: () => setConfirmOpen(false),
      },
    );
  }

  return (
    <>
      <Card>
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-2">
                <FlaskConical
                  className="size-4 text-amber-700 flex-shrink-0"
                  aria-hidden
                />
                {item.label ? (
                  <h2 className="text-base font-semibold text-foreground truncate">
                    {item.label}
                  </h2>
                ) : (
                  <h2 className="text-base font-medium text-muted-foreground italic">
                    Etiketsiz demo
                  </h2>
                )}
                <span
                  className={cn(
                    "text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded border",
                    KIND_TONE[item.kind],
                  )}
                >
                  {KIND_LABEL[item.kind]}
                </span>
              </div>
              <div className="flex items-center gap-4 flex-wrap text-xs text-muted-foreground">
                {item.institution_name ? (
                  <span className="inline-flex items-center gap-1">
                    <Building2 className="size-3.5" aria-hidden />
                    {item.institution_name}
                  </span>
                ) : null}
                <span className="inline-flex items-center gap-1">
                  <UserIcon className="size-3.5" aria-hidden />
                  {item.user_count} kullanıcı
                </span>
                {item.student_count > 0 ? (
                  <span className="inline-flex items-center gap-1">
                    <GraduationCap className="size-3.5" aria-hidden />
                    {item.student_count} öğrenci
                  </span>
                ) : null}
                <span>Oluşturuldu: {fmtRelative(item.created_at)}</span>
              </div>
              <div className="mt-2 text-[10px] font-mono text-muted-foreground/60">
                ID: {item.seed_id.slice(0, 16)}…
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmOpen(true)}
              className="border-rose-300 text-rose-700 hover:bg-rose-50"
            >
              <Trash2 className="size-3.5" aria-hidden />
              Sil
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Confirm dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-rose-800">
              <Trash2 className="size-4" aria-hidden />
              Bu demo seansını sil?
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm">
              <b>{item.label || "Etiketsiz demo"}</b> seansının tüm kayıtları
              cascade silinecek:
            </p>
            <ul className="text-sm space-y-1 ml-4 list-disc text-muted-foreground">
              <li>{item.user_count} kullanıcı</li>
              {item.institution_name ? (
                <li>1 kurum ({item.institution_name})</li>
              ) : null}
              <li>Tüm örnek görev/deneme/seans/kitap verileri</li>
            </ul>
            <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
              Yalnız <code>is_demo=True</code> kayıtlara dokunulur. Gerçek
              hesaplar etkilenmez.
            </p>
            <p className="text-xs italic text-muted-foreground">
              <Tag className="inline size-3 mr-1" aria-hidden />
              Bu işlem geri alınamaz.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              disabled={del.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={handleDelete}
              disabled={del.isPending}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              {del.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Trash2 className="size-4" aria-hidden />
              )}
              Sil
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export { fmtRelative as _fmtRelative };
