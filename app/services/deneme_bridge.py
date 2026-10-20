"""Görev denemesi → Denemeler köprüsü (D3, 2026-10-20).

Öğrenci (ya da koç) programdaki bir deneme satırına sonuç girince (1 kalem = 1 deneme)
o deneme Denemeler sistemine (ExamResult) kendiliğinden yazılır: net grafiği, gelişim
raporu, puan tahmini, veli paneli, Rota hepsi aynı kaydı okur.

Kurallar
· Kayıt yalnız SONUÇ girilince açılır (çözüldü + doğru/yanlış var). "Sonucu sonra
  gireceğim" (sonuç bekliyor) ve "çözmedim" kayıt açmaz; sonuç silinirse kayıt da gider.
· Branş denemesi → branş serisi (ders kırılımı tek satır: dersin adı); genel deneme →
  genel seri. Soru sayısı standardın %60'ının altındaysa (LGS Sayısal Bölüm 40/90)
  genel seriye KARIŞMAZ — bölüm serisi olur.
· Kayıt görevden yönetilir (import_source="task"). Koç aynı denemeyi PDF'ten içe
  aktarıp "yerine yaz" derse kayıt PDF'e dönüşür ve görev artık ona dokunmaz.
· Veliye otomatik duyuru YOK (koç "Veliye duyur" ile kendisi gönderir).

TEK GİRİŞ: SQLAlchemy `before_flush` dinleyicisi — sonucu değiştiren her yol (öğrenci
sonuç penceresi, koç rozeti, geri alma, gün sonu, görev silme) aynı kuralla eşitlenir.
"""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.exam_result import SOURCE_TASK  # noqa: E402  (tek kaynak)
_WATCHED = ("completed_count", "correct_count", "wrong_count", "blank_count",
            "question_count", "duration_minutes", "exam_section", "exam_kind", "subject_id", "label")


def _has_result(item) -> bool:
    return (
        getattr(item, "exam_kind", None) is not None
        and int(item.completed_count or 0) > 0
        and (item.correct_count is not None or item.wrong_count is not None)
    )


_TIMES_RE = re.compile(r"\s*×\s*\d+")
_QN_RE = re.compile(r"\s*\(\s*\d{1,3}\s*soru\s*\)")
_IDX_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s*$")


def _clean(text: str | None) -> str:
    return re.sub(r"\s{2,}", " ", _QN_RE.sub("", _TIMES_RE.sub("", text or ""))).strip()


def _base_title(item) -> str:
    """Denemenin adı: kaynaklıda "Kitap — DENEME 3", kaynaksızda görevin adı (×N/soru atılır)."""
    book = getattr(item, "book", None)
    sec = getattr(item, "section", None)
    if book is not None and sec is not None:
        return f"{book.name} — {_clean(sec.label)}"
    if book is not None:
        return book.name
    task = getattr(item, "task", None)
    return _clean(getattr(task, "title", None)) or _clean(_IDX_RE.sub("", item.label or "")) or "Deneme"


def _title(item) -> str:
    base = _base_title(item)
    if getattr(item, "book", None) is None:
        siblings = sorted((it for it in (item.task.book_items or []) if getattr(it, "exam_kind", None)),
                          key=lambda it: it.id or 0)
        if len(siblings) > 1:
            m = _IDX_RE.search(item.label or "")
            n = int(m.group(1)) if m else next((i for i, it in enumerate(siblings, 1) if it is item), None)
            if n:
                base = f"{base} · {n}. deneme"
    return base[:200]


def _section(item):
    from app.models.curriculum import ExamSection
    from app.services.deneme_service import exam_section_for_subject, item_subject

    raw = getattr(item, "exam_section", None) or exam_section_for_subject(item_subject(item))
    try:
        return ExamSection(raw) if raw else None
    except ValueError:
        return None


def _scope_and_subject(item, section, qn: int | None) -> tuple[str, str | None]:
    """('brans'|'genel', ders kırılımı satır adı)."""
    from app.services.deneme_service import item_subject
    from app.services.exam_scope import BRANCH_RATIO, STANDARD_QUESTIONS

    if item.exam_kind == "brans":
        subj = item_subject(item)
        return "brans", (subj.name if subj is not None else "Branş")
    std = STANDARD_QUESTIONS.get(section.value)
    if std and qn and qn < std * BRANCH_RATIO:
        low = _base_title(item).lower()
        name = "Sayısal bölüm" if "sayısal" in low else ("Sözel bölüm" if "sözel" in low else "Bölüm")
        return "brans", name
    return "genel", None


