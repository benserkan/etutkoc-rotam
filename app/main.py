import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserRole
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
from app.routes import auth as auth_routes
from app.routes.api_v1 import router as api_v1_router
from app.routes.api_v2 import router as api_v2_router
from app.routes import kvkk_public as kvkk_public_routes
from app.routes import offers_public as offers_public_routes
from app.routes import me as me_routes
from app.routes import password as password_routes
from app.routes import plans as plans_routes
from app.routes import signup as signup_routes
from app.routes import (
    admin,
    at_risk,
    dna,
    focus,
    goals,
    health,
    institution,
    parent,
    partials,
    review,
    student,
    student_requests,
    teacher_ai_insights,
    teacher_book_sets,
    teacher_books,
    teacher_dashboard,
    teacher_diagnostics,
    teacher_parents,
    teacher_program,
    teacher_requests,
    teacher_settings,
    teacher_student_detail,
    teacher_students,
    teacher_suggestions,
    teacher_tasks,
    teacher_years,
    whatsapp_webhook,
)
from app.templating import templates


# Bildirim dispatcher — dev modunda lifespan içinde 60sn'lik döngü.
# Production'da bu kapatılır; ayrı `python -m app.dispatcher --loop` process'i çalışır
# (multi-worker'da duplicate gönderim olmasın). Kontrol: `DEBUG=true` env.
async def _dispatcher_loop():
    from app.database import SessionLocal
    from app.services.cron_runner import tick as cron_tick
    from app.services.notification_dispatcher import dispatch_pending
    interval = 60
    logger.info("[dev] Cron + Notification loop başladı (interval=%ds)", interval)
    try:
        while True:
            try:
                with SessionLocal() as db:
                    # Cron job'ları → enqueue
                    try:
                        cron_tick(db)
                    except Exception as e:
                        logger.exception("dev cron_tick hata: %s", e)
                    # Kuyruktaki bildirimleri işle
                    dispatch_pending(db)
            except Exception as e:
                logger.exception("dispatcher loop iter hata: %s", e)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("[dev] Dispatcher loop durdu.")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    task: asyncio.Task | None = None
    if settings.debug:
        task = asyncio.create_task(_dispatcher_loop())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Session güvenliği (Sprint 2 multi-tenant security):
# - max_age: 24 saat default. Admin oturumları rol-bazlı daha kısa
#   tutulabilir ileride (deps.py içinde session.login_at kontrolüyle).
# - https_only: production'da True olmalı (DEBUG=false → Secure flag)
# - same_site=lax: CSRF temel koruması (POST'larda 3rd-party origin engellenir)
# - HttpOnly: Starlette SessionMiddleware default'u (her zaman açık)
# Stage 7 — Sistem geneli duyuruları her request'e inject et.
# Middleware ile request.state.announcements set edilir; base.html okur.
# Sıralama önemli: bu middleware @app.middleware ile EKLENEN ilk middleware
# olmalı (Starlette user_middleware listesinde ilk eleman = INNER → session
# middleware'in ALTINDA çalışır → request.session erişilebilir).
# Katman 11.E — Sistem hata izleme middleware.
# Her HTTP request'i sarmalar: response_time ölç, 5xx veya exception → ErrorEvent,
# yavaş request (>1500ms) → SlowRequestLog. Defansif: kendisi hata fırlatmaz.
@app.middleware("http")
async def error_capture_middleware(request, call_next):
    import time as _time
    from app.models import SLOW_REQUEST_THRESHOLD_MS
    path = request.url.path
    # Static/health/_partial yollarını izleme (gürültü azalt)
    skip = (
        path.startswith("/static")
        or path.startswith("/health")
        or path.startswith("/_partial")
        or path == "/favicon.ico"
    )
    start = _time.perf_counter()
    exc: BaseException | None = None
    status_code = 0
    try:
        response = await call_next(request)
        status_code = getattr(response, "status_code", 0)
    except BaseException as e:
        exc = e
        status_code = 500
        # Aşağıda kaydı yazıp re-raise edeceğiz
    elapsed_ms = int((_time.perf_counter() - start) * 1000)

    if not skip and (exc is not None or status_code >= 500 or elapsed_ms > SLOW_REQUEST_THRESHOLD_MS):
        try:
            from app.database import SessionLocal
            from app.services.error_capture import record_error, record_slow_request
            uid = (
                request.session.get("user_id")
                if hasattr(request, "session") else None
            )
            ip = (request.client.host if request.client else None)
            fwd = request.headers.get("x-forwarded-for")
            if fwd:
                ip = fwd.split(",")[0].strip()[:64]
            ua = request.headers.get("user-agent", "")[:255]
            with SessionLocal() as _db:
                if exc is not None or status_code >= 500:
                    record_error(
                        _db,
                        endpoint=path[:255],
                        method=request.method,
                        status_code=status_code or 500,
                        exception=exc,
                        actor_user_id=uid,
                        ip=ip,
                        user_agent=ua,
                    )
                if elapsed_ms > SLOW_REQUEST_THRESHOLD_MS:
                    record_slow_request(
                        _db,
                        endpoint=path[:255],
                        method=request.method,
                        status_code=status_code or 0,
                        response_time_ms=elapsed_ms,
                        actor_user_id=uid,
                        ip=ip,
                    )
        except Exception:
            logger.exception("error_capture middleware non-fatal fail")

    if exc is not None:
        raise exc
    return response


