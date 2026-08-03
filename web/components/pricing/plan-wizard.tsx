"use client";

/**
 * Paket Seçim Sihirbazı (2026-08-04, kullanıcı fikri).
 *
 * "Kaç öğrencin var?" tek kriter DEĞİL — öğrenci sayısı yalnız TABANI belirler
 * (sert kapasite tavanı). Gerçek ihtiyacı üç şey daha şekillendirir:
 *   1. AI karne okuma yoğunluğu (deneme sonucu PDF'leri → kredi ihtiyacı)
 *   2. Veli asistanı kapsamı (en büyük kredi tüketicisi: kaç veliye açık)
 *   3. Kurulum desteği ihtiyacı (Zirve'nin hizmet ayrıcalığı)
 *
 * Sihirbaz 4 soru sorar, tahmini aylık kredi ihtiyacını GERÇEK işlem
 * maliyetlerinden (catalog.credit_costs — tek kaynak) hesaplar; kapasite
 * paketinin tahsisi yetmiyorsa bir üst paketi gerekçesiyle önerir.
 * Sihirbazı atlamak isteyen alttaki hazır kartlardan seçer.
 */
import * as React from "react";
import { ArrowLeft, Check, Sparkles, Wand2 } from "lucide-react";

import { cn } from "@/lib/utils";
import type { PricingCatalog, SoloTier } from "@/lib/types/pricing";

type ExamUse = "none" | "some" | "full";
type ParentAi = "none" | "few" | "all";
type Setup = "self" | "assisted";

interface Answers {
  students: number;
  examUse: ExamUse | null;
  parentAi: ParentAi | null;
  setup: Setup | null;
}

interface Recommendation {
  tier: SoloTier | null; // null = Keşif (ücretsiz)
  freeLabel: string;
  reasons: string[];
  estimatedCredits: number;
  allocation: number;
  zirveNote: boolean; // kurulum desteği istedi ama önerilen Zirve değil
}

function costOf(catalog: PricingCatalog, needle: string, fallback: number): number {
  const row = (catalog.credit_costs ?? []).find((r) =>
    r.label.toLocaleLowerCase("tr-TR").includes(needle),
  );
  return row?.credits ?? fallback;
}

function computeRecommendation(catalog: PricingCatalog, a: Answers): Recommendation {
  const tiers = catalog.solo.tiers;
  const freeLabel = catalog.cards.find((c) => c.key === "free")?.name ?? "Keşif";
  const freeCap = catalog.solo.free.students;
  const creditsByCode: Record<string, number> = {};
  for (const c of catalog.cards) {
    if (c.audience === "solo" && c.credits_monthly) creditsByCode[c.plan] = c.credits_monthly;
  }

  // Gerçek işlem maliyetleri (tek kaynak) — bulunamazsa güncel varsayılanlar.
  const karne = costOf(catalog, "karne", 6);
  const veliYorum = costOf(catalog, "veli sesli", 8);
  const veliSoru = costOf(catalog, "sohbet", 3);
  const ysa = costOf(catalog, "yanlış", 2);
  const icgoru = costOf(catalog, "hazırlık", 6);

  // Öğrenci başına tahmini aylık kredi
  const karnePerStudent = a.examUse === "full" ? 2.5 : a.examUse === "some" ? 1 : 0;
  // Veli: aylık ~4 sesli yorum + ~8 sohbet sorusu (aktif veli başına)
  const perParent = 4 * veliYorum + 8 * veliSoru;
  const parentShare = a.parentAi === "all" ? 1 : a.parentAi === "few" ? 0.3 : 0;
  const anyAi = a.examUse !== "none" || a.parentAi !== "none";
  const basePerStudent = anyAi ? 4 * ysa + icgoru : 0; // YSA etiket + ayda 1 içgörü
  const perStudent =
    karnePerStudent * karne + parentShare * perParent + basePerStudent;
  const estimated = Math.round(a.students * perStudent);

  const reasons: string[] = [];

  // Ücretsiz yeterli mi? (kapasite + AI istemiyor)
  if (a.students <= freeCap && !anyAi && a.setup !== "assisted") {
    reasons.push(`${a.students} öğrenci ${freeLabel}'in ${freeCap} öğrenci kapasitesine sığıyor`);
    reasons.push("Yapay zekâ özelliği istemedin — çekirdek takip ücretsiz pakette tam");
    return { tier: null, freeLabel, reasons, estimatedCredits: 0, allocation: 0, zirveNote: false };
  }

  // Kapasite tabanı
  let idx = tiers.findIndex(
    (t) => t.max_students == null || a.students <= t.max_students,
  );
  if (idx < 0) idx = tiers.length - 1;
  const capTier = tiers[idx];
  if (a.students <= freeCap && anyAi) {
    reasons.push(
      `${a.students} öğrenci ücretsiz pakete sığar ama yapay zekâ istediğin için ücretli paket gerekir`,
    );
  } else {
    reasons.push(
      `${a.students} öğrenci → ${capTier.max_students == null ? "sınırsız kapasite" : `${capTier.max_students} öğrenci kapasitesi`} (${capTier.label})`,
    );
  }

  // Kredi ihtiyacı tahsisi aşıyorsa bir üst paket (%85 konfor payı)
  let finalIdx = idx;
  const capAlloc = creditsByCode[capTier.code] ?? 0;
  if (estimated > capAlloc * 0.85 && idx < tiers.length - 1) {
    finalIdx = idx + 1;
    reasons.push(
      `Tahmini aylık ihtiyacın ~${estimated.toLocaleString("tr-TR")} kredi — ${capTier.label}'nın ${capAlloc.toLocaleString("tr-TR")} kredisi sıkışır, ${tiers[finalIdx].label} rahat karşılar`,
    );
  } else if (anyAi) {
    reasons.push(
      `Tahmini aylık ihtiyacın ~${estimated.toLocaleString("tr-TR")} kredi — ${tiers[finalIdx].label}'nın ${(creditsByCode[tiers[finalIdx].code] ?? 0).toLocaleString("tr-TR")} kredisi rahat karşılar`,
    );
  }

  // Birebir kurulum isteği → Zirve ayrıcalığı
  const last = tiers.length - 1;
  let zirveNote = false;
  if (a.setup === "assisted") {
    if (finalIdx === last) {
      reasons.push(`Birebir kurulum ve taşıma desteği ${tiers[last].label}'de dahil`);
    } else {
      zirveNote = true;
    }
  }
  if (a.parentAi === "all" && finalIdx >= 1) {
    reasons.push("Veli asistanı tam kapasite kullanımı bu pakette rahat çalışır");
  }

  const tier = tiers[finalIdx];
  return {
    tier,
    freeLabel,
    reasons,
    estimatedCredits: estimated,
    allocation: creditsByCode[tier.code] ?? 0,
    zirveNote,
  };
}

