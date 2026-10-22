"""Öğrenci programı / deneme sonuçları PDF'i — sunucuda (2026-10-21).

Mobil uygulama PDF üretemez (yerel modül yok); öğrenci "PDF" dediğinde kısa ömürlü imzalı
bir bağlantı alır, bağlantı bu modülün ürettiği PDF'i döner (telefonun PDF görüntüleyicisinde
açılır, oradan WhatsApp'a paylaşılır / kaydedilir).

Veri, web'in kullandığı uçlarla AYNI fonksiyonlardan (student_day_v2 / student_week_v2 /
student_exams_v2) — PDF ile ekran ayrışamaz. Yerleşim PyMuPDF ile doğrudan çizilir (HTML
tablo desteği zayıf); durum işaretleri vektör (font glifine bağlı değil).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date

import pymupdf
from sqlalchemy.orm import Session

from app.models import User

FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]

TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
             "Eylül", "Ekim", "Kasım", "Aralık"]
TR_DOW = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
DENEME_BOOK_TYPES = {"brans_denemesi", "genel_deneme"}
PERIOD_LABELS = {"morning": "Sabah", "noon": "Öğle", "evening": "Akşam"}

INK = (0.11, 0.1, 0.09)
MUTED = (0.45, 0.43, 0.41)
GREEN = (0.02, 0.47, 0.34)
AMBER = (0.71, 0.42, 0.0)
INDIGO = (0.26, 0.22, 0.79)
LINE = (0.82, 0.8, 0.78)


class PdfUnavailable(Exception):
    pass


def _fonts() -> tuple[str, str]:
    for reg, bold in FONT_CANDIDATES:
        if os.path.exists(reg) and os.path.exists(bold):
            return reg, bold
    raise PdfUnavailable("Türkçe font bulunamadı")


def long_date(iso: str, dow: bool = False) -> str:
    d = date.fromisoformat(iso)
    s = f"{d.day} {TR_MONTHS[d.month - 1]} {d.year}"
    return f"{s}, {TR_DOW[d.weekday()]}" if dow else s


def short_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {TR_MONTHS[d.month - 1][:3]}"


# ---------------------------------------------------------------- çizim yardımcısı

@dataclass
class Canvas:
    landscape: bool
    title: str
    subtitle: str
    student: str
    brand: str | None
    stats: str = ""
    doc: pymupdf.Document = field(default_factory=pymupdf.open)

    def __post_init__(self):
        self.reg_file, self.bold_file = _fonts()
        self.reg = pymupdf.Font(fontfile=self.reg_file)
        self.bold = pymupdf.Font(fontfile=self.bold_file)
        self.W, self.H = (842, 595) if self.landscape else (595, 842)
        self.M = 26

    # sayfa
    def page(self, i: int) -> int:
        """Sayfa i'yi (yoksa üretip) döner — İNDEKS döner: PyMuPDF yeni sayfa eklenince eski Page
        nesnelerini geçersiz kılar, çizim her seferinde doc[i] ile taze nesneye yapılır."""
        while self.doc.page_count <= i:
            p = self.doc.new_page(width=self.W, height=self.H)
            p.insert_font(fontname="R", fontfile=self.reg_file)
            p.insert_font(fontname="B", fontfile=self.bold_file)
            self._header(p)
        return i

    def P(self, p):
        return self.doc[p] if isinstance(p, int) else p

    @property
    def top(self) -> float:
        return self.M + 46

    @property
    def bottom(self) -> float:
        return self.H - self.M - 14

    def _header(self, p: pymupdf.Page):
        m = self.M
        self.text(p, m, m, self.title, 15, bold=True)
        tw = self.bold.text_length(self.title, 15)
        self.text(p, m + tw + 10, m + 3, self.student, 11, bold=True)
        sub = self.subtitle + (f" · {self.brand}" if self.brand else "")
        self.text(p, m, m + 21, sub, 8.5, color=MUTED)
        if self.stats:
            sw = self.reg.text_length(self.stats, 8.5)
            self.text(p, self.W - m - sw, m + 4, self.stats, 8.5)
        foot = "Altyapı: ETÜTKOÇ Rotam" if self.brand else "etütkoç · rotam"
        fw = self.reg.text_length(foot, 7.5)
        self.text(p, self.W - m - fw, m + 21, foot, 7.5, color=MUTED)
        p.draw_line((m, m + 36), (self.W - m, m + 36), color=INK, width=1.4)

    def finish(self) -> bytes:
        n = self.doc.page_count
        for i in range(n):
            s = f"{i + 1} / {n}"
            self.text(i, self.W - self.M - self.reg.text_length(s, 7), self.H - self.M, s, 7, color=MUTED)
        self.doc.subset_fonts()
        out = self.doc.tobytes(garbage=3, deflate=True)
        self.doc.close()
        return out

    # metin
    def text(self, p, x, y, s, size, bold=False, color=INK):
        p = self.P(p)
        p.insert_text((x, y + size), s, fontname="B" if bold else "R", fontsize=size, color=color)

    def width(self, s, size, bold=False) -> float:
        return (self.bold if bold else self.reg).text_length(s, size)

    def wrap(self, s: str, size: float, w: float, bold=False) -> list[str]:
        out: list[str] = []
        for para in (s or "").split("\n"):
            line = ""
            for word in para.split(" "):
                cand = f"{line} {word}".strip()
                if self.width(cand, size, bold) <= w:
                    line = cand
                    continue
                if line:
                    out.append(line)
                while self.width(word, size, bold) > w and len(word) > 1:  # çok uzun kelime
                    k = len(word)
                    while k > 1 and self.width(word[:k], size, bold) > w:
                        k -= 1
                    out.append(word[:k])
                    word = word[k:]
                line = word
            out.append(line)
        return out

    def mark(self, p, x, y, state: str, s: float = 6.5):
        p = self.P(p)
        r = pymupdf.Rect(x, y, x + s, y + s)
        if state == "done":
            p.draw_rect(r, color=GREEN, fill=GREEN, width=0.6)
            p.draw_polyline([(x + 1.3, y + s * 0.55), (x + s * 0.42, y + s - 1.4), (x + s - 1.1, y + 1.2)],
                            color=(1, 1, 1), width=1.1)
        elif state == "partial":
            p.draw_rect(r, color=AMBER, width=0.8)
            p.draw_rect(pymupdf.Rect(x, y + s / 2, x + s, y + s), color=AMBER, fill=AMBER, width=0.1)
        else:
            p.draw_rect(r, color=MUTED, width=0.7)


# ---------------------------------------------------------------- görev biçimi (web ile aynı kurallar)

def _is_deneme(t) -> bool:
    if any(it.exam_kind or (it.book_type in DENEME_BOOK_TYPES) for it in t.items):
        return True
    # soru/sayfa birimli kaynaksız konu kalemi (topic_id dolu) deneme değildir (2026-10-22)
    return bool(t.items) and all(it.book_id is None and it.is_test_unit is False and not it.topic_id
                                 for it in t.items)


def _state(t) -> str:
    if t.status == "completed" or (t.planned_count > 0 and t.completed_count >= t.planned_count):
        return "done"
    return "partial" if t.completed_count > 0 else "todo"


def _subject(t) -> str:
    if _is_deneme(t):
        return "Denemeler"
    for it in t.items:
        if it.subject_name:
            return it.subject_name
    if " · " in (t.title or ""):
        return t.title.split(" · ", 1)[0]
    return "Diğer"


def _unit(t) -> str:
    if t.work_block_unit:
        return t.work_block_unit
    if any(it.exam_kind for it in t.items):
        return "deneme"
    it = next((x for x in t.items if x.book_id is not None), t.items[0] if t.items else None)
    if it is not None and it.book_id is None and it.topic_id:
        return getattr(it, "unit", None) or "test"  # kaynaksız konu kalemi (2026-10-22)
    if it is not None and it.book_id is None and it.is_test_unit is False:
        return "soru"  # kitapsız tam deneme: planlanan = soru sayısı (web ile aynı)
    if it is not None and it.book_type in DENEME_BOOK_TYPES:
        return "deneme"
    return "test"


def _label(t) -> str:
    books = [it for it in t.items if it.book_id is not None]
    if len(books) > 1:
        same = all(it.book_id == books[0].book_id for it in books)
        parts = [f"{'' if same else it.book_name + ' · '}{it.section_label or ''} ({it.planned})" for it in books]
        return (f"{books[0].book_name} — " if same else "") + " · ".join(parts)
    if books:
        return books[0].book_name + (f" · {books[0].section_label}" if books[0].section_label else "")
    return t.title or "—"


def _activity(t) -> bool:
    return t.planned_count <= 0 and all((it.planned or 0) <= 0 for it in t.items)


def _groups(tasks) -> list[tuple[str | None, list[tuple[str, list]]]]:
    use_p = any(t.period for t in tasks)
    keys = ["morning", "noon", "evening", None] if use_p else ["_all"]
    out = []
    for k in keys:
        if k == "_all":
            ts = list(tasks)
        elif k is None:
            ts = [t for t in tasks if t.period not in PERIOD_LABELS]
        else:
            ts = [t for t in tasks if t.period == k]
        if not ts:
            continue
        g: dict[str, list] = {}
        for t in ts:
            g.setdefault(_subject(t), []).append(t)
        label = None if k == "_all" else (PERIOD_LABELS.get(k) if k else "Zamanı belirsiz")
        out.append((label, list(g.items())))
    return out


def _brand(db: Session, user: User) -> str | None:
    try:
        from app.services.branding import brand_for_user

        b = brand_for_user(db, user)
        return b.name if b else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- HAFTA

def build_week_pdf(db: Session, user: User, start: str | None) -> tuple[bytes, str]:
    from app.routes.api_v2.student import student_week_v2

    wk = student_week_v2(start_param=start, user=user, db=db)
    stats = f"Görev {wk.total_gorev_done}/{wk.total_gorev}"
    if wk.total_test_planned:
        stats += f"   Test {wk.total_test_completed}/{wk.total_test_planned}"
    cv = Canvas(True, "Haftalık Program", f"{long_date(wk.start_date)} — {long_date(wk.end_date)}",
                user.full_name or "", _brand(db, user), stats)
    gap = 5
    colw = (cv.W - 2 * cv.M - 6 * gap) / 7
    for ci, day in enumerate(wk.days):
        x = cv.M + ci * (colw + gap)
        pi, y = 0, cv.top
        p = cv.page(0)

        def head(page, yy, cont=False):
            r = pymupdf.Rect(x, yy, x + colw, yy + 15)
            dark = day.is_today
            cv.P(page).draw_rect(r, color=INK if dark else LINE, fill=INK if dark else (0.95, 0.94, 0.93), width=0.5)
            cv.text(page, x + 3, yy + 3, day.dow_label + (" (devam)" if cont else ""), 7.5, bold=True,
                    color=(1, 1, 1) if dark else INK)
            ds = short_date(day.date)
            cv.text(page, x + colw - 3 - cv.width(ds, 6.5), yy + 4, ds, 6.5,
                    color=(0.85, 0.85, 0.85) if dark else MUTED)
            return yy + 19

        y = head(p, y)

        def need(h):
            nonlocal pi, y, p
            if y + h > cv.bottom:
                pi += 1
                p = cv.page(pi)
                y = head(p, cv.top, cont=True)

        if not day.tasks:
            cv.text(p, x + 3, y, "—", 7, color=MUTED)
            continue
        for plabel, groups in _groups(day.tasks):
            if plabel:
                need(10)
                cv.text(p, x + 2, y, plabel.upper(), 6, bold=True, color=MUTED)
                cv.P(p).draw_line((x, y + 8), (x + colw, y + 8), color=LINE, width=0.4)
                y += 10
            for sname, ts in groups:
                need(10)
                cv.text(p, x + 2, y, sname, 7, bold=True, color=INDIGO if sname == "Denemeler" else INK)
                y += 9.5
                for t in ts:
                    tail = "" if _activity(t) else f" {t.completed_count}/{t.planned_count} {_unit(t)}"
                    lines = cv.wrap(_label(t) + tail, 6.6, colw - 12)
                    need(len(lines) * 8 + 2)
                    cv.mark(p, x + 2, y + 0.8, _state(t), 5.5)
                    for ln in lines:
                        cv.text(p, x + 10, y, ln, 6.6, color=MUTED if _state(t) == "done" else INK)
                        y += 8
                    y += 1.5
                y += 2
    cv.page(0)
    return cv.finish(), f"haftalik-program-{wk.start_date}.pdf"


# ---------------------------------------------------------------- GÜN

def build_day_pdf(db: Session, user: User, day_iso: str | None) -> tuple[bytes, str]:
    from app.routes.api_v2.student import student_day_v2

    day = student_day_v2(date_param=day_iso, user=user, db=db)
    s = day.summary
    stats = f"Görev {s.gorev_done}/{s.gorev_total}"
    if s.test_planned:
        stats += f"   Test {s.test_completed}/{s.test_planned}"
    if s.deneme_count:
        stats += f"   Deneme {s.deneme_count}"
    cv = Canvas(False, "Günün Programı", long_date(day.date, dow=True), user.full_name or "", _brand(db, user), stats)
    pi, y = 0, cv.top
    p = cv.page(0)
    x0, w = cv.M, cv.W - 2 * cv.M

    def need(h):
        nonlocal pi, y, p
        if y + h > cv.bottom:
            pi += 1
            p = cv.page(pi)
            y = cv.top

    if not day.tasks:
        cv.text(p, x0, y, "Bu gün için görev yok.", 10, color=MUTED)
    for plabel, groups in _groups(day.tasks):
        if plabel:
            need(16)
            cv.text(p, x0, y, plabel.upper(), 8, bold=True, color=MUTED)
            cv.P(p).draw_line((x0, y + 11), (x0 + w, y + 11), color=LINE, width=0.5)
            y += 15
        for sname, ts in groups:
            need(18)
            cv.text(p, x0, y, sname, 11, bold=True, color=INDIGO if sname == "Denemeler" else INK)
            y += 16
            for t in ts:
                deneme = _is_deneme(t)
                act = _activity(t)
                head = (t.title or "—") + ("" if act else f"   {t.completed_count}/{t.planned_count} {_unit(t)}")
                lines = cv.wrap(head, 9.5, w - 26, bold=True)
                books = [it for it in t.items if it.book_id is not None or it.topic_name]
                sub = [f"· {it.section_label or it.topic_name or it.book_name} ({it.planned})" for it in books] if len(books) > 1 else []
                videos = [f"{i + 1}. {v.title}" for i, v in enumerate(t.videos or [])] if len(t.videos or []) > 1 else []
                h = 8 + len(lines) * 12 + (len(sub) + len(videos)) * 10 + (14 if not act else 0) + 6
                need(h)
                box = pymupdf.Rect(x0, y, x0 + w, y + h - 4)
                cv.P(p).draw_rect(box, color=INDIGO if deneme else LINE, width=0.9 if deneme else 0.6)
                cv.mark(p, x0 + 7, y + 7, _state(t), 8)
                yy = y + 5
                for ln in lines:
                    cv.text(p, x0 + 21, yy, ln, 9.5, bold=True)
                    yy += 12
                for ln in sub + videos:
                    cv.text(p, x0 + 21, yy, ln, 8, color=MUTED)
                    yy += 10
                if not act:
                    fields = "Doğru ______   Yanlış ______   Boş ______"
                    if deneme:
                        fields += "   Net ______   Süre ______ dk"
                    cv.text(p, x0 + 21, yy + 1, fields, 8, color=MUTED)
                y += h
            y += 4
    need(70)
    y += 6
    cv.text(p, x0, y, "GÜNÜN NOTU", 8, bold=True, color=MUTED)
    y += 14
    if day.day_note:
        for ln in cv.wrap(day.day_note, 9, w):
            need(12)
            cv.text(p, x0, y, ln, 9)
            y += 12
    else:
        for _ in range(3):
            y += 16
            cv.P(p).draw_line((x0, y), (x0 + w, y), color=LINE, width=0.5)
    return cv.finish(), f"gunun-programi-{day.date}.pdf"


# ---------------------------------------------------------------- DENEMELER

def _fmt(n: float) -> str:
    s = f"{n:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def build_exams_pdf(db: Session, user: User) -> tuple[bytes, str]:
    from app.routes.api_v2.student import student_exams_v2

    data = student_exams_v2(period=None, user=user, db=db)
    karne = sorted(data.rows, key=lambda r: r.exam_date)
    program = sorted(data.program_rows or [], key=lambda r: r.exam_date)
    today = date.today().isoformat()
    stats = f"{len(karne)} deneme" + (f"   {len(program)} branş denemesi" if program else "")
    cv = Canvas(False, "Deneme Sonuçlarım", f"{long_date(today)} itibarıyla", user.full_name or "", _brand(db, user), stats)
    pi, y = 0, cv.top
    p = cv.page(0)
    x0, w = cv.M, cv.W - 2 * cv.M
    cols = [("Tarih", 52), ("Deneme", w - 52 - 3 * 30 - 44 - 46), ("D", 30), ("Y", 30), ("B", 30), ("Net", 44), ("Fark", 46)]

    def need(h):
        nonlocal pi, y, p
        if y + h > cv.bottom:
            pi += 1
            p = cv.page(pi)
            y = cv.top

    def table(title: str, rows, with_subjects: bool):
        nonlocal y
        best = max(r.net for r in rows)
        need(40)
        cv.text(p, x0, y, title, 11, bold=True)
        tail = f"  · {len(rows)} deneme · en iyi {_fmt(best)} net"
        cv.text(p, x0 + cv.width(title, 11, True), y + 2, tail, 8, color=MUTED)
        y += 16
        cv.P(p).draw_rect(pymupdf.Rect(x0, y, x0 + w, y + 13), color=LINE, fill=(0.95, 0.94, 0.93), width=0.5)
        cx = x0
        for name, cw in cols:
            cv.text(p, cx + 3, y + 3, name, 7.5, bold=True, color=MUTED)
            cx += cw
        y += 13
        prev = None
        for r in rows:
            name_lines = cv.wrap(r.title, 8.5, cols[1][1] - 6)
            subj = ""
            if with_subjects and r.subjects:
                subj = " · ".join(f"{s.name} {_fmt(s.net)}" for s in r.subjects)
            subj_lines = cv.wrap(subj, 7, cols[1][1] - 6) if subj else []
            h = 6 + len(name_lines) * 10.5 + len(subj_lines) * 9
            need(h)
            cx = x0
            vals = [".".join(reversed(r.exam_date.split("-"))), None, str(r.total_correct), str(r.total_wrong),
                    str(r.total_blank), _fmt(r.net), None]
            for (name, cw), v in zip(cols, vals):
                if v is not None:
                    cv.text(p, cx + 3, y + 3, v, 8.5, bold=(name == "Net"))
                cx += cw
            yy = y + 3
            for ln in name_lines:
                cv.text(p, x0 + cols[0][1] + 3, yy, ln, 8.5)
                yy += 10.5
            for ln in subj_lines:
                cv.text(p, x0 + cols[0][1] + 3, yy, ln, 7, color=MUTED)
                yy += 9
            if prev is not None:
                d = r.net - prev
                s = f"{'+' if d >= 0 else ''}{_fmt(d)}"
                cv.text(p, x0 + w - 46 + 3, y + 3, s, 8.5, color=GREEN if d >= 0 else (0.75, 0.1, 0.2))
            prev = r.net
            y += h
            cv.P(p).draw_line((x0, y), (x0 + w, y), color=LINE, width=0.4)
        y += 14

    def by_series(rows):
        g: dict[str, list] = {}
        for r in rows:
            g.setdefault(r.series_label or r.section_label, []).append(r)
        return g.items()

    if not karne and not program:
        cv.text(p, x0, y, "Henüz deneme sonucu yok.", 10, color=MUTED)
    for title, rows in by_series(karne):
        table(title, rows, True)
    if program:
        need(30)
        cv.text(p, x0, y, "PROGRAMDAKİ BRANŞ DENEMELERİ", 8, bold=True, color=INDIGO)
        y += 14
        for title, rows in by_series(program):
            table(title, rows, False)
    need(14)
    cv.text(p, x0, y, "Netler yalnız aynı türdeki denemelerle kıyaslanır. Net = Doğru − Yanlış ÷ ceza (LGS 3, YKS 4).",
            7, color=MUTED)
    return cv.finish(), f"deneme-sonuclarim-{today}.pdf"


def build_pdf(db: Session, user: User, kind: str, day_iso: str | None) -> tuple[bytes, str]:
    if kind == "week":
        return build_week_pdf(db, user, day_iso)
    if kind == "day":
        return build_day_pdf(db, user, day_iso)
    if kind == "exams":
        return build_exams_pdf(db, user)
    raise ValueError(kind)