@app.middleware("http")
async def inject_announcements(request, call_next):
    """Aktif duyuruları request.state.announcements'a koy.

    Statik/health gibi yollar için atlanır (template render etmiyorlar
    ve DB query maliyetinden kaçınmak iyi). 60sn cache'li olduğu için
    pratikte SQL ucuz ama yine de defansif.
    """
    path = request.url.path
    skip = (
        path.startswith("/static")
        or path.startswith("/health")
        or path.startswith("/_partial")
        or path.endswith(".css")
        or path.endswith(".js")
        or path.endswith(".png")
        or path.endswith(".ico")
    )
    if not skip:
        try:
            from app.database import SessionLocal
            from app.services.announcements import active_for_user
            from app.services.plans import compute_trial_banner
            uid = request.session.get("user_id") if hasattr(request, "session") else None
            with SessionLocal() as _db:
                u = None
                if uid:
                    from app.models import User as _User
                    u = _db.get(_User, uid)
                request.state.announcements = active_for_user(_db, u)
                # Stage 9 (Faz 2.4) — Trial countdown global banner
                request.state.trial_banner = (
                    compute_trial_banner(_db, user=u) if u else None
                )
        except Exception as e:
            # Defansif — duyuru sistemi sayfayı bozmasın
            import logging
            logging.getLogger(__name__).warning("announcement middleware fail (non-fatal): %s", e)
            request.state.announcements = []
            request.state.trial_banner = None
    else:
        request.state.announcements = []
        request.state.trial_banner = None

    response = await call_next(request)
    return response


# SessionMiddleware EN SONA add_middleware ile eklenir → user_middleware
# listesinde son eleman → reversed iter'da ilk wrap → en OUTERMOST →
# request.session inject_announcements çağrılmadan önce hazır.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    max_age=24 * 60 * 60,
    https_only=not settings.debug,  # prod (DEBUG=false) → Secure cookie
)

# CORS — native mobile + PWA için. Origin allowlist settings.cors_origins'tan
# (virgülle ayrılmış). "*" tüm originlere açar; production'da kullanma.
# Cookie-based session web origin'i aynı host olduğu için CORS gerekmez;
# bu middleware esas /api/v1 (JWT) çağrıları için.
_cors_origins_raw = settings.cors_origins.strip()
if _cors_origins_raw == "*":
    _allow_origins = ["*"]
    _allow_credentials = False  # "*" + credentials kombinasyonu spec ihlali
else:
    _allow_origins = [
        o.strip() for o in _cors_origins_raw.split(",") if o.strip()
    ]
    _allow_credentials = True
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["Retry-After"],
    max_age=600,
)

