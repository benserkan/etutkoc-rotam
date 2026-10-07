/**
 * Deneme analizi — saf yardımcılar (sunucu + istemci ortak).
 *
 * Ekran (sekmeler, detay penceresi) ve yazdırma (A4 karne) aynı hesabı
 * kullanır; sayı biçimi Türkçe (virgüllü ondalık).
 */
import type { ExamQuestionItem, ExamResultRow, ExamSectionValue } from "@/lib/types/teacher";

export function fmtNet(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(2).replace(".", ",");
}

export function fmtSigned(n: number): string {
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${fmtNet(Math.abs(n))}`;
}

export function fmtTRDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}.${String(m).padStart(2, "0")}.${y}`;
}

export function fmtInt(n: number): string {
  return n.toLocaleString("tr-TR");
}

export function sectionPenalty(section: ExamSectionValue): number {
  return section === "lgs" ? 3 : 4;
}

/** Aynı türde bir önceki deneme (rows DESC → listedeki bir sonraki eleman). */
/** Denemenin serisi: tür + genel/branş (eski yanıtlarda yalnız tür). */
export function rowSeries(r: ExamResultRow): string {
  return r.series_key || r.section;
}

export interface ExamSeriesOption {
  value: string;
  label: string;
  count: number;
  isBranch: boolean;
}

/** Seri seçenekleri — genel denemeler önce (sayıya göre), sonra branşlar. */
export function examSeriesOptions(rows: ExamResultRow[]): ExamSeriesOption[] {
  const map = new Map<string, ExamSeriesOption>();
  for (const r of rows) {
    const k = rowSeries(r);
    const e = map.get(k);
    if (e) e.count += 1;
    else
      map.set(k, {
        value: k,
        label: r.series_label || r.section_label,
        count: 1,
        isBranch: r.scope === "brans",
      });
  }
  return [...map.values()].sort(
    (a, b) => Number(a.isBranch) - Number(b.isBranch) || b.count - a.count,
  );
}

export function previousExam(rows: ExamResultRow[], row: ExamResultRow): ExamResultRow | null {
  const i = rows.findIndex((r) => r.id === row.id);
  return i >= 0 && i + 1 < rows.length ? rows[i + 1] : null;
}

function subjectKey(name: string): string {
  return name.toLocaleLowerCase("tr-TR").replace(/\s+/g, " ").trim();
}

/** Ders adına göre o denemedeki net (yoksa null). */
export function subjectNetIn(row: ExamResultRow | null, name: string): number | null {
  if (!row) return null;
  const k = subjectKey(name);
  const s = row.subjects.find((x) => subjectKey(x.name) === k);
  return s ? s.net : null;
}

/** Sıralama ÷ katılımcı (%) — karnede ikisi de yazıyorsa. */
export function percentile(row: ExamResultRow): number | null {
  const s = row.score;
  if (!s || !s.rank_overall || !s.participants || s.participants <= 0) return null;
  return Math.round((s.rank_overall / s.participants) * 1000) / 10;
}

/** Ders içinde ilk yarı ↔ ikinci yarı doğruluk (≥10 sorulu derslerde). */
export function halfDrop(items: ExamQuestionItem[]) {
  const by = new Map<string, ExamQuestionItem[]>();
  for (const q of items) {
    const arr = by.get(q.subject) ?? [];
    arr.push(q);
    by.set(q.subject, arr);
  }
  const out: { subject: string; n: number; first: number; second: number }[] = [];
  for (const [subject, qs] of by) {
    if (qs.length < 10) continue;
    const sorted = [...qs].sort((a, b) => (a.question_no ?? 0) - (b.question_no ?? 0));
    const h = Math.floor(sorted.length / 2);
    const acc = (arr: ExamQuestionItem[]) =>
      arr.length ? arr.filter((q) => q.result === "dogru").length / arr.length : 0;
    out.push({ subject, n: qs.length, first: acc(sorted.slice(0, h)), second: acc(sorted.slice(h)) });
  }
  return out;
}

