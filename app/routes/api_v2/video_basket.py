"""Video Sepeti — API v2 (koç).

Koç öğrenci başına YouTube oynatma listesi/video linki yapıştırır → videolar
konu gruplarına ayrılır (video_segmentation) → sepetten haftalık programa
sürüklenir. Programa konan videolar bir VIDEO görevine bağlanır:

  · Aynı gün + aynı konu grubu → TEK görev, birden çok video (görev.videos).
  · Günün video toplamı 60 dk'yı geçerse UYARI (engel değil — koç kararı).
  · Görev silinince videolar kendiliğinden sepete döner (FK SET NULL).
  · "İzlendi" = bağlı görev tamamlandı.

Sahiplik dışı her şey 404. Öğrenci/veli sepeti görmez; yalnız görevi görür.
"""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Subject, Task, TaskStatus, Topic, User
from app.models.video_basket import VIDEO_ROLE_LABELS, VIDEO_ROLES, VideoBasketItem, VideoSource
from app.routes.api_v2.dependencies import assert_active_coaching
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.teacher import TaskCreateBody
from app.routes.api_v2.schemas.video_basket import (
    VideoBasketResponse,
    VideoCopyBody,
    VideoCopyResult,
    VideoGroupKeyBody,
    VideoGroupOut,
    VideoGroupPatchBody,
    VideoImportBody,
    VideoImportResult,
    VideoItemOut,
    VideoItemPatchBody,
    VideoPlaceBody,
    VideoPlaceResult,
    VideoReorderBody,
    VideoSourceDeleteBody,
    VideoSourceOut,
    VideoSourcePatchBody,
)
from app.routes.api_v2.teacher import (
    _create_task_with_items,
    _get_owned_student,
    _invalidate_for_task,
    _parse_iso_date,
    _require_teacher,
    _validate_period,
)
from app.services import video_segmentation as seg
from app.services import youtube_service as yt
from app.services.curriculum_progress import leaf_topics_for_student

router = APIRouter(prefix="/teacher", tags=["v2-video-basket"])

DAY_WARN_MINUTES = 60
_AUTO_TITLE_RE = re.compile(r"— \d+ video(?: \(\d+ dk\))?$")


# ---------------------------------------------------------------- yardımcılar


def _err(status: int, code: str, message: str) -> HTTPException:
    kind = {404: "not_found", 409: "conflict", 422: "validation",
            503: "unavailable", 429: "rate_limited", 502: "upstream"}.get(status, "error")
    return HTTPException(status_code=status, detail={"error": kind, "code": code, "message": message})


def _yt_http(e: yt.YouTubeError) -> HTTPException:
    status = {"not_configured": 503, "bad_url": 422, "not_found": 404,
              "quota": 429, "unavailable": 502}.get(e.code, 502)
    return _err(status, f"youtube_{e.code}", e.message)


def _basket_key(tid: int, sid: int) -> str:
    return f"teacher:{tid}:students:{sid}:video-basket"


def _items(db: Session, sid: int) -> list[VideoBasketItem]:
    return (
        db.query(VideoBasketItem)
        .filter(VideoBasketItem.student_id == sid)
        .order_by(VideoBasketItem.order, VideoBasketItem.id)
        .all()
    )


def _owned_item(db: Session, item_id: int, coach: User) -> VideoBasketItem:
    it = db.get(VideoBasketItem, item_id)
    if it is None:
        raise _err(404, "video_not_found", "Video bulunamadı.")
    _get_owned_student(db, it.student_id, coach.id)  # yabancı öğrenci → 404
    return it


def _subject_accessible(db: Session, subject_id: int | None, coach: User) -> Subject | None:
    if subject_id is None:
        return None
    s = db.get(Subject, subject_id)
    if s is None or not (s.is_builtin or s.teacher_id is None or s.teacher_id == coach.id):
        raise _err(422, "subject_invalid", "Ders bulunamadı.")
    return s


