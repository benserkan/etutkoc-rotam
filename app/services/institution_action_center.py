"""Müdahale Merkezi — "Bugün kime dokunmalıyım?" (2026-05-20).

Kurum yöneticisi için dağınık sinyalleri tek önceliklendirilmiş aksiyon
listesinde toplar. Yeni veri ÜRETMEZ; mevcut servisleri (compliance + risk)
çağırıp kart'a dönüştürür — attention_engine'in kurum-içi, program-odaklı
versiyonu.

Sinyal kaynakları:
  - Boş program (institution_compliance) → koç başına program girilmemiş öğrenci
  - Düşük uyum koç (institution_compliance) → tamamlama < eşik
  - Riskli öğrenci (risk_analysis.bulk_risk_assessment) → critical/high

Gizlilik: D4 deseni — öğrenci/öğretmen ADI görünür, detay sayfası link YOK.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.services.institution_compliance import compute_compliance
from app.services.risk_analysis import bulk_risk_assessment, filter_at_risk


_SEVERITY_RANK = {"critical": 0, "warn": 1, "info": 2}

# Eşikler
EMPTY_CRITICAL = 3       # koç başına 3+ boş program → kritik
LOW_RATE_THRESHOLD = 40  # koç tamamlaması < %40 → uyarı
LOW_RATE_CRITICAL = 25   # < %25 → kritik


def compute_action_center(db: Session, *, institution_id: int) -> dict:
    """Önceliklendirilmiş müdahale kartları + özet sayım."""
    items: list[dict] = []

    comp = compute_compliance(db, institution_id=institution_id, weeks=2)

    # 1) Boş program — koç başına
    for e in comp["empty_program"]:
        sev = "critical" if e["count"] >= EMPTY_CRITICAL else "warn"
        names = ", ".join(e["sample_students"][:5])
        items.append({
            "severity": sev,
            "category": "empty_program",
            "title": f"{e['teacher_name']} — {e['count']} öğrenciye program girilmemiş",
            "description": f"Bu hafta program bekleyen öğrenciler: {names}"
                           + (" …" if e["count"] > len(e["sample_students"][:5]) else ""),
            "teacher_name": e["teacher_name"],
            "count": e["count"],
            "suggestion": "Koça bu hafta için program girmesini hatırlatın.",
        })

    # 2) Düşük uyum koç
    for t in comp["teachers"]:
        if t["rate"] is None or t["student_count"] == 0:
            continue
        if t["rate"] >= LOW_RATE_THRESHOLD:
            continue
        sev = "critical" if t["rate"] < LOW_RATE_CRITICAL else "warn"
        items.append({
            "severity": sev,
            "category": "low_compliance",
            "title": f"{t['teacher_name']} sınıfı %{t['rate']} tamamlama",
            "description": f"{t['student_count']} öğrenci · doğruluk "
                           + (f"%{t['accuracy']}" if t["accuracy"] is not None else "—"),
            "teacher_name": t["teacher_name"],
            "count": t["student_count"],
            "suggestion": "Koçla görüşüp düşük uyum nedenini değerlendirin "
                          "(programlar fazla mı, öğrenci motivasyonu mu?).",
        })

    # 3) Riskli öğrenciler (kurum öğretmenlerinin öğrencileri)
    teacher_ids = [
        t[0] for t in db.query(User.id).filter(
            User.role == UserRole.TEACHER, User.institution_id == institution_id
        ).all()
    ]
    if teacher_ids:
        students = (
            db.query(User)
            .filter(
                User.role == UserRole.STUDENT,
                User.teacher_id.in_(teacher_ids),
                User.is_active.is_(True),
            )
            .all()
        )
        teacher_name = {
            int(t.id): (t.full_name or t.email)
            for t in db.query(User).filter(User.id.in_(teacher_ids)).all()
        }
        assessments = bulk_risk_assessment(db, students=students)
        surfaced_ids: set[int] = set()
        critical = [a for a in filter_at_risk(assessments, min_level="high")]
        critical.sort(key=lambda a: -a.score)
        for a in critical[:15]:
            sev = "critical" if a.level == "critical" else "warn"
            tname = teacher_name.get(a.student.teacher_id, "—") if a.student.teacher_id else "—"
            ind = ", ".join(i.title for i in a.indicators[:3]) if a.indicators else ""
            items.append({
                "severity": sev,
                "category": "at_risk",
                "title": f"{a.student.full_name or a.student.email} — {a.level_label} risk (skor {a.score})",
                "description": (f"Koç: {tname}" + (f" · {ind}" if ind else "")),
                "teacher_name": tname,
                "count": 1,
                "suggestion": "Koçtan öğrenciyle birebir görüşmesini isteyin.",
            })
            surfaced_ids.add(int(a.student.id))

        # 4) Programı var ama yapmıyor — "N gün üst üste boş" (consecutive_empty).
        # Tek başına medium kalıp yukarıdaki high/critical eşiğine düşmeyen ama
        # 3+ gündür program TAMAMLAMAYAN öğrenciler. Kullanıcı talebi: bu da
        # müdahale merkezinde görünmeli (yalnız "her şey yolunda" yanıltıcıydı).
        inactive: list = []
        for a in assessments:
            if int(a.student.id) in surfaced_ids:
                continue
            ce = next((i for i in a.indicators if i.code == "consecutive_empty"), None)
            if ce is not None:
                inactive.append((a, ce))
        # En uzun süre boş olan üstte (göstergenin ağırlığı sabit; gün sayısı title'da)
        inactive.sort(key=lambda x: -x[0].score)
        for a, ce in inactive[:15]:
            tname = teacher_name.get(a.student.teacher_id, "—") if a.student.teacher_id else "—"
            items.append({
                "severity": "warn",
                "category": "inactive_program",
                "title": f"{a.student.full_name or a.student.email} — {ce.title}",
                "description": f"Koç: {tname} · {ce.detail}",
                "teacher_name": tname,
                "count": 1,
                "suggestion": "Programı var ama yapmıyor — koçtan öğrenciyle iletişime geçmesini isteyin.",
            })

    items.sort(key=lambda x: (_SEVERITY_RANK.get(x["severity"], 9), -x["count"]))

    summary = {
        "critical": sum(1 for i in items if i["severity"] == "critical"),
        "warn": sum(1 for i in items if i["severity"] == "warn"),
        "info": sum(1 for i in items if i["severity"] == "info"),
        "total": len(items),
    }
    return {"summary": summary, "items": items}
