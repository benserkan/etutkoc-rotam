import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.deps import get_current_user
from app.models import User, UserRole

logger = logging.getLogger(__name__)
from app.routes import auth as auth_routes
from app.routes import (
    health,
    parent,
    partials,
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
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax")

# Static
from pathlib import Path
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(health.router)
app.include_router(auth_routes.router)
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
app.include_router(whatsapp_webhook.router)


@app.get("/")
def index(user: User | None = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    if user.role == UserRole.TEACHER:
        dest = "/teacher"
    elif user.role == UserRole.PARENT:
        dest = "/parent"
    else:
        dest = "/student"
    return RedirectResponse(url=dest, status_code=status.HTTP_303_SEE_OTHER)




