"""Admin haftalık özet — veri toplama + gönderim servisi.

Cron her Pazartesi 09:00 UTC çalışır ve her aktif kurum için
build_weekly_digest_payload() ile özeti üretip e-posta gönderir.
İdempotency: aynı (institution, week_start) zaten varsa atlanır.

Snapshot UI'da arşiv olarak da gösterilir.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AdminWeeklyDigest,
    Institution,
    User,
    UserRole,
)
from app.services.cohort_analysis import (
    cohort_by_grade,
    cohort_by_track,
    institution_week_over_week,
)
from app.services import completion
from app.services.email_service import send_email
from app.services.risk_analysis import (
    bulk_risk_assessment,
    filter_at_risk,
)
from app.services.teacher_activity import inactive_teachers


logger = logging.getLogger(__name__)


# ---------------------------- Tarih yardımcıları ----------------------------


def _monday_of_week(d: date) -> date:
    """Verilen günün haftasının Pazartesi başlangıcı (0=Mon, 6=Sun)."""
    return d - timedelta(days=d.weekday())


def previous_week_start(today: date | None = None) -> date:
    """Geçen haftanın Pazartesi günü — rapor bu hafta için 'geçen hafta'."""
    if today is None:
        today = date.today()
    this_monday = _monday_of_week(today)
    return this_monday - timedelta(days=7)


# ---------------------------- Payload üretici ----------------------------


_TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
              "Eylül", "Ekim", "Kasım", "Aralık"]
_TR_MON_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def report_week(today: date | None = None) -> tuple[date, date]:
    """Raporlanan hafta: bugünden önceki son TAMAMLANMIŞ Pazartesi–Pazar haftası.
    Pazartesi sabahı gönderim → geçen hafta (2026-11-12: eskiden "son 7 gün"
    Pazartesi'nin yarım gününü katıyordu)."""
    today = today or date.today()
    end = today - timedelta(days=today.weekday() + 1)
    return end - timedelta(days=6), end


def _range_label(ws: date, we: date) -> str:
    if ws.month == we.month:
        return f"{ws.day}–{we.day} {_TR_MONTHS[we.month - 1]} {we.year}"
    return f"{ws.day} {_TR_MONTHS[ws.month - 1]} – {we.day} {_TR_MONTHS[we.month - 1]} {we.year}"


def _short(d: date) -> str:
    return f"{d.day} {_TR_MON_SHORT[d.month - 1]}"


def _days_since(dt, today: date) -> int | None:
    if dt is None:
        return None
    d = dt.date() if hasattr(dt, "date") else dt
    return max(0, (today - d).days)


def _trim_leading_empty(points: list[dict]) -> list[dict]:
    """Kurum sisteme yeni başladıysa veri olmayan ilk haftalar grafikte boş sütun olmasın."""
    i = 0
    while i < len(points) and points[i]["rate"] is None:
        i += 1
    return points[i:]


def _ref_now(week_end: date):
    """Raporlanan haftanın son anı (Pazar 23:59 TR). Haftalık değerlendirmelerde
    "kaç gündür görülmedi" gibi ölçüler de bu ana göre hesaplanır."""
    from datetime import datetime, timezone
    real = datetime.now(timezone.utc)
    ref = datetime(week_end.year, week_end.month, week_end.day, 20, 59, tzinfo=timezone.utc)
    return min(real, ref)


def _headline(rate, delta, risk_total, empty, students) -> tuple[str, str]:
    """Haftanın tek cümlelik özeti (kural tabanlı) → (metin, ton)."""
    if students == 0:
        return "Kurumda bu hafta aktif öğrenci yok.", "info"
    if rate is None:
        return "Bu hafta öğrencilere yayınlanmış test görevi yok; uyum ölçülemedi.", "warn"
    parts = []
    if rate >= 70:
        tone = "good"
        parts.append(f"Öğrenciler programlarının %{rate} oranında testini çözdü — güçlü bir hafta")
    elif rate >= 40:
        tone = "warn"
        parts.append(f"Program uyumu %{rate} — orta seviyede")
    else:
        tone = "bad"
        parts.append(f"Program uyumu %{rate} — düşük")
    if delta is not None and abs(delta) >= 5:
        parts[-1] += f" (geçen haftaya göre {'+' if delta > 0 else '−'}{abs(delta)} puan)"
    text = parts[0] + "."
    extra = []
    if empty:
        extra.append(f"{empty} öğrencinin programı yok")
    if risk_total:
        extra.append(f"{risk_total} öğrenci risk altında")
    if extra:
        text += " Dikkat: " + ", ".join(extra) + "."
        if tone == "good":
            tone = "warn"
    return text, tone


def _grade_highlight(cohorts) -> dict:
    have = [c for c in cohorts if c.weekly_rate_pct is not None]
    best = max(have, key=lambda c: c.weekly_rate_pct) if have else None
    worst = min(have, key=lambda c: c.weekly_rate_pct) if have else None
    return {"best_grade_label": best.cohort_label if best else None,
            "best_grade_rate": best.weekly_rate_pct if best else None,
            "worst_grade_label": worst.cohort_label if worst else None,
            "worst_grade_rate": worst.weekly_rate_pct if worst else None}


def build_weekly_digest_payload(
    db: Session,
    *,
    institution: Institution,
    week_end: date | None = None,
) -> dict[str, Any]:
    """Kurum yöneticisi haftalık özeti (sürüm 2, 2026-11-12).

    week_end: raporlanan haftanın PAZAR günü (verilmezse `report_week()`).
    Tüm sayılar kurum panelindeki servislerden, aynı referans günüyle gelir
    (Program Uyumu · Öğretmen Karnesi · Müdahale Merkezi · Akademik Çıktı · Veli
    Güveni · Havuz). Uyum sayıları `digest_reliability` ile bağımsız olarak yeniden
    hesaplanır; fark varsa bağımsız hesap esas alınır ve skora işlenir.
    """
    from app.services import digest_reliability as dr
    from app.services.institution_academic import compute_academic
    from app.services.institution_action_center import compute_action_center
    from app.services.institution_compliance import compute_compliance
    from app.services.institution_parent_trust import compute_parent_trust
    from app.services.institution_pool import build_overview as pool_overview
    from app.services.institution_teacher_scorecard import compute_teacher_scorecard

    if week_end is None:
        week_start, week_end = report_week()
    else:
        week_start = week_end - timedelta(days=6)
    iid = institution.id
    rel = dr.Reliability()

    comp = compute_compliance(db, institution_id=iid, weeks=8, today=week_end)
    card = compute_teacher_scorecard(db, institution_id=iid, weeks=4, today=week_end)
    act = compute_action_center(db, institution_id=iid, today=week_end)
    acad = compute_academic(db, institution_id=iid, weeks=8, today=week_end)
    trust = compute_parent_trust(db, institution_id=iid, days=30)
    try:
        pool = pool_overview(db, institution_id=iid, today=week_end)
    except Exception as e:  # havuz panosu yardımcı bilgi — özet onsuz da çıkar
        logger.warning("admin_digest pool overview failed inst=%s: %s", iid, e)
        pool = None

    # ---------- öğrenci kümesi (kurum öğrencileri) ----------
    students = (db.query(User).filter(User.role == UserRole.STUDENT,
                                      User.institution_id == iid,
                                      User.is_active.is_(True)).all())
    student_ids = [int(s.id) for s in students]
    student_teacher = {int(s.id): s.teacher_id for s in students}
    teachers = (db.query(User).filter(User.role == UserRole.TEACHER,
                                      User.institution_id == iid).all())
    teacher_ids = {int(t.id) for t in teachers}
    by_coach_ids = {int(s.id) for s in (
        db.query(User).filter(User.role == UserRole.STUDENT, User.is_active.is_(True),
                              User.teacher_id.in_(teacher_ids)).all() if teacher_ids else [])}
    only_coach = by_coach_ids - set(student_ids)
    if only_coach:
        rel.checks.append(dr.Check(
            "student_set", "Öğrenci listesi", "warn",
            f"{len(only_coach)} öğrenci kurumun koçuna bağlı ama kurum kaydında değil; "
            "uyum hesabına girmedi. Kurum panelinden öğrencinin kurumunu kontrol edin."))
    else:
        rel.checks.append(dr.Check("student_set", "Öğrenci listesi", "ok",
                                   f"{len(student_ids)} aktif öğrenci, hepsi kuruma ve bir koça bağlı."
                                   if student_ids else "Aktif öğrenci yok."))

    # ---------- 1. uyum: panel ↔ bağımsız hesap ----------
    s = comp["summary"]
    ind = dr.independent_totals(db, student_ids, week_start, week_end)
    ip = sum(v[0] for v in ind.values())
    ic = sum(v[1] for v in ind.values())
    icorr = sum(v[2] for v in ind.values())
    iwrong = sum(v[3] for v in ind.values())
    ires = sum(v[4] for v in ind.values())
    rate, planned, done = s["rate"], s["planned"], s["completed"]
    if (planned, done) != (ip, ic):
        rel.checks.append(dr.Check(
            "compliance", "Program uyumu", "fixed",
            f"Panel {done}/{planned} test dedi, ham görev kalemlerinden yeniden sayım {ic}/{ip}. "
            "Özette ham sayım kullanıldı."))
        planned, done = ip, ic
        rate = completion.rate(ip, ic)
    else:
        rel.checks.append(dr.Check("compliance", "Program uyumu", "ok",
                                   f"{done}/{planned} test — iki ayrı hesap birebir aynı."))
    accuracy = (round(100 * icorr / (icorr + iwrong)) if (icorr + iwrong) else None)

    # koç satırları toplamı = kurum toplamı
    rows_p = sum(t["planned"] for t in comp["teachers"])
    rows_c = sum(t["completed"] for t in comp["teachers"])
    if (rows_p, rows_c) != (s["planned"], s["completed"]):
        rel.checks.append(dr.Check("coach_rows", "Koç satırları", "fixed",
                                   f"Koç satırlarının toplamı ({rows_c}/{rows_p}) kurum toplamından "
                                   f"({s['completed']}/{s['planned']}) farklı; koç oranları ham sayımdan yeniden kuruldu."))
    else:
        rel.checks.append(dr.Check("coach_rows", "Koç satırları", "ok",
                                   "Koç satırlarının toplamı kurum toplamına eşit."))

    # trendin son haftası = bu hafta
    trend = comp["trend"]
    if trend and trend[-1]["rate"] != s["rate"]:
        rel.checks.append(dr.Check("trend", "8 haftalık eğilim", "fixed",
                                   "Eğilimin son haftası özetle uyuşmadı; son nokta özetten alındı."))
        trend[-1]["rate"] = rate
    else:
        rel.checks.append(dr.Check("trend", "8 haftalık eğilim", "ok",
                                   "Eğilimin son haftası özetle aynı."))
    last_rate = s["last_week_rate"]
    delta = (rate - last_rate) if (rate is not None and last_rate is not None) else None

    # ---------- 2. risk: tek değerlendirme ----------
    ref_now = _ref_now(week_end)
    assessments = bulk_risk_assessment(db, students=students, today=week_end, now=ref_now)
    # Kıyas karneyle aynı kümede (tüm aktif öğrenciler); özette molada olanlar sayılmaz.
    hi_all = sum(1 for a in filter_at_risk(assessments, min_level="high"))
    at_risk = [a for a in filter_at_risk(assessments, min_level="medium") if not a.student.is_paused]
    risk_crit = sum(1 for a in at_risk if a.level == "critical")
    risk_high = sum(1 for a in at_risk if a.level == "high")
    risk_med = sum(1 for a in at_risk if a.level == "medium")
    card_risk = sum(t["risk_students"] for t in card["teachers"])
    hi_total = risk_crit + risk_high
    paused_note = (f" Moladaki {hi_all - hi_total} öğrenci özette sayılmadı." if hi_all != hi_total else "")
    if card_risk != hi_all:
        rel.checks.append(dr.Check("risk", "Risk sayımı", "fixed",
                                   f"Öğretmen karnesi {card_risk}, risk değerlendirmesi {hi_all} yüksek/kritik "
                                   "öğrenci verdi; özette risk değerlendirmesi kullanıldı." + paused_note))
    else:
        rel.checks.append(dr.Check("risk", "Risk sayımı", "ok",
                                   f"{hi_all} yüksek/kritik riskli öğrenci — karne ve risk değerlendirmesi aynı."
                                   + paused_note))
    risk_by_coach: dict[int | None, int] = {}
    for a in at_risk:
        if a.level in ("critical", "high"):
            risk_by_coach[a.student.teacher_id] = risk_by_coach.get(a.student.teacher_id, 0) + 1

    # ---------- programsız: koç satırları ↔ kurum toplamı (aynı kural: 3 günlük süre) ----------
    empty_by = {e["teacher_id"]: e["count"] for e in comp["empty_program"]}
    raw_empty = sum(t["empty_students"] for t in comp["teachers"])
    if raw_empty != s["empty_count"]:
        rel.checks.append(dr.Check(
            "empty", "Programsız öğrenci", "fixed",
            f"Koç satırları {raw_empty}, kurum toplamı {s['empty_count']} programsız öğrenci verdi "
            "(fark: yeni eklenen öğrencilere tanınan 3 günlük süre koç satırında uygulanmamış). "
            "Koç satırları aynı kuralla yeniden sayıldı."))
    else:
        rel.checks.append(dr.Check("empty", "Programsız öğrenci", "ok",
                                   f"{s['empty_count']} öğrenci — koç satırları ve kurum toplamı aynı."))

    # ---------- 3. koç tablosu ----------
    card_by = {t["teacher_id"]: t for t in card["teachers"]}
    teacher_by = {int(t.id): t for t in teachers}
    exam_by = {t["teacher_id"]: t for t in acad.get("teachers", [])}
    coaches = []
    for t in comp["teachers"]:
        tid = t["teacher_id"]
        mine = [sid for sid in student_ids if student_teacher.get(sid) == tid]
        ind_p = sum(ind.get(sid, [0, 0])[0] for sid in mine)
        ind_c = sum(ind.get(sid, [0, 0])[1] for sid in mine)
        tr = completion.rate(ind_p, ind_c)
        u = teacher_by.get(tid) if tid else None
        coaches.append({
            "teacher_id": tid,
            "name": t["teacher_name"],
            "students": t["student_count"],
            "rate": tr,
            "last_rate": t["last_rate"],
            "delta": (tr - t["last_rate"]) if (tr is not None and t["last_rate"] is not None) else None,
            "accuracy": t["accuracy"],
            "empty": empty_by.get(tid, 0),
            "risk": risk_by_coach.get(tid, 0),
            "score": (card_by.get(tid) or {}).get("score"),
            "score_label": (card_by.get(tid) or {}).get("score_label"),
            "exam_count": (exam_by.get(tid) or {}).get("exam_count", 0),
            "seen_days": _days_since(u.last_active_at, week_end + timedelta(days=1)) if u else None,
        })
    coaches.sort(key=lambda c: (c["rate"] is None, c["rate"] if c["rate"] is not None else 999))

    inactives = [c for c in coaches if c["teacher_id"] and (c["seen_days"] is None or c["seen_days"] >= 7)]

    # ---------- 4. müdahale ----------
    sev_order = {"critical": 0, "warn": 1, "info": 2}
    actions = sorted(act["items"], key=lambda i: sev_order.get(i["severity"], 3))[:6]

    # ---------- 5. veri kalitesi ----------
    n = len(student_ids)
    empty = s["empty_count"]
    rel.components.append(dr.Component(
        "program", "Program kapsaması",
        round(100 * (n - empty) / n) if n else None,
        f"{n - empty} / {n} öğrencinin bu hafta programı var." if n else "Aktif öğrenci yok."))
    rel.components.append(dr.Component(
        "results", "Doğru/yanlış girişi",
        round(100 * ires / done) if done >= 10 else None,
        (f"Çözülen {done} testin {ires} tanesinde doğru/yanlış girildi."
         if done >= 10 else "Bu hafta ölçmeye yetecek test çözülmedi (en az 10).")))
    clean, judged = dr.marking_ratio(db, student_ids, week_end)
    rel.components.append(dr.Component(
        "marking", "İşaretleme düzeni",
        round(100 * clean / judged) if judged else None,
        (f"Düzenli işaretleyen öğrenci {clean} / {judged}; kalanlar görevleri saniyeler içinde "
         "toplu işaretliyor (yapıldığını kanıtlamaz)." if judged and clean < judged else
         f"İşaretleme düzeni olağan ({judged} öğrenci)." if judged else
         "Değerlendirmeye yetecek işaretleme yok.")))
    asum = acad["summary"]
    rel.components.append(dr.Component(
        "exams", "Deneme kaydı",
        asum.get("coverage_pct") if n else None,
        f"Son {asum.get('weeks', 8)} haftada {asum.get('students_with_exam', 0)} / {n} öğrencinin denemesi girildi."))

    reliability = rel.as_dict()
    grade_cohorts = cohort_by_grade(db, institution_id=iid, today=week_end)
    track_cohorts = cohort_by_track(db, institution_id=iid, today=week_end)

    headline, tone = _headline(rate, delta, hi_total, empty, n)

    payload: dict[str, Any] = {
        "version": 2,
        "institution_id": iid,
        "institution_name": institution.name,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "week_label": _range_label(week_start, week_end),
        "headline": {"text": headline, "tone": tone},
        "kpis": {
            "students": n,
            "teachers": len(teachers),
            "rate": rate, "last_rate": last_rate, "delta": delta,
            "planned": planned, "completed": done, "accuracy": accuracy,
            "empty": empty,
            "risk_critical": risk_crit, "risk_high": risk_high, "risk_medium": risk_med,
            "parent_coverage": trust["summary"].get("coverage_pct"),
        },
        "trend": _trim_leading_empty(
            [{"label": _short(date.fromisoformat(w["week_start"]) + timedelta(days=6)),
              "rate": w["rate"]} for w in trend]),
        "coaches": coaches,
        "actions": [{"severity": a["severity"], "title": a["title"],
                     "description": a.get("description"),
                     "suggestion": a.get("suggestion")} for a in actions],
        "actions_total": act["summary"],
        "academic": {
            "coverage_pct": asum.get("coverage_pct"),
            "students_with_exam": asum.get("students_with_exam"),
            "recent_exams": asum.get("recent_exams"),
            "avg_net_pct": asum.get("avg_net_pct"),
            "delta": asum.get("delta"),
            "improving": acad.get("improving", [])[:3],
            "declining": acad.get("declining", [])[:3],
        },
        "parents": trust["summary"],
        "pool": ({"students": pool.students, "late_sessions": pool.late_sessions,
                  "open_periods": pool.open_periods, "avg_open_pct": pool.avg_open_pct}
                 if pool and pool.students else None),
        "reliability": reliability,
        # ---- sürüm 1 alanları (arşiv ekranı geriye uyum) ----
        "totals": {"student_count": n, "teacher_count": len(teachers),
                   "inactive_teacher_count": len(inactives)},
        "completion": {"this_week_rate": rate, "last_week_rate": last_rate,
                       "delta_pct": delta,
                       "direction": ("up" if (delta or 0) > 0 else "down" if (delta or 0) < 0 else "flat")},
        "at_risk": {"critical": risk_crit, "high": risk_high, "medium": risk_med,
                    "total": risk_crit + risk_high + risk_med},
        "highlight": _grade_highlight(grade_cohorts),
        "inactive_teachers": [{"id": c["teacher_id"], "name": c["name"], "email": ""}
                              for c in inactives[:5]],
        "grade_cohorts": [{"label": c.cohort_label, "n": c.student_count,
                           "rate": c.weekly_rate_pct, "color": c.rate_color} for c in grade_cohorts],
        "track_cohorts": [{"label": c.cohort_label, "n": c.student_count,
                           "rate": c.weekly_rate_pct, "color": c.rate_color} for c in track_cohorts],
    }
    return payload


# ---------------------------- Gönderim ----------------------------


def send_admin_weekly_digest(
    db: Session,
    *,
    institution: Institution,
    week_end: date | None = None,
    force: bool = False,
    today: date | None = None,
) -> AdminWeeklyDigest:
    """Bir kurum için haftalık özet üret + e-posta gönder + DB'ye kaydet.

    - Idempotency: aynı (institution, week_start) için zaten satır varsa,
      force=False ise mevcut satırı döner (göndermez).
    - force=True: yeniden gönder (manuel "şimdi gönder" butonu için)

    Returns: AdminWeeklyDigest satırı (mevcut veya yeni oluşturulmuş).
    """
    # Raporlanan hafta: geçen Pazartesi–Pazar (week_end verilirse o Pazar)
    if week_end is None:
        week_start, week_end = report_week(today)
    else:
        week_start = week_end - timedelta(days=6)

    existing = (
        db.query(AdminWeeklyDigest)
        .filter(
            AdminWeeklyDigest.institution_id == institution.id,
            AdminWeeklyDigest.week_start_date == week_start,
        )
        .first()
    )
    if existing and not force:
        logger.info(
            "admin_digest: skip — institution=%s, week=%s already sent (id=%s)",
            institution.id, week_start, existing.id,
        )
        return existing

    # Veriyi topla
    payload = build_weekly_digest_payload(
        db, institution=institution, week_end=week_end,
    )

    # Alıcı kurum admin'leri — aktif, e-posta sahibi (pasifler haftalık özet almaz)
    admins = (
        db.query(User)
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.INSTITUTION_ADMIN,
            User.is_active.is_(True),
            User.is_paused.is_(False),
        )
        .all()
    )
    admin_emails = [a.email for a in admins if a.email]

    # Kayıt güncelleme veya yeni oluşturma
    if existing:
        digest = existing
    else:
        digest = AdminWeeklyDigest(
            institution_id=institution.id,
            week_start_date=week_start,
            week_end_date=week_end,
        )
        db.add(digest)

    digest.payload_json = json.dumps(payload, ensure_ascii=False)
    digest.recipient_emails = "\n".join(admin_emails) if admin_emails else None
    digest.recipient_count = len(admin_emails)

    if not admin_emails:
        digest.send_status = "skipped_no_admin"
        digest.error_message = "Aktif institution_admin yok"
        db.commit()
        return digest

    # E-postaları gönder + Stage 6 kredi tüketimi (sadece gerçekten gönderilen)
    from app.models import UsageKind
    from app.services.credits import CreditOwner, record_usage
    owner = CreditOwner.for_institution(institution)
    sent_any = False
    failed_emails: list[str] = []
    for email in admin_emails:
        ctx = {
            "payload": payload,
            "institution": institution,
            "admin_email": email,
            "brand_institution_id": institution.id,   # kurumsal kimlik (logo + ad)
        }
        try:
            ok = send_email(
                to=email, template="admin_weekly_summary", ctx=ctx,
            )
            if ok:
                sent_any = True
                # Kredi düş — log_only'da tüketmeyiz (gerçek maliyet yok)
                try:
                    record_usage(
                        db, owner=owner, kind=UsageKind.EMAIL_SEND,
                        metadata={"template": "admin_weekly_summary", "to": email},
                        autocommit=False,
                    )
                except Exception as ce:
                    logger.warning("credit record_usage failed (non-fatal): %s", ce)
            else:
                # log_only mode: send_email False döner, hata yok
                pass
        except Exception as e:
            logger.exception("admin_digest send failed: %s", e)
            failed_emails.append(email)

    # Status set
    if failed_emails:
        digest.send_status = "failed"
        digest.error_message = "Failed for: " + ", ".join(failed_emails)
    elif sent_any:
        digest.send_status = "sent"
        digest.error_message = None
    else:
        # send_email log_only mode'da False döner — bunu hata sayma
        digest.send_status = "log_only"
        digest.error_message = None

    digest.sent_at = datetime.now(timezone.utc)
    db.flush()  # digest.id (push deep-link için)

    # Mobil push — kurum yöneticilerine "haftalık özet" (e-posta ile birlikte)
    try:
        from app.services.push_notifications import safe_push
        for a in admins:
            safe_push(db, user_id=a.id, title="Haftalık özet hazır",
                      body=f"{institution.name} bu haftanın yönetici özeti hazır.",
                      data={"type": "institution", "screen": "digest", "digest_id": digest.id})
    except Exception as e:
        logger.warning("admin_digest push failed (non-fatal): %s", e)

    db.commit()
    return digest


# ---------------------------- Görüntüleme ----------------------------


def render_digest_html(db: Session, *, institution: Institution, payload: dict) -> tuple[str, str]:
    """Özeti e-postadaki hâliyle çiz (kurum markalı) → (konu, html).

    Arşiv ekranındaki "gönderilen e-posta" görünümü ve test gönderimi bunu kullanır;
    e-posta ile ekran birebir aynı şablondan çıkar."""
    from app.services import branding
    from app.services.email_service import _render

    brand = branding.brand_for_institution(institution)
    subject, html, _plain = _render("admin_weekly_summary", {
        "payload": payload, "institution": institution,
        "brand": brand.as_email_ctx() if brand else None,
    })
    return subject, html
