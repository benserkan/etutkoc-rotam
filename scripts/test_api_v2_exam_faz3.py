"""Deneme analizi Faz 3 — genel ortalama, çeldirici analizi, puan tahmini."""
import json
import secrets
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, ".")
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AuditLog, ExamResult, Subject, SuspiciousIp, User, UserRole  # noqa: E402
from app.models.exam_result import ExamResultQuestion, ExamSection  # noqa: E402
from app.models.user import Track  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PW = "ExamFaz3!2345xyz"
PFX = f"exf3_{secrets.token_hex(3)}"
now = datetime.now(timezone.utc)
ok: list[bool] = []


def chk(label, cond, extra=""):
    ok.append(bool(cond))
    print(("  OK   " if cond else "  FAIL ") + label + (f"  [{extra}]" if not cond and extra else ""))


def mk(db, email, role, **kw):
    u = User(email=email, password_hash=hash_password(PW), full_name=kw.pop("full_name", email[:20]),
             role=role, is_active=True, password_changed_at=now, must_change_password=False,
             email_verified_at=now, **kw)
    db.add(u)
    db.flush()
    return u


KEY = list("ABCDEABCDEABCDEABCDE")  # 20 soru cevap anahtarı


def add_exam(db, sid, tid, title, section, nets, answers=None, score_info=None, d=None):
    D = sum(n["correct"] for n in nets)
    Y = sum(n["wrong"] for n in nets)
    B = sum(n["blank"] for n in nets)
    pen = 3 if section == ExamSection.LGS else 4
    e = ExamResult(student_id=sid, created_by_id=tid, title=title, exam_date=d or date.today() - timedelta(days=3),
                   section=section, total_correct=D, total_wrong=Y, total_blank=B, net=round(D - Y / pen, 2),
                   subject_nets=json.dumps(nets, ensure_ascii=False), import_source="pdf_import",
                   analysis_meta=json.dumps({"score_info": score_info}) if score_info else None)
    db.add(e)
    db.flush()
    if answers is not None:
        subj = db.query(Subject).filter(Subject.name == "TYT Matematik", Subject.curriculum_model.is_(None)).first()
        for i, a in enumerate(answers):
            res = "bos" if a is None else ("dogru" if a == KEY[i] else "yanlis")
            db.add(ExamResultQuestion(exam_result_id=e.id, question_no=i + 1, subject_name_raw="MATEMATİK",
                                      subject_id=subj.id, topic_label_raw="x", correct_answer=KEY[i],
                                      student_answer=a, result=res))
    return e


