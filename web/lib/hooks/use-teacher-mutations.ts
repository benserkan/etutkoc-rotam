"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import { teacherKeys } from "@/lib/api/teacher";
import type {
  BulkResult,
  BulkTasksBody,
  DnaNotifyParentBody,
  DnaNotifyParentResult,
  ExamCreateBody,
  ExamResultRow,
  CoachingSessionCreateBody,
  CoachingSessionRow,
  PaymentCreateBody,
  AiConsentResponse,
  SessionDraftResponse,
  CoachingInsightCacheResponse,
  TeacherPlanResponse,
  PlanUpgradeBody,
  GoalNodeRow,
  ParentInviteBody,
  ParentInviteResult,
  ParentNoteBody,
  ParentNoteResult,
  StudentResetPasswordResult,
  PromoteBody,
  PromoteResult,
  RequestApproveBody,
  RequestRejectBody,
  RequestRespondBody,
  ReviewSeedBody,
  ReviewSeedResult,
  StudentBookAssignBody,
  StudentBookBulkAssignBody,
  StudentBookBulkAssignResult,
  StudentBookListItem,
  StudentBriefProfile,
  StudentCreateBody,
  StudentCreateResult,
  StudentPatchBody,
  TaskCreateBody,
  TaskItemBody,
  SetWeekAnchorBody,
  SetWeekAnchorResult,
  TaskItemPatchBody,
  TaskPatchBody,
  TaskSingleItemEditBody,
  TeacherGoalActionResult,
  TeacherGoalCreateBody,
  TeacherGoalUpdateBody,
  TeacherRequestDetail,
  TeacherStudentDayResponse,
  TeacherTask,
} from "@/lib/types/teacher";

/**
 * Öğretmen paneli mutation hook'ları (Dalga 3 Paket 7).
 *
 * Sözleşme:
 *   - Tüm mutation'lar başarıda backend'in MutationResponse.invalidate listesini
 *     applyInvalidate ile uygular (R-006 OOB swap karşılığı).
 *   - Görev mutasyonları gün cache'i üzerinde optimistic update yapar; 4xx
 *     hatasında rollback + toast (RESERVE_OVER_CAPACITY, has_history, vs.)
 *   - 422 detail.code'a göre Türkçe açıklayıcı toast mesajı.
 *
 * Geliştirici notu: `dateIso` parametresi alan hook'lar gün cache'i üzerinde
 * çalışır; gün-bağımsız işlemler (öğrenci CRUD, kitap atama, veli) için bu yok.
 */

// =============================================================================
// Ortak yardımcılar
// =============================================================================

function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.detail?.message ?? fallback;
  return fallback;
}

function errorCode(e: unknown): string | undefined {
  if (e instanceof ApiError) return e.detail?.code;
  return undefined;
}

/** detail.code'a göre kullanıcı dostu kısa başlık (toast title). */
function errorTitle(e: unknown, fallback: string): string {
  const code = errorCode(e);
  switch (code) {
    case "RESERVE_OVER_CAPACITY":
      return "Kapasite yetersiz";
    case "has_history":
      return "Silinemiyor: geçmiş var";
    case "has_reservations":
      return "Silinemiyor: aktif rezerv var";
    case "email_taken":
      return "E-posta zaten kayıtlı";
    case "already_invited":
      return "Bekleyen davet var";
    case "already_linked":
      return "Veli zaten bağlı";
    case "already_assigned":
      return "Kitap zaten atalı";
    case "plan_quota_exceeded":
      return "Plan kotası dolu";
    case "track_required":
    case "graduate_mode_required":
    case "full_name_required":
    case "invalid_email":
    case "invalid_grade":
    case "invalid_section":
      return "Eksik veya hatalı bilgi";
    case "already_answered":
      return "Talep zaten yanıtlandı";
    case "request_not_found":
    case "student_not_found":
    case "task_not_found":
    case "book_not_found":
    case "assignment_not_found":
    case "link_not_found":
      return "Bulunamadı";
    default:
      return fallback;
  }
}

function showError(e: unknown, fallbackTitle: string) {
  toast.error(errorTitle(e, fallbackTitle), {
    description: errorMessage(e, "Sunucu hatası."),
  });
}

// =============================================================================
// GÜN CACHE — gün üzerinde task ekle/güncelle/sil
// =============================================================================

