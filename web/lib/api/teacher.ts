/**
 * Öğretmen paneli endpoint'lerinin tipli sarmalayıcıları (Paket 5).
 *
 * Bu modül SADECE okuma (GET) sarmalayıcıları içerir. Mutation hook'ları
 * Paket 7'de gelir.
 *
 * QueryKey sözleşmesi backend `MutationResponse.invalidate` listesindeki
 * "teacher:{teacher_id}:students:{id}:day:{date}" gibi düz string'lerle birebir
 * uyumlu olmalıdır (applyInvalidate `:` ile split eder — R-006).
 *
 * Frontend "me" placeholder'ı kullanıyor: öğretmen kendi id'sini bilmeden
 * queryKey üretebilsin diye. Backend invalidate'inde gerçek teacher_id geçer
 * ama uzunluk eşleşmesi yapılmaz; her queryKey o teacher'a özeldir (cookie).
 */
import { api, type MutationResponse } from "@/lib/api";
import type {
  BookOptionsResponse,
  DashboardWarningsFeedResponse,
  PromoteFormResponse,
  ReviewStruggleResponse,
  SectionOptionsResponse,
  SectionStatsResponse,
  SidebarResponse,
  SubjectListResponse,
  StudentBookListResponse,
  StudentExamListResponse,
  WorkBlockListResponse,
  StudentSessionListResponse,
  SessionPrefillResponse,
  BillingMonthResponse,
  StudentPaymentsResponse,
  AiConsentResponse,
  CoachingInsightCacheResponse,
  TeacherPlanResponse,
  TrialStatusResponse,
  SubscriptionRequestBody,
  SubscriptionRequestResult,
  StudentParentsResponse,
  TeacherBadgesResponse,
  TeacherBookListResponse,
  TeacherBurnoutFleetResponse,
  TeacherDashboardResponse,
  TeacherDnaResponse,
  TeacherFocusResponse,
  TeacherGoalsResponse,
  TeacherMeResponse,
  TeacherRequestDetail,
  TeacherRequestListResponse,
  TeacherReviewFleetResponse,
  CarryoverCandidatesResponse,
  CurriculumProgressResponse,
  NextUnitsResponse,
  TeacherReviewResponse,
  TeacherStudentAnalyticsResponse,
  TeacherStudentDayResponse,
  ParentProgramPreviewResponse,
  TeacherStudentDetailResponse,
  TeacherStudentListResponse,
  TeacherStudentWeekResponse,
  TeacherWeekNote,
} from "@/lib/types/teacher";

// =============================================================================
// QueryKey üreticileri
// =============================================================================

