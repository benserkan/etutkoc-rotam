"""Tekrar kartları (FSRS) keşif/deneme — demo doğruluğu için GERÇEK davranışı görür.

Test koç+öğrenci+ders+konu oluşturur, kart seed eder, her rating'in (1-4) sonraki
aralığını + state geçişini gösterir, lapse biriktirip zorlanma skorunu hesaplar.
Sonunda temizler. SALT-DENEME (geçici test verisi).

  python -m scripts.explore_review_cards
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import ReviewCard, ReviewLog, Subject, Topic, User, UserRole
from app.models.review import STATE_NEW
from app.services import review_scheduler as rs
from app.services.security import hash_password

PFX = f"rev_{secrets.token_hex(3)}"
now = datetime.now(timezone.utc)
ids = {"users": [], "subject": None, "topics": []}


def main():
    db = SessionLocal()
    try:
        coach = User(email=f"{PFX}_c@test.invalid", password_hash=hash_password("x12345678"),
                     full_name=f"{PFX}-coach", role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add(coach); db.flush()
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password("x12345678"),
                   full_name=f"{PFX}-stu", role=UserRole.STUDENT, teacher_id=coach.id,
                   is_active=True, grade_level=8)
        db.add(stu); db.flush()
        ids["users"] = [coach.id, stu.id]
        subj = Subject(name=f"{PFX} Mat", teacher_id=coach.id); db.add(subj); db.flush()
        ids["subject"] = subj.id
        topics = []
        for nm in ["Çarpanlar", "Üslü İfadeler", "Karekök", "Olasılık"]:
            t = Topic(subject_id=subj.id, name=nm, teacher_id=coach.id, is_builtin=False)
            db.add(t); db.flush(); topics.append(t)
        ids["topics"] = [t.id for t in topics]
        db.commit()

        print(f"=== TEKRAR KARTLARI DENEMESİ — {PFX} ===\n")

        # 1) Koç seed eder
        res = rs.seed_topics_for_student(db, student=stu, topic_ids=ids["topics"], teacher=coach)
        db.commit()
        print(f"1) Koç '{subj.name}' konularını kart olarak ekledi → eklenen={res.added} atlanan={res.skipped_existing}")
        bd = rs.cards_breakdown(db, student_id=stu.id, now=now)
        print(f"   Kırılım: Yeni={bd.new} Öğreniyor={bd.learning} Pekiştirme={bd.review} "
              f"Yeniden={bd.relearning} | Bugün-vade={bd.due_now} Toplam={bd.total}")

        # 2) Vadesi gelen kartlar (hepsi NEW → hepsi vadeli)
        due = rs.get_due_cards(db, student_id=stu.id, now=now, limit=50)
        print(f"\n2) Öğrenci panelinde vadesi gelen kart: {len(due)} (yeni kart hemen vadeli)")

        # 3) Her rating'in sonraki aralığını göster (yeni kartlar üzerinde)
        print("\n3) Öğrenci değerlendirir → FSRS sonraki tarihi belirler:")
        labels = {1: "Tekrar (unuttum)", 2: "Zor", 3: "İyi", 4: "Kolay"}
        for rating, card in zip([1, 2, 3, 4], due):
            out = rs.record_review(db, card=card, rating=rating, now=now)
            db.commit()
            _due = card.due_at
            if _due is not None and _due.tzinfo is None:
                _due = _due.replace(tzinfo=timezone.utc)
            due_in = (_due - now) if _due else None
            mins = due_in.total_seconds() / 60 if due_in else 0
            human = (f"{mins:.0f} dk sonra" if mins < 90 else
                     f"{mins/60:.1f} saat sonra" if mins < 1440 else
                     f"{mins/1440:.1f} gün sonra")
            print(f"   [{labels[rating]:16}] {card.topic.name:14} → state={card.state:11} "
                  f"sonraki={human:16} (stability={card.stability:.2f})")

        # 4) Bir konuyu üst üste 'Tekrar' (unuttum) → lapse birikir → zorlanma skoru
        print("\n4) 'Karekök' konusu üst üste unutuluyor → zorlanma sinyali:")
        kk = next(c for c in due if c.topic.name == "Karekök")
        for i in range(2):
            rs.record_review(db, card=kk, rating=1, now=now)
            db.commit()
        db.refresh(kk)
        print(f"   Karekök: state={kk.state} lapse(unutma)={kk.lapse_count} difficulty={kk.difficulty:.2f}")
        strug = rs.struggling_topics_for_student(db, student_id=stu.id)
        print(f"\n5) Koç 'Müdahale Önerileri / Zorlanılan Konular' görür ({len(strug)} konu):")
        for s in strug:
            print(f"   • {s.topic_name:14} zorlanma={s.score:.0f}/100  nedenler={', '.join(s.reasons)}")

        print("\n=== ÖZET: koç seed → öğrenci değerlendirir (Tekrar/Zor/İyi/Kolay) → "
              "FSRS aralığı uzar/kısalır → unutulanlar koça 'zorlanılan konu' olarak döner ===")
        return 0
    finally:
        # cleanup
        try:
            sids = ids["users"]
            if sids:
                cids = [r[0] for r in db.query(ReviewCard.id).filter(ReviewCard.student_id.in_(sids)).all()]
                if cids:
                    db.execute(sa_delete(ReviewLog).where(ReviewLog.card_id.in_(cids)))
                    db.execute(sa_delete(ReviewCard).where(ReviewCard.id.in_(cids)))
            if ids["topics"]:
                db.execute(sa_delete(Topic).where(Topic.id.in_(ids["topics"])))
            if ids["subject"]:
                db.execute(sa_delete(Subject).where(Subject.id == ids["subject"]))
            if sids:
                db.execute(sa_delete(User).where(User.id.in_(sids)))
            db.commit()
        except Exception as e:
            print(f"(cleanup uyarı: {e})")
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
