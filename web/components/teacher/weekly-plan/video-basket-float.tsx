"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Check,
  ChevronDown,
  Copy,
  ExternalLink,
  GripVertical,
  History,
  Loader2,
  PencilLine,
  RefreshCw,
  PlaySquare,
  Trash2,
  Undo2,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { getTeacherStudents, teacherKeys } from "@/lib/api/teacher";
import type { TeacherStudentListResponse } from "@/lib/types/teacher";
import {
  getVideoBasket,
  useCopyVideos,
  useDeleteVideo,
  useDeleteVideoGroup,
  useDeleteVideoSource,
  useImportVideos,
  usePatchVideo,
  usePatchVideoGroup,
  usePatchVideoSource,
  useUnplaceVideo,
  VIDEO_MIME,
  videoBasketKeys,
  type VideoBasketResponse,
  type VideoDragPayload,
  type VideoGroup,
  type VideoItem,
  type VideoRole,
  type VideoSource,
} from "@/lib/api/video-basket";

/**
 * Video Sepeti — hafta ekranında YÜZEN pencere (sayfaya sabit; kaydırınca
 * yerinde durur → Hafta Izgarası ile aynı anda görünür).
 *
 * Akış: oynatma listesi / video linki yapıştır → sistem videoları konu
 * gruplarına ayırır → video ya da grubun tamamı ızgaradaki güne sürüklenir.
 * Aynı gün + aynı konu tek görevde toplanır; 60 dk'yı geçen gün uyarı alır.
 */

// Rol renkleri: soru çözümü/checkpoint anlatımdan ayrı görünsün (koç kararı).
const ROLE_TONE: Record<VideoRole, { dot: string; chip: string }> = {
  anlatim: { dot: "bg-cyan-600", chip: "bg-cyan-600 text-white" },
  soru: { dot: "bg-amber-500", chip: "bg-amber-600 text-white" },
  tekrar: { dot: "bg-violet-600", chip: "bg-violet-600 text-white" },
  diger: { dot: "bg-slate-400", chip: "bg-slate-600 text-white" },
};
const ROLE_OPTIONS: { v: VideoRole; l: string }[] = [
  { v: "anlatim", l: "Konu anlatımı" },
  { v: "soru", l: "Soru çözümü" },
  { v: "tekrar", l: "Tekrar / özet" },
  { v: "diger", l: "Diğer" },
];

function startDrag(e: React.DragEvent, payload: VideoDragPayload) {
  e.dataTransfer.setData(VIDEO_MIME, JSON.stringify(payload));
  e.dataTransfer.effectAllowed = "copy";
}