def _find(db: Session, item_id: int):
    from app.models import ExamResult

    return db.query(ExamResult).filter(ExamResult.task_book_item_id == item_id).first()


def sync_item(db: Session, item) -> None:
    """Kalemin sonucuna göre bağlı deneme kaydını aç / güncelle / sil."""
    from app.models import ExamResult
    from app.models.exam_result import compute_net

    if item.id is None:
        return
    rec = _find(db, item.id)
    if rec is not None and rec.import_source != SOURCE_TASK:
        return  # PDF'ten içe aktarılmış kayıt esas — görev dokunmaz
    if not _has_result(item):
        if rec is not None:
            db.delete(rec)
        return
    section = _section(item)
    task = item.task
    if section is None or task is None:
        return
    c, w = int(item.correct_count or 0), int(item.wrong_count or 0)
    qn = item.question_count
    b = item.blank_count if item.blank_count is not None else (max(0, qn - c - w) if qn else 0)
    net = compute_net(c, w, section)
    scope, subj_name = _scope_and_subject(item, section, qn)
    meta = {"source": SOURCE_TASK, "task_id": task.id}
    if item.duration_minutes:
        meta["duration_minutes"] = int(item.duration_minutes)
    if qn:
        meta["question_count"] = int(qn)
    subj_payload = (
        json.dumps([{"name": subj_name, "correct": c, "wrong": w, "blank": int(b), "net": net}],
                   ensure_ascii=False)
        if subj_name else None
    )
    if rec is None:
        rec = ExamResult(student_id=task.student_id, created_by_id=task.student_id,
                         import_source=SOURCE_TASK, task_book_item_id=item.id,
                         title="Deneme", exam_date=task.date, section=section)
        db.add(rec)
    rec.title = _title(item)
    rec.exam_date = task.date
    rec.section = section
    rec.total_correct, rec.total_wrong, rec.total_blank = c, w, int(b)
    rec.net = net
    rec.subject_nets = subj_payload
    rec.analysis_meta = json.dumps(meta, ensure_ascii=False)
    # Kapsam yalnız otomatik sınıflama yanılırsa zorlanır (aksi hâlde "koç işaretledi" görünür).
    from app.services.exam_scope import classify

    if classify(rec) != scope:
        meta["scope"] = scope
        rec.analysis_meta = json.dumps(meta, ensure_ascii=False)


def _changed(obj, names) -> bool:
    st = sa_inspect(obj)
    return any(st.attrs[n].history.has_changes() for n in names if n in st.attrs)


@event.listens_for(Session, "before_flush")
def _bridge_before_flush(session: Session, flush_context, instances) -> None:  # noqa: ARG001
    from app.models import ExamResult, Task, TaskBookItem

    try:
        deleted_items = [o.id for o in session.deleted if isinstance(o, TaskBookItem) and o.id]
        deleted_tasks = [o.id for o in session.deleted if isinstance(o, Task) and o.id]
        if deleted_tasks:
            deleted_items += [r[0] for r in session.query(TaskBookItem.id)
                              .filter(TaskBookItem.task_id.in_(deleted_tasks)).all()]
        if deleted_items:
            for rec in (session.query(ExamResult)
                        .filter(ExamResult.task_book_item_id.in_(deleted_items),
                                ExamResult.import_source == SOURCE_TASK).all()):
                session.delete(rec)
        seen: set[int] = set()
        for o in list(session.dirty):
            if isinstance(o, TaskBookItem) and o.id and o.exam_kind is not None and o not in session.deleted:
                if _changed(o, _WATCHED) and o.id not in seen:
                    seen.add(o.id)
                    sync_item(session, o)
            elif isinstance(o, Task) and o.id and o not in session.deleted and _changed(o, ("date", "title")):
                for it in o.book_items or []:
                    if it.exam_kind is not None and it.id and it.id not in seen:
                        seen.add(it.id)
                        sync_item(session, it)
    except Exception:  # köprü asla ana işlemi bozmaz
        logger.exception("deneme köprüsü eşitlenemedi")
