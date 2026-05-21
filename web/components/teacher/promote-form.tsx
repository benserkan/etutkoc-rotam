"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, GraduationCap, Loader2, TriangleAlert } from "lucide-react";

import { getTeacherPromoteForm, teacherKeys } from "@/lib/api/teacher";
import { usePromoteStudent } from "@/lib/hooks/use-teacher-mutations";
import type {
  GradeChoice,
  GraduateMode,
  PromoteFormResponse,
  Track,
} from "@/lib/types/teacher";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Props {
  studentId: number;
}

/**
 * "Sınıf Yükselt / Yeni Öğretim Yılı" — Jinja `teacher/student_promote.html`
 * paritesi. Mevcut durum + yeni form + canlı müfredat tahmini.
 *
 * Müfredat türetme kuralları (parite — `app/models/curriculum.py`):
 *   - 5-8 → LGS (her zaman)
 *   - 9-10 → MAARIF_LISE (her zaman; 2024'ten itibaren Maarif kohortu)
 *   - 11-12 / mezun → akademik yıl + sınıf'tan entry_year_grade9 türetilir;
 *     entry ≥ 2024 → Maarif, < 2024 → Klasik (son nesil)
 *   - Akademik yıl seçilmediyse Maarif/Klasik tahmini yapılamaz
 */
export function PromoteForm({ studentId }: Props) {
  const q = useQuery<PromoteFormResponse>({
    queryKey: teacherKeys.studentPromoteForm(studentId),
    queryFn: () => getTeacherPromoteForm(studentId),
    staleTime: 30_000,
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-12">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
      </div>
    );
  }
  if (q.error || !q.data) {
    return (
      <div className="text-sm text-rose-600">Form yüklenemedi.</div>
    );
  }

  return <FormBody studentId={studentId} initial={q.data} />;
}

