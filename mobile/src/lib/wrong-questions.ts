/**
 * Yanlış Soru Arşivi — mobil veri katmanı (öğrenci).
 *
 * Backend uçları web ile AYNI (`/api/v2/student/wrong-questions*`). Fark:
 * mobilde foto YÜKLEME multipart FormData (RN file objesi) + görsel GÖSTERME
 * auth'lu BFF ucundan Bearer header ile (kod tabanında ikisi de ilk kez).
 */
import { apiRequest, API_BASE, ApiError, getAccessToken } from "./api";

// ---- Tipler (web schemas/wrong_question.py aynası) ----

export interface WrongImageRef {
  id: number;
  kind: "question" | "solution";
  content_type: string;
  size_bytes: number;
}

export interface WrongQuestion {
  id: number;
  status: "acik" | "kapandi";
  source_kind: "gorev" | "deneme" | "diger";
  error_type: string | null;
  error_type_label: string | null;
  subject_id: number | null;
  subject_name: string | null;
  topic_id: number | null;
  topic_name: string | null;
  book_name: string | null;
  section_label: string | null;
  note: string | null;
  coach_note: string | null;
  ai_question_text: string | null;
  ai_hint: string | null;
  ai_tagged_at: string | null;
  difficulty_guess: string | null;
  correct_streak: number;
  attempts_count: number;
  due_at: string | null;
  is_due: boolean;
  closed_at: string | null;
  created_at: string;
  images: WrongImageRef[];
}

export interface WrongCounts {
  total: number;
  open: number;
  closed: number;
  due: number;
}

export interface WrongListResponse {
  items: WrongQuestion[];
  counts: WrongCounts;
  error_type_labels: Record<string, string>;
}

export interface AiTagResult {
  item: WrongQuestion;
  matched_topic: boolean;
  hint_created: boolean;
  credits_charged: number;
}

interface Mutated<T> {
  data: T;
  invalidate?: string[];
}

export const wrongKeys = {
  list: ["student", "wrong-questions"] as const,
};

// ---- GET ----

export function getWrongQuestions(): Promise<WrongListResponse> {
  return apiRequest<WrongListResponse>("/api/v2/student/wrong-questions");
}

// ---- Multipart yükleme (apiRequest JSON sabit olduğu için ayrı) ----

export interface PhotoAsset {
  uri: string;
  mimeType?: string | null;
  fileName?: string | null;
}

function fileName(a: PhotoAsset, i: number): string {
  if (a.fileName) return a.fileName;
  const ext = (a.mimeType || "image/jpeg").split("/")[1] || "jpg";
  return `soru-${i}.${ext === "jpeg" ? "jpg" : ext}`;
}

async function uploadMultipart<T>(path: string, form: FormData): Promise<T> {
  const token = await getAccessToken();
  // content-type VERİLMEZ — RN FormData boundary'yi kendisi kurar.
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: token ? { authorization: `Bearer ${token}` } : {},
    body: form,
  });
  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail = (data as { detail?: unknown })?.detail ?? data;
    const code = (detail as { code?: string })?.code ?? `http_${res.status}`;
    const message =
      (detail as { message?: string })?.message ??
      (typeof detail === "string" ? detail : "Yükleme başarısız.");
    throw new ApiError(res.status, code, message, data);
  }
  return data as T;
}

/** Yanlış soru ekle — 0..N foto + bağlam alanları (multipart). */
export function createWrongQuestion(
  fields: {
    source_kind?: string;
    book_section_id?: number;
    task_id?: number;
    subject_id?: number;
    topic_id?: number;
    error_type?: string;
    note?: string;
  },
  photos: PhotoAsset[],
): Promise<Mutated<WrongQuestion>> {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) {
    if (v !== undefined && v !== null && v !== "") fd.append(k, String(v));
  }
  photos.forEach((p, i) => {
    // RN'de dosya objesi: { uri, name, type } — as any (RN FormData tipi web'den farklı)
    fd.append("photos", {
      uri: p.uri,
      name: fileName(p, i),
      type: p.mimeType || "image/jpeg",
    } as unknown as Blob);
  });
  return uploadMultipart<Mutated<WrongQuestion>>(
    "/api/v2/student/wrong-questions",
    fd,
  );
}

/** Mevcut kayda çözüm fotoğrafı ekle. */
export function addSolutionPhoto(
  wqId: number,
  photo: PhotoAsset,
): Promise<Mutated<WrongQuestion>> {
  const fd = new FormData();
  fd.append("file", {
    uri: photo.uri,
    name: fileName(photo, 0),
    type: photo.mimeType || "image/jpeg",
  } as unknown as Blob);
  fd.append("kind", "solution");
  return uploadMultipart<Mutated<WrongQuestion>>(
    `/api/v2/student/wrong-questions/${wqId}/images`,
    fd,
  );
}

// ---- Mutation (JSON) ----

export function attemptWrongQuestion(
  wqId: number,
  rating: 1 | 2 | 3 | 4,
): Promise<Mutated<WrongQuestion>> {
  return apiRequest(`/api/v2/student/wrong-questions/${wqId}/attempt`, {
    method: "POST",
    body: { rating },
  });
}

export function updateWrongQuestion(
  wqId: number,
  body: { topic_id?: number; error_type?: string; note?: string; clear_note?: boolean },
): Promise<Mutated<WrongQuestion>> {
  return apiRequest(`/api/v2/student/wrong-questions/${wqId}`, {
    method: "POST",
    body,
  });
}

export function aiTagWrongQuestion(wqId: number): Promise<Mutated<AiTagResult>> {
  return apiRequest(`/api/v2/student/wrong-questions/${wqId}/ai-tag`, {
    method: "POST",
  });
}

export function deleteWrongQuestion(wqId: number): Promise<Mutated<{ deleted: boolean }>> {
  return apiRequest(`/api/v2/student/wrong-questions/${wqId}`, {
    method: "DELETE",
  });
}

// ---- Auth'lu görsel gösterimi ----

export function wrongImageUri(wqId: number, imageId: number): string {
  return `${API_BASE}/api/v2/student/wrong-questions/${wqId}/images/${imageId}`;
}

/** RN <Image source> için auth header'lı kaynak (token secure-store'da). */
export async function wrongImageSource(
  wqId: number,
  imageId: number,
): Promise<{ uri: string; headers: Record<string, string> }> {
  const token = await getAccessToken();
  return {
    uri: wrongImageUri(wqId, imageId),
    headers: token ? { authorization: `Bearer ${token}` } : {},
  };
}