export const teacherKeys = {
  me: () => ["teacher", "me"] as const,
  dashboard: () => ["teacher", "me", "dashboard"] as const,
  badges: () => ["teacher", "me", "badges"] as const,

  // /students — params kısmı listede string olarak normalize edildi (q + filter + page)
  studentsList: (params: TeacherStudentsListParams) =>
    [
      "teacher",
      "me",
      "students",
      params.q ?? "",
      params.risk ?? "all",
      params.grade_level ?? "",
      String(params.page ?? 1),
      String(params.page_size ?? 25),
    ] as const,

  student: (id: number) => ["teacher", "me", "students", String(id)] as const,
  studentSummary: (id: number) =>
    ["teacher", "me", "students", String(id), "summary"] as const,
  studentDay: (id: number, date: string) =>
    ["teacher", "me", "students", String(id), "day", date] as const,
  studentWeek: (id: number, start: string) =>
    ["teacher", "me", "students", String(id), "week", start] as const,
  studentPrograms: (id: number) =>
    ["teacher", "me", "students", String(id), "programs"] as const,
  studentBooks: (id: number) =>
    ["teacher", "me", "students", String(id), "books"] as const,
  studentParents: (id: number) =>
    ["teacher", "me", "students", String(id), "parents"] as const,
  carryoverCandidates: (id: number, programId?: number | null) =>
    ["teacher", "me", "students", String(id), "carryover", String(programId ?? "active")] as const,
  studentCurriculum: (id: number) =>
    ["teacher", "me", "students", String(id), "curriculum"] as const,
  studentNextUnits: (id: number) =>
    ["teacher", "me", "students", String(id), "next-units"] as const,

  // Paket 3.5a — haftalık plan yardımcıları
  studentSidebar: (id: number, subjectId: number | null) =>
    [
      "teacher",
      "me",
      "students",
      String(id),
      "sidebar",
      subjectId === null ? "" : String(subjectId),
    ] as const,
  studentAllSubjects: (id: number) =>
    ["teacher", "me", "students", String(id), "all-subjects"] as const,
  studentBooksBySubject: (id: number, subjectId: number | null) =>
    [
      "teacher",
      "me",
      "students",
      String(id),
      "books-by-subject",
      subjectId === null ? "" : String(subjectId),
    ] as const,
  studentBookSections: (id: number, bookId: number) =>
    [
      "teacher",
      "me",
      "students",
      String(id),
      "book-sections",
      String(bookId),
    ] as const,
  studentSectionStats: (id: number, sectionId: number) =>
    [
      "teacher",
      "me",
      "students",
      String(id),
      "section-stats",
      String(sectionId),
    ] as const,
  studentReviewChips: (
    id: number,
    subjectId: number,
    targetDate: string,
  ) =>
    [
      "teacher",
      "me",
      "students",
      String(id),
      "review-chips",
      String(subjectId),
      targetDate,
    ] as const,

  requestsList: (params: TeacherRequestsListParams) =>
    [
      "teacher",
      "me",
      "requests",
      params.status ?? "pending",
      params.type ?? "all",
      params.student_id !== undefined ? String(params.student_id) : "",
      String(params.page ?? 1),
      String(params.page_size ?? 25),
    ] as const,
  request: (id: number) => ["teacher", "me", "requests", String(id)] as const,

  books: () => ["teacher", "me", "books"] as const,
  studentBookGrid: (studentId: number, bookId: number) =>
    [
      "teacher",
      "me",
      "students",
      String(studentId),
      "book-grid",
      String(bookId),
    ] as const,

  // Paket 3.5c — Sınıf Yükselt / Hedefler / Tekrar / DNA / Odak
  studentPromoteForm: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "promote-form"] as const,
  studentFocus: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "focus"] as const,
  studentDna: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "dna"] as const,
  studentReview: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "review"] as const,
  studentGoals: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "goals"] as const,

  // Paket 3.5d.1 — Analitik / Fleet panoları
  studentAnalytics: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "analytics"] as const,
  burnoutFleet: () => ["teacher", "me", "burnout"] as const,
  reviewFleet: () => ["teacher", "me", "review"] as const,

  // Paket 3.5d.2 — Dashboard warnings feed
  warningsFeed: () => ["teacher", "me", "dashboard", "warnings-feed"] as const,
  taskTemplates: () => ["teacher", "me", "task-templates"] as const,
  studentWorkBlocks: (id: number) =>
    ["teacher", "me", "students", String(id), "work-blocks"] as const,
  studentExams: (id: number) =>
    ["teacher", "me", "students", String(id), "exams"] as const,
  studentSessions: (id: number) =>
    ["teacher", "me", "students", String(id), "sessions"] as const,
  sessionPrefill: (id: number) =>
    ["teacher", "me", "students", String(id), "sessions", "prefill"] as const,
  billing: (month: string) => ["teacher", "me", "billing", month] as const,
  studentPayments: (id: number) =>
    ["teacher", "me", "students", String(id), "payments"] as const,
  aiConsent: () => ["teacher", "me", "ai-consent"] as const,
  coachingInsight: (id: number) =>
    ["teacher", "me", "students", String(id), "coaching-insight"] as const,
  plan: () => ["teacher", "me", "plan"] as const,
  trialStatus: () => ["teacher", "me", "trial-status"] as const,
} as const;

// =============================================================================
// Filtre tipleri
// =============================================================================

