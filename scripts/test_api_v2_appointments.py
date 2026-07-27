# -*- coding: utf-8 -*-
"""Online görüşme / randevu sistemi smoke testi.

Kapsam: koç ataması (tek + haftalık seri) · çakışma/geçmiş-tarih kapıları ·
sahiplik 404 · uygunluk pencereleri + slot üretimi · öğrenci self-servis istek
(pending -> onay/red) · geri çekme · güncelleme/iptal · seri güncelleme/pasif ·
hatırlatma cron'u (D-1 + H-1, idempotent) · veli görünürlüğü + pref süzgeci ·
Google OAuth/Meet link (mock).
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import BackgroundTasks, HTTPException

from app.config import settings
from app.database import SessionLocal
from app.models import (
    APPT_STATUS_CANCELLED,
    APPT_STATUS_DONE,
    APPT_STATUS_NO_SHOW,
    APPT_STATUS_PENDING,
    APPT_STATUS_REJECTED,
    APPT_STATUS_SCHEDULED,
    CoachAvailabilityWindow,
    CoachGoogleAccount,
    CoachingAppointment,
    CoachingAppointmentSeries,
    CoachingChannel,
    CoachingSession,
    CoachingSessionStatus,
    ParentNotificationPref,
    ParentStudentLink,
    User,
    UserRole,
)
from app.routes.api_v2.appointments import (
    parent_student_appointments_v2,
    student_appointment_request_v2,
    student_appointment_slots_v2,
    student_appointment_withdraw_v2,
    student_appointments_v2,
    teacher_appointment_approve_v2,
    teacher_appointment_create_v2,
    teacher_appointment_reject_v2,
    teacher_appointment_status_v2,
    teacher_appointment_update_v2,
    teacher_appointments_v2,
    teacher_availability_replace_v2,
    teacher_google_connect_url_v2,
    teacher_series_update_v2,
)
from app.routes.api_v2.schemas.appointment import (
    AppointmentCreateBody,
    AppointmentStatusBody,
    AppointmentUpdateBody,
    AvailabilityReplaceBody,
    AvailabilityWindowItem,
    RejectBody,
    SeriesUpdateBody,
    StudentRequestBody,
)
from app.services import appointment_service as svc
from app.services import google_meet
from app.services.security import hash_password

PASS = FAIL = 0


def check(n, c, e=""):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n} {e}")


db = SessionLocal()
SUF = "_appt_tmp"


def clean():
    users = db.query(User).filter(User.email.like(f"%{SUF}@x.com")).all()
    uids = [u.id for u in users]
    if uids:
        db.query(CoachingSession).filter(
            CoachingSession.student_id.in_(uids)
        ).delete(synchronize_session=False)
        db.query(CoachingAppointment).filter(
            CoachingAppointment.student_id.in_(uids)
            | CoachingAppointment.coach_id.in_(uids)
        ).delete(synchronize_session=False)
        db.query(CoachingAppointmentSeries).filter(
            CoachingAppointmentSeries.coach_id.in_(uids)
        ).delete(synchronize_session=False)
        db.query(CoachAvailabilityWindow).filter(
            CoachAvailabilityWindow.coach_id.in_(uids)
        ).delete(synchronize_session=False)
        db.query(CoachGoogleAccount).filter(
            CoachGoogleAccount.coach_id.in_(uids)
        ).delete(synchronize_session=False)
        db.query(ParentStudentLink).filter(
            ParentStudentLink.parent_id.in_(uids)
        ).delete(synchronize_session=False)
        db.query(ParentNotificationPref).filter(
            ParentNotificationPref.parent_id.in_(uids)
        ).delete(synchronize_session=False)
    db.query(User).filter(User.email.like(f"%{SUF}@x.com")).delete(
        synchronize_session=False
    )
    db.commit()


def next_weekday_at(days_ahead_min: int, hour: int, minute: int = 0):
    """En az N gün sonrasında, verilen saate denk gelen (date, 'HH:MM')."""
    d = svc.now_tr().date() + timedelta(days=days_ahead_min)
    return d, f"{hour:02d}:{minute:02d}"


clean()
try:
    coach = User(email=f"c{SUF}@x.com", full_name="Koc Appt", role=UserRole.TEACHER,
                 password_hash=hash_password("x"), is_active=True)
    other = User(email=f"o{SUF}@x.com", full_name="Yabanci Koc", role=UserRole.TEACHER,
                 password_hash=hash_password("x"), is_active=True)
    db.add_all([coach, other]); db.flush()
    stu = User(email=f"s{SUF}@x.com", full_name="Ogrenci Appt", role=UserRole.STUDENT,
               password_hash=hash_password("x"), is_active=True, teacher_id=coach.id)
    stu2 = User(email=f"s2{SUF}@x.com", full_name="Ogrenci Iki", role=UserRole.STUDENT,
                password_hash=hash_password("x"), is_active=True, teacher_id=other.id)
    parent = User(email=f"p{SUF}@x.com", full_name="Veli Appt", role=UserRole.PARENT,
                  password_hash=hash_password("x"), is_active=True)
    parent2 = User(email=f"p2{SUF}@x.com", full_name="Yabanci Veli", role=UserRole.PARENT,
                   password_hash=hash_password("x"), is_active=True)
    db.add_all([stu, stu2, parent, parent2]); db.flush()
    db.add(ParentStudentLink(parent_id=parent.id, student_id=stu.id))
    db.commit()

    bg = BackgroundTasks()

    # ---- 1) Koç tek randevu atar ----
    d1, t1 = next_weekday_at(3, 17)
    res = teacher_appointment_create_v2(
        body=AppointmentCreateBody(
            student_id=stu.id, date=d1.isoformat(), start_time=t1,
            duration_min=40, note="Haftalık değerlendirme",
        ),
        background=bg, user=coach, db=db,
    )
    appt1 = res.data.appointment
    check("1. koç tek randevu atadı (scheduled)",
          appt1.status == APPT_STATUS_SCHEDULED and appt1.student_id == stu.id
          and appt1.meeting_link is None)

    # ---- 2) Geçmiş tarihe atama reddedilir ----
    try:
        teacher_appointment_create_v2(
            body=AppointmentCreateBody(
                student_id=stu.id,
                date=(svc.now_tr().date() - timedelta(days=1)).isoformat(),
                start_time="10:00",
            ),
            background=bg, user=coach, db=db,
        )
        check("2. geçmiş tarih reddedilir", False)
    except HTTPException as e:
        check("2. geçmiş tarih reddedilir",
              e.status_code == 422 and e.detail["code"] == "past_datetime")

    # ---- 3) Çakışan saat reddedilir ----
    try:
        teacher_appointment_create_v2(
            body=AppointmentCreateBody(
                student_id=stu.id, date=d1.isoformat(), start_time=t1,
            ),
            background=bg, user=coach, db=db,
        )
        check("3. çakışan saat reddedilir", False)
    except HTTPException as e:
        check("3. çakışan saat reddedilir",
              e.status_code == 422 and e.detail["code"] == "time_conflict")

    # ---- 4) Haftalık seri -> occurrence üretimi ----
    d2, t2 = next_weekday_at(2, 19)
    res = teacher_appointment_create_v2(
        body=AppointmentCreateBody(
            student_id=stu.id, date=d2.isoformat(), start_time=t2,
            duration_min=50, weekly=True,
            meeting_link="https://meet.google.com/abc-defg-hij",
        ),
        background=bg, user=coach, db=db,
    )
    series_id = res.data.series.id if res.data.series else None
    occ = (
        db.query(CoachingAppointment)
        .filter(CoachingAppointment.series_id == series_id)
        .order_by(CoachingAppointment.date)
        .all()
    )
    check("4. haftalık seri: 4+ occurrence + link kopyalandı",
          series_id is not None and len(occ) >= 4
          and all(o.meeting_link for o in occ),
          f"count={len(occ)}")

    # ---- 5) Sahiplik 404 ----
    try:
        teacher_appointment_create_v2(
            body=AppointmentCreateBody(
                student_id=stu2.id, date=d1.isoformat(), start_time="11:00",
            ),
            background=bg, user=coach, db=db,
        )
        check("5a. yabancı öğrenciye atama 404", False)
    except HTTPException as e:
        check("5a. yabancı öğrenciye atama 404", e.status_code == 404)
    try:
        teacher_appointment_update_v2(
            appt_id=appt1.id, body=AppointmentUpdateBody(note="x"),
            background=bg, user=other, db=db,
        )
        check("5b. yabancı koç randevu güncelleyemez 404", False)
    except HTTPException as e:
        check("5b. yabancı koç randevu güncelleyemez 404", e.status_code == 404)

    # ---- 6) Uygunluk pencereleri ----
    tomorrow = svc.now_tr().date() + timedelta(days=1)
    wd = tomorrow.weekday()
    res = teacher_availability_replace_v2(
        body=AvailabilityReplaceBody(windows=[
            AvailabilityWindowItem(weekday=wd, start_time="15:00",
                                   end_time="18:00", slot_minutes=60),
        ]),
        user=coach, db=db,
    )
    check("6a. uygunluk pencereleri kaydedildi",
          len(res.data.availability) == 1
          and res.data.availability[0].start_time == "15:00")
    try:
        teacher_availability_replace_v2(
            body=AvailabilityReplaceBody(windows=[
                AvailabilityWindowItem(weekday=0, start_time="18:00",
                                       end_time="15:00"),
            ]),
            user=coach, db=db,
        )
        check("6b. ters pencere reddedilir", False)
    except HTTPException as e:
        check("6b. ters pencere reddedilir", e.detail["code"] == "invalid_window")

    # ---- 7) Öğrenci slot listesi ----
    slots = student_appointment_slots_v2(user=stu, db=db)
    day_slots = [dd for dd in slots.days if dd.date == tomorrow.isoformat()]
    check("7. slot listesi: yarın 15/16/17 slotları",
          day_slots and {s.start_time for s in day_slots[0].slots} == {"15:00", "16:00", "17:00"},
          f"days={[(dd.date, [s.start_time for s in dd.slots]) for dd in slots.days][:3]}")

    # ---- 8) Öğrenci istek (pending) + mükerrer istek reddi ----
    res = student_appointment_request_v2(
        body=StudentRequestBody(date=tomorrow.isoformat(), start_time="16:00",
                                note="Deneme sonucumu konuşmak istiyorum"),
        background=bg, user=stu, db=db,
    )
    req1 = res.data.appointment
    check("8a. öğrenci isteği pending", req1.status == APPT_STATUS_PENDING)
    try:
        student_appointment_request_v2(
            body=StudentRequestBody(date=tomorrow.isoformat(), start_time="17:00"),
            background=bg, user=stu, db=db,
        )
        check("8b. ikinci bekleyen istek reddedilir", False)
    except HTTPException as e:
        check("8b. ikinci bekleyen istek reddedilir",
              e.detail["code"] == "pending_exists")

    # ---- 9) Uydurma saat isteği reddedilir ----
    appt_req = db.get(CoachingAppointment, req1.id)
    db.delete(appt_req); db.commit()  # tekrar istek açabilsin
    try:
        student_appointment_request_v2(
            body=StudentRequestBody(date=tomorrow.isoformat(), start_time="21:30"),
            background=bg, user=stu, db=db,
        )
        check("9. pencere dışı saat reddedilir", False)
    except HTTPException as e:
        check("9. pencere dışı saat reddedilir",
              e.detail["code"] == "slot_unavailable")

    # ---- 10) İstek -> koç onayı ----
    res = student_appointment_request_v2(
        body=StudentRequestBody(date=tomorrow.isoformat(), start_time="16:00"),
        background=bg, user=stu, db=db,
    )
    req_id = res.data.appointment.id
    pend = teacher_appointments_v2(user=coach, db=db)
    check("10a. koç bekleyen istekleri görür",
          any(p.id == req_id for p in pend.pending))
    res = teacher_appointment_approve_v2(
        appt_id=req_id, background=bg, user=coach, db=db,
    )
    check("10b. onay -> scheduled",
          res.data.appointment.status == APPT_STATUS_SCHEDULED)

    # ---- 11) İstek -> red ----
    res = student_appointment_request_v2(
        body=StudentRequestBody(date=tomorrow.isoformat(), start_time="17:00"),
        background=bg, user=stu, db=db,
    )
    rej_id = res.data.appointment.id
    res = teacher_appointment_reject_v2(
        appt_id=rej_id, body=RejectBody(reason="O saat yüz yüze dersim var"),
        background=bg, user=coach, db=db,
    )
    check("11. red -> rejected + sebep",
          res.data.appointment.status == APPT_STATUS_REJECTED
          and res.data.appointment.cancel_reason)

    # ---- 12) Withdraw: yalnız pending ----
    res = student_appointment_request_v2(
        body=StudentRequestBody(date=tomorrow.isoformat(), start_time="17:00"),
        background=bg, user=stu, db=db,
    )
    wd_id = res.data.appointment.id
    student_appointment_withdraw_v2(appt_id=wd_id, user=stu, db=db)
    check("12a. pending istek geri çekildi",
          db.get(CoachingAppointment, wd_id) is None)
    try:
        student_appointment_withdraw_v2(appt_id=req_id, user=stu, db=db)
        check("12b. scheduled geri çekilemez", False)
    except HTTPException as e:
        check("12b. scheduled geri çekilemez", e.detail["code"] == "not_pending")

    # ---- 13) Güncelleme: saat değişimi + damga sıfırlama ----
    appt_row = db.get(CoachingAppointment, appt1.id)
    appt_row.reminder_d1_sent_at = datetime.now(); db.commit()
    new_d = d1 + timedelta(days=1)
    res = teacher_appointment_update_v2(
        appt_id=appt1.id,
        body=AppointmentUpdateBody(date=new_d.isoformat(), start_time="18:00"),
        background=bg, user=coach, db=db,
    )
    db.refresh(appt_row)
    check("13. saat değişti + hatırlatma damgası sıfırlandı",
          res.data.appointment.start_time == "18:00"
          and appt_row.reminder_d1_sent_at is None)

    # ---- 14) İptal ----
    res = teacher_appointment_status_v2(
        appt_id=appt1.id,
        body=AppointmentStatusBody(status="cancelled", reason="Hastalık"),
        background=bg, user=coach, db=db,
    )
    check("14. iptal + sebep",
          res.data.appointment.status == APPT_STATUS_CANCELLED
          and res.data.appointment.cancel_reason == "Hastalık")

    # ---- 15) Veli görünürlüğü ----
    pv = parent_student_appointments_v2(student_id=stu.id, user=parent, db=db)
    check("15a. bağlı veli yaklaşan randevuları görür",
          any(a.id == req_id for a in pv.upcoming))
    try:
        parent_student_appointments_v2(student_id=stu.id, user=parent2, db=db)
        check("15b. yabancı veli 404", False)
    except HTTPException as e:
        check("15b. yabancı veli 404", e.status_code == 404)

    # ---- 16) Öğrenci listesi ----
    sv = student_appointments_v2(user=stu, db=db)
    check("16. öğrenci listesi: upcoming + can_request",
          any(a.id == req_id for a in sv.upcoming) and sv.can_request)

    # ---- 17) Hatırlatma cron (D-1 + H-1 + idempotent) ----
    # Sistemde şu an: yarın 16:00 randevusu (req_id) -> 24 saat içindeyse D-1.
    # Deterministik olsun diye randevuyu now+2h ve now+30dk olarak kur.
    db.query(CoachingAppointment).filter(
        CoachingAppointment.student_id == stu.id,
    ).delete(synchronize_session=False)
    db.commit()
    now_local = svc.now_tr()
    a_d1 = now_local + timedelta(hours=3)
    a_h1 = now_local + timedelta(minutes=30)
    r1 = CoachingAppointment(
        coach_id=coach.id, student_id=stu.id, date=a_d1.date(),
        start_time=a_d1.strftime("%H:%M"), duration_min=40,
        status=APPT_STATUS_SCHEDULED,
    )
    r2 = CoachingAppointment(
        coach_id=coach.id, student_id=stu.id, date=a_h1.date(),
        start_time=a_h1.strftime("%H:%M"), duration_min=40,
        status=APPT_STATUS_SCHEDULED,
    )
    db.add_all([r1, r2]); db.commit()
    out = svc.run_maintenance(db, now_utc=datetime.utcnow())
    db.commit()
    db.refresh(r1); db.refresh(r2)
    check("17a. D-1 + H-1 hatırlatma gönderildi",
          out["d1_sent"] >= 1 and out["h1_sent"] >= 1
          and r1.reminder_d1_sent_at is not None
          and r2.reminder_h1_sent_at is not None
          and r2.reminder_d1_sent_at is not None,
          str(out))
    out2 = svc.run_maintenance(db, now_utc=datetime.utcnow())
    db.commit()
    check("17b. cron idempotent (ikinci koşum 0)",
          out2["d1_sent"] == 0 and out2["h1_sent"] == 0, str(out2))

    # ---- 18) Veli pref süzgeci ----
    pref = ParentNotificationPref(parent_id=parent.id, appointment_enabled=False)
    db.add(pref); db.commit()
    check("18a. pref kapalı -> veli hedef listesinde yok",
          svc._parent_targets(db, stu.id) == [])
    pref.appointment_enabled = True; db.commit()
    check("18b. pref açık -> veli hedefte",
          svc._parent_targets(db, stu.id) == [parent.id])

    # ---- 19) Seri güncelleme + pasifleştirme ----
    res = teacher_series_update_v2(
        series_id=series_id, body=SeriesUpdateBody(start_time="20:00"),
        user=coach, db=db,
    )
    occ_new = (
        db.query(CoachingAppointment)
        .filter(CoachingAppointment.series_id == series_id,
                CoachingAppointment.status == APPT_STATUS_SCHEDULED)
        .all()
    )
    check("19a. seri saati değişti -> occurrence'lar 20:00",
          res.data.regenerated >= 1
          and all(o.start_time == "20:00" for o in occ_new),
          f"regen={res.data.regenerated}")
    res = teacher_series_update_v2(
        series_id=series_id, body=SeriesUpdateBody(active=False),
        user=coach, db=db,
    )
    remaining = (
        db.query(CoachingAppointment)
        .filter(CoachingAppointment.series_id == series_id,
                CoachingAppointment.status == APPT_STATUS_SCHEDULED)
        .count()
    )
    check("19b. seri pasif -> gelecek occurrence'lar iptal",
          not res.data.series.active and remaining == 0
          and res.data.cancelled >= 1)

    # ---- 20) Google: yapılandırılmamışken 409 + no-op ----
    check("20a. google yapılandırılmamış", not google_meet.is_configured())
    try:
        teacher_google_connect_url_v2(user=coach, db=db)
        check("20b. connect-url 409", False)
    except HTTPException as e:
        check("20b. connect-url 409",
              e.status_code == 409 and e.detail["code"] == "google_not_configured")

    # ---- 21) Google mock: OAuth exchange + otomatik Meet linki ----
    settings.google_oauth_client_id = "test-client"
    settings.google_oauth_client_secret = "test-secret"

    def fake_post_form(url, data):
        if "token" in url:
            return {
                "refresh_token": "fake-refresh",
                "access_token": "fake-access",
                "expires_in": 3600,
            }
        return {}

    calls = {"events": 0}

    def fake_api_request(method, url, *, token, json_body=None):
        if "userinfo" in url:
            return {"email": "koc@gmail.com"}
        if "events" in url and method == "POST":
            calls["events"] += 1
            return {
                "id": f"evt-{calls['events']}",
                "hangoutLink": "https://meet.google.com/xyz-mock-123",
            }
        return {}

    orig_post, orig_api = google_meet._post_form, google_meet._api_request
    google_meet._post_form = fake_post_form
    google_meet._api_request = fake_api_request
    try:
        account = google_meet.exchange_code(db, coach, "fake-code")
        db.commit()
        check("21a. OAuth exchange -> hesap bağlandı + email",
              account.google_email == "koc@gmail.com"
              and account.refresh_token_encrypted != "fake-refresh")

        d3, t3 = next_weekday_at(5, 14)
        res = teacher_appointment_create_v2(
            body=AppointmentCreateBody(
                student_id=stu.id, date=d3.isoformat(), start_time=t3,
            ),
            background=bg, user=coach, db=db,
        )
        check("21b. randevuya otomatik Meet linki",
              res.data.google_link_attached
              and res.data.appointment.meeting_link == "https://meet.google.com/xyz-mock-123"
              and res.data.appointment.link_source == "google")

        # Elle link verilirse Google'a GİDİLMEZ
        before = calls["events"]
        d4, t4 = next_weekday_at(6, 14)
        res = teacher_appointment_create_v2(
            body=AppointmentCreateBody(
                student_id=stu.id, date=d4.isoformat(), start_time=t4,
                meeting_link="https://zoom.us/j/123",
            ),
            background=bg, user=coach, db=db,
        )
        check("21c. elle link -> Google çağrısı yok",
              calls["events"] == before
              and res.data.appointment.link_source == "manual")

        g = svc.google_status(db, coach)
        check("21d. google durum: connected + email",
              g["connected"] and g["email"] == "koc@gmail.com" and g["configured"])
    finally:
        google_meet._post_form = orig_post
        google_meet._api_request = orig_api
        settings.google_oauth_client_id = ""
        settings.google_oauth_client_secret = ""

    # ---- 22) F4 — randevudan seans kaydı (KS1 köprüsü) ----
    from app.routes.api_v2.appointments import (
        teacher_appointment_record_session_v2,
    )
    from app.routes.api_v2.schemas.appointment import RecordSessionBody

    try:
        teacher_appointment_record_session_v2(
            appt_id=r1.id, body=RecordSessionBody(outcome="done"),
            user=coach, db=db,
        )
        check("22a. gündemsiz done reddedilir", False)
    except HTTPException as e:
        check("22a. gündemsiz done reddedilir",
              e.detail["code"] == "agenda_required")

    res = teacher_appointment_record_session_v2(
        appt_id=r1.id,
        body=RecordSessionBody(
            outcome="done",
            agenda="Deneme analizi + haftalık plan konuşuldu",
            mood=4,
        ),
        user=coach, db=db,
    )
    sess = db.get(CoachingSession, res.data.session_id)
    db.refresh(r1)
    check("22b. done -> DONE seans (online, süre, bağ) + randevu done",
          sess is not None
          and sess.status == CoachingSessionStatus.DONE
          and sess.channel == CoachingChannel.ONLINE
          and sess.appointment_id == r1.id
          and sess.duration_min == r1.duration_min
          and sess.session_date == r1.date
          and sess.auto_snapshot
          and r1.status == APPT_STATUS_DONE)

    try:
        teacher_appointment_record_session_v2(
            appt_id=r1.id,
            body=RecordSessionBody(outcome="done", agenda="tekrar"),
            user=coach, db=db,
        )
        check("22c. mükerrer seans reddedilir", False)
    except HTTPException as e:
        check("22c. mükerrer seans reddedilir",
              e.detail["code"] == "session_exists")

    bundle = teacher_appointments_v2(user=coach, db=db)
    row = next((a for a in bundle.items if a.id == r1.id), None)
    check("22d. takvim satırında session_id",
          row is not None and row.session_id == sess.id)

    res = teacher_appointment_record_session_v2(
        appt_id=r2.id, body=RecordSessionBody(outcome="no_show"),
        user=coach, db=db,
    )
    sess2 = db.get(CoachingSession, res.data.session_id)
    db.refresh(r2)
    check("22e. no_show -> NO_SHOW seans + varsayılan gündem",
          sess2 is not None
          and sess2.status == CoachingSessionStatus.NO_SHOW
          and "gelmedi" in sess2.agenda.lower()
          and r2.status == APPT_STATUS_NO_SHOW)

    res = student_appointment_request_v2(
        body=StudentRequestBody(date=tomorrow.isoformat(), start_time="15:00"),
        background=bg, user=stu, db=db,
    )
    pend_id = res.data.appointment.id
    try:
        teacher_appointment_record_session_v2(
            appt_id=pend_id,
            body=RecordSessionBody(outcome="done", agenda="x"),
            user=coach, db=db,
        )
        check("22f. pending istekten seans olmaz", False)
    except HTTPException as e:
        check("22f. pending istekten seans olmaz",
              e.detail["code"] == "pending_needs_review")

    # Taze iptal kaydı (appt1 test 17'de silinmişti — SQLite id-reuse tuzağı)
    cancelled_appt = CoachingAppointment(
        coach_id=coach.id, student_id=stu.id,
        date=tomorrow, start_time="09:00", duration_min=40,
        status=APPT_STATUS_CANCELLED,
    )
    db.add(cancelled_appt); db.commit()
    try:
        teacher_appointment_record_session_v2(
            appt_id=cancelled_appt.id,
            body=RecordSessionBody(outcome="done", agenda="x"),
            user=coach, db=db,
        )
        check("22g. iptal randevudan seans olmaz", False)
    except HTTPException as e:
        check("22g. iptal randevudan seans olmaz",
              e.detail["code"] == "not_recordable")

    try:
        teacher_appointment_record_session_v2(
            appt_id=r1.id,
            body=RecordSessionBody(outcome="done", agenda="x"),
            user=other, db=db,
        )
        check("22h. yabancı koç 404", False)
    except HTTPException as e:
        check("22h. yabancı koç 404", e.status_code == 404)

finally:
    clean()
    db.close()

print(f"\n{'='*50}\nSONUC: {PASS} PASS / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
