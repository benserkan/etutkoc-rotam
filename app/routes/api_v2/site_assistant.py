"""Site asistanı "Rota" uçları — /api/v2/assistant (2026-10-03).

Giriş İSTEĞE BAĞLIDIR: ziyaretçi de kullanır (session_key = tarayıcının
ürettiği rastgele kimlik). Giriş yapmışsa rol ve hesap özeti kullanılır.

GET  /assistant?page=&session_key=       karşılama + hazır sorular + kalan hak
POST /assistant/ask                      {chip} → hazır cevap · {question} → yapay zekâ
POST /assistant/handoff                  ekibe aktar (destek talebi / iletişim talebi)
GET  /admin/assistant/messages           süper yönetici: sorular + en çok sorulanlar

Kilit hijyeni: durum okunur → işlem KAPATILIR → Gemini işlem DIŞINDA → kısa yazım.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.routes.api_v2.dependencies import _resolve_user_v2, bearer_scheme
from app.services import site_assistant as sa
from app.services.rate_limit import SlidingWindowLimiter, _client_ip

logger = logging.getLogger(__name__)
router = APIRouter(tags=["site-assistant"])

_ASK_LIMIT = SlidingWindowLimiter(window_seconds=60, max_hits=20)
_HANDOFF_LIMIT = SlidingWindowLimiter(window_seconds=600, max_hits=5)
_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def optional_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
                  db: Session = Depends(get_db)) -> User | None:
    try:
        user = _resolve_user_v2(request, creds, db)
    except HTTPException:
        return None
    if user.must_change_password:
        return None
    return user


def _key(session_key: str | None, user: User | None) -> str:
    if session_key and _KEY_RE.match(session_key):
        return session_key
    if user is not None:
        return f"u{user.id}"
    raise HTTPException(status_code=422, detail={"code": "session_key_required",
                                                 "message": "Oturum anahtarı eksik."})


def _page(p: str | None) -> str | None:
    if not p:
        return None
    p = p.split("?")[0].split("#")[0]
    return p[:200] if p.startswith("/") else None


# ----------------------------------------------------------------- şemalar

class AAction(BaseModel):
    type: str
    label: str | None = None
    href: str | None = None
    plan: str | None = None
    section: str | None = None


class AChip(BaseModel):
    id: str
    label: str


class AState(BaseModel):
    audience: str
    greeting: str
    chips: list[AChip]
    ai_left: int
    whatsapp: str
    logged_in: bool
    user_name: str | None = None


class AMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(max_length=2000)


class AAskBody(BaseModel):
    session_key: str | None = Field(default=None, max_length=64)
    page: str | None = Field(default=None, max_length=300)
    chip: str | None = Field(default=None, max_length=80)
    label: str | None = Field(default=None, max_length=200)
    question: str | None = Field(default=None, max_length=800)
    history: list[AMessage] = Field(default_factory=list, max_length=20)


class AAnswer(BaseModel):
    answer: str
    action: AAction | None = None
    source: str          # rule | ai | fallback | limit
    ai_left: int


class AHandoffBody(BaseModel):
    session_key: str | None = Field(default=None, max_length=64)
    page: str | None = Field(default=None, max_length=300)
    message: str = Field(min_length=3, max_length=2000)
    transcript: list[AMessage] = Field(default_factory=list, max_length=30)
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=200)   # bal küpü (bot tuzağı)


class AHandoffResult(BaseModel):
    ok: bool
    message: str
    whatsapp_url: str


# ----------------------------------------------------------------- uçlar

@router.get("/assistant", response_model=AState)
def assistant_state(request: Request, page: str | None = None, session_key: str | None = None,
                    user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    aud = sa.audience_for(user)
    pg = _page(page)
    key = _key(session_key, user)
    tstate = sa._teacher_state(db, user) if aud == "teacher" else None
    return AState(
        audience=aud,
        greeting=sa.greeting(db, user, aud, pg, tstate),
        chips=[AChip(**c) for c in sa.chips(db, user, aud, pg, tstate)],
        ai_left=sa.ai_left(db, user=user, session_key=key, iph=sa.ip_hash(_client_ip(request))),
        whatsapp=sa.whatsapp_number(),
        logged_in=user is not None,
        user_name=(user.full_name if user else None),
    )


@router.post("/assistant/ask", response_model=AAnswer)
def assistant_ask(body: AAskBody, request: Request, user: User | None = Depends(optional_user),
                  db: Session = Depends(get_db)):
    ip = _client_ip(request)
    ok, retry = _ASK_LIMIT.hit(f"ask:u{user.id}" if user else f"ask:{ip}")
    if not ok:
        raise HTTPException(status_code=429, detail={"code": "too_many",
                                                     "message": f"Biraz yavaş: {retry} saniye sonra tekrar dene."})
    aud = sa.audience_for(user)
    pg = _page(body.page)
    key = _key(body.session_key, user)
    iph = sa.ip_hash(ip)
    tstate = sa._teacher_state(db, user) if aud == "teacher" else None
    left = sa.ai_left(db, user=user, session_key=key, iph=iph)

    if body.chip:
        res = sa.rule_answer(db, user, aud, body.chip, tstate)
        sa.log_message(db, user=user, session_key=key, iph=iph, audience=aud, page=pg,
                       chip=body.chip[:60], question=(body.label or body.chip)[:800],
                       answer=res["answer"], source="rule")
        db.commit()
        return AAnswer(answer=res["answer"], action=res["action"], source="rule", ai_left=left)

    q = (body.question or "").strip()
    if not q:
        raise HTTPException(status_code=422, detail={"code": "question_required",
                                                     "message": "Bir soru yaz ya da hazır sorulardan birini seç."})
    if left <= 0:
        res = sa.fallback_answer(q, aud, pg)
        msg = ("Bugünlük yapay zekâ soru hakkın doldu; en yakın bilgiyi veriyorum. " + res["answer"])
        sa.log_message(db, user=user, session_key=key, iph=iph, audience=aud, page=pg, chip=None,
                       question=q, answer=msg, source="limit")
        db.commit()
        return AAnswer(answer=msg, action=res["action"], source="limit", ai_left=0)

    sections = sa.retrieve(q + " " + " ".join(h.text for h in body.history[-2:] if h.role == "user"),
                           aud, pg)
    facts = sa.account_facts(db, user, aud)
    db.commit()  # uzun dış çağrı açık işlem içinde yapılmaz
    try:
        res = sa.ai_answer(q, [h.model_dump() for h in body.history], audience=aud, page=pg,
                           sections=sections, facts=facts, tstate=tstate)
        source = "ai"
    except Exception:  # noqa: BLE001 — asistan asla boş dönmez
        logger.warning("site assistant AI failed", exc_info=True)
        res = sa.fallback_answer(q, aud, pg)
        source = "fallback"
    sa.log_message(db, user=user, session_key=key, iph=iph, audience=aud, page=pg, chip=None,
                   question=q, answer=res["answer"], source=source)
    db.commit()
    return AAnswer(answer=res["answer"], action=res["action"], source=source,
                   ai_left=max(0, left - (1 if source == "ai" else 0)))


def _wa_url(text: str) -> str:
    return f"https://wa.me/{sa.whatsapp_number()}?text={quote(text[:900])}"


_ROLE_LABEL = {"public": "ziyaretçi", "teacher": "koç", "student": "öğrenci", "parent": "veli",
               "institution_admin": "kurum yöneticisi", "super_admin": "süper yönetici"}


def _send_mails(recipients: list[str], ctx: dict, push_ids: list[int], push_title: str,
                push_body: str) -> None:
    """Arka plan: e-postalar + süper yöneticiye mobil bildirim (best-effort)."""
    from app.database import SessionLocal
    from app.services.email_service import send_email
    for to in recipients:
        try:
            send_email(to, "support_billing_handoff", dict(ctx))
        except Exception:  # noqa: BLE001
            logger.warning("assistant handoff mail failed to=%s", to, exc_info=True)
    if push_ids:
        try:
            from app.services.push_notifications import safe_push
            with SessionLocal() as db:
                for uid in push_ids:
                    safe_push(db, user_id=uid, title=push_title, body=push_body,
                              data={"type": "admin", "screen": "contact"})
        except Exception:  # noqa: BLE001
            logger.warning("assistant handoff push failed", exc_info=True)


@router.post("/assistant/handoff", response_model=AHandoffResult)
def assistant_handoff(body: AHandoffBody, request: Request, background: BackgroundTasks,
                      user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    ip = _client_ip(request)
    ok, retry = _HANDOFF_LIMIT.hit(f"handoff:u{user.id}" if user else f"handoff:{ip}")
    if not ok:
        raise HTTPException(status_code=429, detail={"code": "too_many",
                                                     "message": "Çok sayıda mesaj gönderildi; biraz sonra tekrar dene."})
    aud = sa.audience_for(user)
    pg = _page(body.page)
    key = _key(body.session_key, user)
    msg = body.message.strip()
    transcript = [{"who": "Kullanıcı" if m.role == "user" else "Rota", "text": m.text[:400]}
                  for m in body.transcript[-10:]]
    membership = sa.topic_is_membership([msg] + [m.text for m in body.transcript if m.role == "user"])
    wa_text = f"Merhaba, ETÜTKOÇ Rotam hakkında yazıyorum. {msg}"

    if body.website:   # bot — sessizce kabul et
        return AHandoffResult(ok=True, message="Mesajın iletildi.", whatsapp_url=_wa_url(wa_text))

    ctx_base = {
        "requester_role": _ROLE_LABEL.get(aud),
        "message": msg, "transcript": transcript, "page": pg,
        "origin": "asistandan", "origin_sentence": "site asistanında sorusunu çözemedi ve size yazdı.",
        "topic_label": "Üyelik talebi" if membership else "Destek talebi",
        "heading": "Yeni üyelik / ödeme talebi" if membership else "Asistandan yeni talep",
    }

    # --- Koç ve kurum yöneticisi: destek sistemi (yazışma panelde sürer)
    if aud in ("teacher", "institution_admin"):
        from app.routes.api_v2.plan_assistant import _handoff_recipients
        from app.services import support_request_service as srs
        lines = [msg, "", "— Site asistanından aktarıldı —", f"Sayfa: {pg or '-'}"]
        plan_ctx: dict = {}
        if aud == "teacher":
            tstate = sa._teacher_state(db, user)
            if tstate:
                p = tstate["plan"]
                from app.routes.api_v2.plan_assistant import _STATUS_TR
                plan_ctx = {"plan_label": p["plan_label"],
                            "status_label": _STATUS_TR.get(p["status"], p["status"]),
                            "student_count": p["student_count"],
                            "payment_issue": (p.get("last_payment_issue") or {}).get("title")}
                lines.append(f"Paket: {p['plan_label']} · aktif öğrenci: {p['student_count']}")
        if transcript:
            lines += ["", "Konuşma:"] + [f"{t['who']}: {t['text']}" for t in transcript]
        try:
            req = srs.create_request(db, requester=user, category="billing" if membership else "technical",
                                     subject=("Paket / ödeme sorusu" if membership else "Asistandan destek talebi"),
                                     body="\n".join(lines)[:3900])
        except srs.SupportError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
        sa.log_message(db, user=user, session_key=key, iph=sa.ip_hash(ip), audience=aud, page=pg,
                       chip=None, question=msg, answer=None, source="handoff", handoff=True)
        db.commit()
        if aud == "teacher":
            recipients, inbox = _handoff_recipients(db, user)
            push_ids: list[int] = []
        else:
            recipients, push_ids = sa.super_admin_recipients(db)
            inbox = "/admin/support"
        inst = getattr(user, "institution", None)
        ctx = {**ctx_base, **plan_ctx, "requester_name": user.full_name or user.email,
               "institution_name": getattr(inst, "name", None), "inbox_path": inbox,
               "request_id": req.id, "contact_email": user.email}
        if recipients or push_ids:
            background.add_task(_send_mails, recipients, ctx, push_ids,
                                "Asistandan yeni talep", f"{ctx['requester_name']}: {msg[:120]}")
        who = "kurum yöneticine" if (aud == "teacher" and user.institution_id) else "ekibimize"
        return AHandoffResult(ok=True, whatsapp_url=_wa_url(wa_text),
                              message=f"Mesajın {who} iletildi. Cevabı Destek sayfandan takip edebilirsin.")

    # --- Ziyaretçi, öğrenci, veli, süper yönetici: iletişim talebi (+ ziyaretçide satış adayı)
    from app.models.contact_request import CONTACT_STATUS_NEW, ContactRequest
    from app.services.phone_service import normalize_e164_tr

    if user is not None:
        name = user.full_name or user.email
        email = user.email
        phone = getattr(user, "phone", None)
    else:
        name = (body.name or "").strip()
        email = (body.email or "").strip()
        phone = normalize_e164_tr(body.phone or "") if (body.phone or "").strip() else None
        if len(name) < 2:
            raise HTTPException(status_code=422, detail={"code": "name_required",
                                                         "message": "Adını yaz ki sana dönebilelim."})
        if (body.phone or "").strip() and not phone:
            raise HTTPException(status_code=422, detail={"code": "invalid_phone",
                                                         "message": "Geçerli bir cep telefonu yaz (5XX...)."})
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise HTTPException(status_code=422, detail={"code": "invalid_email",
                                                         "message": "E-posta adresini kontrol et."})
        if not phone and not email:
            raise HTTPException(status_code=422, detail={"code": "contact_required",
                                                         "message": "Sana dönebilmemiz için telefon ya da e-posta yaz."})

    prospect_note = ""
    if user is None and phone:
        from app.models.sales_prospect import (PROSPECT_KIND_COACH, PROSPECT_KIND_INSTITUTION,
                                               SalesProspect)
        from app.services import prospect_service
        kind = (PROSPECT_KIND_INSTITUTION if re.search(r"kurum|dershane|etüt|etut|okul", sa._norm(msg))
                else PROSPECT_KIND_COACH)
        try:
            pr = prospect_service.create_prospect(
                db, actor_user_id=None, name=name, phone=phone, kind=kind, email=email or None,
                source="inbound", opt_in=True, note=f"Site asistanı: {msg[:200]}")
            prospect_note = f" aday_id={pr.id}"
        except prospect_service.ProspectError as exc:
            if exc.code == "duplicate_phone":
                ex = db.query(SalesProspect).filter_by(phone=phone).first()
                if ex is not None:
                    prospect_note = f" aday_id={ex.id}"

    tx = "\n".join(f"{t['who']}: {t['text']}" for t in transcript)
    full = (f"[Site asistanı · {_ROLE_LABEL.get(aud)} · sayfa {pg or '-'}]{prospect_note}\n{msg}"
            + (f"\n\nKonuşma:\n{tx}" if tx else ""))
    cr = ContactRequest(
        name=name[:160], email=(email or "asistan-lead@etutkoc.local")[:255], phone=(phone or None),
        source="assistant", message=full[:4000], status=CONTACT_STATUS_NEW,
    )
    db.add(cr)
    sa.log_message(db, user=user, session_key=key, iph=sa.ip_hash(ip), audience=aud, page=pg,
                   chip=None, question=msg, answer=None, source="handoff", handoff=True)
    db.commit()
    recipients, push_ids = sa.super_admin_recipients(db)
    ctx = {**ctx_base, "requester_name": name, "contact_phone": phone, "contact_email": email or None,
           "inbox_path": "/admin/contact-requests", "request_id": cr.id}
    background.add_task(_send_mails, recipients, ctx, push_ids, "Asistandan yeni talep",
                        f"{name}: {msg[:120]}")
    reply = ("Mesajın ekibimize iletildi; en kısa sürede sana döneceğiz."
             if user is None else "Mesajın ekibimize iletildi; e-posta adresinden sana döneceğiz.")
    return AHandoffResult(ok=True, message=reply, whatsapp_url=_wa_url(wa_text))


# ----------------------------------------------------------------- süper yönetici

class AdminAssistantRow(BaseModel):
    id: int
    created_at: datetime
    audience: str
    audience_label: str
    page: str | None
    question: str
    answer: str | None
    source: str
    handoff: bool
    user_id: int | None
    user_name: str | None


class AdminTopQuestion(BaseModel):
    question: str
    count: int


class AdminAssistantResponse(BaseModel):
    days: int
    total: int
    ai_count: int
    handoff_count: int
    by_audience: dict[str, int]
    top_questions: list[AdminTopQuestion]
    items: list[AdminAssistantRow]


@router.get("/admin/assistant/messages", response_model=AdminAssistantResponse)
def admin_assistant_messages(request: Request, days: int = Query(7, ge=1, le=90),
                             audience: str | None = None, only_handoff: bool = False,
                             user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "missing_credentials", "message": "Giriş gerekli."})
    if user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail={"code": "role_required", "message": "Yetkin yok."})
    from app.models import AssistantMessage as AM
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(AM).filter(AM.created_at >= since)
    if audience in sa.AUDIENCES:
        q = q.filter(AM.audience == audience)
    total = q.count()
    ai_count = q.filter(AM.source == "ai").count()
    handoff_count = q.filter(AM.handoff.is_(True)).count()
    by_aud = dict(db.query(AM.audience, func.count(AM.id)).filter(AM.created_at >= since)
                  .group_by(AM.audience).all())
    top_rows = (q.filter(AM.handoff.is_(False))
                .with_entities(AM.question, func.count(AM.id).label("n"))
                .group_by(AM.question).order_by(func.count(AM.id).desc()).limit(15).all())
    rows_q = q.filter(AM.handoff.is_(True)) if only_handoff else q
    rows = rows_q.order_by(AM.created_at.desc()).limit(200).all()
    names = {}
    uids = {r.user_id for r in rows if r.user_id}
    if uids:
        names = dict(db.query(User.id, User.full_name).filter(User.id.in_(uids)).all())
    return AdminAssistantResponse(
        days=days, total=total, ai_count=ai_count, handoff_count=handoff_count,
        by_audience={k: int(v) for k, v in by_aud.items()},
        top_questions=[AdminTopQuestion(question=qq, count=int(n)) for qq, n in top_rows],
        items=[AdminAssistantRow(
            id=r.id, created_at=r.created_at, audience=r.audience,
            audience_label=_ROLE_LABEL.get(r.audience, r.audience), page=r.page,
            question=r.question, answer=r.answer, source=r.source, handoff=bool(r.handoff),
            user_id=r.user_id, user_name=names.get(r.user_id)) for r in rows],
    )