export interface TeacherStudentsListParams {
  q?: string;
  grade_level?: number;
  risk?: "all" | "ok" | "medium" | "high" | "critical";
  page?: number;
  page_size?: number;
}

export interface TeacherRequestsListParams {
  status?: "pending" | "approved" | "rejected" | "withdrawn" | "resolved" | "all";
  type?: "change" | "replace" | "remove" | "question" | "add" | "all";
  student_id?: number;
  page?: number;
  page_size?: number;
}

// =============================================================================
// GET sarmalayıcıları
// =============================================================================

function buildQuery(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export function getTeacherMe(): Promise<TeacherMeResponse> {
  return api<TeacherMeResponse>("/api/v2/teacher/me");
}

export function getTeacherDashboard(): Promise<TeacherDashboardResponse> {
  return api<TeacherDashboardResponse>("/api/v2/teacher/dashboard");
}

export function getTeacherBadges(): Promise<TeacherBadgesResponse> {
  return api<TeacherBadgesResponse>("/api/v2/teacher/badges");
}

export function getTeacherStudentExams(
  studentId: number,
): Promise<StudentExamListResponse> {
  return api<StudentExamListResponse>(
    `/api/v2/teacher/students/${studentId}/exams`,
  );
}

export function getTeacherWorkBlocks(
  studentId: number,
  includeArchived = false,
): Promise<WorkBlockListResponse> {
  const qs = includeArchived ? "?include_archived=true" : "";
  return api<WorkBlockListResponse>(
    `/api/v2/teacher/students/${studentId}/work-blocks${qs}`,
  );
}

export function getTeacherStudentSessions(
  studentId: number,
): Promise<StudentSessionListResponse> {
  return api<StudentSessionListResponse>(
    `/api/v2/teacher/students/${studentId}/sessions`,
  );
}

export function getTeacherSessionPrefill(
  studentId: number,
): Promise<SessionPrefillResponse> {
  return api<SessionPrefillResponse>(
    `/api/v2/teacher/students/${studentId}/sessions/prefill`,
  );
}

export function getTeacherBilling(month: string): Promise<BillingMonthResponse> {
  return api<BillingMonthResponse>(`/api/v2/teacher/billing?month=${month}`);
}

export function getTeacherStudentPayments(
  studentId: number,
): Promise<StudentPaymentsResponse> {
  return api<StudentPaymentsResponse>(
    `/api/v2/teacher/students/${studentId}/payments`,
  );
}

export function getTeacherAiConsent(): Promise<AiConsentResponse> {
  return api<AiConsentResponse>("/api/v2/teacher/ai-consent");
}

export function getTeacherCoachingInsight(
  studentId: number,
): Promise<CoachingInsightCacheResponse> {
  return api<CoachingInsightCacheResponse>(
    `/api/v2/teacher/students/${studentId}/coaching-insight`,
  );
}

export function getTeacherPlan(): Promise<TeacherPlanResponse> {
  return api<TeacherPlanResponse>("/api/v2/teacher/plan");
}

export function getTeacherTrialStatus(): Promise<TrialStatusResponse> {
  return api<TrialStatusResponse>("/api/v2/teacher/trial-status");
}

export function submitSubscriptionRequest(
  body: SubscriptionRequestBody,
): Promise<MutationResponse<SubscriptionRequestResult>> {
  return api<MutationResponse<SubscriptionRequestResult>>(
    "/api/v2/teacher/subscription-request",
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function cancelSubscription(): Promise<MutationResponse<SubscriptionRequestResult>> {
  return api<MutationResponse<SubscriptionRequestResult>>(
    "/api/v2/teacher/subscription/cancel", { method: "POST" },
  );
}

export function resumeSubscription(): Promise<MutationResponse<SubscriptionRequestResult>> {
  return api<MutationResponse<SubscriptionRequestResult>>(
    "/api/v2/teacher/subscription/resume", { method: "POST" },
  );
}

export function getTeacherStudents(
  params: TeacherStudentsListParams,
): Promise<TeacherStudentListResponse> {
  const qs = buildQuery({
    q: params.q,
    grade_level: params.grade_level,
    risk: params.risk,
    page: params.page,
    page_size: params.page_size,
  });
  return api<TeacherStudentListResponse>(`/api/v2/teacher/students${qs}`);
}

export function getTeacherStudent(id: number): Promise<TeacherStudentDetailResponse> {
  return api<TeacherStudentDetailResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(id))}`,
  );
}

export function getTeacherStudentDay(
  id: number,
  date?: string,
): Promise<TeacherStudentDayResponse> {
  const qs = buildQuery({ date });
  return api<TeacherStudentDayResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(id))}/day${qs}`,
  );
}