function FormBody({
  studentId,
  initial,
}: {
  studentId: number;
  initial: PromoteFormResponse;
}) {
  const router = useRouter();
  const [grade, setGrade] = React.useState<GradeChoice>(
    initial.suggested_grade as GradeChoice,
  );
  const [yearId, setYearId] = React.useState<number | "">(
    initial.suggested_year_id ?? "",
  );
  const [track, setTrack] = React.useState<Track | "">(
    (initial.current_track ?? "") as Track | "",
  );
  const [graduateMode, setGraduateMode] = React.useState<GraduateMode | "">(
    (initial.current_graduate_mode ?? "") as GraduateMode | "",
  );
  const [entryYear, setEntryYear] = React.useState<string>(
    initial.entry_year_grade9 != null ? String(initial.entry_year_grade9) : "",
  );

  const isGraduate = grade === "graduate";
  const numericGrade = isGraduate ? null : Number(grade);
  const trackRequired = isGraduate || (numericGrade !== null && numericGrade >= 11);

  const selectedYear = initial.years.find((y) => y.id === yearId);
  const yearStart = selectedYear?.start_year ?? null;

  const curriculumPreview = React.useMemo(
    () => deriveCurriculum({
      grade: numericGrade,
      isGraduate,
      yearStart,
      entryOverride: entryYear ? Number(entryYear) : null,
      maarifFirst: initial.maarif_first_grade9_year,
    }),
    [numericGrade, isGraduate, yearStart, entryYear, initial.maarif_first_grade9_year],
  );

  const isCurriculumChanging =
    curriculumPreview &&
    initial.current_curriculum_model &&
    curriculumPreview.key !== initial.current_curriculum_model;

  const promote = usePromoteStudent(studentId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const entryNum = entryYear ? Number(entryYear) : null;
    promote.mutate(
      {
        body: {
          grade,
          academic_year_id: yearId === "" ? null : yearId,
          track: track || null,
          graduate_mode: isGraduate ? (graduateMode || null) : null,
          entry_year_grade9:
            entryNum && entryNum >= 2000 && entryNum <= 2100 ? entryNum : null,
        },
      },
      {
        onSuccess: () => {
          router.push(`/teacher/students/${studentId}`);
        },
      },
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <header>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          <Link
            href={`/teacher/students/${studentId}`}
            className="hover:underline"
          >
            ← {initial.student_name}
          </Link>
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
          <ArrowUpRight className="size-6 text-violet-600" aria-hidden />
          {initial.is_graduate ? "Yeni Öğretim Yılı" : "Sınıf Yükselt"}
        </h1>
        <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
          {initial.is_graduate
            ? "Mezun öğrenciler için sınıf değişmez; yeni öğretim yılına geçerken akademik yıl, alan ve çalışma şekli güncellenebilir."
            : "Yeni akademik yıla geçişte öğrencinin sınıf, alan ve müfredat bilgilerini güncelleyin."}{" "}
          <b>Kitap kütüphanesi ve görev tarihçesi korunur.</b>
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
              Mevcut durum
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <Row label="Sınıf" value={initial.current_grade_label} />
              <Row label="Akademik yıl" value={initial.current_academic_year_name} />
              <Row label="Alan" value={initial.current_track_label} />
              <Row label="Müfredat" value={initial.current_curriculum_label} />
              <Row label="Hedef sınav" value={initial.current_exam_label} />
              {initial.is_graduate && initial.current_graduate_mode ? (
                <Row
                  label="Çalışma şekli"
                  value={
                    initial.current_graduate_mode === "full_time"
                      ? "Tam-zamanlı (okul yok)"
                      : "Dershane / etüt merkezi"
                  }
                />
              ) : null}
            </dl>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-violet-500 ring-1 ring-inset ring-violet-500/10">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase tracking-wider text-violet-500 font-medium">
              Yeni durum
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <Field label="Akademik yıl">
                <select
                  value={yearId}
                  onChange={(e) =>
                    setYearId(e.target.value === "" ? "" : Number(e.target.value))
                  }
                  className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                >
                  <option value="">— Değişiklik yok —</option>
                  {initial.years.map((y) => (
                    <option key={y.id} value={y.id}>
                      {y.name}
                    </option>
                  ))}
                </select>
                {initial.years.length === 0 ? (
                  <p className="text-[11px] text-muted-foreground mt-1">
                    Listede yıl yok — önce{" "}
                    <Link
                      href="/teacher/years"
                      className="text-indigo-600 hover:underline"
                    >
                      akademik yıllar
                    </Link>{" "}
                    sayfasından ekleyin.
                  </p>
                ) : null}
              </Field>

              <Field label="Yeni sınıf" required>
                <select
                  value={grade}
                  onChange={(e) => setGrade(e.target.value as GradeChoice)}
                  required
                  className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                >
                  {initial.grade_choices.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </Field>

              {trackRequired ? (
                <Field label="Alan (YKS)" required>
                  <select
                    value={track}
                    onChange={(e) => setTrack(e.target.value as Track | "")}
                    required
                    className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                  >
                    <option value="">— Seçiniz —</option>
                    {initial.track_choices.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-muted-foreground mt-1">
                    11. sınıf, 12. sınıf ve mezunlar için zorunlu.
                  </p>
                </Field>
              ) : null}

              {isGraduate ? (
                <Field label="Çalışma şekli" required>
                  <select
                    value={graduateMode}
                    onChange={(e) =>
                      setGraduateMode(e.target.value as GraduateMode | "")
                    }
                    required
                    className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                  >
                    <option value="">— Seçiniz —</option>
                    {initial.graduate_mode_choices.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </Field>
              ) : null}

              <details className="border-t border-border pt-3">
                <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                  İleri: 9&apos;a giriş yılı override (sınıf tekrarı vb.)
                </summary>
                <div className="mt-2">
                  <input
                    type="number"
                    value={entryYear}
                    onChange={(e) => setEntryYear(e.target.value)}
                    min={2000}
                    max={2100}
                    placeholder="örn 2023"
                    className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                  />
                  <p className="text-[11px] text-muted-foreground mt-1">
                    Boş bırakılırsa akademik yıl + sınıftan tahmin edilir.
                    Maarif/Klasik kohort kararını override eder.
                  </p>
                </div>
              </details>

              {curriculumPreview ? (
                <div className="rounded-lg border-l-4 border-l-violet-500 bg-violet-500/5 px-3 py-2.5">
                  <div className="text-[11px] uppercase tracking-wider text-violet-500 font-semibold">
                    Yeni müfredat tahmini
                  </div>
                  <div className="text-sm font-bold text-foreground mt-0.5">
                    {curriculumPreview.label}
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    {curriculumPreview.explain}
                  </div>
                  {isCurriculumChanging ? (
                    <div className="mt-2 text-[11px] rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-1.5 inline-flex items-start gap-1.5">
                      <TriangleAlert
                        className="size-3.5 text-amber-500 mt-0.5 flex-shrink-0"
                        aria-hidden
                      />
                      <span className="text-foreground/90">
                        Müfredat modeli değişiyor — bazı kitap/dersler artık
                        eşleşmeyebilir. Yeni yılda kütüphaneyi gözden geçirin.
                      </span>
                    </div>
                  ) : null}
                </div>
              ) : trackRequired && yearStart === null ? (
                <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
                  Akademik yıl seçilince Maarif/Klasik tahmini yapılır.
                </div>
              ) : null}

              <div className="flex items-center justify-between pt-3 border-t border-border">
                <Link
                  href={`/teacher/students/${studentId}`}
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Vazgeç
                </Link>
                <Button type="submit" disabled={promote.isPending}>
                  {promote.isPending ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                  ) : (
                    <GraduationCap className="size-4" aria-hidden />
                  )}
                  {initial.is_graduate
                    ? "Yeni yıla geç ve kaydet"
                    : "Yükselt ve kaydet"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex gap-2">
      <dt className="w-32 text-muted-foreground flex-shrink-0">{label}:</dt>
      <dd className="font-medium text-foreground">{value || "—"}</dd>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm text-foreground mb-1">
        {label}
        {required ? <span className="text-rose-500 ml-0.5">*</span> : null}
      </label>
      {children}
    </div>
  );
}

/**
 * Müfredat türetme — `app/models/curriculum.py` derive_curriculum_model paritesi.
 */
function deriveCurriculum({
  grade,
  isGraduate,
  yearStart,
  entryOverride,
  maarifFirst,
}: {
  grade: number | null;
  isGraduate: boolean;
  yearStart: number | null;
  entryOverride: number | null;
  maarifFirst: number;
}): { key: string; label: string; explain: string } | null {
  if (grade === null && !isGraduate) return null;
  if (!isGraduate && grade !== null && grade <= 8) {
    return { key: "lgs", label: "LGS Müfredatı", explain: "5-8 her zaman LGS müfredatına bağlı" };
  }
  if (!isGraduate && (grade === 9 || grade === 10)) {
    return {
      key: "maarif_lise",
      label: "Maarif Modeli",
      explain: "9-10 her zaman Maarif kohortu",
    };
  }
  let entry: number | null = entryOverride;
  if (entry === null && yearStart !== null) {
    if (isGraduate) entry = yearStart - 4;
    else if (grade !== null) entry = yearStart - (grade - 9);
  }
  if (entry === null) return null;
  if (entry >= maarifFirst) {
    return {
      key: "maarif_lise",
      label: "Maarif Modeli",
      explain: `9'a ${entry}'te girdi → Maarif kohortu`,
    };
  }
  return {
    key: "klasik_lise",
    label: "Klasik Lise",
    explain: `9'a ${entry}'te girdi → Klasik (son nesil)`,
  };
}
