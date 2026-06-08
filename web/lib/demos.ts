/**
 * Demo Kütüphanesi — TEK KAYNAK (registry).
 *
 * Her demo: rol (kim için) + contextKey (uygulamada NEREYİ anlattığı / journey
 * adımı). Tüm yüzeyler buradan beslenir:
 *   1. Panel-içi "▶ Nasıl kullanılır?" rozeti  (DemoHint, contextKey ile)
 *   2. /demos kütüphanesi (rol-sekmeli + sıralı liste)
 *   3. Anasayfa "Nasıl çalışır — İzle" galerisi (rol-sekmeli vitrin)
 *   4. Pano "Başlarken" onboarding checklist'i
 *   5. Anasayfa bilgi kartlarındaki "Demo İzle" (kart↔demo bağlam eşleşmesi)
 *
 * Yeni demo eklemek = buraya 1 satır → ilgili her yerde otomatik belirir.
 * Format: sahne + sesli anlatım (Jinja oynatıcı). Oynatma: /demos?play={slug}.
 *
 * Kaynak: app/templates/landing/demos.html playlist (35 demo, 4 rol).
 */

export type DemoRole = "teacher" | "student" | "parent" | "institution_admin";

export interface DemoEntry {
  slug: string; // /demos?play={slug}
  role: DemoRole;
  contextKey: string; // uygulamadaki yer / journey adımı (panel eşleşmesi)
  title: string;
  durationLabel: string;
  order: number; // rol içi journey sırası (kütüphane/galeri/onboarding sıralama)
  status: "published" | "coming_soon";
}

const DUR = "8 sahne · ~2 dk";

