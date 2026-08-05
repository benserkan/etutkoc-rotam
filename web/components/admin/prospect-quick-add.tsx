"use client";

/**
 * Hedef Havuzu — MOBİL hızlı ekleme (2026-08-05).
 *
 * Kullanım senaryosu: Serkan telefonunda Instagram'da koç hesaplarını geziyor.
 * İşletme profilindeki "Ara" düğmesinden numarayı kopyalıyor → bu sekmeye
 * geçiyor → yapıştır → Ekle. Hedef: kişi başına ~20 saniye.
 *
 * iOS notları (Safari):
 * - Tüm inputlar >= 16px font: küçük fontta Safari odakta SAYFAYI ZOOMLAR ve
 *   kullanıcı her alanda geri çıkmak zorunda kalır.
 * - `inputMode="tel"` → numara tuş takımı; `autoCapitalize="none"` +
 *   `autoCorrect="off"` → Instagram kullanıcı adını bozmaz.
 * - Dokunma hedefleri >= 44px (Apple HIG).
 * - Eklendikten sonra wa.me linki YENİ SEKMEDE açılır → iOS WhatsApp
 *   uygulamasına devreder; metin hazır gelir, gönderi tuşuna kullanıcı basar
 *   (Faz 1 Click-to-WhatsApp deseni — Cloud API numarası yakılmaz).
 */
import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Check, Loader2, MessageCircle, Plus, UserPlus } from "lucide-react";

import { adminKeys, getAdminProspects, getAdminWhatsAppTemplates } from "@/lib/api/admin";
import { useCreateProspect } from "@/lib/hooks/use-admin-mutations";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const TEMPLATE_KEY = "koc_kesif_ilk_temas";

/** Şablon bulunamazsa (seed koşmamışsa) kullanılan yedek metin. */
const FALLBACK_MESSAGE =
  "Merhaba {{koc_adi}}, ben Serkan Aydın — Trabzon'da öğrenci koçluğu yapıyorum. " +
  "Paylaşımlarınızı takip ediyorum.\n\nKendi öğrencilerim için bir sistem geliştirdim: " +
  "deneme karnesinin PDF'ini yüklüyorsun, yapay zekâ soru soru konu analizini çıkarıyor; " +
  "veliye durumu sesli anlatıyor.\n\nSatış için yazmıyorum — sahada olan bir meslektaş " +
  "olarak fikrinizi merak ediyorum: işinize yarar mı, eksiği ne?\n\nTek seferlik yazıyorum; " +
  "ilgilenmezseniz rahatsız etmem. İyi çalışmalar.";

type Added = { name: string; phone: string; instagram: string | null };

