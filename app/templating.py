from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.models.book import BOOK_TYPE_LABELS, BookType
from app.models.task import TASK_TYPE_LABELS, TaskStatus, TaskType
from app.models.task_request import REQUEST_STATUS_LABELS, REQUEST_TYPE_LABELS


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

templates.env.globals["BOOK_TYPE_LABELS"] = BOOK_TYPE_LABELS
templates.env.globals["BookType"] = BookType
templates.env.globals["TASK_TYPE_LABELS"] = TASK_TYPE_LABELS
templates.env.globals["TaskType"] = TaskType
templates.env.globals["TaskStatus"] = TaskStatus
templates.env.globals["REQUEST_TYPE_LABELS"] = REQUEST_TYPE_LABELS
templates.env.globals["REQUEST_STATUS_LABELS"] = REQUEST_STATUS_LABELS
templates.env.globals["settings"] = settings
# Today helper — phase aktif olup olmadığı kontrolü için
templates.env.globals["today_date"] = lambda: date.today()