export function getTeacherStudentWeek(
  id: number,
  start?: string,
  programId?: number | null,
): Promise<TeacherStudentWeekResponse> {
  const qs = buildQuery({
    start,
    program_id: programId != null ? String(programId) : undefined,
  });
  return api<TeacherStudentWeekResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(id))}/week${qs}`,
  );
}

export function getTeacherStudentCurriculum(
  id: number,
): Promise<CurriculumProgressResponse> {
  return api<CurriculumProgressResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(id))}/curriculum`,
  );
}

export function getTeacherNextUnits(id: number): Promise<NextUnitsResponse> {
  return api<NextUnitsResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(id))}/next-units`,
  );
}

export function getCarryoverCandidates(
  id: number,
  programId?: number | null,
): Promise<CarryoverCandidatesResponse> {
  const qs = buildQuery({
    program_id: programId != null ? String(programId) : undefined,
  });
  return api<CarryoverCandidatesResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(id))}/carryover-candidates${qs}`,
  );
}

export function getParentProgramPreview(
  id: number,
  opts: { start?: string; programId?: number | null } = {},
): Promise<ParentProgramPreviewResponse> {
  const qs = buildQuery({
    week_start: opts.start,
    program_id: opts.programId != null ? String(opts.programId) : undefined,
  });
  return api<ParentProgramPreviewResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(id))}/program/parent-preview${qs}`,
  );
}

export function getTeacherStudentPrograms(
  id: number,
): Promise<import("@/lib/types/teacher").WeeklyProgramListResponse> {
  return api(
    `/api/v2/teacher/students/${encodeURIComponent(String(id))}/programs`,
  );
}

export function getTeacherStudentBooks(id: number): Promise<StudentBookListResponse> {
  return api<StudentBookListResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(id))}/books`,
  );
}

export function getTeacherStudentParents(id: number): Promise<StudentParentsResponse> {
  return api<StudentParentsResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(id))}/parents`,
  );
}

export function getTeacherRequests(
  params: TeacherRequestsListParams,
): Promise<TeacherRequestListResponse> {
  const qs = buildQuery({
    status: params.status,
    type: params.type,
    student_id: params.student_id,
    page: params.page,
    page_size: params.page_size,
  });
  return api<TeacherRequestListResponse>(`/api/v2/teacher/requests${qs}`);
}

export function getTeacherRequest(id: number): Promise<TeacherRequestDetail> {
  return api<TeacherRequestDetail>(
    `/api/v2/teacher/requests/${encodeURIComponent(String(id))}`,
  );
}

export function getTeacherBooks(): Promise<TeacherBookListResponse> {
  return api<TeacherBookListResponse>("/api/v2/teacher/books");
}

// =============================================================================
// Paket 3.5a — haftalık plan yardımcı GET'leri
// =============================================================================

export function getStudentSidebar(
  studentId: number,
  subjectId: number | null,
): Promise<SidebarResponse> {
  const qs = buildQuery({
    subject_id: subjectId !== null ? String(subjectId) : "",
  });
  return api<SidebarResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/sidebar-items${qs}`,
  );
}

export function getStudentAllSubjects(
  studentId: number,
): Promise<SubjectListResponse> {
  return api<SubjectListResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/all-subjects`,
  );
}

export function getStudentBooksBySubject(
  studentId: number,
  subjectId: number | null,
): Promise<BookOptionsResponse> {
  const qs = buildQuery({
    subject_id: subjectId !== null ? String(subjectId) : "",
  });
  return api<BookOptionsResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/books-by-subject${qs}`,
  );
}