function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}.${m}`;
}

/** Öğrenciye göre video durumu (sepet öğrenci başına — durum da öyle).
 *  bekliyor: hiç verilmedi · programda: bugün/ileri bir güne verildi ·
 *  izlenmedi: geçmiş bir güne verildi ama görev tamamlanmadı · izlendi: görev
 *  tamamlandı. Dört durum zemin tonu + dolgulu rozetle ayrışır. */
type VideoState = "bekliyor" | "programda" | "izlenmedi" | "izlendi";

function todayIso(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function videoState(v: VideoItem, today: string): VideoState {
  if (v.status === "watched") return "izlendi";
  if (v.status === "planned") {
    return v.task_date && v.task_date < today ? "izlenmedi" : "programda";
  }
  return "bekliyor";
}

const STATE_META: Record<VideoState, { label: string; row: string; badge: string }> = {
  bekliyor: { label: "Verilmedi", row: "", badge: "bg-slate-500 text-white" },
  programda: {
    label: "Programda",
    row: "border-l-4 border-l-sky-500 bg-sky-500/10",
    badge: "bg-sky-600 text-white",
  },
  izlenmedi: {
    label: "Verildi, izlenmedi",
    row: "border-l-4 border-l-amber-500 bg-amber-500/15",
    badge: "bg-amber-600 text-white",
  },
  izlendi: {
    label: "İzlendi",
    row: "border-l-4 border-l-emerald-500 bg-emerald-500/15",
    badge: "bg-emerald-700 text-white",
  },
};
const STATE_ORDER: VideoState[] = ["izlendi", "izlenmedi", "programda", "bekliyor"];

export function VideoBasketFloat({
  studentId,
  subjects,
}: {
  studentId: number;
  subjects: { id: number; name: string }[];
}) {
  const [open, setOpen] = React.useState(false);
  const q = useQuery<VideoBasketResponse>({
    queryKey: videoBasketKeys.basket(studentId),
    queryFn: () => getVideoBasket(studentId),
    staleTime: 30_000,
  });
  const waiting = q.data?.waiting_count ?? 0;
  // Sepet LİSTE LİSTE gösterilir: yeni getirilen liste eskisine karışmaz.
  // null = otomatik (en son kullanılan, sepette videosu olan liste).
  const [picked, setPicked] = React.useState<ListFilter | null>(null);
  const groups = q.data?.groups ?? [];
  const sources = q.data?.sources ?? [];
  const inBasket = sources.filter((s) => s.in_basket > 0);
  const hasLoose = groups.some((g) => g.source_id == null);
  const valid = (f: ListFilter | null) =>
    f === "all" ||
    (f === "none" && hasLoose) ||
    (typeof f === "number" && inBasket.some((s) => s.id === f));
  const active: ListFilter =
    picked !== null && valid(picked)
      ? picked
      : inBasket[0]
        ? inBasket[0].id
        : hasLoose
          ? "none"
          : "all";
  const shownGroups =
    active === "all"
      ? groups
      : active === "none"
        ? groups.filter((g) => g.source_id == null)
        : groups.filter((g) => g.source_id === active);

  return (
    <>
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          data-section="week:video-basket-fab"
          className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full bg-cyan-700 px-4 py-2.5 text-sm font-semibold text-white shadow-lg hover:bg-cyan-800"
          title="Video Sepeti — oynatma listesinden günlere sürükle"
        >
          <PlaySquare className="size-4" aria-hidden />
          Video Sepeti
          {waiting > 0 ? (
            <span className="rounded-full bg-white px-1.5 text-[11px] font-bold text-cyan-800">
              {waiting}
            </span>
          ) : null}
        </button>
      ) : (
        <div
          data-section="week:video-basket"
          className="fixed bottom-4 right-4 z-40 flex max-h-[min(80vh,720px)] w-[min(380px,calc(100vw-2rem))] flex-col rounded-xl border border-border bg-card shadow-2xl"
        >
          <div className="flex items-center gap-2 border-b border-border px-3 py-2">
            <PlaySquare className="size-4 text-cyan-700 dark:text-cyan-300" aria-hidden />
            <span className="text-sm font-semibold text-foreground">Video Sepeti</span>
            <span className="text-[11px] text-muted-foreground">
              {waiting} video bekliyor
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="ml-auto rounded p-1 text-muted-foreground hover:bg-muted"
              aria-label="Kapat"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <ImportForm
              studentId={studentId}
              subjects={subjects}
              configured={q.data?.youtube_configured ?? true}
              onImported={(sid) => {
                if (sid != null) setPicked(sid);
              }}
            />
            {sources.length > 0 ? (
              <SavedSources
                studentId={studentId}
                subjects={subjects}
                sources={sources}
                onShow={(sid) => setPicked(sid)}
              />
            ) : null}
            <p className="px-3 pb-2 text-[11px] text-muted-foreground">
              Videoyu ya da grubun başlığını Hafta Izgarası&apos;ndaki bir güne sürükle.
              Aynı gün + aynı konu tek görevde toplanır.
            </p>
            {q.isLoading && !q.data ? (
              <div className="flex items-center gap-2 px-3 py-3 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" aria-hidden /> Yükleniyor…
              </div>
            ) : groups.length === 0 ? (
              <p className="px-3 pb-3 text-xs italic text-muted-foreground">
                Sepet boş. Yukarıya bir YouTube oynatma listesi linki yapıştır ya da kayıtlı
                listelerinden birini getir.
              </p>
            ) : (
              <>
                <div className="px-3 pb-2">
                  <label
                    className="block text-[11px] font-medium text-muted-foreground"
                    htmlFor="vb-list"
                  >
                    Gösterilen liste
                  </label>
                  <select
                    id="vb-list"
                    value={String(active)}
                    onChange={(e) => {
                      const v = e.target.value;
                      setPicked(v === "all" || v === "none" ? v : Number(v));
                    }}
                    className="mt-0.5 w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                    data-section="week:video-basket-list"
                  >
                    {inBasket.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} — {s.in_basket} video, {s.waiting} bekliyor
                      </option>
                    ))}
                    {hasLoose ? <option value="none">Listesiz / tek videolar</option> : null}
                    <option value="all">Tüm listeler birlikte</option>
                  </select>
                </div>
                <BasketList key={String(active)} studentId={studentId} groups={shownGroups} />
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function ImportForm({
  studentId,
  subjects,
  configured,
  onImported,
}: {
  studentId: number;
  subjects: { id: number; name: string }[];
  configured: boolean;
  onImported: (sourceId: number | null) => void;
}) {
  const [url, setUrl] = React.useState("");
  const [subjectId, setSubjectId] = React.useState<string>("");
  const imp = useImportVideos(studentId);
  return (
    <form
      className="space-y-2 px-3 py-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (!url.trim()) return;
        imp.mutate(
          { url: url.trim(), subject_id: subjectId ? Number(subjectId) : null },
          {
            onSuccess: (res) => {
              setUrl("");
              onImported(res.data.source_id);
            },
          },
        );
      }}
    >
      {!configured ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
          YouTube anahtarı henüz tanımlı değil — süper admin AI Ayarları&apos;ndan girilince
          liste alınabilir.
        </p>
      ) : null}
      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="YouTube oynatma listesi ya da video linki"
        className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
      />
      <div className="flex gap-2">
        <select
          value={subjectId}
          onChange={(e) => setSubjectId(e.target.value)}
          className="min-w-0 flex-1 rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          aria-label="Ders"
        >
          <option value="">Ders seç (konu eşleşmesi için)</option>
          {subjects.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={imp.isPending || !url.trim()}
          className="inline-flex shrink-0 items-center gap-1 rounded-md bg-cyan-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-cyan-800 disabled:opacity-50"
        >
          {imp.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
          Getir
        </button>
      </div>
      {imp.isPending ? (
        <p className="text-[11px] text-muted-foreground">
          Videolar okunuyor ve konulara ayrılıyor…
        </p>
      ) : null}
    </form>
  );
}

type ListFilter = number | "none" | "all";

function dayLabel(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/** Koçun daha önce getirdiği listeler — YouTube'da tekrar aramaya gerek kalmaz. */
function SavedSources({
  studentId,
  subjects,
  sources,
  onShow,
}: {
  studentId: number;
  subjects: { id: number; name: string }[];
  sources: VideoSource[];
  onShow: (sourceId: number) => void;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="mx-3 mb-2 rounded-md border border-border" data-section="week:video-sources">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 px-2 py-1.5 text-left text-xs font-semibold text-foreground"
        aria-expanded={open}
      >
        <History className="size-3.5 text-cyan-700 dark:text-cyan-300" aria-hidden />
        Kayıtlı listelerim ({sources.length})
        <ChevronDown
          className={cn(
            "ml-auto size-3.5 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>
      {open ? (
        <ul className="space-y-1.5 border-t border-border/60 p-2">
          {sources.map((s) => (
            <SourceRow
              key={s.id}
              studentId={studentId}
              subjects={subjects}
              src={s}
              onShow={onShow}
            />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function SourceRow({
  studentId,
  subjects,
  src,
  onShow,
}: {
  studentId: number;
  subjects: { id: number; name: string }[];
  src: VideoSource;
  onShow: (sourceId: number) => void;
}) {
  const imp = useImportVideos(studentId);
  const patch = usePatchVideoSource();
  const del = useDeleteVideoSource();
  const [editing, setEditing] = React.useState(false);
  const [label, setLabel] = React.useState(src.label ?? src.name);
  const [subjectId, setSubjectId] = React.useState(String(src.subject_id ?? ""));
  const [confirming, setConfirming] = React.useState(false);
  const [removeWaiting, setRemoveWaiting] = React.useState(false);

  return (
    <li className="rounded-md border border-border px-2 py-1.5">
      {editing ? (
        <form
          className="space-y-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            patch.mutate(
              {
                sourceId: src.id,
                body: { label: label.trim(), subject_id: subjectId ? Number(subjectId) : 0 },
              },
              { onSuccess: () => setEditing(false) },
            );
          }}
        >
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={src.title ?? "Liste adı"}
            aria-label="Liste adı"
            className="w-full rounded border border-border bg-background px-1.5 py-1 text-xs"
            autoFocus
          />
          <select
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            aria-label="Ders"
            className="w-full rounded border border-border bg-background px-1.5 py-1 text-xs"
          >
            <option value="">Ders yok</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <div className="flex justify-end gap-1.5">
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted"
            >
              Vazgeç
            </button>
            <button
              type="submit"
              disabled={patch.isPending}
              className="rounded bg-cyan-700 px-2 py-0.5 text-xs font-medium text-white disabled:opacity-50"
            >
              Kaydet
            </button>
          </div>
        </form>
      ) : (
        <div className="flex items-start gap-1.5">
          <div className="min-w-0 flex-1">
            <p className="break-words text-xs font-medium text-foreground">{src.name}</p>
            {src.label && src.title && src.label !== src.title ? (
              <p className="break-words text-[10px] text-muted-foreground">
                YouTube adı: {src.title}
              </p>
            ) : null}
            <p className="text-[10px] text-muted-foreground">
              {src.subject_name ? `${src.subject_name} · ` : ""}
              {src.video_count} video · son kullanım {dayLabel(src.last_used_at)}
              {src.in_basket > 0 ? ` · sepette ${src.in_basket}` : " · bu öğrencide yok"}
            </p>
          </div>
          <div className="flex shrink-0 items-center">
            {src.in_basket > 0 ? (
              <button
                type="button"
                onClick={() => onShow(src.id)}
                className="rounded px-1.5 py-0.5 text-[11px] font-medium text-cyan-800 hover:bg-muted dark:text-cyan-200"
              >
                Göster
              </button>
            ) : null}
            <IconBtn
              label={
                src.in_basket > 0
                  ? "Listeye sonradan eklenen videoları getir"
                  : "Bu öğrencinin sepetine getir"
              }
              onClick={() => imp.mutate({ source_id: src.id }, { onSuccess: () => onShow(src.id) })}
            >
              {imp.isPending ? (
                <Loader2 className="size-3 animate-spin" aria-hidden />
              ) : (
                <RefreshCw className="size-3" aria-hidden />
              )}
            </IconBtn>
            <a
              href={src.url}
              target="_blank"
              rel="noreferrer"
              title="YouTube'da aç"
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <ExternalLink className="size-3" aria-hidden />
            </a>
            <IconBtn
              label="Adını / dersini düzenle"
              onClick={() => {
                setLabel(src.label ?? src.name);
                setSubjectId(String(src.subject_id ?? ""));
                setConfirming(false);
                setEditing(true);
              }}
            >
              <PencilLine className="size-3" aria-hidden />
            </IconBtn>
            <IconBtn label="Kayıtlı listeyi sil" onClick={() => setConfirming((v) => !v)}>
              <Trash2 className="size-3" aria-hidden />
            </IconBtn>
          </div>
        </div>
      )}
      {confirming && !editing ? (
        <div className="mt-1.5 space-y-1.5 rounded border border-rose-200 bg-rose-50 px-2 py-1.5 text-[11px] text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
          <p>Liste kayıtlardan silinsin mi? Programa konmuş videolar ve görevler kalır.</p>
          {src.waiting > 0 ? (
            <label className="flex items-start gap-1.5">
              <input
                type="checkbox"
                checked={removeWaiting}
                onChange={(e) => setRemoveWaiting(e.target.checked)}
                className="mt-0.5"
              />
              Bu öğrencinin sepetinde bekleyen {src.waiting} videoyu da kaldır
            </label>
          ) : null}
          <div className="flex justify-end gap-1.5">
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="rounded px-2 py-0.5 hover:bg-rose-100 dark:hover:bg-rose-500/20"
            >
              Vazgeç
            </button>
            <button
              type="button"
              disabled={del.isPending}
              onClick={() =>
                del.mutate({
                  sourceId: src.id,
                  student_id: studentId,
                  remove_waiting: removeWaiting,
                })
              }
              className="rounded bg-rose-600 px-2 py-0.5 font-medium text-white disabled:opacity-50"
            >
              Sil
            </button>
          </div>
        </div>
      ) : null}
    </li>
  );
}

function BasketList({ studentId, groups }: { studentId: number; groups: VideoGroup[] }) {
  const [onlyWaiting, setOnlyWaiting] = React.useState(false);
  const today = todayIso();
  const shown = onlyWaiting ? groups.filter((g) => g.waiting_count > 0) : groups;
  return (
    <div className="space-y-2 px-3 pb-3">
      <div
        data-section="week:video-state-legend"
        className="flex flex-wrap items-center gap-1 text-[10px]"
      >
        {STATE_ORDER.map((st) => (
          <span key={st} className={cn("rounded px-1.5 py-0.5 font-medium", STATE_META[st].badge)}>
            {STATE_META[st].label}
          </span>
        ))}
      </div>
      <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
        <input
          type="checkbox"
          checked={onlyWaiting}
          onChange={(e) => setOnlyWaiting(e.target.checked)}
        />
        Yalnız verilmeyen videolar
      </label>
      {shown.length === 0 ? (
        <p className="text-xs italic text-muted-foreground">
          Verilmeyen video kalmadı — hepsi programda.
        </p>
      ) : (
        shown.map((g) => (
          <GroupCard
            key={g.group_key}
            studentId={studentId}
            group={g}
            onlyWaiting={onlyWaiting}
            today={today}
          />
        ))
      )}
    </div>
  );
}

function GroupCard({
  studentId,
  group,
  onlyWaiting,
  today,
}: {
  studentId: number;
  group: VideoGroup;
  onlyWaiting: boolean;
  today: string;
}) {
  // Uzun listede panel dolmasın: gruplar kapalı gelir, başlığa tıklayınca açılır.
  const [collapsed, setCollapsed] = React.useState(true);
  const [editing, setEditing] = React.useState(false);
  const [label, setLabel] = React.useState(group.label);
  const [copyOpen, setCopyOpen] = React.useState(false);
  const patchGroup = usePatchVideoGroup(studentId);
  const delGroup = useDeleteVideoGroup(studentId);
  const items = onlyWaiting ? group.items.filter((i) => i.status === "waiting") : group.items;
  const waitingIds = group.items.filter((i) => i.status === "waiting").map((i) => i.id);
  const stateCounts = STATE_ORDER.map((st) => ({
    st,
    n: group.items.filter((i) => videoState(i, today) === st).length,
  })).filter((c) => c.n > 0 && c.st !== "bekliyor");

  return (
    <div className="rounded-lg border border-border">
      <div
        draggable={waitingIds.length > 0 && !editing}
        onDragStart={(e) =>
          startDrag(e, { itemIds: waitingIds, label: `${group.label} (${waitingIds.length} video)` })
        }
        className={cn(
          "flex items-start gap-1.5 rounded-t-lg bg-muted/40 px-2 py-1.5",
          waitingIds.length > 0 && "cursor-grab active:cursor-grabbing",
        )}
        title={waitingIds.length > 0 ? "Bekleyen videoların tümünü bir güne sürükle" : undefined}
      >
        <GripVertical className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden />
        <div className="min-w-0 flex-1">
          {editing ? (
            <form
              className="flex gap-1"
              onSubmit={(e) => {
                e.preventDefault();
                patchGroup.mutate(
                  { group_key: group.group_key, label },
                  { onSuccess: () => setEditing(false) },
                );
              }}
            >
              <input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="min-w-0 flex-1 rounded border border-border bg-background px-1.5 py-0.5 text-xs"
                autoFocus
              />
              <button type="submit" className="rounded bg-cyan-700 p-1 text-white" aria-label="Kaydet">
                <Check className="size-3" aria-hidden />
              </button>
            </form>
          ) : (
            <button
              type="button"
              onClick={() => setCollapsed((v) => !v)}
              aria-expanded={!collapsed}
              className="block w-full break-words text-left text-xs font-semibold text-foreground hover:underline"
            >
              {group.label}
            </button>
          )}
          <p className="text-[10px] text-muted-foreground">
            {group.subject_name ? `${group.subject_name} · ` : ""}
            {group.topic_name ? "müfredata bağlı" : "konu eşleşmedi"} · {group.items.length} video ·{" "}
            {group.total_min} dk
          </p>
          {stateCounts.length > 0 ? (
            <div className="mt-0.5 flex flex-wrap gap-1 text-[10px]">
              {stateCounts.map((c) => (
                <span key={c.st} className={cn("rounded px-1 font-medium", STATE_META[c.st].badge)}>
                  {c.n} {STATE_META[c.st].label.toLocaleLowerCase("tr")}
                </span>
              ))}
            </div>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center">
          <IconBtn label="Grubu yeniden adlandır" onClick={() => { setLabel(group.label); setEditing((v) => !v); }}>
            <PencilLine className="size-3" aria-hidden />
          </IconBtn>
          <IconBtn label="Başka öğrenciye kopyala" onClick={() => setCopyOpen((v) => !v)}>
            <Copy className="size-3" aria-hidden />
          </IconBtn>
          <IconBtn
            label="Bekleyen videoları sepetten sil"
            onClick={() => {
              if (window.confirm(`"${group.label}" grubundaki bekleyen videolar sepetten silinsin mi? Programdakiler kalır.`)) {
                delGroup.mutate({ group_key: group.group_key });
              }
            }}
          >
            <Trash2 className="size-3" aria-hidden />
          </IconBtn>
          <IconBtn label={collapsed ? "Aç" : "Katla"} onClick={() => setCollapsed((v) => !v)}>
            <ChevronDown className={cn("size-3 transition-transform", collapsed ? "" : "rotate-180")} aria-hidden />
          </IconBtn>
        </div>
      </div>
      {copyOpen ? (
        <CopyToStudent
          studentId={studentId}
          groupKey={group.group_key}
          onDone={() => setCopyOpen(false)}
        />
      ) : null}
      {collapsed ? null : (
        <ul className="divide-y divide-border/60">
          {items.map((v) => (
            <VideoRow key={v.id} v={v} state={videoState(v, today)} />
          ))}
        </ul>
      )}
    </div>
  );
}

function IconBtn({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
    >
      {children}
    </button>
  );
}

function VideoRow({ v, state }: { v: VideoItem; state: VideoState }) {
  const patch = usePatchVideo();
  const del = useDeleteVideo();
  const unplace = useUnplaceVideo();
  const waiting = v.status === "waiting";
  const tone = ROLE_TONE[v.role] ?? ROLE_TONE.anlatim;
  return (
    <li
      draggable={waiting}
      onDragStart={(e) => startDrag(e, { itemIds: [v.id], label: v.title })}
      className={cn(
        "flex items-start gap-1.5 px-2 py-1.5",
        waiting && "cursor-grab active:cursor-grabbing",
        STATE_META[state].row,
      )}
      data-video-state={state}
    >
      <span className={cn("mt-1 size-2 shrink-0 rounded-full", tone.dot)} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="break-words text-xs text-foreground">{v.title}</p>
        <div className="mt-0.5 flex flex-wrap items-center gap-1 text-[10px] text-muted-foreground">
          {v.duration_min ? <span>{v.duration_min} dk</span> : null}
          <select
            value={v.role}
            onChange={(e) => patch.mutate({ itemId: v.id, body: { role: e.target.value as VideoRole } })}
            className={cn("rounded px-1 py-0 text-[10px] font-medium", tone.chip)}
            aria-label="Video rolü"
          >
            {ROLE_OPTIONS.map((o) => (
              <option key={o.v} value={o.v} className="bg-background text-foreground">
                {o.l}
              </option>
            ))}
          </select>
          {state !== "bekliyor" ? (
            <span className={cn("rounded px-1 font-medium", STATE_META[state].badge)}>
              {state === "programda" ? "programda" : STATE_META[state].label.toLocaleLowerCase("tr")}
              {v.task_date ? ` · ${shortDate(v.task_date)}` : ""}
            </span>
          ) : null}
        </div>
      </div>
      <div className="flex shrink-0 items-center">
        <a
          href={v.url}
          target="_blank"
          rel="noreferrer"
          title="YouTube'da aç"
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ExternalLink className="size-3" aria-hidden />
        </a>
        {v.status === "planned" ? (
          <IconBtn label="Programdan çıkar (sepete dön)" onClick={() => unplace.mutate({ itemId: v.id })}>
            <Undo2 className="size-3" aria-hidden />
          </IconBtn>
        ) : null}
        {v.status !== "watched" ? (
          <IconBtn
            label="Sepetten sil"
            onClick={() => {
              if (window.confirm("Video sepetten silinsin mi?")) del.mutate({ itemId: v.id });
            }}
          >
            <Trash2 className="size-3" aria-hidden />
          </IconBtn>
        ) : null}
      </div>
    </li>
  );
}

function CopyToStudent({
  studentId,
  groupKey,
  onDone,
}: {
  studentId: number;
  groupKey: string;
  onDone: () => void;
}) {
  const params = { status: "aktif" as const, page_size: 200 };
  const q = useQuery<TeacherStudentListResponse>({
    queryKey: teacherKeys.studentsList(params),
    queryFn: () => getTeacherStudents(params),
    staleTime: 60_000,
  });
  const [target, setTarget] = React.useState("");
  const copy = useCopyVideos(studentId);
  const others = (q.data?.items ?? []).filter((s) => s.id !== studentId);
  return (
    <div className="flex gap-1.5 border-b border-border/60 bg-muted/20 px-2 py-1.5">
      <select
        value={target}
        onChange={(e) => setTarget(e.target.value)}
        className="min-w-0 flex-1 rounded border border-border bg-background px-1.5 py-1 text-xs"
        aria-label="Hedef öğrenci"
      >
        <option value="">Öğrenci seç…</option>
        {others.map((s) => (
          <option key={s.id} value={s.id}>
            {s.full_name}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={!target || copy.isPending}
        onClick={() =>
          copy.mutate(
            { target_student_id: Number(target), group_keys: [groupKey] },
            { onSuccess: onDone },
          )
        }
        className="shrink-0 rounded bg-cyan-700 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
      >
        Kopyala
      </button>
    </div>
  );
}