function OptionButton({
  title,
  desc,
  selected,
  onClick,
}: {
  title: string;
  desc?: string;
  selected?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded-xl border-2 px-4 py-3 text-left transition",
        selected
          ? "border-cyan-600 bg-cyan-50"
          : "border-slate-200 bg-white hover:border-cyan-300",
      )}
    >
      <span className="block text-sm font-semibold text-slate-900">{title}</span>
      {desc ? <span className="mt-0.5 block text-xs text-slate-600">{desc}</span> : null}
    </button>
  );
}

export function PlanWizard({
  catalog,
  onSkip,
}: {
  catalog: PricingCatalog;
  onSkip?: () => void;
}) {
  const [step, setStep] = React.useState(0);
  const [a, setA] = React.useState<Answers>({
    students: 10,
    examUse: null,
    parentAi: null,
    setup: null,
  });
  const done = step === 4;
  const rec = done ? computeRecommendation(catalog, a) : null;
  const trialDays = catalog.solo.trial_days;

  const next = () => setStep((s) => Math.min(4, s + 1));
  const back = () => setStep((s) => Math.max(0, s - 1));

  return (
    <div className="mx-auto mt-8 max-w-xl rounded-2xl border border-cyan-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-display text-base font-bold text-slate-900">
          <Wand2 className="size-4 text-cyan-700" aria-hidden />
          Paket seçim sihirbazı
        </h2>
        <div className="flex items-center gap-1" aria-hidden>
          {[0, 1, 2, 3].map((i) => (
            <span
              key={i}
              className={cn(
                "h-1.5 w-5 rounded-full",
                i <= Math.min(step, 3) ? "bg-cyan-600" : "bg-slate-200",
              )}
            />
          ))}
        </div>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        4 kısa soruyla gerçekte hangi pakete ihtiyacın olduğunu birlikte bulalım —
        ya da{" "}
        <button type="button" onClick={onSkip} className="font-medium text-cyan-700 underline">
          atla, kartlardan kendim seçeyim
        </button>
        .
      </p>

      <div className="mt-5">
        {step === 0 ? (
          <div>
            <p className="text-sm font-semibold text-slate-900">1 · Kaç öğrencin var?</p>
            <input
              type="range"
              min={1}
              max={40}
              value={a.students}
              onChange={(e) => setA({ ...a, students: Number(e.target.value) })}
              className="mt-3 w-full accent-cyan-700"
            />
            <p className="mt-1 text-center text-sm text-slate-700">
              <span className="font-display text-xl font-extrabold">
                {a.students >= 40 ? "40+" : a.students}
              </span>{" "}
              öğrenci
              <span className="ml-2 text-xs text-muted-foreground">
                (yakında büyüyeceksen hedefini seç)
              </span>
            </p>
            <WizardNav onNext={next} />
          </div>
        ) : step === 1 ? (
          <div className="space-y-2">
            <p className="text-sm font-semibold text-slate-900">
              2 · Deneme karnelerini (deneme sonucu PDF dosyası) yapay zekâya okutmak ister misin?
            </p>
            <p className="text-xs text-muted-foreground">
              Karneyi yüklersin; sistem soru soru okuyup konu analizini çıkarır — elle giriş yerine.
            </p>
            <OptionButton
              title="Hayır, denemeleri elle girerim"
              desc="Net takibi yine tam çalışır"
              selected={a.examUse === "none"}
              onClick={() => { setA({ ...a, examUse: "none" }); next(); }}
            />
            <OptionButton
              title="Ara sıra — önemli denemelerde"
              desc="Öğrenci başına ayda ~1 karne"
              selected={a.examUse === "some"}
              onClick={() => { setA({ ...a, examUse: "some" }); next(); }}
            />
            <OptionButton
              title="Evet, her denemede"
              desc="Öğrenci başına ayda 2-3 karne — konu analizi hep güncel"
              selected={a.examUse === "full"}
              onClick={() => { setA({ ...a, examUse: "full" }); next(); }}
            />
            <WizardNav onBack={back} />
          </div>
        ) : step === 2 ? (
          <div className="space-y-2">
            <p className="text-sm font-semibold text-slate-900">
              3 · Velilere yapay zekâ asistanı (Rota) açmak ister misin?
            </p>
            <p className="text-xs text-muted-foreground">
              Veli, çocuğunun durumunu Rota&apos;dan sesli yorum ve sohbetle öğrenir —
              &quot;bu hafta ne yaptı?&quot; telefonları azalır.
            </p>
            <OptionButton
              title="Şimdilik hayır"
              desc="Veliye e-posta raporu yine gider"
              selected={a.parentAi === "none"}
              onClick={() => { setA({ ...a, parentAi: "none" }); next(); }}
            />
            <OptionButton
              title="Birkaç veliye"
              desc="En çok soran velilerle başla"
              selected={a.parentAi === "few"}
              onClick={() => { setA({ ...a, parentAi: "few" }); next(); }}
            />
            <OptionButton
              title="Tüm velilere"
              desc="Veli memnuniyeti = kayıt yenileme"
              selected={a.parentAi === "all"}
              onClick={() => { setA({ ...a, parentAi: "all" }); next(); }}
            />
            <WizardNav onBack={back} />
          </div>
        ) : step === 3 ? (
          <div className="space-y-2">
            <p className="text-sm font-semibold text-slate-900">4 · Kuruluma nasıl başlamak istersin?</p>
            <OptionButton
              title="Kendim kurarım"
              desc="Sesli rehber turu adım adım yol gösterir"
              selected={a.setup === "self"}
              onClick={() => { setA({ ...a, setup: "self" }); next(); }}
            />
            <OptionButton
              title="Birebir destek istiyorum"
              desc="Kitaplarını ve öğrencilerini birlikte kuralım (Zirve ayrıcalığı)"
              selected={a.setup === "assisted"}
              onClick={() => { setA({ ...a, setup: "assisted" }); next(); }}
            />
            <WizardNav onBack={back} />
          </div>
        ) : rec ? (
          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-cyan-700">
              Sana uygun paket
            </p>
            <div className="mt-2 flex items-baseline justify-between gap-3">
              <h3 className="font-display text-2xl font-extrabold text-slate-900">
                {rec.tier ? rec.tier.label : rec.freeLabel}
              </h3>
              <p className="text-lg font-bold text-slate-900">
                {rec.tier ? `${rec.tier.monthly.toLocaleString("tr-TR")} ₺/ay` : "Ücretsiz"}
              </p>
            </div>
            <ul className="mt-3 space-y-1.5">
              {rec.reasons.map((r) => (
                <li key={r} className="flex items-start gap-2 text-sm text-slate-700">
                  <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
                  {r}
                </li>
              ))}
            </ul>
            {rec.zirveNote ? (
              <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                <Sparkles className="mr-1 inline size-3.5" aria-hidden />
                Birebir kurulum desteği <strong>Zirve</strong>&apos;de dahil. İstersen
                Zirve ile başlayıp kurulum bitince paketini düşürebilirsin.
              </p>
            ) : null}
            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <a
                href={
                  rec.tier
                    ? `/signup/teacher?plan=${encodeURIComponent(rec.tier.code)}`
                    : "/signup/teacher"
                }
                className="inline-flex flex-1 items-center justify-center rounded-lg bg-cyan-700 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-cyan-800"
              >
                {rec.tier ? `${trialDays} gün ücretsiz dene` : "Ücretsiz başla"}
              </a>
              <button
                type="button"
                onClick={onSkip}
                className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Kartları incele
              </button>
            </div>
            <button
              type="button"
              onClick={() => setStep(0)}
              className="mt-3 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="size-3.5" aria-hidden /> Baştan başla
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function WizardNav({ onBack, onNext }: { onBack?: () => void; onNext?: () => void }) {
  return (
    <div className="mt-4 flex items-center justify-between">
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" aria-hidden /> Geri
        </button>
      ) : (
        <span />
      )}
      {onNext ? (
        <button
          type="button"
          onClick={onNext}
          className="rounded-lg bg-cyan-700 px-5 py-2 text-sm font-bold text-white hover:bg-cyan-800"
        >
          Devam
        </button>
      ) : (
        <span />
      )}
    </div>
  );
}