export function getStudentBookSections(
  studentId: number,
  bookId: number,
): Promise<SectionOptionsResponse> {
  return api<SectionOptionsResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/book-sections?book_id=${encodeURIComponent(String(bookId))}`,
  );
}

/**
 * Sinema-koltuğu grid (öğretmen → öğrencinin kitabı).
 * Eşdeğer Jinja: book_grid_content.html partial. Tipler v2 student schema'sı
 * ile aynı (BookGridResponse).
 */
export function getTeacherStudentBookGrid(
  studentId: number,
  bookId: number,
): Promise<import("@/lib/types/student").BookGridResponse> {
  return api<import("@/lib/types/student").BookGridResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/books/${encodeURIComponent(String(bookId))}/book-grid`,
  );
}

export function getStudentSectionStats(
  studentId: number,
  sectionId: number,
): Promise<SectionStatsResponse> {
  return api<SectionStatsResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/section-stats?section_id=${encodeURIComponent(String(sectionId))}`,
  );
}

export function getStudentReviewChips(
  studentId: number,
  subjectId: number,
  targetDate: string,
): Promise<ReviewStruggleResponse> {
  return api<ReviewStruggleResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/review-struggle-suggestions?subject_id=${encodeURIComponent(String(subjectId))}&target_date=${encodeURIComponent(targetDate)}`,
  );
}

export function getStudentWeekNotes(
  studentId: number,
  weekStart: string,
): Promise<TeacherWeekNote[]> {
  return api<TeacherWeekNote[]>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/week-notes?week_start=${encodeURIComponent(weekStart)}`,
  );
}

// =============================================================================
// Paket 3.5c — Sınıf Yükselt / Hedefler / Tekrar / DNA / Odak (GET)
// =============================================================================

export function getTeacherPromoteForm(
  studentId: number,
): Promise<PromoteFormResponse> {
  return api<PromoteFormResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/promote-form`,
  );
}

export function getTeacherStudentFocus(
  studentId: number,
): Promise<TeacherFocusResponse> {
  return api<TeacherFocusResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/focus`,
  );
}

export function getTeacherStudentDna(
  studentId: number,
): Promise<TeacherDnaResponse> {
  return api<TeacherDnaResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/dna`,
  );
}

export function getTeacherStudentReview(
  studentId: number,
): Promise<TeacherReviewResponse> {
  return api<TeacherReviewResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/review`,
  );
}

export function getTeacherStudentGoals(
  studentId: number,
): Promise<TeacherGoalsResponse> {
  return api<TeacherGoalsResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/goals`,
  );
}

// =============================================================================
// Paket 3.5d.1 — Analitik / Fleet (GET)
// =============================================================================

export function getTeacherStudentAnalytics(
  studentId: number,
): Promise<TeacherStudentAnalyticsResponse> {
  return api<TeacherStudentAnalyticsResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/analytics`,
  );
}

export function getTeacherBurnoutFleet(): Promise<TeacherBurnoutFleetResponse> {
  return api<TeacherBurnoutFleetResponse>("/api/v2/teacher/burnout");
}

export function getTeacherReviewFleet(): Promise<TeacherReviewFleetResponse> {
  return api<TeacherReviewFleetResponse>("/api/v2/teacher/review");
}

// =============================================================================
// Paket 3.5d.2 — Dashboard warnings feed
// =============================================================================

export function getTeacherWarningsFeed(): Promise<DashboardWarningsFeedResponse> {
  return api<DashboardWarningsFeedResponse>(
    "/api/v2/teacher/dashboard/warnings-feed",
  );
}

export function getTaskTemplates(): Promise<
  import("@/lib/types/teacher").TaskTemplateListResponse
> {
  return api<import("@/lib/types/teacher").TaskTemplateListResponse>(
    "/api/v2/teacher/task-templates",
  );
}
