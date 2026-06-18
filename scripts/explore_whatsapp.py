"""WhatsApp Click-to-WA keşif/deneme — demo doğruluğu için GERÇEK çıktı.

Yerel şablonları listeler; koç→öğrenci + kurum→öğretmen için gerçek wa.me URL +
render edilmiş mesaj + maskeli telefon üretir; spam guard istatistiğini gösterir.
SALT-DENEME (oluşturduğu test kullanıcılarını + log'u siler).

  python -m scripts.explore_whatsapp
"""
from __future__ import annotations
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import secrets
from sqlalchemy import delete as sa_delete
from app.database import SessionLocal
from app.models import User, UserRole
from app.models.whatsapp_template import WhatsAppTemplate
from app.models.whatsapp_dispatch_log import WhatsAppDispatchLog
from app.services import whatsapp_link_service as wl
from app.services import whatsapp_spam_guard as sg
from app.services.security import hash_password

PFX = f"wa_{secrets.token_hex(3)}"


def main():
    db = SessionLocal()
    uids = []
    try:
        # 0) Yerel şablon envanteri
        tmpls = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.is_active == True).all()  # noqa: E712
        print(f"=== YEREL ŞABLON ENVANTERİ — {len(tmpls)} aktif şablon ===\n")
        by_role: dict[str, list] = {}
        for t in tmpls:
            by_role.setdefault(t.target_role or "any", []).append(t)
        for role, items in by_role.items():
            print(f"[target_role={role}] {len(items)} şablon:")
            for t in items[:8]:
                flags = []
                if t.allow_bulk:
                    flags.append("toplu")
                if t.allow_freeform_note:
                    flags.append("serbest-not")
                if t.requires_date:
                    flags.append("tarihli")
                print(f"   • {t.key:28} [{t.category}] {t.name_tr[:34]:34} {('/'.join(flags)) or '-'}")
            print()

        # Demo için gerçek örnek şablonlar seç
        teacher_tmpl = next((t for t in tmpls if t.target_role in ("teacher", "any") and t.category == "veli"), None)
        teacher_tmpl = teacher_tmpl or next((t for t in tmpls if t.target_role in ("teacher", "any")), None)
        inst_tmpl = next((t for t in tmpls if t.target_role in ("institution_admin", "any")), None)

        # 1) Test ekosistemi: koç + öğrenci(tel) + kurum + öğretmen(tel)
        coach = User(email=f"{PFX}_c@test.invalid", password_hash=hash_password("x12345678"),
                     full_name=f"{PFX}-koç", role=UserRole.TEACHER, is_active=True, plan="solo_pro",
                     phone="905321110011", phone_verified_at=None)
        db.add(coach); db.flush()
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password("x12345678"),
                   full_name="Ahmet Yılmaz", role=UserRole.STUDENT, teacher_id=coach.id,
                   is_active=True, grade_level=8, phone="905329876543", phone_verified_at=None)
        db.add(stu); db.flush()
        uids = [coach.id, stu.id]
        db.commit()

        # 2) KOÇ → ÖĞRENCİ gerçek dispatch
        print("=" * 70)
        print("KOÇ → ÖĞRENCİ (Ahmet) — gerçek Click-to-WA çıktısı")
        print("=" * 70)
        if teacher_tmpl:
            var_defs = wl.parse_variables_json(teacher_tmpl.variables_json)
            print(f"Şablon: {teacher_tmpl.name_tr}  (key={teacher_tmpl.key})")
            print(f"Ham içerik: {teacher_tmpl.content_template[:200]}")
            print(f"Değişkenler: {[d.get('key') for d in var_defs if isinstance(d, dict)]}")
            res = wl.build_wa_dispatch(
                db, sender=coach, template_id=teacher_tmpl.id, target_user_id=stu.id,
                variables={}, write_log=True,
            )
            print(f"\nMaskeli telefon : {res.target_phone_masked}")
            print(f"Karakter        : {res.character_count}")
            print(f"\n--- RENDER EDİLEN MESAJ ---\n{res.rendered_text}")
            print(f"\n--- wa.me URL ---\n{res.wa_url[:280]}")
        else:
            print("(uygun koç şablonu yok)")

        # 3) KURUM YÖNETİCİSİ → ÖĞRETMEN gerçek dispatch
        print("\n" + "=" * 70)
        print("KURUM YÖNETİCİSİ → ÖĞRETMEN — gerçek Click-to-WA çıktısı")
        print("=" * 70)
        # kurum + yönetici + öğretmen
        from app.models import Institution
        inst = Institution(name=f"{PFX}-Kurum", slug=f"{PFX}-kurum", is_active=True, plan="etut_standart")
        db.add(inst); db.flush()
        admin = User(email=f"{PFX}_a@test.invalid", password_hash=hash_password("x12345678"),
                     full_name=f"{PFX}-yönetici", role=UserRole.INSTITUTION_ADMIN, is_active=True,
                     institution_id=inst.id, phone="905323330033")
        teach2 = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password("x12345678"),
                      full_name="Zeynep Koç", role=UserRole.TEACHER, is_active=True,
                      institution_id=inst.id, phone="905324440044")
        db.add_all([admin, teach2]); db.flush()
        uids += [admin.id, teach2.id]
        db.commit()
        if inst_tmpl:
            print(f"Şablon: {inst_tmpl.name_tr}  (key={inst_tmpl.key})")
            print(f"Ham içerik: {inst_tmpl.content_template[:200]}")
            res2 = wl.build_wa_dispatch(
                db, sender=admin, template_id=inst_tmpl.id, target_user_id=teach2.id,
                variables={}, write_log=True,
            )
            print(f"\nMaskeli telefon : {res2.target_phone_masked}")
            print(f"\n--- RENDER EDİLEN MESAJ ---\n{res2.rendered_text}")
            print(f"\n--- wa.me URL ---\n{res2.wa_url[:280]}")
        else:
            print("(uygun kurum şablonu yok)")

        # 4) Yetki kontrolü kanıtı (sızıntı önleme)
        print("\n" + "=" * 70)
        print("YETKİ KANITI")
        print("=" * 70)
        print(f"Koç → kendi öğrencisi : {wl.can_send_wa_to(db, sender=coach, target=stu)}")
        print(f"Koç → kurum öğretmeni : {wl.can_send_wa_to(db, sender=coach, target=teach2)}  (yetkisiz)")
        print(f"Kurum yön. → öğretmeni : {wl.can_send_wa_to(db, sender=admin, target=teach2)}")
        print(f"can_message_phone (numara var, doğrulanmamış, SMS kapalı) : {wl.can_message_phone(stu)}")

        # 5) Spam guard istatistiği
        print("\n" + "=" * 70)
        print("SPAM GUARD")
        print("=" * 70)
        st = sg.compute_dispatch_stats(db, coach)
        print(f"Koç bugün: {st['today_count']} · bu hafta: {st['week_count']} · seviye: {st['warning_level']}")
        return 0
    finally:
        try:
            if uids:
                db.execute(sa_delete(WhatsAppDispatchLog).where(WhatsAppDispatchLog.sender_user_id.in_(uids)))
                db.execute(sa_delete(User).where(User.id.in_(uids)))
                from app.models import Institution as _I
                db.execute(sa_delete(_I).where(_I.slug == f"{PFX}-kurum"))
                db.commit()
        except Exception as e:
            print(f"(cleanup uyarı: {e})")
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
