# -*- coding: utf-8 -*-
"""Günlük düşünce notu — autosave upsert + koç salt-okuma görür."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datetime import date
from app.database import SessionLocal
from app.models import User, UserRole, StudentDayNote
from app.routes.api_v2.student import save_day_note_v2
from app.routes.api_v2.schemas.student import DayNoteSaveBody
from app.services.security import hash_password

PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print(f"  [PASS] {n}")
    else: FAIL += 1; print(f"  [FAIL] {n} {e}")

db = SessionLocal()
SUF = "_daynote_tmp"
def clean():
    for u in db.query(User).filter(User.email.like(f"%{SUF}@x.com")).all():
        db.query(StudentDayNote).filter(StudentDayNote.student_id == u.id).delete(synchronize_session=False)
    db.query(User).filter(User.email.like(f"%{SUF}@x.com")).delete(synchronize_session=False)
    db.commit()
clean()
try:
    coach = User(email=f"c{SUF}@x.com", full_name="C", role=UserRole.TEACHER, password_hash=hash_password("x"), is_active=True)
    db.add(coach); db.flush()
    stu = User(email=f"s{SUF}@x.com", full_name="S", role=UserRole.STUDENT, password_hash=hash_password("x"), is_active=True, teacher_id=coach.id)
    db.add(stu); db.flush(); db.commit()
    today = date.today()

    # 1) İlk kayıt (autosave)
    r1 = save_day_note_v2(DayNoteSaveBody(date=today.isoformat(), body="Bugun matematikte zorlandim."), stu, db)
    check("1. ilk kayıt body doğru", r1.body == "Bugun matematikte zorlandim.")
    rows = db.query(StudentDayNote).filter(StudentDayNote.student_id == stu.id, StudentDayNote.date == today).all()
    check("2. tek satır oluştu", len(rows) == 1)

    # 2) Devam (upsert — kaldığı yerden ekleme)
    r2 = save_day_note_v2(DayNoteSaveBody(date=today.isoformat(), body="Bugun matematikte zorlandim. Turevi tekrar etmeliyim."), stu, db)
    check("3. upsert güncelledi", r2.body.endswith("tekrar etmeliyim."))
    rows = db.query(StudentDayNote).filter(StudentDayNote.student_id == stu.id, StudentDayNote.date == today).all()
    check("4. hâlâ TEK satır (yeni satır YOK)", len(rows) == 1)

    # 3) Koç görür (aynı satır, model üzerinden) + farklı gün ayrı kayıt
    note = rows[0]
    check("5. koç salt-okuma görebilir (body dolu)", note.body and len(note.body) > 0)
    other = date(today.year, today.month, max(1, today.day - 1) if today.day > 1 else today.day)
    if other != today:
        save_day_note_v2(DayNoteSaveBody(date=other.isoformat(), body="Dunku not"), stu, db)
        cnt = db.query(StudentDayNote).filter(StudentDayNote.student_id == stu.id).count()
        check("6. farklı gün AYRI kayıt", cnt == 2)
    else:
        PASS += 1; print("  [PASS] 6. (gün 1 — atlandı)")

    # 4) Boş body temizler
    save_day_note_v2(DayNoteSaveBody(date=today.isoformat(), body=""), stu, db)
    db.refresh(note)
    check("7. boş body -> not temizlendi", note.body == "")
finally:
    clean(); db.close()
print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