def _item_status(it: VideoBasketItem) -> str:
    if it.task_id is None or it.task is None:
        return "waiting"
    return "watched" if it.task.status == TaskStatus.COMPLETED else "planned"


def _task_title(subject_name: str | None, label: str, vids: list[VideoBasketItem]) -> str:
    total = sum(v.duration_sec or 0 for v in vids)
    mins = f" ({max(1, round(total / 60))} dk)" if total else ""
    head = f"{subject_name} · {label}" if subject_name else label
    return f"{head} — {len(vids)} video{mins}"[:255]


def _refresh_task(db: Session, task: Task) -> None:
    """Görevin başlık/link'ini bağlı videolardan yeniden üret (koçun elle
    yazdığı başlık korunur: yalnız otomatik biçimli başlık yenilenir)."""
    vids = sorted(
        db.query(VideoBasketItem).filter(VideoBasketItem.task_id == task.id).all(),
        key=lambda v: (v.order, v.id),
    )
    if not vids:
        return
    first = vids[0]
    subj = db.get(Subject, first.subject_id) if first.subject_id else None
    if not task.title or _AUTO_TITLE_RE.search(task.title):
        task.title = _task_title(subj.name if subj else None, first.group_label, vids)
    task.link_url = first.url


def _day_minutes(db: Session, sid: int, d: date) -> int:
    total = (
        db.query(func.coalesce(func.sum(VideoBasketItem.duration_sec), 0))
        .join(Task, Task.id == VideoBasketItem.task_id)
        .filter(VideoBasketItem.student_id == sid, Task.date == d)
        .scalar()
    )
    return round(int(total or 0) / 60)


def _next_order(db: Session, sid: int) -> int:
    m = db.query(func.max(VideoBasketItem.order)).filter(VideoBasketItem.student_id == sid).scalar()
    return int(m or 0) + 1


def _detach(db: Session, it: VideoBasketItem) -> Task | None:
    """Videoyu görevinden çıkar. Görevde video kalmazsa görev silinir.
    Dönüş: dokunulan (hâlâ var olan) görev ya da None."""
    task = it.task
    if task is None:
        it.task_id = None
        return None
    if task.status == TaskStatus.COMPLETED:
        raise _err(409, "video_watched",
                   "Bu video izlendi olarak işaretli görevde; önce görevi geri al.")
    it.task_id = None
    db.flush()
    left = db.query(VideoBasketItem).filter(VideoBasketItem.task_id == task.id).count()
    if left == 0:
        db.delete(task)
        return None
    _refresh_task(db, task)
    return task


def _sources_key(tid: int) -> str:
    return f"teacher:{tid}:video-sources"


def _owned_source(db: Session, source_id: int, coach: User) -> VideoSource:
    src = db.get(VideoSource, source_id)
    if src is None or src.coach_id != coach.id:
        raise _err(404, "source_not_found", "Kayıtlı liste bulunamadı.")
    return src


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _source_rows(db: Session, coach_id: int, student_id: int | None) -> list[VideoSourceOut]:
    srcs = (db.query(VideoSource).filter(VideoSource.coach_id == coach_id)
            .order_by(VideoSource.last_used_at.desc(), VideoSource.id.desc()).all())
    if not srcs:
        return []
    subj_ids = {s.subject_id for s in srcs if s.subject_id}
    subj = {x.id: x.name for x in db.query(Subject).filter(Subject.id.in_(subj_ids))} if subj_ids else {}
    counts: dict[int, tuple[int, int]] = {}
    if student_id is not None:
        rows = (
            db.query(VideoBasketItem.source_id, func.count(VideoBasketItem.id),
                     func.sum(case((VideoBasketItem.task_id.is_(None), 1), else_=0)))
            .filter(VideoBasketItem.student_id == student_id, VideoBasketItem.source_id.isnot(None))
            .group_by(VideoBasketItem.source_id).all()
        )
        counts = {sid: (int(t or 0), int(w or 0)) for sid, t, w in rows}
    return [
        VideoSourceOut(
            id=s.id, name=s.display_name, title=s.title, label=s.label, url=s.url,
            subject_id=s.subject_id, subject_name=subj.get(s.subject_id),
            video_count=s.video_count, created_at=_iso(s.created_at),
            last_used_at=_iso(s.last_used_at),
            in_basket=counts.get(s.id, (0, 0))[0], waiting=counts.get(s.id, (0, 0))[1],
        )
        for s in srcs
    ]


