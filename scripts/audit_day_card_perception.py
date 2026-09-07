"""Gün kartı — karışıklık algılama + kullanışlılık ÖLÇÜMÜ (2026-09-07).

Koç: "sabah/öğle/akşam belirgin ayrılmıyor, başlıkların ve görevlerin zemin
rengi aynı; gün içinde ne dersler ne periyotlar okunabilir."

Tahmin etmek yerine ÖLÇÜYORUZ. Seed: 1 gün · 3 periyot · 3 ders · 9 görev
(koçun tarif ettiği gerçek durum). Gerçek tarayıcıda çizilen kartta:

  1. HİYERARŞİ AYRIŞMASI — her katmanın (kart zemini · periyot başlığı ·
     ders başlığı · görev satırı) hesaplanmış arka plan rengi alınır;
     komşu katmanlar arası algısal fark ΔE (CIE76) ölçülür.
     Eşik: ΔE < 5 = insan gözü "aynı renk" der (JND ~2.3). Hiyerarşi
     katmanı ayrışmıyorsa Gestalt "kapatma/benzerlik" ilkesi çöker — koç
     nereye baktığını kaybeder.
  2. DERS AYRIŞMASI — farklı derslerin görev satırı zeminleri birbirinden
     ayrışıyor mu? (aynı ΔE)
  3. DİKEY YOĞUNLUK — 9 görevlik gün kaç piksel? Bir 1080p ekranda kaç
     görev sığar? Kaç kere kaydırmak gerekir?
  4. GÖRSEL AĞIRLIK ENVANTERİ — satır başına kaç rozet/ikon/metin parçası
     var (dikkat rekabeti). 6+ parça = tarama maliyeti yüksek.
  5. BAŞLIK TEKRARI — aynı ders adı bir günde kaç kez yazılıyor (ders
     başlığı + her satırdaki ders rozeti = gürültü).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import re
import secrets
from datetime import date, timedelta

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskType,
    Topic,
    User,
    UserRole,
)
from app.models.book import BookType
from app.services.security import hash_password

WEB = "http://localhost:3000"
PFX = f"perc_{secrets.token_hex(3)}"
PWD = "Percept!2345"


# ---------------------------------------------------------------- renk yardımcıları
def _parse_rgb(css: str) -> tuple[float, float, float, float] | None:
    m = re.match(r"rgba?\(([^)]+)\)", css or "")
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).replace("/", " ").split(",")]
    if len(parts) == 1:
        parts = m.group(1).split()
    nums = [float(p.rstrip("%")) for p in parts if p]
    if len(nums) == 3:
        return nums[0], nums[1], nums[2], 1.0
    if len(nums) >= 4:
        return nums[0], nums[1], nums[2], nums[3]
    return None


def _composite(fg: tuple, bg: tuple) -> tuple[float, float, float]:
    """rgba'yı arka plan üstüne bindir → opak rgb."""
    r, g, b, a = fg
    br, bgc, bb = bg[:3]
    return (r * a + br * (1 - a), g * a + bgc * (1 - a), b * a + bb * (1 - a))


def _rgb_to_lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 1.00000
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(c1: tuple, c2: tuple) -> float:
    l1, a1, b1 = _rgb_to_lab(c1)
    l2, a2, b2 = _rgb_to_lab(c2)
    return math.sqrt((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)


def verdict(de: float) -> str:
    if de < 2.3:
        return "AYNI (fark yok)"
    if de < 5:
        return "zar zor"
    if de < 10:
        return "fark edilir"
    return "belirgin"


# ---------------------------------------------------------------- seed
def _sweep_orphans(db) -> None:
    """Yarıda kesilen önceki koşuların artığı: student_book'u silinmiş ama
    section_progress satırı kalmış kayıtlar. SQLite'ta FK cascade kapalı;
    id yeniden kullanılınca yeni seed UNIQUE'e çarpar. Başlamadan süpür."""
    from sqlalchemy import text

    db.execute(text(
        "DELETE FROM section_progress "
        "WHERE student_book_id NOT IN (SELECT id FROM student_books)"
    ))
    db.commit()


def seed() -> dict:
    with SessionLocal() as db:
        _sweep_orphans(db)
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Algı Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Algı Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()

        subjects = []
        for i, nm in enumerate(("Matematik", "Fizik", "Türkçe")):
            s = Subject(name=f"{PFX} {nm}", teacher_id=coach.id, order=i + 1)
            db.add(s)
            db.flush()
            t = Topic(subject_id=s.id, name=f"{nm} Konusu", order=1,
                      teacher_id=coach.id)
            db.add(t)
            db.flush()
            b = Book(name=f"{nm} Soru Bankası", teacher_id=coach.id,
                     subject_id=s.id, type=BookType.SORU_BANKASI)
            db.add(b)
            db.flush()
            sec = BookSection(book_id=b.id, label=f"{nm} Bölümü", order=1,
                              test_count=50, topic_id=t.id)
            db.add(sec)
            db.flush()
            sb = StudentBook(student_id=st.id, book_id=b.id)
            db.add(sb)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                                   reserved_count=0, completed_count=0))
            subjects.append((s, b, sec))

        day = date.today()  # hafta penceresi içinde kalsın (bugün seçili gün)
        # 3 periyot × 3 ders = 9 görev — koçun tarif ettiği gün
        for period in ("morning", "noon", "evening"):
            for s, b, sec in subjects:
                t = Task(student_id=st.id, date=day, type=TaskType.TEST,
                         title=f"{b.name} — {sec.label}: 3 test",
                         is_draft=False, period=period)
                db.add(t)
                db.flush()
                db.add(TaskBookItem(task_id=t.id, book_id=b.id,
                                    book_section_id=sec.id, planned_count=3))
        db.commit()
        return {
            "coach": coach.id, "student": st.id,
            "subjects": [s.id for s, _, _ in subjects],
            "books": [b.id for _, b, _ in subjects],
            "email": f"{PFX}_t@test.invalid", "day": day.isoformat(),
        }


def cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uid = [ids["coach"], ids["student"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(uid)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        sbids = [r[0] for r in db.query(StudentBook.id)
                 .filter(StudentBook.book_id.in_(ids["books"])).all()]
        if sbids:
            db.execute(sa_delete(SectionProgress)
                       .where(SectionProgress.student_book_id.in_(sbids)))
            db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sbids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(User).where(User.id.in_(uid)))
        db.commit()


JS_PROBE = """
() => {
  const card = document.querySelector('#day-editor') || document.body;
  const bg = (el) => getComputedStyle(el).backgroundColor;
  // Efektif zemin: saydam katmanları üste doğru bindirmek için zinciri topla
  const chain = (el) => {
    const out = [];
    let n = el;
    while (n && n !== document.documentElement) {
      out.push(bg(n));
      n = n.parentElement;
    }
    out.push(bg(document.body), bg(document.documentElement));
    return out;
  };
  const periodHeads = [...document.querySelectorAll('div')].filter(d =>
    d.className && typeof d.className === 'string' &&
    d.querySelector(':scope > span.uppercase.tracking-wider.font-bold'));
  // Periyot BÖLGESİ zemini (yeni tasarım) — section[aria-label]
  const zones = [...document.querySelectorAll('section[aria-label]')];
  const subjectHeads = [...document.querySelectorAll('div.border-l-\\\\[3px\\\\]')].filter(d =>
    d.className.includes('bg-muted/20'));
  const rows = [...document.querySelectorAll('.task-row')];
  const pick = (els) => els.map(e => ({
    chain: chain(e), h: e.getBoundingClientRect().height,
    text: (e.innerText || '').slice(0, 80),
    badges: e.querySelectorAll('span.rounded, span.rounded-md, span.rounded-full').length,
    icons: e.querySelectorAll('svg').length,
  }));
  return {
    cardChain: chain(card),
    cardH: card.getBoundingClientRect().height,
    viewportH: window.innerHeight,
    period: pick(periodHeads),
    zones: pick(zones),
    subject: pick(subjectHeads),
    rows: pick(rows),
    subjectNameMentions: (document.querySelector('#day-editor') || document.body)
      .innerText.split(/\\n/).filter(l => /Matematik|Fizik|Türkçe/.test(l)).length,
  };
}
"""


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = seed()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{WEB}/teacher/students/{ids['student']}/week",
                      wait_until="networkidle")
            page.wait_for_timeout(3000)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(1200)
            # bugün varsayılan seçili gün (fihrist BUGÜN rozetli)
            page.wait_for_selector('.task-row', timeout=8000)
            page.wait_for_timeout(800)

            page.screenshot(path="/tmp/perception_before.png", full_page=True)
            data = page.evaluate(JS_PROBE)

            # GERÇEK PİKSEL ÖLÇÜMÜ: CSS zincirini bindirmek alfa'lı Tailwind
            # sınıflarında (bg-x/80) hata veriyor. Ekranın kendisinden oku.
            from PIL import Image
            import io as _io

            def px_at(sel: str, idx: int = 0, dx: int = 6, dy: int = 6):
                els = page.query_selector_all(sel)
                if len(els) <= idx:
                    return None
                box = els[idx].bounding_box()
                if not box:
                    return None
                # elemanı görünür kıl ve ekran görüntüsünü al
                els[idx].scroll_into_view_if_needed()
                page.wait_for_timeout(120)
                box = els[idx].bounding_box()
                shot = page.screenshot(clip={
                    "x": box["x"], "y": box["y"],
                    "width": max(1, min(box["width"], 400)),
                    "height": max(1, box["height"]),
                })
                im = Image.open(_io.BytesIO(shot)).convert("RGB")
                # sağ-alt köşeye yakın nokta: metin/ikonların uzağı
                x = min(im.width - 1, max(0, im.width - dx))
                y = min(im.height - 1, max(0, im.height - dy))
                return tuple(float(c) for c in im.getpixel((x, y)))

            data["px"] = {
                "card": px_at("#day-editor", 0, dx=10, dy=40),
                "period_head": px_at('section[aria-label] > div:first-child', 0, dx=120, dy=6),
                "zones": [px_at("section[aria-label]", i, dx=8, dy=8) for i in range(3)],
                "rows": [px_at(".task-row", i, dx=8, dy=6) for i in range(3)],
                "old_period_head": px_at("div.bg-foreground\/\[0\.07\]", 0),
            }
            b.close()
    finally:
        cleanup(ids)

    # ------------------------------------------------------------ analiz
    def effective(chain: list[str]) -> tuple[float, float, float]:
        """Zinciri alttan üste bindir (body → kart → eleman)."""
        acc = (255.0, 255.0, 255.0)
        for css in reversed(chain):
            c = _parse_rgb(css)
            if c is None or c[3] == 0:
                continue
            acc = _composite(c, acc)
        return acc

    px = data.get("px") or {}

    def eff_or_px(chain_key: str, px_key: str, idx: int | None = None):
        """Piksel ölçümü varsa onu, yoksa CSS zincirini kullan."""
        v = px.get(px_key)
        if isinstance(v, list) and idx is not None:
            v = v[idx] if idx < len(v) else None
        if v:
            return tuple(v)
        return None

    card_bg = eff_or_px("cardChain", "card") or effective(data["cardChain"])
    print("\n=== GÜN KARTI ALGI ÖLÇÜMÜ (1 gün · 3 periyot · 3 ders · 9 görev) ===\n")
    print(f"Kart zemini: rgb{tuple(round(x) for x in card_bg)}")

    print("\n[1] HİYERARŞİ AYRIŞMASI — komşu katmanlar arası renk farkı (ΔE)")
    print("    JND ≈ 2.3 · <5 'aynı renk' · ≥10 belirgin\n")
    findings: list[str] = []

    if data["period"]:
        p_bg = eff_or_px("", "period_head") or effective(data["period"][0]["chain"])
        de = delta_e(p_bg, card_bg)
        print(f"    periyot başlığı ↔ kart zemini : ΔE {de:5.1f}  → {verdict(de)}")
        if de < 10:
            findings.append(f"Periyot başlığı kart zemininden zar zor ayrışıyor (ΔE {de:.1f})")
    if data.get("zones"):
        z = [eff_or_px("", "zones", i) or effective(x["chain"])
             for i, x in enumerate(data["zones"])]
        for name, zb in zip(("Sabah", "Öğle", "Akşam"), z):
            de = delta_e(zb, card_bg)
            print(f"    {name:6} bölgesi ↔ kart zemini : ΔE {de:5.1f}  → {verdict(de)}")
        if len(z) >= 3:
            print(f"    Sabah ↔ Öğle bölgesi           : ΔE {delta_e(z[0], z[1]):5.1f}")
            print(f"    Öğle ↔ Akşam bölgesi           : ΔE {delta_e(z[1], z[2]):5.1f}")
    if data["subject"]:
        s_bg = effective(data["subject"][0]["chain"])
        de = delta_e(s_bg, card_bg)
        print(f"    ders başlığı    ↔ kart zemini : ΔE {de:5.1f}  → {verdict(de)}")
        if de < 5:
            findings.append(f"Ders başlığı kart zemininden AYRIŞMIYOR (ΔE {de:.1f})")
        if data["period"]:
            de2 = delta_e(s_bg, p_bg)
            print(f"    ders başlığı    ↔ periyot başl.: ΔE {de2:5.1f}  → {verdict(de2)}")
            if de2 < 10:
                findings.append(
                    f"Ders başlığı ile periyot başlığı iki ayrı hiyerarşi katmanı ama "
                    f"görsel fark küçük (ΔE {de2:.1f})"
                )
    if data["rows"]:
        r_bg = eff_or_px("", "rows", 0) or effective(data["rows"][0]["chain"])
        de = delta_e(r_bg, card_bg)
        print(f"    görev satırı    ↔ kart zemini : ΔE {de:5.1f}  → {verdict(de)}")
        if de < 2.3:
            findings.append("Görev satırı zemini kart zeminiyle BİREBİR AYNI — satırlar birbirinden yalnız metinle ayrılıyor")

    print("\n[2] DERS AYRIŞMASI — farklı derslerin satır zeminleri")
    if len(data["rows"]) >= 3:
        bgs = [eff_or_px("", "rows", i) or effective(r["chain"])
               for i, r in enumerate(data["rows"][:3])]
        d01 = delta_e(bgs[0], bgs[1])
        d12 = delta_e(bgs[1], bgs[2])
        print(f"    Matematik satırı ↔ Fizik satırı : ΔE {d01:5.1f}  → {verdict(d01)}")
        print(f"    Fizik satırı ↔ Türkçe satırı    : ΔE {d12:5.1f}  → {verdict(d12)}")
        if max(d01, d12) < 2.3:
            findings.append(
                "Farklı derslerin görev satırları AYNI zeminde — ders ancak 10px'lik "
                "rozet okunarak anlaşılıyor (ön-dikkat değil, okuma gerektirir)"
            )

    print("\n[3] DİKEY YOĞUNLUK")
    card_h = data["cardH"]
    vh = data["viewportH"]
    row_h = sum(r["h"] for r in data["rows"]) / max(1, len(data["rows"]))
    per_h = sum(r["h"] for r in data["period"]) / max(1, len(data["period"]))
    sub_h = sum(r["h"] for r in data["subject"]) / max(1, len(data["subject"]))
    overhead = len(data["period"]) * per_h + len(data["subject"]) * sub_h
    print(f"    kart yüksekliği        : {card_h:.0f}px  (ekran {vh}px → {card_h/vh:.1f} ekran)")
    print(f"    görev satırı ort.      : {row_h:.0f}px  → 9 görev = {9*row_h:.0f}px")
    print(f"    başlık yükü            : {len(data['period'])} periyot × {per_h:.0f}px + "
          f"{len(data['subject'])} ders × {sub_h:.0f}px = {overhead:.0f}px")
    if card_h > 0:
        ratio = overhead / card_h
        print(f"    başlık/içerik oranı    : %{100*ratio:.0f} — kartın bu kadarı BAŞLIK, görev değil")
        if ratio > 0.3:
            findings.append(
                f"Kartın %{100*ratio:.0f}'i başlık (periyot + ders). 9 görev için "
                f"{len(data['period']) + len(data['subject'])} başlık satırı var — "
                "ders başlıkları her periyotta tekrar ediyor"
            )
    if card_h > vh:
        findings.append(
            f"9 görevlik gün tek ekrana sığmıyor ({card_h:.0f}px > {vh}px) — "
            "koç sabahı görürken akşamı göremiyor; periyotlar arası kıyas kaydırma ister"
        )

    print("\n[4] GÖRSEL AĞIRLIK — görev satırı başına dikkat rekabeti")
    if data["rows"]:
        r0 = data["rows"][0]
        print(f"    rozet: {r0['badges']} · ikon: {r0['icons']} · metin: '{r0['text'][:60]}…'")
        parts = r0["badges"] + r0["icons"] + 2  # + başlık + sayı
        print(f"    satır başına görsel parça ≈ {parts}")
        if parts >= 6:
            findings.append(
                f"Görev satırında ≈{parts} görsel parça (ders rozeti + tip rozeti + "
                "ikonlar + başlık + sayı). Rozetler aynı boy/aynı stilde → hiçbiri öne çıkmıyor"
            )

    print("\n[5] BAŞLIK TEKRARI")
    print(f"    ders adı gün içinde {data['subjectNameMentions']} satırda geçiyor (3 ders için)")
    if data["subjectNameMentions"] > 9:
        findings.append(
            f"3 ders adı {data['subjectNameMentions']} kez yazılıyor: ders başlığı + her satırda "
            "ders rozeti + başlık içinde kitap adı → aynı bilgi 3 kez"
        )

    print("\n=== BULGULAR ===")
    for i, f in enumerate(findings, 1):
        print(f"  {i}. {f}")
    print(f"\nEkran görüntüsü: /tmp/perception_before.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
