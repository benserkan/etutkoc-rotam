"""Kapsamlı simülasyon: teklif yaşam döngüsü + past_due/öğrenci-sayısı + aksiyon merkezi.

Üç bölüm:
  SİM 1 — Teklif: kuyruk(DRAFT) → gönder(SENT) → kullanıcı açtı(viewed_at) → kabul.
  SİM 2 — Süre dolunca öğrenci-sayısı karar mekanizması (4 senaryo, fire testi).
  SİM 3 — Aksiyon Merkezi (kurum) sinyal yakalama + quick-action (manuel görev).

Geçici kullanıcılar oluşturur, sonunda temizler. Gerçek hesaplara dokunmaz.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    CrmAction, Institution, Offer, OfferStatus, User, UserRole,
)
from app.models.plan_history import PlanChangeHistory, PlanOwnerType
from app.models.suspicious_ip import SuspiciousIp
from app.services import plans, trial_notifications as tn
from app.services import offers as offers_service
from app.services import action_center
from app.services.institution_360 import create_action
from app.services.security import hash_password

PFX = f"simflow_{secrets.token_hex(3)}"
PWD = hash_password("SimFlow!23x")
now = datetime.now(timezone.utc)
created_user_ids: list[int] = []
created_inst_ids: list[int] = []


def line(s=""):
    print(s)


def mk_coach(suffix, plan, trial_days=None, n_students=0, sub_status=None, period_end=None):
    with SessionLocal() as db:
        c = User(email=f"{PFX}_{suffix}@test.invalid", password_hash=PWD,
                 full_name=f"{PFX}-{suffix}", role=UserRole.TEACHER, institution_id=None,
                 is_active=True, plan=plan,
                 trial_ends_at=(now + timedelta(days=trial_days)) if trial_days is not None else None,
                 post_trial_plan="solo_free",
                 subscription_status=sub_status, subscription_period_end=period_end,
                 subscription_cycle="monthly" if sub_status else None,
                 password_changed_at=now, must_change_password=False)
        db.add(c); db.flush()
        cid = c.id
        for i in range(n_students):
            db.add(User(email=f"{PFX}_{suffix}_s{i}@test.invalid", password_hash=PWD,
                        full_name=f"{PFX}-{suffix}-öğr{i}", role=UserRole.STUDENT,
                        teacher_id=cid, institution_id=None, grade_level=8, is_active=True,
                        password_changed_at=now, must_change_password=False))
        db.commit()
    created_user_ids.append(cid)
    if n_students:
        with SessionLocal() as db:
            sids = [row[0] for row in db.query(User.id).filter(
                User.email.like(f"{PFX}_{suffix}_s%")).all()]
        created_user_ids.extend(sids)
    return cid


def sim1_offer_lifecycle():
    line("\n" + "=" * 70)
    line("SİM 1 — TEKLİF YAŞAM DÖNGÜSÜ (solo koç: kuyruk→gönder→açıldı→kabul)")
    line("=" * 70)
    # super admin (teklif aktörü)
    with SessionLocal() as db:
        adm = User(email=f"{PFX}_adm@test.invalid", password_hash=PWD, full_name=f"{PFX}-adm",
                   role=UserRole.SUPER_ADMIN, is_active=True, password_changed_at=now, must_change_password=False)
        db.add(adm); db.commit(); created_user_ids.append(adm.id)
    cid = mk_coach("s1", "solo_trial", trial_days=2, n_students=4)
    line(f"  Koç: {PFX}_s1@test.invalid (id={cid}) · solo_trial · 2 gün kaldı · 4 öğrenci")

    # 1) Sistem kuyruğa alıyor mu? (trial_reminder cron'unun reminders adımı)
    with SessionLocal() as db:
        tn.send_trial_reminders(db, now=now)
        offer = db.query(Offer).filter(Offer.user_id == cid).order_by(Offer.id.desc()).first()
    if offer is None:
        line("  ❌ Kuyrukta teklif oluşmadı."); return
    line(f"  1) KUYRUK: send_trial_reminders → Offer #{offer.id} status={offer.status.value} "
         f"(DRAFT = admin onayı bekliyor) · kind={offer.kind.value} · new_plan={offer.new_plan}")

    # 2) Admin gönderiyor (DRAFT → SENT + e-posta log)
    with SessionLocal() as db:
        res = offers_service.send_offer(db, offer_id=offer.id)
        o = db.get(Offer, offer.id)
        token = o.token
        line(f"  2) GÖNDER: send_offer → status={o.status.value} · sent_at={o.sent_at} "
             f"· e-posta_denendi={res.get('sent_via_email')} (EMAIL kapalıysa log-only)")
        line(f"     Public link: /offers/{token}")

    # 3) Kullanıcı linki açıyor (viewed_at) — gerçek public endpoint
    c = TestClient(app)
    r = c.get(f"/api/v2/offers/{token}")
    with SessionLocal() as db:
        o = db.get(Offer, offer.id)
        line(f"  3) AÇILDI: GET /offers/{{token}} → HTTP {r.status_code} · viewed_at={o.viewed_at} "
             f"→ admin '360 Teklifler'de 'Açıldı: ...' görür")

    # 4) Kullanıcı kabul ediyor
    r = c.post(f"/api/v2/offers/{token}/accept")
    with SessionLocal() as db:
        o = db.get(Offer, offer.id)
        coach = db.get(User, cid)
        line(f"  4) KABUL: POST /accept → HTTP {r.status_code} · status={o.status.value} "
             f"· responded_at={o.responded_at}")
        line(f"     SONUÇ: koç planı={coach.plan} · trial_ends_at={coach.trial_ends_at} (kabulde plan değişir)")
    line("  ZAMAN ÇİZELGESİ: oluştu(DRAFT/kuyruk) → gönderildi → AÇILDI → kabul → plan aktif ✅")


def _report_coach(label, cid):
    with SessionLocal() as db:
        c = db.get(User, cid)
        st = plans.solo_trial_status(db, user=c)
        q = plans.check_solo_student_quota(db, teacher=c, extra_count=1)
    line(f"  [{label}] {c.email}")
    line(f"      plan={st['plan_code']} · aktif öğrenci={st['student_count']} · limit="
         f"{'sınırsız' if st['student_limit'] == -1 else st['student_limit']} · over_limit={st['over_limit']}")
    line(f"      paywall={st['paywall']} (past_due={st['past_due']}) → aktif koçluk "
         f"{'KİLİTLİ (yeni program/görev yok)' if st['paywall'] else 'açık'}")
    effective_add = q.ok and not st["paywall"]
    line(f"      yeni öğrenci eklenebilir mi (API, paywall dahil)? {effective_add}  "
         f"[plan-kotası={q.ok}, paywall={st['paywall']}] (öneri: {q.upgrade_target_code})")


def sim2_paywall_students():
    line("\n" + "=" * 70)
    line("SİM 2 — SÜRE DOLUNCA ÖĞRENCİ-SAYISI KARAR MEKANİZMASI (fire testi)")
    line("=" * 70)

    # A: 20 öğrencili trial → süre dolar
    a = mk_coach("s2a", "solo_trial", trial_days=-1, n_students=20)  # trial geçmiş
    # B: 2 öğrencili trial → süre dolar
    b = mk_coach("s2b", "solo_trial", trial_days=-1, n_students=2)
    with SessionLocal() as db:
        plans.expire_trials(db, now=now)
    line("\n  → expire_trials çalıştı (trial'ı geçmiş koçlar solo_free'ye düşer):")
    line("\n  A) 20 ÖĞRENCİLİ koç (deneme bitti):")
    _report_coach("A", a)
    line("\n  B) 2 ÖĞRENCİLİ koç (deneme bitti):")
    _report_coach("B", b)

    # C: aktif ücretli, dönem sonu geçmiş → past_due
    c = mk_coach("s2c", "solo_pro", n_students=10, sub_status="active", period_end=now - timedelta(days=1))
    # D: iptal edilmiş, dönem sonu geçmiş → solo_free
    d = mk_coach("s2d", "solo_pro", n_students=10, sub_status="canceled", period_end=now - timedelta(days=1))
    with SessionLocal() as db:
        tn.process_renewals(db, now=now)
    line("\n  → process_renewals çalıştı (dönem sonu geçen abonelikler):")
    line("\n  C) ÜCRETLİ, dönem sonu geçti (yenilenmedi):")
    _report_coach("C", c)
    line("\n  D) İPTAL edilmiş, dönem sonu geçti:")
    _report_coach("D", d)
    line("\n  KARAR MEKANİZMASI: öğrenciler ASLA otomatik pasifleşmez/silinmez. Plan düşer,")
    line("  fazla öğrencisi varsa AKTİF KOÇLUK kilitlenir (paywall); koç ya yükseltir ya")
    line("  kendisi öğrenci pasifleştirip limite iner. 'Hangi öğrenci' kararını koç verir.")


def sim3_action_center():
    line("\n" + "=" * 70)
    line("SİM 3 — AKSİYON MERKEZİ (kurum) SİNYAL YAKALAMA + QUICK-ACTION")
    line("=" * 70)
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Dershane", slug=f"{PFX}-d", plan="institution_trial",
                           trial_ends_at=now + timedelta(days=1), post_trial_plan="institution_free",
                           is_active=True)
        db.add(inst); db.commit(); iid = inst.id
    created_inst_ids.append(iid)
    line(f"  Kurum: {PFX} Dershane (id={iid}) · institution_trial · 1 gün kaldı")

    with SessionLocal() as db:
        data = action_center.action_center_data(db)
        mine = [it for it in data["items"] if it.institution_id == iid]
    if not mine:
        line("  ❌ Aksiyon merkezi bu kurumu yakalamadı.");
    else:
        it = mine[0]
        line(f"  1) YAKALANDI: '{it.primary_signal.title}' · severity={it.primary_signal.severity} "
             f"· skor={it.total_score}")
        line(f"     Önerilen aksiyonlar:")
        for sa in it.suggested_actions:
            line(f"       - [{sa.kind}] {sa.label}: \"{sa.summary}\"")
        # 2) quick-action → CRM aksiyonu (manuel görev)
        with SessionLocal() as db:
            act = create_action(db, institution_id=iid, kind="call",
                                summary="Trial bitiyor — yükseltme görüşmesi",
                                by_user_id=created_user_ids[0] if created_user_ids else None,
                                result="pending",
                                follow_up_at=now + timedelta(days=3))
            line(f"  2) QUICK-ACTION → CrmAction #{act.id} · kind={act.kind.value} · "
                 f"result={act.result.value if hasattr(act.result,'value') else act.result} · "
                 f"follow_up={act.follow_up_at}")
        line("     → Bu bir MANUEL GÖREV/LOG'dur: sistem otomatik aramaz/mesaj atmaz.")
        line("       Admin arar/e-posta atar, sonucu kaydeder, takip tarihinde tekrar görür.")
        line("     → Tür: arama/e-posta/WhatsApp/not (kind). Şablon → aksiyon ile script hazır gelir.")
    line("\n  BULGU: Aksiyon Merkezi KURUM-merkezlidir; bağımsız koç burada GÖRÜNMEZ.")
    line("  Bağımsız koç süresi dolan → trial_reminder cron (DRAFT teklif + e-posta) +")
    line("  Ticari Pano 'denemesi bitenler' listesinde yakalanır.")


def cleanup():
    with SessionLocal() as db:
        if created_user_ids:
            db.execute(sa_delete(Offer).where(Offer.user_id.in_(created_user_ids)))
            db.execute(sa_delete(PlanChangeHistory).where(
                PlanChangeHistory.owner_id.in_(created_user_ids),
                PlanChangeHistory.owner_type == PlanOwnerType.USER))
            db.execute(sa_delete(User).where(User.id.in_(created_user_ids)))
        if created_inst_ids:
            db.execute(sa_delete(CrmAction).where(CrmAction.institution_id.in_(created_inst_ids)))
            db.execute(sa_delete(Offer).where(Offer.institution_id.in_(created_inst_ids)))
            db.execute(sa_delete(PlanChangeHistory).where(
                PlanChangeHistory.owner_id.in_(created_inst_ids),
                PlanChangeHistory.owner_type == PlanOwnerType.INSTITUTION))
            db.execute(sa_delete(Institution).where(Institution.id.in_(created_inst_ids)))
        # bu koşunun ürettiği otomatik DRAFT teklifleri temizle
        db.execute(sa_delete(Offer).where(
            Offer.status == OfferStatus.DRAFT,
            Offer.title == "Pro'ya geçiş — deneme bitiyor"))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def main():
    try:
        sim1_offer_lifecycle()
        sim2_paywall_students()
        sim3_action_center()
    finally:
        cleanup()
    line("\n=== SİMÜLASYON BİTTİ (geçici veriler temizlendi) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