function setDayCache(
  qc: ReturnType<typeof useQueryClient>,
  studentId: number,
  dateIso: string,
  patch: (prev: TeacherStudentDayResponse) => TeacherStudentDayResponse,
): TeacherStudentDayResponse | undefined {
  const key = teacherKeys.studentDay(studentId, dateIso);
  const prev = qc.getQueryData<TeacherStudentDayResponse>(key);
  if (!prev) return undefined;
  const next = patch(prev);
  // KPI'ları yeniden hesapla
  const planned = next.tasks.reduce((s, t) => s + t.planned_count, 0);
  const completed = next.tasks.reduce((s, t) => s + t.completed_count, 0);
  next.today_planned = planned;
  next.today_completed = completed;
  next.today_pct = planned > 0 ? completed / planned : 0;
  qc.setQueryData(key, next);
  return prev;
}

interface DayCacheCtx {
  previous: TeacherStudentDayResponse | undefined;
  dateIso: string;
}

// =============================================================================
// TASK CRUD
// =============================================================================

export function useCreateTask(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherTask>,
    ApiError,
    { body: TaskCreateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<TeacherTask>>(
        `/api/v2/teacher/students/${studentId}/tasks`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Görev oluşturulamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Görev eklendi");
    },
  });
}

/**
 * POST /api/v2/teacher/students/{id}/set-week-anchor
 * Manuel anchor set veya "clear" ile sıfırla (Jinja teacher_program.py:518-552 parite).
 * 422 invalid_anchor_date hata kodlarını toast'lar.
 */
export function useSetWeekAnchor(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SetWeekAnchorResult>,
    ApiError,
    { body: SetWeekAnchorBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<SetWeekAnchorResult>>(
        `/api/v2/teacher/students/${studentId}/set-week-anchor`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "invalid_anchor_date") {
        toast.error("Geçersiz tarih", {
          description: err.detail?.message ?? "YYYY-MM-DD bekleniyor.",
        });
      } else {
        showError(err, "Anchor güncellenemedi");
      }
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        res.data.is_manual
          ? "Anchor güncellendi"
          : "Manuel anchor sıfırlandı",
      );
    },
  });
}