def _upsert_source(db: Session, coach: User, url: str, data: yt.YtImport,
                   subject_id: int | None) -> VideoSource:
    """Getirilen listeyi koçun kayıtlı listelerine yaz/tazele (tekil anahtar)."""
    key = f"pl:{data.playlist_id}" if data.playlist_id else f"v:{data.videos[0].youtube_id}"
    src = (db.query(VideoSource)
           .filter(VideoSource.coach_id == coach.id, VideoSource.source_key == key).first())
    now = datetime.now(timezone.utc)
    title = data.playlist_title or (data.videos[0].title if data.kind == "video" else None)
    if src is None:
        src = VideoSource(coach_id=coach.id, source_key=key, created_at=now)
        db.add(src)
    src.url = (f"https://www.youtube.com/playlist?list={data.playlist_id}"
               if data.playlist_id else url.strip())[:500]
    src.playlist_id = data.playlist_id
    if title:
        src.title = title[:300]
    if subject_id:
        src.subject_id = subject_id
    src.video_count = len(data.videos)
    src.last_used_at = now
    db.flush()
    return src


# ---------------------------------------------------------------- okuma


@router.get("/students/{student_id}/video-basket", response_model=VideoBasketResponse)
def get_video_basket(student_id: int, user: User = Depends(_require_teacher),
                     db: Session = Depends(get_db)):
    _get_owned_student(db, student_id, user.id)
    items = _items(db, student_id)
    subj_ids = {i.subject_id for i in items if i.subject_id}
    top_ids = {i.topic_id for i in items if i.topic_id}
    subj = {s.id: s.name for s in db.query(Subject).filter(Subject.id.in_(subj_ids))} if subj_ids else {}
    tops = {t.id: t.name for t in db.query(Topic).filter(Topic.id.in_(top_ids))} if top_ids else {}

    groups: dict[str, VideoGroupOut] = {}
    waiting = 0
    for it in items:
        st = _item_status(it)
        waiting += st == "waiting"
        g = groups.get(it.group_key)
        if g is None:
            g = groups[it.group_key] = VideoGroupOut(
                group_key=it.group_key, label=it.group_label, topic_id=it.topic_id,
                topic_name=tops.get(it.topic_id), subject_id=it.subject_id,
                subject_name=subj.get(it.subject_id), playlist_title=it.playlist_title,
                source_id=it.source_id, items=[],
            )
        g.items.append(VideoItemOut(
            id=it.id, youtube_id=it.youtube_id, title=it.title, url=it.url,
            channel_title=it.channel_title, duration_min=it.duration_min, role=it.role,
            role_label=VIDEO_ROLE_LABELS.get(it.role, it.role), order=it.order, status=st,
            task_id=it.task_id if st != "waiting" else None,
            task_date=it.task.date.isoformat() if st != "waiting" and it.task else None,
        ))
        g.total_min += it.duration_min or 0
        g.waiting_count += st == "waiting"
    return VideoBasketResponse(
        youtube_configured=yt.is_configured(), groups=list(groups.values()),
        waiting_count=waiting, day_warn_minutes=DAY_WARN_MINUTES,
        sources=_source_rows(db, user.id, student_id),
    )


# ---------------------------------------------------------------- içe aktarma


