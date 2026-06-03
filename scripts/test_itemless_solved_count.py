# -*- coding: utf-8 -*-
"""Itemless (etkinlik/diğer) görevde çözülen soru girişi -> test hacmine sayılır.

KULLANICI: "olmayan kitaptan test" gibi kalemsiz göreve öğrenci çözdüğü soruyu
giremiyordu. Artık girer; kategori etkinlik kalır, 'çözülen test'e sayılır."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datetime import date
from app.database import SessionLocal
from app.models import User, UserRole, Task, TaskStatus, TaskType
from app.routes.api_v2.student import complete_task_v2, uncomplete_task_v2
from app.routes.api_v2.schemas.student import CompleteTaskBody
from app.services import gorev_stats
from app.services.security import hash_password

PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print(f"  [PASS] {n}")
    else: FAIL += 1; print(f"  [FAIL] {n} {e}")

db = SessionLocal()
SUF = "_itemsolved_tmp"
def clean():
    for u in db.query(User).filter(User.email.like(f"%{SUF}@x.com")).all():
        db.query(Task).filter(Task.student_id == u.id).delete(synchronize_session=False)
    db.query(User).filter(User.email.like(f"%{SUF}@x.com")).delete(synchronize_session=False)
    db.commit()
clean()
try:
    coach = User(email=f"c{SUF}@x.com", full_name="C", role=UserRole.TEACHER, password_hash=hash_password("x"), is_active=True)
    db.add(coach); db.flush()
    stu = User(email=f"s{SUF}@x.com", full_name="S", role=UserRole.STUDENT, password_hash=hash_password("x"), is_active=True, teacher_id=coach.id)
    db.add(stu); db.flush()
    today = date.today()
    # Kalemsiz "diğer" görev (olmayan kitaptan test) — book_items YOK
    t = Task(student_id=stu.id, date=today, type=TaskType.OTHER, title="345 SB 20 test (sistemde yok)", is_draft=False, status=TaskStatus.PENDING)
    db.add(t); db.commit(); db.refresh(t)
    tid = t.id

    # 1) Çözülen soru ile tamamla
    res = complete_task_v2(tid, CompleteTaskBody(solved_count=20), stu, db)
    db.refresh(t)
    check("1. itemless complete solved_count=20 kaydedildi", t.solved_count == 20, f"got {t.solved_count}")
    check("2. status COMPLETED", t.status == TaskStatus.COMPLETED)
    check("3. response solved_count=20", res.data.solved_count == 20, f"got {res.data.solved_count}")

    # 2) gorev_stats: kategori etkinlik, test_completed=20, gorev_done=1
    g = gorev_stats.summarize([t])
    check("4. kategori etkinlik (deneme/tam_deneme DEĞİL)", g.cat_total["etkinlik"] == 1 and g.cat_total["tam_deneme"] == 0)
    check("5. test_completed=20 (çözülen test hacmine)", g.test_completed == 20, f"got {g.test_completed}")
    check("6. test_planned=0 (plan yok)", g.test_planned == 0, f"got {g.test_planned}")
    check("7. gorev_done=1 (manşet görev tamam)", g.gorev_done == 1)

    # 3) Geri al -> solved_count temizlenir + test_completed 0
    uncomplete_task_v2(tid, stu, db)
    db.refresh(t)
    check("8. uncomplete -> solved_count temizlendi", t.solved_count is None, f"got {t.solved_count}")
    g2 = gorev_stats.summarize([t])
    check("9. uncomplete sonrası test_completed=0", g2.test_completed == 0)

    # 4) 0 girince None (sayılmaz)
    complete_task_v2(tid, CompleteTaskBody(solved_count=0), stu, db)
    db.refresh(t)
    check("10. solved_count=0 -> None (sayılmaz)", t.solved_count is None)
finally:
    clean(); db.close()
print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
