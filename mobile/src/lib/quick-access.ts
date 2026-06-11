import { apiRequest } from "./api";

/**
 * Hızlı erişim kartları (QA-3) — davranıştan öğrenen panel kısayolları.
 *
 * Web ile AYNI backend: skor/yaşam döngüsü sunucuda; mobil yalnız
 * (a) ekran ziyaretlerini katalog path'ine çevirip gönderir,
 * (b) gelen kartların route_key'ini mobil ekrana çevirir.
 *
 * İki yönlü eşleme tabloları buradadır — yeni mobil ekran eklenince
 * (web'de karşılığı varsa) İKİ tabloya da satır eklenir.
 */

export type QuickCardState = "suggested" | "established" | "pinned";

export interface QuickCard {
  route_key: string;
  entity_id: number | null;
  href: string;
  label: string;
  sublabel: string | null;
  state: QuickCardState;
  score: number;
  card_clicks: number;
}

export const quickAccessKeys = {
  cards: ["quick-cards"] as const,
};

export function getQuickCards(): Promise<{ cards: QuickCard[] }> {
  return apiRequest<{ cards: QuickCard[] }>("/api/v2/me/quick-cards");
}

export function postPanelVisits(
  events: { path: string; dwell_ms?: number }[],
): Promise<{ accepted: number }> {
  return apiRequest<{ accepted: number }>("/api/v2/me/panel-visits", {
    method: "POST",
    body: { events, source: "mobile" },
  });
}

export function clickQuickCard(card: QuickCard): Promise<unknown> {
  return apiRequest("/api/v2/me/quick-cards/click", {
    method: "POST",
    body: { route_key: card.route_key, entity_id: card.entity_id },
  });
}

export function pinQuickCard(card: QuickCard, pinned: boolean): Promise<unknown> {
  return apiRequest("/api/v2/me/quick-cards/pin", {
    method: "POST",
    body: { route_key: card.route_key, entity_id: card.entity_id, pinned },
  });
}

export function dismissQuickCard(card: QuickCard): Promise<unknown> {
  return apiRequest("/api/v2/me/quick-cards/dismiss", {
    method: "POST",
    body: { route_key: card.route_key, entity_id: card.entity_id },
  });
}

// ============================================================================
// 1) Mobil ekran → katalog web path (ziyaret izleme)
// ============================================================================

type Params = Record<string, string | string[] | undefined>;

function p(params: Params, key: string): string | null {
  const v = params[key];
  const s = Array.isArray(v) ? v[0] : v;
  return s && /^\d+$/.test(s) ? s : null;
}

/**
 * expo-router pathname + params → backend rota kataloğundaki web path.
 * Eşleşmeyen ekran null döner (sayılmaz). Param'lı ekranlarda id yoksa null.
 */
export function mobilePathToCatalogPath(
  pathname: string,
  params: Params,
): string | null {
  const id = p(params, "id");
  switch (pathname) {
    // Koç
    case "/teacher/students":
      return "/teacher/students";
    case "/teacher-student":
      return id ? `/teacher/students/${id}` : null;
    case "/teacher-student-dev":
      return id ? `/teacher/students/${id}/dna` : null;
    case "/teacher/billing":
      return "/teacher/billing";
    case "/teacher/requests":
      return "/teacher/requests";
    case "/teacher/support":
      return "/teacher/support";
    case "/teacher-plan":
      return "/teacher/plan";
    // Öğrenci
    case "/student/today":
    case "/day":
      return "/student/day";
    case "/student/week":
      return "/student/week";
    case "/student-books":
      return "/student/books";
    case "/student/gelisim":
      return "/student/dna";
    case "/student-focus":
      return "/student/focus";
    case "/student-goals":
      return "/student/goals";
    case "/student-review":
      return "/student/review";
    case "/student/requests":
      return "/student/requests";
    // Veli
    case "/parent-child":
      return id ? `/parent/students/${id}` : null;
    case "/parent-child-week":
      return id ? `/parent/students/${id}/week` : null;
    case "/parent-child-report":
      return id ? `/parent/students/${id}/report` : null;
    case "/parent-child-exams":
      return id ? `/parent/students/${id}/exams` : null;
    case "/parent/notifications":
      return "/parent/notifications";
    case "/parent/support":
      return "/parent/support";
    // Konu performansı (generic ekran — source'a göre)
    case "/topic-performance": {
      const source = (Array.isArray(params.source) ? params.source[0] : params.source) ?? "student";
      if (source === "student") return "/student/topics";
      if (source === "parent" && id) return `/parent/students/${id}/topics`;
      return null; // teacher kaynağı web'de ayrı sayfa değil (sekme)
    }
    // Kurum yöneticisi
    case "/institution/action-center":
      return "/institution/action-center";
    case "/institution-compliance":
      return "/institution/compliance";
    case "/institution-academic":
      return "/institution/academic";
    case "/institution-at-risk":
      return "/institution/at-risk";
    case "/institution-burnout":
      return "/institution/burnout";
    case "/institution-cohorts":
      return "/institution/cohorts";
    case "/institution-heatmap":
      return "/institution/activity-heatmap";
    case "/institution-activity":
      return "/institution/activity-stream";
    case "/institution-scorecard":
      return "/institution/teacher-scorecard";
    case "/institution-parent-trust":
      return "/institution/parent-trust";
    case "/institution-goals":
      return "/institution/goals";
    case "/institution-teacher":
      return id ? `/institution/teachers/${id}` : null;
    case "/institution-invitations":
      return "/institution/invitations";
    case "/institution-digest":
      return "/institution/admin-digest";
    case "/institution-quota":
      return "/institution/quota";
    case "/institution-usage":
      return "/institution/usage";
    case "/institution-subscription":
      return "/institution/subscription";
    case "/institution/support":
      return "/institution/support";
    default:
      return null;
  }
}