@router.post("/students/{student_id}/video-basket/import",
             response_model=MutationResponse[VideoImportResult])
def import_videos(student_id: int, body: VideoImportBody,
                  user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    saved: VideoSource | None = None
    if body.source_id:
        saved = _owned_source(db, body.source_id, user)
    url = (body.url or "").strip() or (saved.url if saved else "")
    if len(url) < 3:
        raise _err(422, "url_required", "Bir YouTube linki yapıştır ya da kayıtlı listeden seç.")
    subject_id = body.subject_id if body.subject_id is not None else (saved.subject_id if saved else None)
    subject = _subject_accessible(db, subject_id or None, user)
    try:
        data = yt.fetch(url)
    except yt.YouTubeError as e:
        raise _yt_http(e)
    source = _upsert_source(db, user, url, data, subject.id if subject else None)
    # Tekrar kontrolü LİSTE İÇİNDE: başka listede de olan video bu listeyi eksik bırakmasın
    existing = {
        r[0] for r in db.query(VideoBasketItem.youtube_id)
        .filter(VideoBasketItem.student_id == student.id,
                VideoBasketItem.source_id == source.id).all()
    }
    fresh = [v for v in data.videos if v.youtube_id not in existing]
    skipped = len(data.videos) - len(fresh)
    if not fresh:
        db.commit()
        return MutationResponse[VideoImportResult](
            data=VideoImportResult(added=0, skipped_existing=skipped, groups=0,
                                   playlist_title=data.playlist_title, truncated=data.truncated,
                                   source_id=source.id),
            invalidate=[_basket_key(user.id, student.id), _sources_key(user.id)],
        )
    topics: list[Topic] = []
    if subject is not None:
        topics = leaf_topics_for_student(db, student, user.id, [subject.id]).by_subject.get(subject.id, [])
    token = secrets.token_hex(4)
    segs = seg.segment([seg.SegVideo(v.youtube_id, v.title) for v in fresh], topics,
                       batch_token=token, use_ai=bool(topics))
    by_id = {v.youtube_id: v for v in fresh}
    base = _next_order(db, student.id)
    for s in segs:
        v = by_id[s.key]
        db.add(VideoBasketItem(
            student_id=student.id, coach_id=user.id, youtube_id=v.youtube_id,
            title=(v.title or "Video")[:300], channel_title=(v.channel_title or None),
            duration_sec=v.duration_sec, playlist_id=data.playlist_id,
            playlist_title=(data.playlist_title or None),
            subject_id=subject.id if subject else None, topic_id=s.topic_id,
            group_key=s.group_key, group_label=s.group_label[:255], role=s.role,
            order=base + s.order, source_id=source.id,
        ))
    db.commit()
    gkeys = {s.group_key for s in segs}
    unmatched = len({s.group_key for s in segs if s.topic_id is None and s.role != "diger"})
    return MutationResponse[VideoImportResult](
        data=VideoImportResult(added=len(segs), skipped_existing=skipped, groups=len(gkeys),
                               playlist_title=data.playlist_title, truncated=data.truncated,
                               unmatched_groups=unmatched, source_id=source.id),
        invalidate=[_basket_key(user.id, student.id), _sources_key(user.id)],
    )


# ---------------------------------------------------------------- düzenleme


@router.post("/video-basket/items/{item_id}", response_model=MutationResponse[dict])
def patch_video(item_id: int, body: VideoItemPatchBody,
                user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    it = _owned_item(db, item_id, user)
    if body.role is not None:
        if body.role not in VIDEO_ROLES:
            raise _err(422, "role_invalid", "Geçersiz video rolü.")
        it.role = body.role
    if body.group_key is not None:
        if body.group_key == "new":
            it.group_key = f"{secrets.token_hex(4)}:v{it.id}"
            it.group_label = seg.clean_label(it.title)[:255]
            it.topic_id = None
        else:
            ref = (db.query(VideoBasketItem)
                   .filter(VideoBasketItem.student_id == it.student_id,
                           VideoBasketItem.group_key == body.group_key).first())
            if ref is None:
                raise _err(404, "group_not_found", "Grup bulunamadı.")
            it.group_key, it.group_label = ref.group_key, ref.group_label
            it.topic_id, it.subject_id = ref.topic_id, ref.subject_id
    db.commit()
    return MutationResponse[dict](data={"id": it.id}, invalidate=[_basket_key(user.id, it.student_id)])


@router.post("/students/{student_id}/video-basket/groups", response_model=MutationResponse[dict])
def patch_group(student_id: int, body: VideoGroupPatchBody,
                user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    _get_owned_student(db, student_id, user.id)
    rows = (db.query(VideoBasketItem)
            .filter(VideoBasketItem.student_id == student_id,
                    VideoBasketItem.group_key == body.group_key).all())
    if not rows:
        raise _err(404, "group_not_found", "Grup bulunamadı.")
    subject_id = body.subject_id if body.subject_id is not None else rows[0].subject_id
    if body.subject_id is not None:
        _subject_accessible(db, body.subject_id, user)
    topic: Topic | None = None
    if body.topic_id:
        topic = db.get(Topic, body.topic_id)
        if topic is None or not (topic.is_builtin or topic.teacher_id == user.id):
            raise _err(422, "topic_invalid", "Konu bulunamadı.")
        subject_id = topic.subject_id
    label = (body.label or "").strip() or (topic.name if topic else None)
    for r in rows:
        if label:
            r.group_label = label[:255]
        if body.topic_id is not None:
            r.topic_id = topic.id if topic else None
        r.subject_id = subject_id
    db.flush()
    for tid in {r.task_id for r in rows if r.task_id}:
        t = db.get(Task, tid)
        if t is not None:
            _refresh_task(db, t)
    db.commit()
    return MutationResponse[dict](data={"updated": len(rows)},
                                  invalidate=[_basket_key(user.id, student_id)])


@router.post("/students/{student_id}/video-basket/reorder", response_model=MutationResponse[dict])
def reorder_videos(student_id: int, body: VideoReorderBody,
                   user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    _get_owned_student(db, student_id, user.id)
    rows = {r.id: r for r in db.query(VideoBasketItem).filter(
        VideoBasketItem.student_id == student_id, VideoBasketItem.id.in_(body.item_ids))}
    if len(rows) != len(set(body.item_ids)):
        raise _err(404, "video_not_found", "Video bulunamadı.")
    base = min(r.order for r in rows.values())
    for i, iid in enumerate(body.item_ids):
        rows[iid].order = base + i
    db.commit()
    return MutationResponse[dict](data={"ok": True}, invalidate=[_basket_key(user.id, student_id)])


@router.delete("/video-basket/items/{item_id}", response_model=MutationResponse[dict])
def delete_video(item_id: int, user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    it = _owned_item(db, item_id, user)
    sid = it.student_id
    inv = [_basket_key(user.id, sid)]
    if it.task is not None:
        inv += _invalidate_for_task(it.task, user.id)
        _detach(db, it)
    db.delete(it)
    db.commit()
    return MutationResponse[dict](data={"deleted": 1}, invalidate=list(dict.fromkeys(inv)))


@router.post("/students/{student_id}/video-basket/groups/delete", response_model=MutationResponse[dict])
def delete_group(student_id: int, body: VideoGroupKeyBody,
                 user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Grubun SEPETTEKİ videolarını sil; programa konmuş olanlar kalır."""
    _get_owned_student(db, student_id, user.id)
    n = (db.query(VideoBasketItem)
         .filter(VideoBasketItem.student_id == student_id,
                 VideoBasketItem.group_key == body.group_key,
                 VideoBasketItem.task_id.is_(None))
         .delete(synchronize_session=False))
    db.commit()
    return MutationResponse[dict](data={"deleted": n}, invalidate=[_basket_key(user.id, student_id)])


# ---------------------------------------------------------------- programa koyma


@router.post("/students/{student_id}/video-basket/place",
             response_model=MutationResponse[VideoPlaceResult])
def place_videos(student_id: int, body: VideoPlaceBody,
                 user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Seçili videoları bir güne koy. Aynı gün + aynı konu grubu → tek görev.
    Zaten programdaki video TAŞINIR (eski görevinden çıkar)."""
    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    d = _parse_iso_date(body.date)
    period = _validate_period(body.period)
    rows = {r.id: r for r in db.query(VideoBasketItem).filter(
        VideoBasketItem.student_id == student.id, VideoBasketItem.id.in_(body.item_ids))}
    if len(rows) != len(set(body.item_ids)):
        raise _err(404, "video_not_found", "Video bulunamadı.")
    ordered = sorted(rows.values(), key=lambda r: (r.order, r.id))

    inv: list[str] = [_basket_key(user.id, student.id)]
    for r in ordered:  # taşınan videolar önce eski görevinden çıkar
        if r.task_id is not None:
            if r.task and r.task.date == d:
                continue
            old = r.task
            _detach(db, r)
            if old is not None:
                inv += _invalidate_for_task(old, user.id)
    db.flush()

    by_group: dict[str, list[VideoBasketItem]] = {}
    for r in ordered:
        if r.task_id is None:
            by_group.setdefault(r.group_key, []).append(r)

    touched: list[Task] = []
    for gkey, vids in by_group.items():
        task = (
            db.query(Task).join(VideoBasketItem, VideoBasketItem.task_id == Task.id)
            .filter(Task.student_id == student.id, Task.date == d,
                    VideoBasketItem.group_key == gkey,
                    Task.status != TaskStatus.COMPLETED)
            .first()
        )
        if task is None:
            subj = db.get(Subject, vids[0].subject_id) if vids[0].subject_id else None
            payload = TaskCreateBody(
                date=d.isoformat(), type="video",
                title=_task_title(subj.name if subj else None, vids[0].group_label, vids),
                period=period, is_draft=body.is_draft, link_url=vids[0].url, items=[],
            )
            task = _create_task_with_items(db, student=student, payload=payload)
            db.flush()
        for v in vids:
            v.task_id = task.id
        db.flush()
        _refresh_task(db, task)
        touched.append(task)
    db.commit()

    minutes = _day_minutes(db, student.id, d)
    warnings: list[str] = []
    if minutes > DAY_WARN_MINUTES:
        warnings.append(
            f"{d.strftime('%d.%m')} günü toplam video süresi {minutes} dk "
            f"({DAY_WARN_MINUTES} dk'yı geçti)."
        )
    for t in touched:
        inv += _invalidate_for_task(t, user.id)
    return MutationResponse[VideoPlaceResult](
        data=VideoPlaceResult(task_ids=[t.id for t in touched], day_minutes=minutes),
        invalidate=list(dict.fromkeys(inv)), warnings=warnings,
    )


@router.post("/video-basket/items/{item_id}/unplace", response_model=MutationResponse[dict])
def unplace_video(item_id: int, user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    it = _owned_item(db, item_id, user)
    if it.task_id is None:
        return MutationResponse[dict](data={"ok": True}, invalidate=[])
    old = it.task
    inv = [_basket_key(user.id, it.student_id)] + (_invalidate_for_task(old, user.id) if old else [])
    _detach(db, it)
    db.commit()
    return MutationResponse[dict](data={"ok": True}, invalidate=list(dict.fromkeys(inv)))


# ---------------------------------------------------------------- kopyala


@router.post("/students/{student_id}/video-basket/copy", response_model=MutationResponse[VideoCopyResult])
def copy_videos(student_id: int, body: VideoCopyBody,
                user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    _get_owned_student(db, student_id, user.id)
    target = _get_owned_student(db, body.target_student_id, user.id)
    if target.id == student_id:
        raise _err(422, "same_student", "Aynı öğrenciye kopyalanamaz.")
    q = db.query(VideoBasketItem).filter(VideoBasketItem.student_id == student_id)
    if body.group_keys:
        q = q.filter(VideoBasketItem.group_key.in_(body.group_keys))
    src = q.order_by(VideoBasketItem.order, VideoBasketItem.id).all()
    have = {(r[0], r[1]) for r in db.query(VideoBasketItem.youtube_id, VideoBasketItem.source_id)
            .filter(VideoBasketItem.student_id == target.id).all()}
    token = secrets.token_hex(4)
    base = _next_order(db, target.id)
    added = 0
    for i, s in enumerate(src):
        if (s.youtube_id, s.source_id) in have:
            continue
        have.add((s.youtube_id, s.source_id))
        db.add(VideoBasketItem(
            student_id=target.id, coach_id=user.id, youtube_id=s.youtube_id, title=s.title,
            channel_title=s.channel_title, duration_sec=s.duration_sec,
            playlist_id=s.playlist_id, playlist_title=s.playlist_title,
            subject_id=s.subject_id, topic_id=s.topic_id,
            group_key=f"{token}:{s.group_key.split(':', 1)[-1]}"[:64],
            group_label=s.group_label, role=s.role, order=base + i, source_id=s.source_id,
        ))
        added += 1
    db.commit()
    return MutationResponse[VideoCopyResult](
        data=VideoCopyResult(added=added, skipped_existing=len(src) - added),
        invalidate=[_basket_key(user.id, target.id)],
    )



# ---------------------------------------------------------------- kayıtlı listeler


@router.get("/video-sources", response_model=list[VideoSourceOut])
def list_sources(student_id: int | None = None, user: User = Depends(_require_teacher),
                 db: Session = Depends(get_db)):
    if student_id is not None:
        _get_owned_student(db, student_id, user.id)
    return _source_rows(db, user.id, student_id)


@router.post("/video-sources/{source_id}", response_model=MutationResponse[dict])
def patch_source(source_id: int, body: VideoSourcePatchBody,
                 user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Kayıtlı listenin adını / dersini düzenle (sepetteki videolara dokunmaz)."""
    src = _owned_source(db, source_id, user)
    if body.label is not None:
        src.label = body.label.strip()[:200] or None
    if body.subject_id is not None:
        src.subject_id = _subject_accessible(db, body.subject_id, user).id if body.subject_id else None
    db.commit()
    return MutationResponse[dict](data={"id": src.id},
                                  invalidate=[_sources_key(user.id), f"teacher:{user.id}:students"])


@router.post("/video-sources/{source_id}/delete", response_model=MutationResponse[dict])
def delete_source(source_id: int, body: VideoSourceDeleteBody,
                  user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Kayıtlı listeyi sil. İstenirse bu öğrencinin sepetinde BEKLEYEN videoları
    da silinir; programa konmuş videolar ve görevler hiçbir durumda silinmez."""
    src = _owned_source(db, source_id, user)
    removed = 0
    if body.remove_waiting and body.student_id is not None:
        _get_owned_student(db, body.student_id, user.id)
        removed = (db.query(VideoBasketItem)
                   .filter(VideoBasketItem.student_id == body.student_id,
                           VideoBasketItem.source_id == src.id,
                           VideoBasketItem.task_id.is_(None))
                   .delete(synchronize_session=False))
    db.query(VideoBasketItem).filter(VideoBasketItem.source_id == src.id).update(
        {VideoBasketItem.source_id: None}, synchronize_session=False)
    db.delete(src)
    db.commit()
    return MutationResponse[dict](data={"deleted": 1, "removed_videos": removed},
                                  invalidate=[_sources_key(user.id), f"teacher:{user.id}:students"])
