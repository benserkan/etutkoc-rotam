"""Veli deneme maili — hedef net · genel ortalama · tahmini puan bloğu (2026-10-02)."""
import json
import secrets
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, ".")
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import ExamResult, ExamTarget, User, UserRole  # noqa: E402
from app.models.exam_result import ExamSection  # noqa: E402
from app.models.user import Track  # noqa: E402
from app.services.email_service import _render  # noqa: E402
from app.services.exam_parent_summary import build_email_context, build_parent_exam_summary  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"epg_{secrets.token_hex(3)}"
now = datetime.now(timezone.utc)
ok: list[bool] = []


def chk(label, cond, extra=""):
    ok.append(bool(cond))
    print(("  OK   " if cond else "  FAIL ") + label + (f"  [{extra}]" if not cond and extra else ""))


NETS = [
    {"name": "TYT Türkçe", "correct": 30, "wrong": 8, "blank": 2, "net": 28.0},
    {"name": "TYT Matematik", "correct": 20, "wrong": 8, "blank": 12, "net": 18.0},
]


def mk(db, email, role, **kw):
    u = User(email=email, password_hash=hash_password("x" * 12), full_name=kw.pop("full_name", "Ada Deneme"),
             role=role, is_active=True, password_changed_at=now, **kw)
    db.add(u)
    db.flush()
    return u


def exam(db, sid, tid, title, days, meta=None, section=ExamSection.TYT):
    e = ExamResult(student_id=sid, created_by_id=tid, title=title, exam_date=date.today() - timedelta(days=days),
                   section=section, total_correct=50, total_wrong=16, total_blank=14, net=46.0,
                   subject_nets=json.dumps(NETS, ensure_ascii=False),
                   analysis_meta=json.dumps(meta) if meta else None)
    db.add(e)
    db.flush()
    return e


