"""Deneme duyurusu — ÖNİZLE / DÜZENLE / GÖNDER, GERÇEK TARAYICI (2026-09-10).

Dev sunucu (:3000 + :8081) + Playwright ister. Kendi seed'ini kurar/temizler.

KOÇ İSTEĞİ (birebir): "bir denemenin sonuç bilgileri veliye mail olarak
gönderilirken mail içeriğinin ne olduğu önizlenmeli (modal), düzenlenebilmeli —
kullanılan bazı ifadeler koç tarafından kaldırılma ihtiyacı hissedilebilir —
düzenleme yapılıp gönderilebilse daha iyi olurdu."

ÖNCESİ: `window.confirm` (görsel 1) — koç neyin gideceğini GÖRMEDEN onaylıyordu.

Senaryolar:
   1. Zarf düğmesi tarayıcı confirm'i DEĞİL modal açar
   2. Modalda mailin gerçek içeriği var (net · D/Y/B · yorum · ders tablosu)
   3. Alıcı veli listesi + gidecek sayısı butonda yazılı
   4. Modal AÇILDIĞINDA hiçbir bildirim gitmemiştir (salt okuma)
   5. Bir yorum cümlesi SİLİNİR (koçun asıl isteği)
   6. Kalan cümle DÜZENLENİR
   7. Koçun kendi cümlesi EKLENİR
   8. Ders tablosu çıkarılabilir (checkbox)
   9. "Gönder" → veliye giden mail KOÇUN metnini taşır, silinen cümle YOKTUR
  10. Gönderim sonrası satır "Duyuruldu" olur (mükerrer engeli)
  11. Koyu temada modal okunur (kontrast ölçümü)
  12. "Nerede net kazanabilir?" tablosu modalda + maile giden metinde
  13. Geçmiş denemelerle karşılaştırma tablosu (aynı tür, trend oku)
  14. İki bölüm de checkbox'la çıkarılabilir
  15. "PDF olarak indir" → yazdırma açılır, çıktı KOÇUN düzenlemesini taşır
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secrets
from datetime import date

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models.curriculum import Subject, Topic
from app.models.exam_result import ExamResultQuestion
from app.models import (
    ExamResult,
    ExamSection,
    NotificationKind,
    NotificationLog,
    ParentNotificationPref,
    ParentStudentLink,
    Track,
    User,
    UserRole,
)
from app.services.security import hash_password

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lea_{secrets.token_hex(3)}"
PWD = "ExamAnn!23456"
SHOT_DIR = os.environ.get("SHOT_DIR", os.path.join(os.getcwd(), ".shots"))

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Duyuru Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Emir Deneme", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12, track=Track.SAYISAL)
        parent = User(email=f"{PFX}_p@test.invalid", password_hash=hash_password(PWD),
                      full_name="Duyuru Veli", role=UserRole.PARENT, is_active=True)
        db.add_all([st, parent])
        db.flush()
        db.add(ParentStudentLink(parent_id=parent.id, student_id=st.id))
        db.add(ParentNotificationPref(parent_id=parent.id))
        db.flush()

        nets = (
            '[{"name":"TYT Türkçe","correct":36,"wrong":4,"blank":0,"net":35.0},'
            '{"name":"TYT Matematik","correct":20,"wrong":18,"blank":2,"net":15.5},'
            '{"name":"TYT Fizik","correct":6,"wrong":1,"blank":0,"net":5.75}]'
        )
        prev = ExamResult(
            student_id=st.id, title="Önceki TYT", exam_date=date(2026, 8, 20),
            section=ExamSection.TYT, total_correct=50, total_wrong=20,
            total_blank=50, net=45.0, created_by_id=coach.id,
        )
        db.add(prev)
        cur = ExamResult(
            student_id=st.id, title="ÇAP Maarif Birinci Basamak",
            exam_date=date(2026, 9, 5), section=ExamSection.TYT,
            total_correct=62, total_wrong=23, total_blank=35, net=56.25,
            created_by_id=coach.id, subject_nets=nets,
        )
        db.add(cur)
        db.flush()

        # NET FIRSATI + GECMIS KARSILASTIRMA icin: onceki denemeye de ders
        # netleri, iki denemeye de konu bagli soru satirlari.
        prev.subject_nets = (
            '[{"name":"TYT Türkçe","correct":33,"wrong":6,"blank":1,"net":31.5},'
            '{"name":"TYT Matematik","correct":17,"wrong":18,"blank":5,"net":12.5}]'
        )
        for sname, tname in (
            ("TYT Matematik", "Fonksiyonlar"),
            ("TYT Türkçe", "Paragrafta Anlam"),
        ):
            sub = db.query(Subject).filter(Subject.name == sname).first()
            if sub is None:
                sub = Subject(name=sname, teacher_id=None)
                db.add(sub)
                db.flush()
            tp = (db.query(Topic)
                  .filter(Topic.subject_id == sub.id, Topic.name == tname)
                  .first())
            if tp is None:
                tp = Topic(subject_id=sub.id, name=tname, order=0)
                db.add(tp)
                db.flush()
            for target in (cur, prev):
                for _ in range(2):
                    db.add(ExamResultQuestion(
                        exam_result_id=target.id, subject_id=sub.id,
                        topic_id=tp.id, result="yanlis",
                    ))
        db.flush()
        db.commit()
        return {
            "coach": coach.id, "student": st.id, "parent": parent.id,
            "exam": cur.id, "email": f"{PFX}_t@test.invalid",
        }


def cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uids = [ids["coach"], ids["student"], ids["parent"]]
        db.execute(sa_delete(NotificationLog).where(
            NotificationLog.parent_id.in_(uids)))
        db.execute(sa_delete(ParentNotificationPref).where(
            ParentNotificationPref.parent_id.in_(uids)))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(uids)))
        exam_ids = [r[0] for r in db.query(ExamResult.id)
                    .filter(ExamResult.student_id.in_(uids)).all()]
        if exam_ids:
            db.execute(sa_delete(ExamResultQuestion)
                       .where(ExamResultQuestion.exam_result_id.in_(exam_ids)))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def mail_count(parent_id: int) -> int:
    with SessionLocal() as db:
        return (
            db.query(NotificationLog)
            .filter(NotificationLog.parent_id == parent_id,
                    NotificationLog.kind == NotificationKind.EXAM_RESULT)
            .count()
        )


def last_mail(parent_id: int) -> dict:
    with SessionLocal() as db:
        log = (
            db.query(NotificationLog)
            .filter(NotificationLog.parent_id == parent_id,
                    NotificationLog.kind == NotificationKind.EXAM_RESULT)
            .order_by(NotificationLog.id.desc())
            .first()
        )
        if log is None:
            return {}
        try:
            return json.loads(log.payload_json or "{}")
        except (ValueError, TypeError):
            return {}


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOT_DIR, exist_ok=True)
    ids = seed()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1500, "height": 1000})

            # Tarayıcı confirm'i çıkarsa testi asmasın — ama çıkmamalı (senaryo 1)
            dialogs: list[str] = []
            page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))

            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            page.goto(
                f"{WEB}/teacher/students/{ids['student']}?period=all#exams",
                wait_until="networkidle",
            )
            page.wait_for_timeout(2500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(1000)
            tab = page.query_selector('button:has-text("Denemeler")')
            if tab:
                tab.click()
                page.wait_for_timeout(2000)

            before = mail_count(ids["parent"])

            # ---- 1. Zarf düğmesi → modal (confirm DEĞİL)
            env = page.query_selector('button[aria-label="Sonucu veliye duyur"]')
            if env is None:
                page.screenshot(path=os.path.join(SHOT_DIR, "ann_fail.png"),
                                full_page=True)
                check("1. zarf düğmesi bulunamadı", False, "buton yok")
                b.close()
                return 1
            env.click()
            page.wait_for_timeout(2500)
            modal = page.query_selector('[role="dialog"]')
            check(
                "1. tarayıcı confirm'i DEĞİL modal açılır",
                modal is not None and len(dialogs) == 0
                and "önizle" in (modal.inner_text().lower() if modal else ""),
                f"dialogs={dialogs} modal={modal is not None}",
            )
            if modal is None:
                b.close()
                return 1
            mtext = modal.inner_text()

            # ---- 2. Mailin gerçek içeriği
            check(
                "2. modalda mailin içeriği: net · D/Y/B · yorum · ders tablosu",
                "56,25" in mtext and "62 doğru" in mtext and "23 yanlış" in mtext
                and "Bu deneme ne anlatıyor?" in mtext
                and "TYT Matematik" in mtext and "TYT Türkçe" in mtext,
                mtext[:260],
            )

            # ---- 3. Alıcılar + gönder butonu sayıyı yazıyor
            send_btn = page.query_selector(
                '[role="dialog"] button:has-text("veliye gönder")')
            check(
                "3. alıcı velisi listelenir + buton kaç veliye gideceğini yazar",
                "Duyuru Veli" in mtext and send_btn is not None
                and "1 veliye gönder" in (send_btn.inner_text() if send_btn else ""),
                f"buton={send_btn.inner_text() if send_btn else None}",
            )

            # ---- 4. Önizleme salt okuma
            check("4. modal açılınca hiçbir mail gitmedi (salt okuma)",
                  mail_count(ids["parent"]) == before,
                  f"{before} → {mail_count(ids['parent'])}")

            page.screenshot(path=os.path.join(SHOT_DIR, "ann_preview.png"))
            # Modal uzun: alt bolumler (karsilastirma + firsat) icin ikinci kare
            page.evaluate(
                """() => {
                  const d = document.querySelector('[role="dialog"]');
                  if (d) d.scrollTop = d.scrollHeight;
                }"""
            )
            page.wait_for_timeout(600)
            page.screenshot(path=os.path.join(SHOT_DIR, "ann_preview_bottom.png"))
            page.evaluate(
                """() => {
                  const d = document.querySelector('[role="dialog"]');
                  if (d) d.scrollTop = 0;
                }"""
            )
            page.wait_for_timeout(400)

            areas = page.query_selector_all('[role="dialog"] textarea')
            n_before = len(areas)
            auto_lines = [a.input_value() for a in areas]
            check("5a. kural motorunun cümleleri düzenlenebilir alanlarda",
                  n_before >= 3 and any("net çıkardı" in x for x in auto_lines),
                  f"n={n_before} {auto_lines[:2]}")

            # ---- 5. SON cümleyi sil (koçun asıl isteği: ifade kaldırma)
            removed_text = auto_lines[-1]
            page.query_selector_all(
                '[role="dialog"] button[aria-label*="cümleyi kaldır"]'
            )[-1].click()
            page.wait_for_timeout(500)
            areas = page.query_selector_all('[role="dialog"] textarea')
            check("5b. cümle silinir (satır sayısı azalır)",
                  len(areas) == n_before - 1, f"{n_before} → {len(areas)}")

            # ---- 6. İlk cümleyi düzenle
            edited_first = "Merhaba, Emir bu denemede 56,25 net çıkardı."
            areas[0].fill(edited_first)
            page.wait_for_timeout(300)

            # ---- 7. Kendi cümlesini ekle
            page.click('[role="dialog"] button:has-text("Cümle ekle")')
            page.wait_for_timeout(400)
            areas = page.query_selector_all('[role="dialog"] textarea')
            own_line = "Cumartesi görüşmemizde ayrıntısını konuşacağız."
            areas[-1].fill(own_line)
            page.wait_for_timeout(300)
            check("6/7. cümle düzenlenir + koçun kendi cümlesi eklenir",
                  len(areas) == n_before and areas[0].input_value() == edited_first,
                  f"n={len(areas)} ilk={areas[0].input_value()[:50]}")

            # ---- 12/13. Net fırsatı + geçmiş karşılaştırma modalda
            mtext_pre = page.query_selector('[role="dialog"]').inner_text()
            check(
                "12. 'Nerede net kazanabilir?' tablosu modalda "
                "(konu + kazanç + toplam)",
                "Nerede net kazanabilir" in mtext_pre
                and "Fonksiyonlar" in mtext_pre
                and "Hepsi kapanırsa" in mtext_pre
                and "+5,00" in mtext_pre,
                mtext_pre[-420:],
            )
            check(
                "13. geçmiş karşılaştırma tablosu modalda "
                "(iki sütun + toplam net satırı)",
                "Önceki denemelerle karşılaştırma" in mtext_pre
                and "Toplam net" in mtext_pre
                and "20.08" in mtext_pre and "05.09" in mtext_pre,
                mtext_pre[-420:],
            )

            # ---- 14. İki bölüm de kapatılabilir
            page.uncheck(
                '[role="dialog"] label:has-text("Önceki denemelerle") input')
            page.uncheck(
                '[role="dialog"] label:has-text("Nerede net kazanabilir") input')
            page.wait_for_timeout(600)
            mtext_off = page.query_selector('[role="dialog"]').inner_text()
            check(
                "14. iki bölüm de checkbox'la çıkarılır (önizlemeden düşer)",
                "Toplam net" not in mtext_off and "Hepsi kapanırsa" not in mtext_off,
                mtext_off[-300:],
            )
            # geri aç — gönderim testinde ikisi de gitsin
            page.check(
                '[role="dialog"] label:has-text("Önceki denemelerle") input')
            page.check(
                '[role="dialog"] label:has-text("Nerede net kazanabilir") input')
            page.wait_for_timeout(500)

            # ---- 8. Ders tablosunu çıkar
            page.uncheck(
                '[role="dialog"] label:has-text("Ders bazında") input')
            page.wait_for_timeout(500)
            mtext2 = page.query_selector('[role="dialog"]').inner_text()
            check("8. ders tablosu checkbox'la çıkarılır (önizlemeden de düşer)",
                  "TYT Matematik" not in mtext2,
                  mtext2[-200:])

            page.screenshot(path=os.path.join(SHOT_DIR, "ann_edited.png"))

            # ---- 15. "PDF olarak indir" — yazdırma penceresi + içerik
            #      window.print() headless'ta diyalog açmaz; çağrıldığını
            #      yakalamak için stub'larız (buton gerçekten tetikliyor mu).
            page.evaluate(
                """() => {
                  window.__printed = 0;
                  const orig = window.print;
                  window.print = function () { window.__printed++; };
                  window.__origPrint = orig;
                  // iframe icindeki print de sayilsin
                  const obs = new MutationObserver((muts) => {
                    muts.forEach((m) => m.addedNodes.forEach((n) => {
                      if (n.tagName === 'IFRAME' && n.contentWindow) {
                        try {
                          n.contentWindow.print = function () {
                            window.__printed++;
                          };
                        } catch (e) {}
                      }
                    }));
                  });
                  obs.observe(document.body, { childList: true });
                }"""
            )
            mails_before_pdf = mail_count(ids["parent"])
            page.click('[role="dialog"] button:has-text("PDF olarak indir")')
            page.wait_for_timeout(3000)
            printed = page.evaluate("() => window.__printed || 0")
            frame_html = page.evaluate(
                """() => {
                  const f = [...document.querySelectorAll('iframe')].pop();
                  return f && f.contentDocument
                    ? f.contentDocument.documentElement.innerHTML
                    : '';
                }"""
            )
            check(
                "15a. 'PDF olarak indir' → yazdırma tetiklenir + çıktı mailin "
                "aynısı (net şeridi + koçun cümlesi)",
                printed >= 1
                and "56,25" in frame_html
                and edited_first in frame_html,
                f"printed={printed} len={len(frame_html)}",
            )
            check(
                "15b. çıktı koçun düzenlemesini taşır: silinen cümle YOK, "
                "kapatılan ders tablosu YOK",
                removed_text not in frame_html
                and "Ders bazında" not in frame_html
                and "Nerede net kazanabilir" in frame_html,
                frame_html[:200],
            )
            check(
                "15c. PDF çıktısı GÖNDERİM YAPMAZ",
                mail_count(ids["parent"]) == mails_before_pdf,
                f"{mails_before_pdf} -> {mail_count(ids['parent'])}",
            )
            page.evaluate("() => { if (window.__origPrint) window.print = window.__origPrint; }")

            # ---- 11. Koyu tema kontrastı (modal açıkken)
            page.evaluate("() => document.documentElement.classList.add('dark')")
            page.wait_for_timeout(700)
            low = measure(page, '[role="dialog"]', min_ratio=3.0)
            page.screenshot(path=os.path.join(SHOT_DIR, "ann_dark.png"))
            check("11. koyu temada modal okunur (kontrast ≥ 3.0 / WCAG AA)",
                  low["bad"] == 0, f"{low}")
            page.evaluate("() => document.documentElement.classList.remove('dark')")
            page.wait_for_timeout(400)

            # ---- 9. Gönder
            page.click('[role="dialog"] button:has-text("veliye gönder")')
            page.wait_for_timeout(3500)
            payload = last_mail(ids["parent"])
            narr = payload.get("narrative", [])
            check(
                "9. giden mail: KOÇUN metni + silinen cümle YOK + ders tablosu boş "
                "AMA net fırsatı ve karşılaştırma tabloları VAR",
                mail_count(ids["parent"]) == before + 1
                and narr and narr[0] == edited_first
                and own_line in narr
                and removed_text not in narr
                and payload.get("subjects") == []
                and payload.get("net_text") == "56,25"
                and len(payload.get("opportunities") or []) >= 2
                and (payload.get("history") or {}).get("has_data") is True,
                f"narr={narr} subj={payload.get('subjects')}",
            )

            # ---- 10. Satır "Duyuruldu"ya döner
            page.wait_for_timeout(1500)
            body = page.inner_text("body")
            check("10. gönderim sonrası satır 'Duyuruldu' olur",
                  "Duyuruldu" in body,
                  body[:200])
            page.screenshot(path=os.path.join(SHOT_DIR, "ann_sent.png"),
                            full_page=True)
            b.close()
    finally:
        cleanup(ids)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===  (ekran görüntüleri: {SHOT_DIR})")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