export const DEMOS: DemoEntry[] = [
  // ============================ KOÇ (öğretmen) ============================
  { slug: "book-add-coach", role: "teacher", contextKey: "library", title: "Kitap Ekleme ve Kütüphane", durationLabel: DUR, order: 1, status: "published" },
  { slug: "program-create-coach", role: "teacher", contextKey: "program", title: "Haftalık Program Oluşturma", durationLabel: DUR, order: 2, status: "published" },
  { slug: "week-grid-coach", role: "teacher", contextKey: "week-grid", title: "Hafta Izgarası (Koç)", durationLabel: DUR, order: 3, status: "published" },
  { slug: "sessions-coach", role: "teacher", contextKey: "sessions", title: "Seanslar + Yapay Zekâ (Koç)", durationLabel: DUR, order: 4, status: "published" },
  { slug: "dna-coach", role: "teacher", contextKey: "dna", title: "Çalışma DNA (Koç)", durationLabel: DUR, order: 5, status: "published" },
  { slug: "review-cards-coach", role: "teacher", contextKey: "review", title: "Tekrar Kartları (Koç)", durationLabel: DUR, order: 6, status: "published" },
  { slug: "focus-coach", role: "teacher", contextKey: "focus", title: "Odaklı Çalışma (Koç)", durationLabel: DUR, order: 7, status: "published" },
  { slug: "goals-coach", role: "teacher", contextKey: "goals", title: "Hedefler (Koç)", durationLabel: DUR, order: 8, status: "published" },
  { slug: "topic-performance", role: "teacher", contextKey: "topic-performance", title: "Konu Performansı", durationLabel: DUR, order: 9, status: "published" },
  { slug: "task-request-coach", role: "teacher", contextKey: "requests", title: "Öğrenci Taleplerini Yönetme (Koç)", durationLabel: DUR, order: 10, status: "published" },
  { slug: "support-system-coach", role: "teacher", contextKey: "support", title: "Destek / İletişim (Koç)", durationLabel: DUR, order: 11, status: "published" },
  { slug: "whatsapp-coach", role: "teacher", contextKey: "whatsapp", title: "WhatsApp ile Veli İletişimi (Koç)", durationLabel: DUR, order: 12, status: "published" },
  { slug: "billing-coach", role: "teacher", contextKey: "billing", title: "Tahsilat (Koç)", durationLabel: DUR, order: 13, status: "published" },
  { slug: "academic-years-coach", role: "teacher", contextKey: "academic-years", title: "Akademik Yıllar (Koç)", durationLabel: DUR, order: 14, status: "published" },
  { slug: "promote-grade-coach", role: "teacher", contextKey: "grade-advance", title: "Sınıf Yükseltme (Koç)", durationLabel: DUR, order: 15, status: "published" },

  // ============================ ÖĞRENCİ ============================
  { slug: "daily-manage-student", role: "student", contextKey: "day", title: "Programımı Günlük Yönetme", durationLabel: DUR, order: 1, status: "published" },
  { slug: "week-grid-student", role: "student", contextKey: "week", title: "Hafta Izgarası (Öğrenci)", durationLabel: DUR, order: 2, status: "published" },
  { slug: "goals-student", role: "student", contextKey: "goals", title: "Hedeflerim (Öğrenci)", durationLabel: DUR, order: 3, status: "published" },
  { slug: "focus-student", role: "student", contextKey: "focus", title: "Odaklı Çalışma (Öğrenci)", durationLabel: DUR, order: 4, status: "published" },
  { slug: "review-cards-student", role: "student", contextKey: "review", title: "Tekrar Kartları (Öğrenci)", durationLabel: DUR, order: 5, status: "published" },
  { slug: "dna-student", role: "student", contextKey: "dna", title: "Çalışma DNA (Öğrenci)", durationLabel: DUR, order: 6, status: "published" },
  { slug: "task-request-student", role: "student", contextKey: "requests", title: "Koçumdan Talep Etme", durationLabel: DUR, order: 7, status: "published" },

  // ============================ VELİ ============================
  { slug: "weekly-report-parent", role: "parent", contextKey: "weekly-report", title: "Haftalık Rapor (Veli)", durationLabel: DUR, order: 1, status: "published" },
  { slug: "parent-ai-insight-parent", role: "parent", contextKey: "ai-insight", title: "Yapay Zekâ Durum Analizi (Veli)", durationLabel: DUR, order: 2, status: "published" },
  { slug: "notif-prefs-parent", role: "parent", contextKey: "settings", title: "Bildirim Tercihleri (Veli)", durationLabel: DUR, order: 3, status: "published" },

  // ============================ KURUM YÖNETİCİSİ ============================
  { slug: "inst-activity-stream", role: "institution_admin", contextKey: "activity-stream", title: "Aktivite Akışı (Kurum)", durationLabel: DUR, order: 1, status: "published" },
  { slug: "inst-invitations", role: "institution_admin", contextKey: "invitations", title: "Öğretmen Davet (Kurum)", durationLabel: DUR, order: 2, status: "published" },
  { slug: "inst-teacher-detail", role: "institution_admin", contextKey: "teacher-detail", title: "Öğretmen Sayfası (Kurum)", durationLabel: DUR, order: 3, status: "published" },
  { slug: "inst-roster", role: "institution_admin", contextKey: "roster", title: "Roster (Kurum)", durationLabel: DUR, order: 4, status: "published" },
  { slug: "inst-analysis-1", role: "institution_admin", contextKey: "analysis", title: "Analiz Panoları (Kurum)", durationLabel: DUR, order: 5, status: "published" },
  { slug: "inst-analysis-2", role: "institution_admin", contextKey: "analysis-2", title: "Karne · Hedef · Özet (Kurum)", durationLabel: DUR, order: 6, status: "published" },
  { slug: "inst-parent-trust", role: "institution_admin", contextKey: "parent-trust", title: "Veli Güveni (Kurum)", durationLabel: DUR, order: 7, status: "published" },
  { slug: "inst-requests", role: "institution_admin", contextKey: "requests", title: "Talepler (Kurum)", durationLabel: DUR, order: 8, status: "published" },
  { slug: "whatsapp-institution", role: "institution_admin", contextKey: "whatsapp", title: "WhatsApp ile Kurumsal İletişim", durationLabel: DUR, order: 9, status: "published" },
  { slug: "inst-membership", role: "institution_admin", contextKey: "membership", title: "Üyelik (Kurum)", durationLabel: DUR, order: 10, status: "published" },
];

/** Belirli bir bağlam + rol için yayınlanmış demo (yoksa null → slot görünmez). */
export function demoFor(contextKey: string, role: DemoRole): DemoEntry | null {
  return (
    DEMOS.find(
      (d) => d.status === "published" && d.role === role && d.contextKey === contextKey,
    ) ?? null
  );
}

/** Bir rolün yayınlanmış demoları (journey sırasıyla) — kütüphane/galeri/onboarding. */
export function demosForRole(role: DemoRole): DemoEntry[] {
  return DEMOS.filter((d) => d.status === "published" && d.role === role).sort(
    (a, b) => a.order - b.order,
  );
}

/** Slug → demo (oynatıcı/derin link için). */
export function demoBySlug(slug: string): DemoEntry | null {
  return DEMOS.find((d) => d.slug === slug) ?? null;
}

/** Oynatma URL'i — /demos?play={slug} (yeni sekmede <a target=_blank>). */
export function demoPlayUrl(slug: string): string {
  return `/demos?play=${encodeURIComponent(slug)}`;
}