ids: list[int] = []
try:
    with SessionLocal() as db:
        t = mk(db, f"{PFX}_t@test.invalid", UserRole.TEACHER)
        s = mk(db, f"{PFX}_s@test.invalid", UserRole.STUDENT, teacher_id=t.id, grade_level=12,
               track=Track.SAYISAL, full_name="Ada Deneme")
        bare = mk(db, f"{PFX}_b@test.invalid", UserRole.STUDENT, teacher_id=t.id, grade_level=12)
        ids = [t.id, s.id, bare.id]
        old = exam(db, s.id, t.id, "Eski TYT", 20)
        meta = {"score_info": {"score": 280.5, "averages": {
            "label": "Genel ortalama", "total": 40.0, "subjects": {"TYT Türkçe": 22.5}}}}
        cur = exam(db, s.id, t.id, "Yeni TYT", 2, meta=meta)
        db.add(ExamTarget(student_id=s.id, section="tyt", target_net=60, set_by_id=t.id,
                          subject_targets="{}", target_date=date(2027, 6, 1)))
        plain = exam(db, bare.id, t.id, "Sade TYT", 2)
        db.commit()

        # 1 — hedef + ortalama + puan
        sm = build_parent_exam_summary(db, cur)
        g = sm.get("goal") or {}
        chk("1a hedef 60 net, 14 net kaldı", g.get("target_net_text") == "60,00"
            and g.get("target_gap_text") == "14,00" and not g.get("target_reached"), g)
        chk("1b hedef tarihi", g.get("target_date_tr") == "01.06.2027", g.get("target_date_tr"))
        chk("1c genel ortalama 40, 6 net üzerinde", g.get("avg_total_text") == "40,00"
            and g.get("avg_diff_text") == "6,00" and g.get("avg_direction") == "above", g)
        chk("1d tahmini TYT puanı + karne puanı", bool(g.get("score_text")) and "TYT" in (g.get("score_label") or "")
            and g.get("karne_score_text") == "280,50", g)
        tr = next(x for x in sm["subjects"] if x["name"] == "TYT Türkçe")
        chk("1e ders ortalaması ders satırına işlendi", tr.get("avg") == 22.5 and tr.get("avg_text") == "22,50", tr)
        nar = " ".join(sm["narrative"])
        chk("1f yorumda hedef + ortalama + puan cümleleri",
            "hedefimiz 60,00 net" in nar and "ortalamanın 6,00 net üzerinde" in nar and "tahmini" in nar, nar)

        # 2 — eski deneme: puan tahmini o türün SON denemesine ait -> eski mailde yok
        g_old = build_parent_exam_summary(db, old).get("goal") or {}
        chk("2 eski denemenin mailinde bugünkü puan tahmini YOK", not g_old.get("score_text"), g_old)

        # 3 — hedefe ulaştı
        tg = db.query(ExamTarget).filter(ExamTarget.student_id == s.id).first()
        tg.target_net = 40
        db.commit()
        g3 = build_parent_exam_summary(db, cur).get("goal") or {}
        chk("3 hedefe ulaştı", g3.get("target_reached") is True)

        # 4 — veri olmayan öğrenci: hedef/ortalama yok (puan tahmini var)
        g4 = build_parent_exam_summary(db, plain).get("goal") or {}
        chk("4 hedefsiz/ortalamasız öğrencide bu alanlar yok",
            not g4.get("target_net_text") and not g4.get("avg_total_text"), g4)

        # 5 — include_goal=False kutuları ve ders ortalamasını çıkarır
        ctx = build_email_context(db, cur, include_goal=False)
        chk("5 include_goal=False -> goal None + ders ortalaması yok",
            ctx["goal"] is None and all("avg" not in x for x in ctx["subjects"]))

        # 6 — şablon render
        ctx = build_email_context(db, cur)
        ctx["unsubscribe_token"] = ""
        _sub, html, _txt = _render("parent_exam_result", ctx)
        chk("6a mailde Hedef net kutusu", "Hedef net" in html and "Hedefe ulaştı" in html)
        chk("6b mailde Genel ortalama + Ort. sütunu", "Genel ortalama" in html and ">Ort.<" in html and "22,50" in html)
        chk("6c mailde Tahmini puan + karne", "Tahmini puan" in html and "karnede 280,50" in html)
        ctx2 = build_email_context(db, cur, include_goal=False)
        ctx2["unsubscribe_token"] = ""
        _s2, html2, _t2 = _render("parent_exam_result", ctx2)
        chk("6d kapatılınca mailde kutular yok", "Hedef net" not in html2 and ">Ort.<" not in html2)

        # 7 — Rota deneme paketi hedef + ortalama + puan taşır
        from app.services.parent_commentary import build_bundle, compute_signature
        st = db.get(User, s.id)
        b = build_bundle(db, st, st, "deneme")
        tg = (b.get("targets") or [{}])[0]
        chk("7a pakette hedef + son denemenin hedefe uzaklığı",
            tg.get("target_net") == 40 and tg.get("gap_to_target") == -6.0, b.get("targets"))
        new_row = next(x for x in b["exams"] if x["title"] == "Yeni TYT")
        chk("7b pakette genel ortalama + karne puanı",
            new_row.get("general_average_net") == 40.0 and new_row.get("karne_score") == 280.5, new_row)
        chk("7c pakette tahmini puan", bool((b.get("score_estimate") or {}).get("scores")), b.get("score_estimate"))
        sig1 = compute_signature(db, s.id, "deneme")
        tg_row = db.query(ExamTarget).filter(ExamTarget.student_id == s.id).first()
        tg_row.target_net = 55
        db.commit()
        chk("7d hedef değişince yorum bayatlar", compute_signature(db, s.id, "deneme") != sig1)
        sig_b = compute_signature(db, bare.id, "deneme")
        chk("7e hedefsiz öğrencide imza eski biçimde", set(sig_b) == {"exam_ids"}, sig_b)
finally:
    with SessionLocal() as db:
        if ids:
            db.execute(sa_delete(ExamTarget).where(ExamTarget.student_id.in_(ids)))
            db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(ids)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.commit()

print(f"\n{sum(ok)}/{len(ok)} passed")
sys.exit(0 if all(ok) else 1)
