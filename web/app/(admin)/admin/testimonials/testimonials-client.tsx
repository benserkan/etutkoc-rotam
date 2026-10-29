"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Star, Plus, Pencil, Eye, EyeOff, Clock, Trash2, Building2, User2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { getAdminTestimonials, testimonialKeys } from "@/lib/api/testimonials";
import {
  useCreateTestimonial,
  useDeleteTestimonial,
  useSetTestimonialStatus,
  useUpdateTestimonial,
} from "@/lib/hooks/use-admin-mutations";
import type {
  TestimonialAdminItem,
  TestimonialAdminListResponse,
  TestimonialCreateBody,
  TestimonialKind,
  TestimonialStatus,
} from "@/lib/types/testimonial";

const KIND_TONE: Record<string, string> = {
  review: "bg-sky-100 text-sky-800 border-sky-200",
  institution_ref: "bg-violet-100 text-violet-800 border-violet-200",
  success_story: "bg-amber-100 text-amber-800 border-amber-200",
};
const STATUS_TONE: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800 border-amber-200",
  published: "bg-emerald-100 text-emerald-800 border-emerald-200",
  hidden: "bg-slate-100 text-slate-600 border-slate-200",
};

function Pill({ children, tone }: { children: React.ReactNode; tone: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium", tone)}>
      {children}
    </span>
  );
}

function Stars({ n }: { n: number | null }) {
  if (!n) return null;
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`${n} yıldız`}>
      {Array.from({ length: 5 }).map((_, i) => (
        <Star key={i} className={cn("size-3.5", i < n ? "fill-amber-400 text-amber-400" : "text-slate-300")} aria-hidden />
      ))}
    </span>
  );
}

const STATUS_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "Tümü" },
  { key: "pending", label: "Bekleyen" },
  { key: "published", label: "Yayında" },
  { key: "hidden", label: "Gizli" },
];