export function ProspectQuickAdd() {
  const [name, setName] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [instagram, setInstagram] = React.useState("");
  const [city, setCity] = React.useState("");
  const [note, setNote] = React.useState("");
  const [kind, setKind] = React.useState<"coach" | "institution">("coach");
  const [added, setAdded] = React.useState<Added | null>(null);
  const [session, setSession] = React.useState<Added[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const nameRef = React.useRef<HTMLInputElement>(null);

  const mut = useCreateProspect();

  // Mesaj şablonu (tek kaynak: WhatsApp Şablonları paneli)
  const tplQ = useQuery({
    queryKey: adminKeys.whatsappTemplates("admin_yonetici", null, false),
    queryFn: () => getAdminWhatsAppTemplates("admin_yonetici", null, false),
    staleTime: 10 * 60_000,
  });
  const template =
    tplQ.data?.items.find((t) => t.key === TEMPLATE_KEY)?.content_template ??
    FALLBACK_MESSAGE;

  // Bugünkü toplam (spam raylarını göz önünde tut: günde 10-15 hedefi)
  const listQ = useQuery({
    queryKey: adminKeys.prospects("", "", ""),
    queryFn: () => getAdminProspects("", "", ""),
    staleTime: 60_000,
  });
  const total = listQ.data?.items.length ?? 0;

  function waHref(a: Added): string {
    const first = (a.name.split(" ")[0] || a.name).trim();
    const text = template.replace(/\{\{koc_adi\}\}/g, first);
    return `https://wa.me/${a.phone}?text=${encodeURIComponent(text)}`;
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const n = name.trim();
    const p = phone.trim();
    if (n.length < 2) { setError("Ad en az 2 karakter olmalı."); return; }
    if (!p) { setError("Telefon zorunlu."); return; }
    mut.mutate(
      {
        name: n, phone: p, kind,
        instagram: instagram.trim() || null,
        city: city.trim() || null,
        note: note.trim() || null,
        source: "manual",
        opt_in: false,
      },
      {
        onSuccess: (res) => {
          const rec: Added = {
            name: res.data.name, phone: res.data.phone,
            instagram: res.data.instagram ?? null,
          };
          setAdded(rec);
          setSession((s) => [rec, ...s].slice(0, 20));
          setName(""); setPhone(""); setInstagram(""); setCity(""); setNote("");
        },
        onError: (err) => {
          const msg = (err as { detail?: { message?: string } })?.detail?.message;
          setError(msg ?? "Eklenemedi.");
        },
      },
    );
  }

  return (
    <div className="mx-auto w-full max-w-md space-y-4 pb-24">
      <div className="flex items-center justify-between gap-2">
        <Link href="/admin/prospects" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          <ArrowLeft className="size-4" aria-hidden /> Havuz
        </Link>
        <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
          Havuzda {total} kayıt
        </span>
      </div>

      <div>
        <h1 className="text-xl font-bold">Hızlı ekle</h1>
        <p className="mt-0.5 text-[13px] leading-snug text-muted-foreground">
          Instagram&apos;da koç hesabını aç → <b>Ara</b> düğmesinden numarayı kopyala →
          buraya yapıştır. Yalnız <b>işletme iletişimi yayımlı</b> hesapları ekle.
        </p>
      </div>

      {/* Eklendi kartı — hemen WhatsApp'a geçiş */}
      {added ? (
        <Card className="border-emerald-300 bg-emerald-50 p-4 dark:bg-emerald-500/10 dark:border-emerald-500/30">
          <p className="flex items-center gap-2 text-sm font-semibold text-emerald-900 dark:text-emerald-200">
            <Check className="size-4" aria-hidden /> {added.name} havuza eklendi
          </p>
          <a
            href={waHref(added)}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 text-base font-semibold text-white active:bg-emerald-700"
          >
            <MessageCircle className="size-5" aria-hidden /> WhatsApp&apos;ta aç (metin hazır)
          </a>
          <button
            type="button"
            onClick={() => { setAdded(null); nameRef.current?.focus(); }}
            className="mt-2 flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl border border-emerald-300 bg-white text-sm font-medium text-emerald-800 active:bg-emerald-50"
          >
            <Plus className="size-4" aria-hidden /> Yeni kişi ekle
          </button>
        </Card>
      ) : null}

      <Card className="p-4">
        <form onSubmit={submit} method="post" className="space-y-3">
          {/* Tür — büyük dokunma hedefi */}
          <div className="grid grid-cols-2 gap-2">
            {([["coach", "Bağımsız Koç"], ["institution", "Kurum"]] as const).map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => setKind(k)}
                className={
                  "min-h-[44px] rounded-xl border text-sm font-semibold transition " +
                  (kind === k
                    ? "border-cyan-600 bg-cyan-50 text-cyan-900 dark:bg-cyan-500/15 dark:text-cyan-200"
                    : "border-input bg-background text-muted-foreground")
                }
              >
                {label}
              </button>
            ))}
          </div>

          <Field label="Ad / İşletme *">
            <input
              ref={nameRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ayşe Yılmaz"
              autoCapitalize="words"
              className={INPUT}
            />
          </Field>

          <Field label="Telefon *">
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="0555 123 45 67"
              inputMode="tel"
              autoComplete="tel"
              className={INPUT}
            />
          </Field>

          <Field label="Instagram">
            <input
              value={instagram}
              onChange={(e) => setInstagram(e.target.value)}
              placeholder="@kullaniciadi"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              className={INPUT}
            />
          </Field>

          <div className="grid grid-cols-2 gap-2">
            <Field label="Şehir">
              <input
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="Trabzon"
                autoCapitalize="words"
                className={INPUT}
              />
            </Field>
            <Field label="Not">
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="12 bin takipçi"
                className={INPUT}
              />
            </Field>
          </div>

          {error ? (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-[13px] font-medium text-rose-800 dark:bg-rose-500/10 dark:text-rose-300">
              {error}
            </p>
          ) : null}

          <Button
            type="submit"
            disabled={mut.isPending}
            className="min-h-[52px] w-full bg-cyan-700 text-base font-semibold text-white hover:bg-cyan-800 active:bg-cyan-900"
          >
            {mut.isPending ? <Loader2 className="size-5 animate-spin" aria-hidden />
                           : <UserPlus className="size-5" aria-hidden />}
            Havuza ekle
          </Button>
        </form>
      </Card>

      {/* Bu oturumda eklenenler — "ekledim mi?" sorusunu anında yanıtlar */}
      {session.length ? (
        <div>
          <p className="mb-1.5 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Bu oturumda eklediklerin ({session.length})
          </p>
          <Card className="divide-y divide-border">
            {session.map((a) => (
              <div key={a.phone} className="flex items-center justify-between gap-2 px-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{a.name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {a.phone}{a.instagram ? ` · @${a.instagram}` : ""}
                  </p>
                </div>
                <a
                  href={waHref(a)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex size-11 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-700 active:bg-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-400"
                  aria-label={`${a.name} — WhatsApp'ta aç`}
                >
                  <MessageCircle className="size-5" aria-hidden />
                </a>
              </div>
            ))}
          </Card>
        </div>
      ) : null}

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        Kayıtlar <b>izinsiz (opt-in yok)</b> olarak eklenir. Mesaj kendi telefonundan,
        birebir gider; günde <b>10-15</b> mesajı geçme. Yanıt gelirse durum
        Havuz&apos;dan &quot;İletişim kuruldu&quot;ya çekilir.
      </p>
    </div>
  );
}

// iOS: 16px altı fontta Safari odakta sayfayı zoomlar → text-base sabit.
const INPUT =
  "w-full rounded-xl border border-input bg-background px-3 py-3 text-base " +
  "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-cyan-600";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