with SessionLocal() as db:
    t = mk(db, f"{PFX}_t@test.invalid", UserRole.TEACHER, plan="solo_pro", subscription_status="active")
    t2 = mk(db, f"{PFX}_t2@test.invalid", UserRole.TEACHER, plan="solo_pro", subscription_status="active")
    s = mk(db, f"{PFX}_s@test.invalid", UserRole.STUDENT, teacher_id=t.id, grade_level=12, track=Track.SAYISAL)
    p1 = mk(db, f"{PFX}_p1@test.invalid", UserRole.STUDENT, teacher_id=t.id, grade_level=12)
    p2 = mk(db, f"{PFX}_p2@test.invalid", UserRole.STUDENT, teacher_id=t.id, grade_level=12)
    lg = mk(db, f"{PFX}_l@test.invalid", UserRole.STUDENT, teacher_id=t.id, grade_level=8)
    tyt_nets = [
        {"name": "TYT Türkçe", "correct": 30, "wrong": 8, "blank": 2, "net": 28.0},
        {"name": "TYT Tarih", "correct": 4, "wrong": 1, "blank": 0, "net": 3.75},
        {"name": "TYT Matematik", "correct": 10, "wrong": 6, "blank": 4, "net": 8.5},
        {"name": "TYT Geometri", "correct": 6, "wrong": 0, "blank": 4, "net": 6.0},
        {"name": "TYT Fizik", "correct": 5, "wrong": 0, "blank": 2, "net": 5.0},
    ]
    # öğrencinin cevapları: 6 yanlış, hepsi "B"ye yönelik; 4 boş
    ans = ["A", "B", "C", "D", "E", "A", "B", "C", "D", "E", "B", "B", "B", "B", "B", "B", None, None, None, None]
    e1 = add_exam(db, s.id, t.id, "ÖZDEBİR TG 3. Prova TYT", ExamSection.TYT, tyt_nets, ans,
                  score_info={"score": 320.0, "averages": {"label": "Genel ortalama", "total": 40.5,
                                                          "subjects": {"MATEMATİK": 7.25, "TÜRKÇE": 20.0}}})
    # akranlar: aynı deneme (ad biçimi farklı, 1 gün sonra)
    peer_ans = ["A", "B", "C", "D", "E", "A", "B", "C", "D", "E", "B", "B", "B", "D", "E", "A", "B", "C", "D", "E"]
    add_exam(db, p1.id, t.id, "Özdebir TG 3. PROVA tyt", ExamSection.TYT, tyt_nets, peer_ans,
             d=date.today() - timedelta(days=2))
    add_exam(db, p2.id, t.id, "ÖZDEBİR TG 3. PROVA TYT!", ExamSection.TYT, tyt_nets, peer_ans,
             d=date.today() - timedelta(days=3))
    ayt = [{"name": "AYT Matematik", "correct": 20, "wrong": 4, "blank": 16, "net": 19.0},
           {"name": "AYT Fizik", "correct": 6, "wrong": 4, "blank": 4, "net": 5.0},
           {"name": "AYT Kimya", "correct": 7, "wrong": 0, "blank": 6, "net": 7.0},
           {"name": "AYT Biyoloji", "correct": 8, "wrong": 4, "blank": 1, "net": 7.0}]
    add_exam(db, s.id, t.id, "AYT Deneme", ExamSection.AYT_SAY, ayt, d=date.today() - timedelta(days=1))
    lgs = [{"name": "Türkçe", "correct": 18, "wrong": 3, "blank": 0, "net": 17.0},
           {"name": "Matematik", "correct": 12, "wrong": 6, "blank": 2, "net": 10.0},
           {"name": "Fen Bilimleri", "correct": 15, "wrong": 3, "blank": 2, "net": 14.0},
           {"name": "T.C. İnkılap Tarihi", "correct": 9, "wrong": 0, "blank": 1, "net": 9.0},
           {"name": "Din Kültürü", "correct": 10, "wrong": 0, "blank": 0, "net": 10.0},
           {"name": "İngilizce", "correct": 8, "wrong": 0, "blank": 2, "net": 8.0}]
    add_exam(db, lg.id, t.id, "LGS Deneme", ExamSection.LGS, lgs)
    db.commit()
    ids = dict(t=t.id, t2=t2.id, s=s.id, p1=p1.id, p2=p2.id, lg=lg.id, e1=e1.id)


def login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return c