// ============================================================================
// 2) route_key → mobil ekran (kart navigasyonu)
// ============================================================================

/**
 * Kartın route_key'ini mobil router href'ine çevirir. Mobilde karşılığı
 * olmayan anahtar (örn. teacher.library, admin.*) null döner — kart GİZLENİR.
 */
export function mobileHrefForCard(card: QuickCard): string | null {
  const e = card.entity_id;
  const withId = (base: string) => (e ? `${base}?id=${e}` : null);
  switch (card.route_key) {
    // Koç
    case "teacher.students":
      return "/teacher/students";
    case "teacher.student_detail":
    case "teacher.student_day":
    case "teacher.student_week":
      return withId("/teacher-student");
    case "teacher.student_dna":
    case "teacher.student_focus":
    case "teacher.student_goals":
    case "teacher.student_review":
      return withId("/teacher-student-dev");
    case "teacher.billing":
      return "/teacher/billing";
    case "teacher.requests":
      return "/teacher/requests";
    case "teacher.support":
    case "teacher.support_inbox":
      return "/teacher/support";
    case "teacher.plan":
      return "/teacher-plan";
    // Öğrenci
    case "student.day":
      return "/student/today";
    case "student.week":
      return "/student/week";
    case "student.books":
      return "/student-books";
    case "student.dna":
      return "/student/gelisim";
    case "student.focus":
      return "/student-focus";
    case "student.goals":
      return "/student-goals";
    case "student.review":
      return "/student-review";
    case "student.requests":
      return "/student/requests";
    case "student.topics":
      return "/topic-performance?source=student";
    // Veli
    case "parent.child_detail":
      return withId("/parent-child");
    case "parent.child_week":
      return withId("/parent-child-week");
    case "parent.child_report":
      return withId("/parent-child-report");
    case "parent.child_exams":
      return withId("/parent-child-exams");
    case "parent.child_topics":
      return e ? `/topic-performance?source=parent&id=${e}` : null;
    case "parent.notifications":
      return "/parent/notifications";
    case "parent.support":
      return "/parent/support";
    // Kurum yöneticisi
    case "institution.action_center":
      return "/institution/action-center";
    case "institution.compliance":
      return "/institution-compliance";
    case "institution.academic":
      return "/institution-academic";
    case "institution.at_risk":
      return "/institution-at-risk";
    case "institution.burnout":
      return "/institution-burnout";
    case "institution.cohorts":
      return "/institution-cohorts";
    case "institution.activity_heatmap":
      return "/institution-heatmap";
    case "institution.activity_stream":
      return "/institution-activity";
    case "institution.teacher_scorecard":
      return "/institution-scorecard";
    case "institution.parent_trust":
      return "/institution-parent-trust";
    case "institution.goals":
      return "/institution-goals";
    case "institution.teacher_detail":
      return withId("/institution-teacher");
    case "institution.invitations":
      return "/institution-invitations";
    case "institution.admin_digest":
      return "/institution-digest";
    case "institution.quota":
      return "/institution-quota";
    case "institution.usage":
      return "/institution-usage";
    case "institution.subscription":
      return "/institution-subscription";
    case "institution.support":
    case "institution.support_inbox":
      return "/institution/support";
    default:
      return null;
  }
}