# Static
from pathlib import Path
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(health.router)
app.include_router(auth_routes.router)
app.include_router(password_routes.router)
app.include_router(signup_routes.router)
app.include_router(plans_routes.router)
app.include_router(me_routes.router)
app.include_router(kvkk_public_routes.router)
app.include_router(offers_public_routes.router)
app.include_router(admin.router)
app.include_router(institution.router)
app.include_router(at_risk.router)
app.include_router(partials.router)
app.include_router(teacher_dashboard.router)
app.include_router(teacher_ai_insights.router)
app.include_router(teacher_settings.router)
app.include_router(teacher_years.router)
app.include_router(teacher_students.router)
app.include_router(teacher_student_detail.router)
app.include_router(teacher_program.router)
app.include_router(teacher_tasks.router)
app.include_router(teacher_suggestions.router)
app.include_router(teacher_diagnostics.router)
app.include_router(teacher_books.router)
app.include_router(teacher_book_sets.router)
app.include_router(teacher_parents.router)
app.include_router(teacher_requests.router)
app.include_router(student.router)
app.include_router(student_requests.router)
app.include_router(parent.router)
app.include_router(goals.router)
app.include_router(review.router)
app.include_router(dna.router)
app.include_router(focus.router)
app.include_router(whatsapp_webhook.router)
app.include_router(api_v1_router)
app.include_router(api_v2_router)


@app.get("/")
def index(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Public landing (vitrin). Logged-in user için role-bazlı dashboard redirect."""
    if user:
        if user.role == UserRole.TEACHER:
            dest = "/teacher"
        elif user.role == UserRole.PARENT:
            dest = "/parent"
        elif user.role == UserRole.SUPER_ADMIN:
            dest = "/admin"
        elif user.role == UserRole.INSTITUTION_ADMIN:
            dest = "/institution"
        else:
            dest = "/student"
        return RedirectResponse(url=dest, status_code=status.HTTP_303_SEE_OTHER)

    # Katman 9 — A/B variant atama için session_id ensure'le.
    # Landing'e logged-in user gelmiyor (yukarıda redirect ediliyor); viewer=None.
    from app.services import feature_catalog as fc
    from app.services import telemetry as tel
    from fastapi.responses import HTMLResponse

    response = HTMLResponse("", status_code=200)  # cookie set için ön-yanıt
    sid = tel.ensure_session_id(request, response)
    feature_cards, variant_slug = fc.get_for_landing_with_variant(
        db, viewer=None, session_id=sid,
    )
    rendered = templates.TemplateResponse(
        "landing/index.html",
        {
            "request": request,
            "user": None,
            "feature_cards": feature_cards,
            "variant_slug": variant_slug,
        },
    )
    # Cookie'yi gerçek yanıta taşı
    for cookie_header in response.headers.getlist("set-cookie"):
        rendered.headers.append("set-cookie", cookie_header)
    return rendered


# ---------------------------- Katman 6 — Telemetri public endpoint ----------------------------


from fastapi import Response
from pydantic import BaseModel, Field as PField


class TelemetryEventIn(BaseModel):
    """Anasayfa kartı olay bildirimi (sendBeacon body'si)."""
    slug: str = PField(..., min_length=1, max_length=80)
    event: str = PField(..., min_length=1, max_length=20)
    variant: str | None = PField(default=None, max_length=40)


@app.post("/api/telemetry/event", status_code=204)
def telemetry_event(
    payload: TelemetryEventIn,
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Anonim/auth fark etmez — anasayfa kart davranışı kaydı.

    KVKK: düz IP/UA tutulmaz; SHA256 hash. Anon session cookie 90 gün.
    Throttle: aynı (session, slug, event) son 10sn'de → no-op.
    variant: Katman 9 A/B test variant_slug (opsiyonel) — istatistik için.
    Yanıt: 204 No Content (sendBeacon için ideal).
    """
    from app.services import telemetry as tel
    sid = tel.ensure_session_id(request, response)
    tel.record_event(
        db,
        slug=payload.slug,
        event_type=payload.event,
        session_id=sid,
        request=request,
        viewer=user,
        variant_slug=payload.variant,
    )
    return Response(status_code=204, headers=response.headers)


@app.get("/demos")
def demos(
    request: Request,
    play: str | None = None,
    user: User | None = Depends(get_current_user),
):
    """Public demo videoları oynatma sayfası (YouTube benzeri playlist).

    Query: ?play=<slug> → ilgili demo otomatik seçilir.
    user varsa rolüne göre playlist filtrelenir + varsayılan slug rolüne uygun seçilir.
    """
    # Rol bazlı varsayılan: öğretmen daily-plan görsün, öğrenci focus-pomodoro
    if not play:
        if user is not None and user.role == UserRole.STUDENT:
            play = "focus-pomodoro"
        else:
            play = "daily-plan"
    return templates.TemplateResponse(
        "landing/demos.html",
        {"request": request, "user": user, "play_slug": play},
    )