export function usePatchTask(studentId: number, dateIso: string) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherTask>,
    ApiError,
    { taskId: number; body: TaskPatchBody },
    DayCacheCtx
  >({
    mutationFn: ({ taskId, body }) =>
      api<MutationResponse<TeacherTask>>(`/api/v2/teacher/tasks/${taskId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onMutate: async ({ taskId, body }) => {
      await qc.cancelQueries({
        queryKey: teacherKeys.studentDay(studentId, dateIso),
      });
      const previous = setDayCache(qc, studentId, dateIso, (prev) => ({
        ...prev,
        tasks: prev.tasks.map((t) =>
          t.id !== taskId
            ? t
            : {
                ...t,
                title: body.title ?? t.title,
                type: body.type ?? t.type,
                scheduled_hour:
                  body.scheduled_hour !== undefined && body.scheduled_hour !== null
                    ? `${String(body.scheduled_hour).padStart(2, "0")}:00`
                    : body.scheduled_hour === null
                      ? null
                      : t.scheduled_hour,
                order: body.order ?? t.order,
                is_draft: body.is_draft ?? t.is_draft,
                notes: body.notes !== undefined ? body.notes : t.notes,
              },
        ),
      }));
      return { previous, dateIso };
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous)
        qc.setQueryData(
          teacherKeys.studentDay(studentId, ctx.dateIso),
          ctx.previous,
        );
      showError(err, "Görev güncellenemedi");
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
    },
  });
}

/**
 * Tek kalemli görev için atomik düzenleme (kaynak/sayı/tarih/saat/tip).
 * Backend rezerv'i otomatik dengeler, başlığı yeniden üretir.
 * 422 hata kodları: multi_item_task, source_change_with_completed,
 * planned_below_completed.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- API tutarlılığı (taskId üzerinden gidiyor; future invalidation için imza korunur)
export function usePatchTaskSingleItem(_studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherTask>,
    ApiError,
    { taskId: number; body: TaskSingleItemEditBody }
  >({
    mutationFn: ({ taskId, body }) =>
      api<MutationResponse<TeacherTask>>(
        `/api/v2/teacher/tasks/${taskId}/single-item`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "source_change_with_completed") {
        toast.error("Çözülen test var", {
          description: err.detail?.message ?? "Kaynak değişikliği yapılamaz.",
        });
      } else if (code === "planned_below_completed") {
        toast.error("Sayı çok düşük", {
          description: err.detail?.message ?? "Tamamlanan miktardan az olamaz.",
        });
      } else if (code === "multi_item_task") {
        toast.error("Çok kalemli görev", {
          description: "Bu form yalnızca tek kalemli görevler için geçerli.",
        });
      } else {
        showError(err, "Görev güncellenemedi");
      }
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Görev güncellendi");
    },
  });
}

export function useDeleteTask(studentId: number, dateIso: string) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<{ deleted: boolean; task_id: number }>,
    ApiError,
    { taskId: number },
    DayCacheCtx
  >({
    mutationFn: ({ taskId }) =>
      api<MutationResponse<{ deleted: boolean; task_id: number }>>(
        `/api/v2/teacher/tasks/${taskId}`,
        { method: "DELETE" },
      ),
    onMutate: async ({ taskId }) => {
      await qc.cancelQueries({
        queryKey: teacherKeys.studentDay(studentId, dateIso),
      });
      const previous = setDayCache(qc, studentId, dateIso, (prev) => ({
        ...prev,
        tasks: prev.tasks.filter((t) => t.id !== taskId),
      }));
      return { previous, dateIso };
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous)
        qc.setQueryData(
          teacherKeys.studentDay(studentId, ctx.dateIso),
          ctx.previous,
        );
      showError(err, "Görev silinemedi");
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Görev silindi");
    },
  });
}

export function useAddTaskItem(studentId: number, dateIso: string) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherTask>,
    ApiError,
    { taskId: number; body: TaskItemBody }
  >({
    mutationFn: ({ taskId, body }) =>
      api<MutationResponse<TeacherTask>>(
        `/api/v2/teacher/tasks/${taskId}/items`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Kalem eklenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kalem eklendi");
      // Optimistic update yapmadık (yeni kalem ID'si server'dan gelir);
      // invalidate gün cache'ini bayatlayıp yeniden çeker.
      void studentId;
      void dateIso;
    },
  });
}

export function usePatchTaskItem(studentId: number, dateIso: string) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherTask>,
    ApiError,
    { taskId: number; itemId: number; body: TaskItemPatchBody },
    DayCacheCtx
  >({
    mutationFn: ({ taskId, itemId, body }) =>
      api<MutationResponse<TeacherTask>>(
        `/api/v2/teacher/tasks/${taskId}/items/${itemId}`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onMutate: async ({ taskId, itemId, body }) => {
      await qc.cancelQueries({
        queryKey: teacherKeys.studentDay(studentId, dateIso),
      });
      const previous = setDayCache(qc, studentId, dateIso, (prev) => ({
        ...prev,
        tasks: prev.tasks.map((t) => {
          if (t.id !== taskId) return t;
          const items = t.items.map((it) =>
            it.id !== itemId ? it : { ...it, planned_count: body.planned_count },
          );
          const planned = items.reduce((s, it) => s + it.planned_count, 0);
          return {
            ...t,
            items,
            planned_count: planned,
            pct: planned > 0 ? t.completed_count / planned : 0,
          };
        }),
      }));
      return { previous, dateIso };
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous)
        qc.setQueryData(
          teacherKeys.studentDay(studentId, ctx.dateIso),
          ctx.previous,
        );
      showError(err, "Kalem güncellenemedi");
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
    },
  });
}

export function useBulkTasks(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<BulkResult>,
    ApiError,
    { body: BulkTasksBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<BulkResult>>(
        `/api/v2/teacher/students/${studentId}/bulk-tasks`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Toplu görev oluşturulamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(`${res.data.created_count} görev eklendi`);
    },
  });
}

// =============================================================================
// REQUEST AKSİYONLARI
// =============================================================================

export function useApproveRequest(requestId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherRequestDetail>,
    ApiError,
    { body: RequestApproveBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<TeacherRequestDetail>>(
        `/api/v2/teacher/requests/${requestId}/approve`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Talep onaylanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Talep onaylandı");
    },
  });
}

export function useRejectRequest(requestId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherRequestDetail>,
    ApiError,
    { body: RequestRejectBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<TeacherRequestDetail>>(
        `/api/v2/teacher/requests/${requestId}/reject`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Talep reddedilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Talep reddedildi");
    },
  });
}

export function useRespondRequest(requestId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherRequestDetail>,
    ApiError,
    { body: RequestRespondBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<TeacherRequestDetail>>(
        `/api/v2/teacher/requests/${requestId}/respond`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Cevap gönderilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Cevap gönderildi");
    },
  });
}

// =============================================================================
// STUDENT CRUD
// =============================================================================

export function useCreateStudent() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<StudentCreateResult>,
    ApiError,
    { body: StudentCreateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<StudentCreateResult>>("/api/v2/teacher/students", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (err) => showError(err, "Öğrenci eklenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      // temp_password toast başlığında DEĞİL — modal kendisi gösterecek.
      toast.success("Öğrenci eklendi");
    },
  });
}

export function usePatchStudent(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<StudentBriefProfile>,
    ApiError,
    { body: StudentPatchBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<StudentBriefProfile>>(
        `/api/v2/teacher/students/${studentId}`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Öğrenci güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Öğrenci güncellendi");
    },
  });
}

export function useDeactivateStudent(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<StudentBriefProfile>,
    ApiError,
    void
  >({
    mutationFn: () =>
      api<MutationResponse<StudentBriefProfile>>(
        `/api/v2/teacher/students/${studentId}/deactivate`,
        { method: "POST" },
      ),
    onError: (err) => showError(err, "Pasifleştirilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Öğrenci pasifleştirildi");
    },
  });
}

export function useReactivateStudent(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<StudentBriefProfile>,
    ApiError,
    void
  >({
    mutationFn: () =>
      api<MutationResponse<StudentBriefProfile>>(
        `/api/v2/teacher/students/${studentId}/reactivate`,
        { method: "POST" },
      ),
    onError: (err) => showError(err, "Aktifleştirilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Öğrenci aktifleştirildi");
    },
  });
}

export function useDeleteStudent(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<{ deleted: boolean; student_id: number }>,
    ApiError,
    void
  >({
    mutationFn: () =>
      api<MutationResponse<{ deleted: boolean; student_id: number }>>(
        `/api/v2/teacher/students/${studentId}`,
        { method: "DELETE" },
      ),
    onError: (err) => showError(err, "Öğrenci silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Öğrenci silindi");
    },
  });
}

// =============================================================================
// KİTAP ATAMA / VELİ
// =============================================================================

export function useAssignBook(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<StudentBookListItem>,
    ApiError,
    { body: StudentBookAssignBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<StudentBookListItem>>(
        `/api/v2/teacher/students/${studentId}/books`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Kitap atanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kitap atandı");
    },
  });
}

export function useBulkAssignBooks(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<StudentBookBulkAssignResult>,
    ApiError,
    { body: StudentBookBulkAssignBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<StudentBookBulkAssignResult>>(
        `/api/v2/teacher/students/${studentId}/books/bulk`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Toplu kitap atanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const { assigned_count, skipped_already_ids, skipped_invalid_ids } = res.data;
      if (assigned_count === 0 && skipped_already_ids.length === 0 && skipped_invalid_ids.length === 0) {
        toast.success("Atanacak kitap seçilmedi.");
        return;
      }
      const parts: string[] = [];
      if (assigned_count > 0) parts.push(`${assigned_count} kitap atandı`);
      if (skipped_already_ids.length > 0) parts.push(`${skipped_already_ids.length} zaten atalıydı`);
      if (skipped_invalid_ids.length > 0) parts.push(`${skipped_invalid_ids.length} geçersiz`);
      toast.success(parts.join(" · "));
    },
  });
}

export function useUnassignBook(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<{ unassigned: boolean; book_id: number; student_id: number }>,
    ApiError,
    { bookId: number }
  >({
    mutationFn: ({ bookId }) =>
      api<
        MutationResponse<{
          unassigned: boolean;
          book_id: number;
          student_id: number;
        }>
      >(`/api/v2/teacher/students/${studentId}/books/${bookId}`, {
        method: "DELETE",
      }),
    onError: (err) => showError(err, "Kitap kaldırılamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Atama kaldırıldı");
    },
  });
}

export function useInviteParent(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ParentInviteResult>,
    ApiError,
    { body: ParentInviteBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<ParentInviteResult>>(
        `/api/v2/teacher/students/${studentId}/parents`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Veli daveti gönderilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Davet gönderildi");
    },
  });
}

export function useUnlinkParent(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<{ unlinked: boolean; link_id: number; student_id: number }>,
    ApiError,
    { linkId: number }
  >({
    mutationFn: ({ linkId }) =>
      api<
        MutationResponse<{
          unlinked: boolean;
          link_id: number;
          student_id: number;
        }>
      >(`/api/v2/teacher/students/${studentId}/parents/${linkId}`, {
        method: "DELETE",
      }),
    onError: (err) => showError(err, "Bağlantı kaldırılamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Veli bağlantısı kaldırıldı");
    },
  });
}

// =============================================================================
// Paket 3.5c — Promote / Goals / Review / DNA / Focus mutations
// =============================================================================

export function usePromoteStudent(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PromoteResult>, ApiError, { body: PromoteBody }>({
    mutationFn: ({ body }) =>
      api<MutationResponse<PromoteResult>>(
        `/api/v2/teacher/students/${studentId}/promote`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "track_required") {
        toast.error("11. sınıf, 12. sınıf ve mezunlar için alan zorunlu.");
        return;
      }
      if (code === "graduate_mode_required") {
        toast.error("Mezun öğrenciler için çalışma şekli zorunlu.");
        return;
      }
      if (code === "invalid_academic_year") {
        toast.error("Seçili akademik yıl bulunamadı veya sizin değil.");
        return;
      }
      showError(err, "Sınıf yükseltilemedi");
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
  });
}

export function useReviewSeedSubject(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<ReviewSeedResult>, ApiError, { body: ReviewSeedBody }>({
    mutationFn: ({ body }) =>
      api<MutationResponse<ReviewSeedResult>>(
        `/api/v2/teacher/students/${studentId}/review/seed`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Konular eklenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const { added, skipped_existing, subject_name } = res.data;
      const parts = [`${added} yeni kart eklendi`];
      if (skipped_existing > 0) parts.push(`${skipped_existing} kart zaten vardı`);
      toast.success(`${subject_name} · ${parts.join(" · ")}`);
    },
  });
}

export function useDnaNotifyParent(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<DnaNotifyParentResult>,
    ApiError,
    { body: DnaNotifyParentBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<DnaNotifyParentResult>>(
        `/api/v2/teacher/students/${studentId}/dna/notify-parent`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "empty_message") {
        toast.error("Mesaj boş olamaz.");
        return;
      }
      if (code === "no_active_parents") {
        toast.error("Bu öğrenciye bağlı aktif veli yok.");
        return;
      }
      showError(err, "Veli bildirimi gönderilemedi");
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        `Bildirim kuyruğa düştü — ${res.data.parent_count} veliye gönderiliyor.`,
      );
    },
  });
}

export function useCreateGoal(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<GoalNodeRow>,
    ApiError,
    { body: TeacherGoalCreateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<GoalNodeRow>>(
        `/api/v2/teacher/students/${studentId}/goals`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "invalid_title") {
        toast.error("Hedef başlığı boş olamaz.");
        return;
      }
      if (code === "invalid_date") {
        toast.error("Tarih formatı geçersiz. YYYY-AA-GG bekleniyor.");
        return;
      }
      showError(err, "Hedef oluşturulamadı");
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Hedef eklendi");
    },
  });
}

export function useUpdateGoal() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherGoalActionResult>,
    ApiError,
    { goalId: number; body: TeacherGoalUpdateBody }
  >({
    mutationFn: ({ goalId, body }) =>
      api<MutationResponse<TeacherGoalActionResult>>(
        `/api/v2/teacher/goals/${goalId}`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Hedef güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Hedef güncellendi");
    },
  });
}

export function useAchieveGoal() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherGoalActionResult>,
    ApiError,
    { goalId: number }
  >({
    mutationFn: ({ goalId }) =>
      api<MutationResponse<TeacherGoalActionResult>>(
        `/api/v2/teacher/goals/${goalId}/achieve`,
        { method: "POST" },
      ),
    onError: (err) => showError(err, "Hedef tamamlanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Hedef tamamlandı");
    },
  });
}

export function useAbandonGoal() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherGoalActionResult>,
    ApiError,
    { goalId: number }
  >({
    mutationFn: ({ goalId }) =>
      api<MutationResponse<TeacherGoalActionResult>>(
        `/api/v2/teacher/goals/${goalId}/abandon`,
        { method: "POST" },
      ),
    onError: (err) => showError(err, "Hedef bırakılamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Hedef bırakıldı olarak işaretlendi");
    },
  });
}

export function useDeleteGoal() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherGoalActionResult>,
    ApiError,
    { goalId: number }
  >({
    mutationFn: ({ goalId }) =>
      api<MutationResponse<TeacherGoalActionResult>>(
        `/api/v2/teacher/goals/${goalId}`,
        { method: "DELETE" },
      ),
    onError: (err) => showError(err, "Hedef silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Hedef silindi");
    },
  });
}

export function useResetStudentPassword(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<StudentResetPasswordResult>,
    ApiError,
    Record<string, never>
  >({
    mutationFn: () =>
      api<MutationResponse<StudentResetPasswordResult>>(
        `/api/v2/teacher/students/${studentId}/reset-password`,
        { method: "POST" },
      ),
    onError: (err) => showError(err, "Şifre sıfırlanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Geçici şifre oluşturuldu");
    },
  });
}

export function useSendParentNote(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ParentNoteResult>,
    ApiError,
    { body: ParentNoteBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<ParentNoteResult>>(
        `/api/v2/teacher/students/${studentId}/parent-note`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "note_too_short") {
        toast.error("Not en az 10 karakter olmalıdır.");
        return;
      }
      if (code === "no_active_parents") {
        toast.error("Bu öğrenciye bağlı aktif veli yok.");
        return;
      }
      showError(err, "Not gönderilemedi");
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const { fired } = res.data;
      if (fired === 0) {
        toast.success("Not kaydedildi (aktif veli bulunamadı).");
      } else {
        toast.success(`Not ${fired} veliye iletildi (kuyruğa alındı).`);
      }
    },
  });
}

export function useSeedExamGoals(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherGoalActionResult>,
    ApiError,
    Record<string, never>
  >({
    mutationFn: () =>
      api<MutationResponse<TeacherGoalActionResult>>(
        `/api/v2/teacher/students/${studentId}/goals/seed-exam`,
        { method: "POST" },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "no_exam_target") {
        toast.error("Önce öğrenciye sınav hedefi tanımla.");
        return;
      }
      if (code === "already_seeded") {
        toast.error("Otomatik hedef ağacı zaten kurulu.");
        return;
      }
      showError(err, "Otomatik hedef ağacı kurulamadı");
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Sınav hedefinden otomatik ağaç kuruldu");
    },
  });
}

// =============================================================================
// KP4a — Deneme sınavı sonuçları
// =============================================================================

export function useCreateExam(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ExamResultRow>,
    ApiError,
    { body: ExamCreateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<ExamResultRow>>(
        `/api/v2/teacher/students/${studentId}/exams`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "empty_exam") {
        toast.error("Eksik değer", {
          description: "En az bir doğru/yanlış/boş değeri girin.",
        });
      } else if (code === "invalid_date") {
        toast.error("Geçersiz tarih", { description: "YYYY-MM-DD bekleniyor." });
      } else if (code === "title_required") {
        toast.error("Deneme adı zorunlu");
      } else {
        showError(err, "Deneme eklenemedi");
      }
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Deneme sonucu eklendi");
    },
  });
}

export function useDeleteExam() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<{ deleted: boolean; id: number }>,
    ApiError,
    { examId: number }
  >({
    mutationFn: ({ examId }) =>
      api<MutationResponse<{ deleted: boolean; id: number }>>(
        `/api/v2/teacher/exams/${examId}`,
        { method: "DELETE" },
      ),
    onError: (err) => showError(err, "Deneme silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Deneme silindi");
    },
  });
}

// =============================================================================
// KS1 — Koçluk seansları
// =============================================================================

function sessionError(err: unknown) {
  const code = errorCode(err);
  if (code === "agenda_required") toast.error("Gündem zorunlu", { description: "Konuşulacakları girin." });
  else if (code === "invalid_date") toast.error("Geçersiz tarih", { description: "YYYY-MM-DD bekleniyor." });
  else if (code === "invalid_mood") toast.error("Ruh hali 1-5 arası olmalı");
  else showError(err, "Seans kaydedilemedi");
}

export function useCreateSession(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<CoachingSessionRow>, ApiError, { body: CoachingSessionCreateBody }>({
    mutationFn: ({ body }) =>
      api<MutationResponse<CoachingSessionRow>>(
        `/api/v2/teacher/students/${studentId}/sessions`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: sessionError,
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Seans kaydedildi");
    },
  });
}

export function useUpdateSession() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<CoachingSessionRow>, ApiError, { sessionId: number; body: CoachingSessionCreateBody }>({
    mutationFn: ({ sessionId, body }) =>
      api<MutationResponse<CoachingSessionRow>>(
        `/api/v2/teacher/sessions/${sessionId}`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: sessionError,
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Seans güncellendi");
    },
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<{ deleted: boolean; id: number }>, ApiError, { sessionId: number }>({
    mutationFn: ({ sessionId }) =>
      api<MutationResponse<{ deleted: boolean; id: number }>>(
        `/api/v2/teacher/sessions/${sessionId}`,
        { method: "DELETE" },
      ),
    onError: (err) => showError(err, "Seans silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Seans silindi");
    },
  });
}

// =============================================================================
// KS2 — Tahsilat
// =============================================================================

export function useSetRate(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<{ student_id: number; session_fee: number }>, ApiError, { sessionFee: number }>({
    mutationFn: ({ sessionFee }) =>
      api<MutationResponse<{ student_id: number; session_fee: number }>>(
        `/api/v2/teacher/students/${studentId}/rate`,
        { method: "POST", body: JSON.stringify({ session_fee: sessionFee }) },
      ),
    onError: (err) => {
      if (errorCode(err) === "invalid_fee") toast.error("Ücret negatif olamaz");
      else showError(err, "Ücret kaydedilemedi");
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Ücret güncellendi");
    },
  });
}

export function useCreatePayment(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<{ id: number }>, ApiError, { body: PaymentCreateBody }>({
    mutationFn: ({ body }) =>
      api<MutationResponse<{ id: number }>>(
        `/api/v2/teacher/students/${studentId}/payments`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "invalid_amount") toast.error("Tutar 0'dan büyük olmalı");
      else if (code === "invalid_date") toast.error("Geçersiz tarih");
      else showError(err, "Ödeme kaydedilemedi");
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Ödeme kaydedildi");
    },
  });
}

export function useDeletePayment() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<{ deleted: boolean; id: number }>, ApiError, { paymentId: number }>({
    mutationFn: ({ paymentId }) =>
      api<MutationResponse<{ deleted: boolean; id: number }>>(
        `/api/v2/teacher/payments/${paymentId}`,
        { method: "DELETE" },
      ),
    onError: (err) => showError(err, "Ödeme silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Ödeme silindi");
    },
  });
}

// =============================================================================
// KS3a — AI yakalama (foto → metin)
// =============================================================================

export function useSetAiConsent() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<AiConsentResponse>, ApiError, void>({
    mutationFn: () =>
      api<MutationResponse<AiConsentResponse>>("/api/v2/teacher/ai-consent", { method: "POST" }),
    onError: (err) => showError(err, "Onay kaydedilemedi"),
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
  });
}

export function useParseSessionPhoto(studentId: number) {
  // Fotoğraf yalnızca metne çevrilir; DB'ye hiçbir şey yazılmaz (taslak döner).
  // Bu yüzden cache bayatlatması gerekmez; kural bilerek susturuldu.
  // eslint-disable-next-line lgs/missing-invalidate -- parse yan etkisiz, taslak döner
  return useMutation<SessionDraftResponse, ApiError, { imageBase64: string; mediaType: string }>({
    mutationFn: ({ imageBase64, mediaType }) =>
      api<SessionDraftResponse>(
        `/api/v2/teacher/students/${studentId}/sessions/parse-photo`,
        { method: "POST", body: JSON.stringify({ image_base64: imageBase64, media_type: mediaType }) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "consent_required") toast.error("Önce AI işleme onayı gerekli");
      else if (code === "plan_upgrade_required") toast.error("Bu özellik ücretli pakette", { description: "Paketinizi yükseltin." });
      else if (code === "ai_credit_exhausted") toast.error("Kredi sınırına ulaşıldı");
      else if (code === "photo_unreadable") toast.error("Fotoğraf okunamadı", { description: "Daha net bir fotoğraf deneyin." });
      else if (code === "invalid_media_type") toast.error("Desteklenmeyen görsel türü (JPEG/PNG/WebP)");
      else if (code === "image_too_large") toast.error("Görsel çok büyük");
      else if (code === "ai_unavailable") toast.error("AI servisi şu an kullanılamıyor");
      else showError(err, "Fotoğraf işlenemedi");
    },
  });
}

export function useParseSessionVoice(studentId: number) {
  // Ses yalnızca metne çevrilir; DB'ye hiçbir şey yazılmaz (taslak döner).
  // eslint-disable-next-line lgs/missing-invalidate -- parse yan etkisiz, taslak döner
  return useMutation<SessionDraftResponse, ApiError, { audioBase64: string; mediaType: string }>({
    mutationFn: ({ audioBase64, mediaType }) =>
      api<SessionDraftResponse>(
        `/api/v2/teacher/students/${studentId}/sessions/parse-voice`,
        { method: "POST", body: JSON.stringify({ audio_base64: audioBase64, media_type: mediaType }) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "consent_required") toast.error("Önce AI işleme onayı gerekli");
      else if (code === "plan_upgrade_required") toast.error("Bu özellik ücretli pakette", { description: "Paketinizi yükseltin." });
      else if (code === "ai_credit_exhausted") toast.error("Kredi sınırına ulaşıldı");
      else if (code === "voice_unreadable") toast.error("Ses anlaşılamadı", { description: "Daha sessiz bir ortamda, net konuşarak tekrar deneyin." });
      else if (code === "invalid_media_type") toast.error("Desteklenmeyen ses türü");
      else if (code === "audio_too_large") toast.error("Ses kaydı çok uzun");
      else if (code === "ai_unavailable") toast.error("AI servisi şu an kullanılamıyor");
      else showError(err, "Ses işlenemedi");
    },
  });
}

export function useUpgradePlan() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<TeacherPlanResponse>, ApiError, PlanUpgradeBody>({
    mutationFn: (body) =>
      api<MutationResponse<TeacherPlanResponse>>("/api/v2/teacher/plan/upgrade", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.setQueryData(teacherKeys.plan(), res.data);
      toast.success(`${res.data.plan_label} paketine geçildi`);
    },
    onError: (err) => {
      const code = errorCode(err);
      if (code === "managed_by_institution") toast.error("Paketiniz kurumunuz tarafından yönetilir");
      else if (code === "invalid_plan") toast.error("Geçersiz paket seçimi");
      else showError(err, "Paket yükseltilemedi");
    },
  });
}

export function useGenerateCoachingInsight(studentId: number) {
  const qc = useQueryClient();
  // POST = üret/yenile (KREDİ DÜŞER). Sonuç DB'ye cache'lenir; GET ücretsiz okur.
  // Başarıda cache query'sini setQueryData ile günceller (invalidate yerine doğrudan yaz).
  // eslint-disable-next-line lgs/missing-invalidate -- setQueryData ile cache güncelleniyor
  return useMutation<CoachingInsightCacheResponse, ApiError, void>({
    mutationFn: () =>
      api<CoachingInsightCacheResponse>(`/api/v2/teacher/students/${studentId}/coaching-insight`, { method: "POST" }),
    onSuccess: (data) => {
      qc.setQueryData(teacherKeys.coachingInsight(studentId), data);
    },
    onError: (err) => {
      const code = errorCode(err);
      if (code === "consent_required") toast.error("Önce AI işleme onayı gerekli");
      else if (code === "plan_upgrade_required") toast.error("Bu özellik ücretli pakette", { description: "Paketinizi yükseltin." });
      else if (code === "ai_credit_exhausted") toast.error("Kredi sınırına ulaşıldı");
      else if (code === "not_enough_data") toast.error("İçgörü için en az bir seans kaydı gerekir");
      else if (code === "insight_unreadable") toast.error("İçgörü üretilemedi", { description: "Lütfen tekrar deneyin." });
      else if (code === "ai_unavailable") toast.error("AI servisi şu an kullanılamıyor");
      else showError(err, "İçgörü alınamadı");
    },
  });
}