export function TestimonialsClient({ initial }: { initial: TestimonialAdminListResponse }) {
  const [statusFilter, setStatusFilter] = React.useState<string>("");
  const [editing, setEditing] = React.useState<TestimonialAdminItem | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [deleting, setDeleting] = React.useState<TestimonialAdminItem | null>(null);

  const q = useQuery({
    queryKey: testimonialKeys.admin(statusFilter || null, null),
    queryFn: () => getAdminTestimonials(statusFilter || null, null),
    initialData: statusFilter === "" ? initial : undefined,
  });

  const data = q.data ?? initial;
  const counts = data.counts ?? {};
  const setStatus = useSetTestimonialStatus();
  const del = useDeleteTestimonial();

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      {/* Başlık paneli */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex size-9 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
              <Star className="size-5" aria-hidden />
            </span>
            <div>
              <h1 className="text-lg font-semibold">Sosyal Kanıt</h1>
              <p className="mt-0.5 max-w-2xl text-sm text-muted-foreground">
                Kullanıcı yorumları, kurum referansları ve başarı hikâyeleri. Buradan giriş yap,
                uygulama-içi gelen yorumları incele ve <strong>yayınla</strong> — yalnız “Yayında”
                olanlar anasayfada görünür. Kişisel ad/rol yalnız onayınızla yayınlanır (KVKK).
              </p>
            </div>
          </div>
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" aria-hidden /> Yeni Kayıt
          </Button>
        </div>

        {/* Sayım kartları */}
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <CountCard label="Bekleyen" value={counts.pending ?? 0} tone="text-amber-700" />
          <CountCard label="Yayında" value={counts.published ?? 0} tone="text-emerald-700" />
          <CountCard label="Gizli" value={counts.hidden ?? 0} tone="text-slate-600" />
          <CountCard label="Toplam" value={counts.total ?? 0} tone="text-foreground" />
        </div>
      </div>

      {/* Filtre */}
      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setStatusFilter(f.key)}
            className={cn(
              "rounded-full border px-3 py-1 text-sm transition-colors",
              statusFilter === f.key
                ? "border-foreground bg-foreground text-background"
                : "border-border text-muted-foreground hover:bg-muted",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Liste */}
      <div className="mt-4 space-y-3">
        {data.items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            Kayıt yok. “Yeni Kayıt” ile yorum/referans/başarı hikâyesi ekleyebilirsin.
          </p>
        ) : (
          data.items.map((t) => (
            <article key={t.id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Pill tone={KIND_TONE[t.kind] ?? "bg-slate-100 text-slate-700 border-slate-200"}>
                  {t.kind_label}
                </Pill>
                <Pill tone={STATUS_TONE[t.status] ?? "bg-slate-100 text-slate-700 border-slate-200"}>
                  {t.status_label}
                </Pill>
                {t.featured ? <Pill tone="bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200">Öne çıkan</Pill> : null}
                <span className="text-xs text-muted-foreground">· {t.source_label}</span>
                <Stars n={t.rating} />
              </div>

              <p className="mt-2 whitespace-pre-wrap text-sm text-foreground">{t.content}</p>

              <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1 font-medium text-foreground">
                  {t.kind === "institution_ref" ? <Building2 className="size-3.5" aria-hidden /> : <User2 className="size-3.5" aria-hidden />}
                  {t.author_name}
                </span>
                {t.author_role_label ? <span>· {t.author_role_label}</span> : null}
                {t.author_title ? <span>· {t.author_title}</span> : null}
                {t.institution_name ? <span>· {t.institution_name}</span> : null}
                {!t.consent_public ? <span className="text-rose-600">· ad yayın onayı yok</span> : null}
              </div>

              {/* Aksiyonlar */}
              <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-border pt-3">
                {t.status !== "published" ? (
                  <Button size="sm" variant="outline" onClick={() => setStatus.mutate({ id: t.id, status: "published" })} disabled={setStatus.isPending}>
                    <Eye className="size-4" aria-hidden /> Yayınla
                  </Button>
                ) : null}
                {t.status !== "hidden" ? (
                  <Button size="sm" variant="outline" onClick={() => setStatus.mutate({ id: t.id, status: "hidden" })} disabled={setStatus.isPending}>
                    <EyeOff className="size-4" aria-hidden /> Gizle
                  </Button>
                ) : null}
                {t.status !== "pending" ? (
                  <Button size="sm" variant="ghost" onClick={() => setStatus.mutate({ id: t.id, status: "pending" })} disabled={setStatus.isPending}>
                    <Clock className="size-4" aria-hidden /> Beklet
                  </Button>
                ) : null}
                <Button size="sm" variant="ghost" onClick={() => setEditing(t)}>
                  <Pencil className="size-4" aria-hidden /> Düzenle
                </Button>
                <Button size="sm" variant="ghost" className="text-rose-600 hover:text-rose-700" onClick={() => setDeleting(t)}>
                  <Trash2 className="size-4" aria-hidden /> Sil
                </Button>
              </div>
            </article>
          ))
        )}
      </div>

      {/* Oluştur / Düzenle dialog */}
      {(creating || editing) ? (
        <TestimonialFormDialog
          item={editing}
          kinds={data.kinds}
          roles={data.roles}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
        />
      ) : null}

      {/* Sil onayı */}
      <Dialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Kaydı sil?</DialogTitle>
            <DialogDescription>
              Bu sosyal kanıt kalıcı olarak silinir. Geri alınamaz.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleting(null)}>Vazgeç</Button>
            <Button
              className="bg-rose-600 text-white hover:bg-rose-700"
              disabled={del.isPending}
              onClick={() => {
                if (deleting) del.mutate(deleting.id, { onSuccess: () => setDeleting(null) });
              }}
            >
              Sil
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CountCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <p className={cn("text-2xl font-bold", tone)}>{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

const SELECT_CLS =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

function TestimonialFormDialog({
  item,
  kinds,
  roles,
  onClose,
}: {
  item: TestimonialAdminItem | null;
  kinds: Record<string, string>;
  roles: Record<string, string>;
  onClose: () => void;
}) {
  const isEdit = !!item;
  const create = useCreateTestimonial();
  const update = useUpdateTestimonial();

  const [kind, setKind] = React.useState<TestimonialKind>(item?.kind ?? "review");
  const [authorName, setAuthorName] = React.useState(item?.author_name ?? "");
  const [authorRole, setAuthorRole] = React.useState(item?.author_role ?? "");
  const [authorTitle, setAuthorTitle] = React.useState(item?.author_title ?? "");
  const [institutionName, setInstitutionName] = React.useState(item?.institution_name ?? "");
  const [rating, setRating] = React.useState<string>(item?.rating ? String(item.rating) : "");
  const [content, setContent] = React.useState(item?.content ?? "");
  const [statusV, setStatusV] = React.useState<TestimonialStatus>(item?.status ?? "published");
  const [consent, setConsent] = React.useState(item?.consent_public ?? true);
  const [featured, setFeatured] = React.useState(item?.featured ?? false);
  const [sortOrder, setSortOrder] = React.useState<string>(String(item?.sort_order ?? 0));

  const busy = create.isPending || update.isPending;

  function submit() {
    const base = {
      kind,
      author_name: authorName.trim(),
      author_role: authorRole || null,
      author_title: authorTitle.trim() || null,
      institution_name: institutionName.trim() || null,
      rating: rating ? Number(rating) : null,
      content: content.trim(),
      consent_public: consent,
      featured,
      sort_order: Number(sortOrder) || 0,
    };
    if (isEdit && item) {
      update.mutate({ id: item.id, body: base }, { onSuccess: onClose });
    } else {
      const body: TestimonialCreateBody = { ...base, status: statusV };
      create.mutate(body, { onSuccess: onClose });
    }
  }

  const canSubmit = authorName.trim().length >= 2 && content.trim().length >= 5;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Kaydı düzenle" : "Yeni sosyal kanıt"}</DialogTitle>
          <DialogDescription>
            Anasayfada gösterilecek yorum / kurum referansı / başarı hikâyesi.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium">Tür</label>
            <select className={SELECT_CLS} value={kind} onChange={(e) => setKind(e.target.value as TestimonialKind)}>
              {Object.entries(kinds).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Yorum / metin</label>
            <textarea
              className={cn(SELECT_CLS, "min-h-[120px] resize-y")}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Sistem hakkındaki yorum / referans metni…"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">Görünen ad</label>
              <Input value={authorName} onChange={(e) => setAuthorName(e.target.value)} placeholder="Örn. Z. A. / Demir Dershanesi" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Rol</label>
              <select className={SELECT_CLS} value={authorRole} onChange={(e) => setAuthorRole(e.target.value)}>
                <option value="">— seçilmedi —</option>
                {Object.entries(roles).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">Ünvan (opsiyonel)</label>
              <Input value={authorTitle} onChange={(e) => setAuthorTitle(e.target.value)} placeholder="Örn. 8. sınıf velisi" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Kurum adı (opsiyonel)</label>
              <Input value={institutionName} onChange={(e) => setInstitutionName(e.target.value)} placeholder="Kurum referansı için" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">Puan (1-5, opsiyonel)</label>
              <select className={SELECT_CLS} value={rating} onChange={(e) => setRating(e.target.value)}>
                <option value="">—</option>
                {[5, 4, 3, 2, 1].map((n) => (
                  <option key={n} value={n}>{n} yıldız</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Sıra (küçük = üstte)</label>
              <Input type="number" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />
            </div>
          </div>

          {!isEdit ? (
            <div>
              <label className="mb-1 block text-sm font-medium">Durum</label>
              <select className={SELECT_CLS} value={statusV} onChange={(e) => setStatusV(e.target.value as TestimonialStatus)}>
                <option value="published">Yayında (anasayfada görünür)</option>
                <option value="pending">Bekliyor</option>
                <option value="hidden">Gizli</option>
              </select>
            </div>
          ) : null}

          <div className="flex flex-col gap-2 pt-1">
            <label className="inline-flex items-center gap-2 text-sm">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="size-4" />
              Ad/rol yayınına onay var (KVKK)
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input type="checkbox" checked={featured} onChange={(e) => setFeatured(e.target.checked)} className="size-4" />
              Öne çıkar (anasayfada üstte)
            </label>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Vazgeç</Button>
          <Button onClick={submit} disabled={!canSubmit || busy}>
            {isEdit ? "Kaydet" : "Ekle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
