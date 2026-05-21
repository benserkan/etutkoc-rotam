/**
 * Öğretmen paneli için TanStack Query sarmalayıcıları (Paket 6).
 *
 * Server Component `initialData` ile hydration + client re-fetch (focus, badge
 * polling, vs.) için tek noktadan tipli hook'lar.
 *
 * QueryKey sözleşmesi: `web/lib/api/teacher.ts:teacherKeys` ile birebir aynı.
 * Backend `MutationResponse.invalidate` ile uyumlu (R-006).
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import {
  getTeacherDashboard,
  getTeacherStudents,
  getTeacherStudent,
  teacherKeys,
  type TeacherStudentsListParams,
} from "@/lib/api/teacher";
import type {
  TeacherDashboardResponse,
  TeacherStudentDetailResponse,
  TeacherStudentListResponse,
} from "@/lib/types/teacher";

export function useTeacherDashboard(
  initialData?: TeacherDashboardResponse,
): UseQueryResult<TeacherDashboardResponse> {
  return useQuery<TeacherDashboardResponse>({
    queryKey: teacherKeys.dashboard(),
    queryFn: () => getTeacherDashboard(),
    initialData,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}

export function useTeacherStudents(
  params: TeacherStudentsListParams,
  initialData?: TeacherStudentListResponse,
): UseQueryResult<TeacherStudentListResponse> {
  return useQuery<TeacherStudentListResponse>({
    queryKey: teacherKeys.studentsList(params),
    queryFn: () => getTeacherStudents(params),
    initialData,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}

export function useTeacherStudent(
  id: number,
  initialData?: TeacherStudentDetailResponse,
): UseQueryResult<TeacherStudentDetailResponse> {
  return useQuery<TeacherStudentDetailResponse>({
    queryKey: teacherKeys.student(id),
    queryFn: () => getTeacherStudent(id),
    initialData,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}