try:
    ct, ct2 = login(f"{PFX}_t@test.invalid"), login(f"{PFX}_t2@test.invalid")
    cs = login(f"{PFX}_s@test.invalid")

    # ---------- genel ortalama
    rows = ct.get(f"/api/v2/teacher/students/{ids['s']}/exams?period=all").json()["rows"]
    r1 = next(r for r in rows if r["id"] == ids["e1"])
    av = r1["averages"]
    chk("1 karne ortalaması öğrencinin ders adına eşlendi", av and av["subjects"].get("TYT Matematik") == 7.25
        and av["subjects"].get("TYT Türkçe") == 20.0 and av["source"] == "auto", av)
    chk("2 toplam genel ortalama", av["total"] == 40.5)
    r = ct.post(f"/api/v2/teacher/exams/{ids['e1']}/averages",
                json={"label": "Kurum ortalaması", "total": 38, "subjects": {"TYT Fizik": 3.5}})
    chk("3 elle ortalama kaydedildi + öncelikli", r.status_code == 200 and r.json()["averages"]["source"] == "manual"
        and r.json()["averages"]["subjects"] == {"TYT Fizik": 3.5}, r.text[:200])
    r = ct.post(f"/api/v2/teacher/exams/{ids['e1']}/averages", json={"subjects": {"Uydurma Ders": 3}})
    chk("4 denemede olmayan ders 422", r.status_code == 422)
    r = ct2.post(f"/api/v2/teacher/exams/{ids['e1']}/averages", json={"total": 10})
    chk("5 başka koç 404", r.status_code == 404)
    r = ct.post(f"/api/v2/teacher/exams/{ids['e1']}/averages", json={})
    chk("6 boş gövde elle girişi kaldırır → karne ortalaması geri", r.json()["averages"]["source"] == "auto")
    srows = cs.get("/api/v2/student/exams?period=all").json()["rows"]
    chk("7 öğrenci de ortalamayı görür", next(x for x in srows if x["id"] == ids["e1"])["averages"]["total"] == 40.5)

    # ---------- çeldirici
    d = ct.get(f"/api/v2/teacher/exams/{ids['e1']}/distractors").json()
    letters = {x["letter"]: x for x in d["letters"]}
    chk("8 şık dağılımı: 16 cevap, B 8 kez", d["answered"] == 16 and letters["B"]["chosen"] == 8, letters)
    chk("9 yanlışların tamamı B'de (5)", letters["B"]["wrong_chosen"] == 5 and d["wrong_count"] == 5, d["wrong_count"])
    notes = " ".join(d["notes"])
    chk("10 not: B eğilimi + üst üste işaretleme", "B şıkkında" in notes and "üst üste" in notes, notes)
    chk("11 akran: aynı denemeye giren 2 öğrenci (ad biçimi farklı)", d["peer_count"] == 2)
    q12 = next(q for q in d["questions"] if q["question_no"] == 13)
    chk("12 soru 13: akranlar B'ye düştü, öğrenci de → ortak tuzak", q12["top_wrong_option"] == "B"
        and q12["same_as_student"] and q12["peer_correct_pct"] == 0, q12)
    q17 = next(q for q in d["questions"] if q["question_no"] == 17)
    chk("13 boş soru 17: akranların tamamı doğru", q17["peer_correct_pct"] == 100 and q17["result"] == "bos")
    chk("14 doğru sorular listede yok", all(q["result"] != "dogru" for q in d["questions"]))
    chk("15 başka koç çeldirici 404", ct2.get(f"/api/v2/teacher/exams/{ids['e1']}/distractors").status_code == 404)
    sd = cs.get(f"/api/v2/student/exams/{ids['e1']}/distractors")
    chk("16 öğrenci kendi çeldiricisini görür", sd.status_code == 200 and sd.json()["peer_count"] == 2)

    # ---------- puan tahmini
    sc = ct.get(f"/api/v2/teacher/students/{ids['s']}/score-estimate").json()
    by = {x["key"]: x for x in sc["scores"]}
    # TYT: Türkçe 28*3.3 + Sosyal 3.75*3.4 + Mat (8.5+6)*3.3 + Fen 5*3.4 = 92.4+12.75+47.85+17 = 170 → 270
    chk("17 TYT tahmini 270,00", sc["kind"] == "yks" and by["TYT"]["score"] == 270.0, by.get("TYT"))
    # SAY: 100 + 170*0.4(68) + 19*3 + 5*2.85 + 7*3.07 + 7*3.07 = 100+68+57+14.25+42.98 = 282.23
    chk("18 SAY birleşik tahmini 282,23 + öğrencinin alanı", by["SAY"]["score"] == 282.23 and by["SAY"]["is_student_track"],
        by.get("SAY"))
    cal = sc["calibration"]
    chk("19 karne puanıyla kıyas (320 ↔ 270, fark −50)", cal and cal[0]["karne_score"] == 320 and cal[0]["diff"] == -50.0, cal)
    chk("20 tahmini ibaresi", "Tahmini" in sc["disclaimer"])
    lg_sc = ct.get(f"/api/v2/teacher/students/{ids['lg']}/score-estimate").json()
    # LGS: (17+10+14)*4=164 + 9+10+8=27 → 191/270*400+100 = 382.96
    chk("21 LGS tahmini 382,96", lg_sc["kind"] == "lgs" and lg_sc["scores"][0]["score"] == 382.96, lg_sc["scores"])
    chk("22 başka koç puan tahmini 404",
        ct2.get(f"/api/v2/teacher/students/{ids['s']}/score-estimate").status_code == 404)
    chk("23 öğrenci kendi tahmini", cs.get("/api/v2/student/score-estimate").json()["scores"][0]["key"] == "TYT")
    np_ = ct.get(f"/api/v2/teacher/students/{ids['p1']}/score-estimate").json()
    chk("24 AYT'siz öğrencide alan puanı uyarısı", len(np_["scores"]) == 1 and any("AYT" in w for w in np_["warnings"]))
finally:
    with SessionLocal() as db:
        sids = [ids["s"], ids["p1"], ids["p2"], ids["lg"]]
        eids = [e for (e,) in db.query(ExamResult.id).filter(ExamResult.student_id.in_(sids)).all()]
        db.execute(sa_delete(ExamResultQuestion).where(ExamResultQuestion.exam_result_id.in_(eids)))
        db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(eids)))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(list(ids.values()))))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(sids + [ids["t"], ids["t2"]])))
        db.commit()

print(f"\n=== {sum(ok)} passed, {len(ok) - sum(ok)} failed ===")
sys.exit(0 if all(ok) else 1)