/** Kural tabanlı kısa yorumlar — sayı uydurmaz, yalnız kayıtlı veriden. */
export function buildInsights(rows: ExamResultRow[]): string[] {
  const last = rows[0];
  if (!last) return [];
  const prev = rows[1] ?? null;
  const out: string[] = [];
  if (!prev) {
    out.push("Bu türde ilk deneme — gelişimi görmek için aynı türden ikinci denemeyi ekle.");
  } else {
    const d = last.net - prev.net;
    if (Math.abs(d) < 0.01) {
      out.push(`Toplam net önceki denemeyle aynı (${fmtNet(last.net)}).`);
    } else {
      out.push(
        `Toplam net önceki denemeye göre ${fmtSigned(d)} (${fmtNet(prev.net)} → ${fmtNet(last.net)}).`,
      );
    }
    const diffs = last.subjects
      .map((s) => {
        const p = subjectNetIn(prev, s.name);
        return p == null ? null : { name: s.name, d: s.net - p };
      })
      .filter((x): x is { name: string; d: number } => x != null);
    const up = [...diffs].sort((a, b) => b.d - a.d)[0];
    const down = [...diffs].sort((a, b) => a.d - b.d)[0];
    if (up && up.d >= 1) out.push(`En çok yükselen ders: ${up.name} (${fmtSigned(up.d)} net).`);
    if (down && down.d <= -1) out.push(`En çok düşen ders: ${down.name} (${fmtSigned(down.d)} net).`);
    const db = last.total_blank - prev.total_blank;
    if (db >= 3) {
      out.push(
        `Boş sayısı ${prev.total_blank} → ${last.total_blank} arttı — süre ya da çekingenlik konuşulabilir.`,
      );
    } else if (db <= -3) {
      out.push(`Boş sayısı ${prev.total_blank} → ${last.total_blank} azaldı.`);
    }
  }
  const p = percentile(last);
  if (p != null) out.push(`Katılımcıların ilk %${String(p).replace(".", ",")}'sinde.`);
  return out;
}

/** Paylaşım metni — WhatsApp/kopyala. Emoji YOK (bazı cihazlarda kırık kutu). */
export function buildShareText(
  row: ExamResultRow,
  prev: ExamResultRow | null,
  studentName?: string | null,
): string {
  const lines: string[] = [];
  lines.push(`*${studentName ? `${studentName} — ` : ""}${row.title}*`);
  lines.push(`${row.section_label} · ${fmtTRDate(row.exam_date)}`);
  lines.push("");
  let netLine = `Toplam net: *${fmtNet(row.net)}*`;
  if (prev) netLine += ` (önceki denemeye göre ${fmtSigned(row.net - prev.net)})`;
  lines.push(netLine);
  lines.push(`Doğru ${row.total_correct} · Yanlış ${row.total_wrong} · Boş ${row.total_blank}`);
  if (row.score?.score != null) {
    let s = `Puan: ${fmtNet(row.score.score)}`;
    if (row.score.rank_overall && row.score.participants) {
      s += ` · Sıralama: ${fmtInt(row.score.rank_overall)} / ${fmtInt(row.score.participants)}`;
    }
    lines.push(s);
  }
  if (row.subjects.length) {
    lines.push("");
    lines.push("Dersler:");
    for (const s of row.subjects) {
      const p = subjectNetIn(prev, s.name);
      lines.push(`• ${s.name}: ${fmtNet(s.net)} net${p != null ? ` (${fmtSigned(s.net - p)})` : ""}`);
    }
  }
  if (row.note) {
    lines.push("");
    lines.push(`Koç notu: ${row.note}`);
  }
  return lines.join("\n");
}

export function examPrintUrl(studentId: number, examId: number): string {
  return `/teacher/students/${studentId}/exams/${examId}/print`;
}
