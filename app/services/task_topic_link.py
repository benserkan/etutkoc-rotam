"""Konusuz test görevlerini müfredat konusuna bağlama (2026-10-16).

Saha bulgusu (Açı Seçkin Kurs, rehber öğretmen #167): koç görevlerin %86'sını
"Diğer" etkinliği olarak, ders + konu + test sayısını SERBEST METNE yazarak verdi
("Matematik · TRİGO" + not "AÇI 2 TEST"). Sistem bunları etkinlik saydığı için
kurum tabloları (kohort/uyum/karne), müfredat ilerlemesi, konu performansı ve
analitik boş kaldı — oysa aynı görev "kaynaksız konu" kalemi (topic_id + N test)
olarak verilseydi hepsi dolardı.

Bu modül TEK MERKEZ:
  · `extract_test_count`  — metinden "N test" (notta da başlıkta da)
  · `suggest_topic`       — dersin konuları içinde kısa yazımı ("trigo",
    "ebob ekok", "hız ivme") konuya eşler; tema/ünite adı yazıldıysa o temanın
    ALT konularını seçenek olarak döner (görev yalnız alt konuya bağlanır)
  · `unlinked_test_tasks` — bir koçun konusuz test görevleri (+ öneriler)
  · `convert_task`        — görevi kaynaksız konu kalemine çevirir (tamamlanmışsa
    çözülen test olarak sayılır)

Deterministik, yapay zekâsız. Belirsizde ASLA kendi başına bağlamaz — öneri
döner, karar koçta (kullanıcı kuralı: konu eşleşmesi koç onaylı).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Task, TaskBookItem, Topic, User
from app.models.curriculum import Subject
from app.models.task import TaskStatus, TaskType
from app.services.curriculum_mapping import normalize

# "2 test", "2test", "3 adet test", "2 yaprak test" — notta ya da başlıkta
_COUNT_RE = re.compile(r"(\d{1,2})\s*(?:adet\s*)?(?:yaprak\s*)?tes(?:t|tler)?\b", re.IGNORECASE)
MAX_COUNT = 30

# Konu eşleştirmesinde anlam taşımayan sözcükler (başlıkta sık geçen gürültü)
_NOISE = {
    "ve", "ile", "test", "testi", "testler", "tes", "adet", "yaprak", "konu", "konusu",
    "tekrar", "tekrari", "odev", "odevin", "odevi", "calis", "calisma", "soru", "sorular",
    "video", "izle", "not", "al", "unite", "tema", "bolum", "genel", "karma", "deneme",
}
# Kısaltma/akronim köprüsü: koçun yazımı → konu adında aranacak sözcükler
_ABBREV: dict[str, tuple[str, ...]] = {
    "ebob": ("obeb", "okek", "ebob", "ekok", "carpanlar"),
    "ebok": ("obeb", "okek", "ebob", "ekok", "carpanlar"),
    "ekok": ("obeb", "okek", "ebob", "ekok", "carpanlar"),
    "obeb": ("obeb", "okek", "ebob", "ekok", "carpanlar"),
    "okek": ("obeb", "okek", "ebob", "ekok", "carpanlar"),
    "trigo": ("trigonometri", "trigonometrik"),
    "trig": ("trigonometri", "trigonometrik"),
    "tean": ("teen",),
}
MIN_PREFIX = 3


def extract_test_count(*texts: str | None) -> int | None:
    for txt in texts:
        if not txt:
            continue
        m = _COUNT_RE.search(txt)
        if m:
            n = int(m.group(1))
            if 1 <= n <= MAX_COUNT:
                return n
    return None


def split_title(title: str | None) -> tuple[str, str]:
    """'Matematik · TRİGO' → ('Matematik', 'TRİGO'). Ayraç yoksa ders boş."""
    t = (title or "").strip()
    for sep in (" · ", "·", " - "):
        if sep in t:
            a, b = t.split(sep, 1)
            return a.strip(), b.strip()
    return "", t


def _tokens(text: str) -> list[str]:
    return [w for w in normalize(text).split() if w and w not in _NOISE and not w.isdigit()]


def _tok_match(q: str, w: str) -> bool:
    if q == w:
        return True
    if len(q) >= MIN_PREFIX and len(w) >= MIN_PREFIX and (w.startswith(q) or q.startswith(w)):
        return True
    return w in _ABBREV.get(q, ())


@dataclass
class TopicOption:
    topic_id: int
    name: str
    grade_level: int | None
    parent_name: str | None = None
    subject_name: str | None = None   # yalnız dersin sınav karşılığından gelirse dolu


@dataclass
class TopicSuggestion:
    subject_id: int | None
    subject_name: str | None
    test_count: int | None
    topic: TopicOption | None = None          # tek ve kesin öneri (koç yine onaylar)
    confident: bool = False
    options: list[TopicOption] = field(default_factory=list)
    reason: str = ""


def _subject_topics(db: Session, student: User, subject_id: int) -> tuple[list[Topic], set[int], dict[int, Topic]]:
    """Dersin konuları (builtin + koçun kendi), öğrencinin sınıfına kadar (kümülatif)."""
    topics = (
        db.query(Topic)
        .filter(Topic.subject_id == subject_id,
                or_(Topic.is_builtin.is_(True), Topic.teacher_id == student.teacher_id))
        .order_by(Topic.order, Topic.id)
        .all()
    )
    max_grade = 99 if (student.is_graduate or student.grade_level is None) else student.grade_level
    topics = [t for t in topics if t.grade_level is None or t.grade_level <= max_grade]
    parents = {t.parent_id for t in topics if t.parent_id is not None}
    by_id = {t.id: t for t in topics}
    return topics, parents, by_id


def _opt(t: Topic, by_id: dict[int, Topic], subject_name: str | None = None) -> TopicOption:
    p = by_id.get(t.parent_id) if t.parent_id else None
    return TopicOption(topic_id=t.id, name=t.name, grade_level=t.grade_level,
                       parent_name=p.name if p else None, subject_name=subject_name)


def _score(topics: list[Topic], q: list[str], own: int | None) -> list[tuple[float, Topic]]:
    scored: list[tuple[float, Topic]] = []
    for t in topics:
        w = _tokens(re.sub(r"^\d+\.\s*(tema|ünite|unite|öğrenme alanı)\s*:\s*", "", t.name, flags=re.I))
        if not w:
            continue
        q_hit = sum(1 for a in q if any(_tok_match(a, b) for b in w))
        if q_hit == 0:
            continue
        w_hit = sum(1 for b in w if any(_tok_match(a, b) for a in q))
        score = 0.7 * q_hit / len(q) + 0.3 * w_hit / len(w)
        if own is not None and t.grade_level == own:
            score += 0.05
        scored.append((score, t))
    scored.sort(key=lambda x: (-x[0], x[1].order, x[1].id))
    return scored


def _dedupe(scored: list[tuple[float, Topic]]) -> list[tuple[float, Topic]]:
    """Aynı adlı konu birden çok sınıfta tekrar eder (Sözcükte Anlam 5-8) → en iyi skorlu kalır."""
    seen: set[str] = set()
    out = []
    for sc, t in scored:
        k = normalize(t.name)
        if k in seen:
            continue
        seen.add(k)
        out.append((sc, t))
    return out


def _exam_counterparts(db: Session, subject: Subject) -> list[Subject]:
    """Okul dersinin TYT karşılığı (Maarif Edebiyat'ta dil bilgisi yok → TYT Türkçe'de var)."""
    from app.services.curriculum_progress import _SCHOOL_EXAM_SYNONYMS

    if subject.curriculum_model is None:   # zaten sınav taksonomisi dersi
        return []
    bases = {subject.name} | _SCHOOL_EXAM_SYNONYMS.get(subject.name, set())
    names = {f"TYT {b}" for b in bases}
    return (db.query(Subject)
            .filter(Subject.is_builtin.is_(True), Subject.name.in_(names))
            .order_by(Subject.order, Subject.id).all())


def suggest_topic(db: Session, student: User, subject: Subject | None, text: str,
                  notes: str | None = None) -> TopicSuggestion:
    """Dersin konuları içinde `text`e en uyan konu(lar). Kesin değilse seçenek döner."""
    count = extract_test_count(notes, text)
    sug = TopicSuggestion(subject_id=subject.id if subject else None,
                          subject_name=subject.name if subject else None, test_count=count)
    if subject is None:
        sug.reason = "Ders anlaşılamadı."
        return sug
    topics, parents, by_id = _subject_topics(db, student, subject.id)
    leaves = [t for t in topics if t.id not in parents]
    q = _tokens(text)
    if not q:
        sug.reason = "Başlıkta konu adı yok — listeden seç."
        return sug

    own = student.grade_level
    scored = _dedupe(_score(topics, q, own))
    if not scored:
        # Okul dersinde yok → sınav karşılığına bak (yalnız seçenek; kesin sayılmaz)
        for ex in _exam_counterparts(db, subject):
            ex_topics, ex_parents, ex_by_id = _subject_topics(db, student, ex.id)
            ex_scored = [(sc, t) for sc, t in _dedupe(_score(ex_topics, q, own)) if t.id not in ex_parents]
            if ex_scored:
                sug.options = [_opt(t, ex_by_id, ex.name) for _, t in ex_scored[:6]]
                sug.reason = f"{subject.name} müfredatında yok — {ex.name} konularından seç."
                return sug
    if not scored:
        sug.reason = "Konu bulunamadı — listeden seç."
        return sug
    best_score, best = scored[0]

    # Tema/ünite adı yazılmış → alt konularını seçenek ver (görev yalnız alt konuya bağlanır)
    if best.id in parents:
        kids = [t for t in leaves if t.parent_id == best.id]
        sug.options = [_opt(t, by_id) for t in kids]
        sug.reason = f"'{best.name}' bir tema/ünite — hangi alt konu çalışıldı?"
        return sug

    leaf_scored = [(s, t) for s, t in scored if t.id not in parents]
    sug.options = [_opt(t, by_id) for _, t in leaf_scored[:6]]
    full = all(any(_tok_match(a, b) for b in _tokens(best.name)) for a in q)
    runner = leaf_scored[1][0] if len(leaf_scored) > 1 else 0.0
    sug.topic = _opt(best, by_id)
    sug.confident = full and best_score - runner >= 0.1
    sug.reason = "" if sug.confident else "Tahmin — doğru konuyu seç."
    return sug


def resolve_subject(db: Session, student: User, name: str) -> Subject | None:
    """Başlıktaki ders adı → öğrencinin göreceği ders (görev formunun listesiyle aynı kural)."""
    if not name:
        return None
    from app.services.curriculum_progress import exam_subject_visible_for_track

    key = normalize(name)
    cm = student.effective_curriculum_model
    rows = (
        db.query(Subject)
        .filter(or_(Subject.is_builtin.is_(True), Subject.teacher_id == student.teacher_id))
        .order_by(Subject.order, Subject.id)
        .all()
    )
    for s in rows:
        if normalize(s.name) != key:
            continue
        if not s.covers_grade(student.grade_level, is_graduate=student.is_graduate):
            continue
        if cm and s.curriculum_model and s.curriculum_model != cm:
            continue
        if not exam_subject_visible_for_track(s, student.track):
            continue
        return s
    return None


# ------------------------------------------------------------- konusuz test görevleri

LINKABLE_TYPES = (TaskType.OTHER, TaskType.TEKRAR, TaskType.OZET)


def is_unlinked_test_task(task: Task, *, itemless: bool | None = None) -> bool:
    """Kalemsiz, bloksuz, etkinlik tipli ve metninde 'N test' geçen görev.

    `itemless=True`: çağıran kalemsizliği SQL'de süzdü (book_items yüklenmez, N+1 yok)."""
    if task.work_block_id is not None:
        return False
    if itemless is None and task.book_items:
        return False
    if task.type not in LINKABLE_TYPES:
        return False
    _, detail = split_title(task.title)
    return extract_test_count(task.notes, detail, task.title) is not None


@dataclass
class UnlinkedTask:
    task: Task
    student: User
    subject: Subject | None
    detail: str
    suggestion: TopicSuggestion


def unlinked_test_tasks(db: Session, students: list[User], limit: int = 400) -> list[UnlinkedTask]:
    if not students:
        return []
    by_id = {s.id: s for s in students}
    tasks = (
        db.query(Task)
        .filter(Task.student_id.in_(list(by_id)), Task.type.in_(LINKABLE_TYPES),
                Task.work_block_id.is_(None), ~Task.book_items.any())
        .order_by(Task.date.desc(), Task.id)
        .all()
    )
    out: list[UnlinkedTask] = []
    subj_cache: dict[tuple[int, str], Subject | None] = {}
    for t in tasks:
        if not is_unlinked_test_task(t, itemless=True):
            continue
        st = by_id[t.student_id]
        sname, detail = split_title(t.title)
        ck = (st.id, sname)
        if ck not in subj_cache:
            subj_cache[ck] = resolve_subject(db, st, sname)
        subj = subj_cache[ck]
        out.append(UnlinkedTask(task=t, student=st, subject=subj, detail=detail,
                                suggestion=suggest_topic(db, st, subj, detail, t.notes)))
        if len(out) >= limit:
            break
    return out


def count_unlinked(db: Session, student_ids: list[int]) -> dict[int, int]:
    """Öğrenci başına konusuz test görevi sayısı (kurum/koç uyarı bantları için; öneri hesaplamaz)."""
    if not student_ids:
        return {}
    tasks = (
        db.query(Task)
        .filter(Task.student_id.in_(student_ids), Task.type.in_(LINKABLE_TYPES),
                Task.work_block_id.is_(None), ~Task.book_items.any())
        .all()
    )
    out: dict[int, int] = {}
    for t in tasks:
        if is_unlinked_test_task(t, itemless=True):
            out[t.student_id] = out.get(t.student_id, 0) + 1
    return out


class LinkError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def convert_task(db: Session, task: Task, student: User, topic_id: int, planned_count: int) -> TaskBookItem:
    """Konusuz görevi kaynaksız konu kalemli TEST görevine çevirir.

    · Görev, tarih, başlık, not, periyot, taslak durumu AYNEN kalır (koçun yazdığı başlık korunur).
    · Tamamlanmış görev → kalem çözülen = planlanan (öğrenci görevi bitirdi demişti).
    · Rezerv/kapasite yok (kaynaksız kalem). Öğrencinin girdiği 'çözdüğüm soru' alanı silinmez.
    """
    if task.book_items:
        raise LinkError("already_linked", "Bu görev zaten kaleme bağlı.")
    if task.work_block_id is not None:
        raise LinkError("block_task", "İş bloğu görevi dönüştürülemez.")
    if not (1 <= int(planned_count) <= MAX_COUNT):
        raise LinkError("bad_count", f"Test sayısı 1–{MAX_COUNT} arası olmalı.")
    topic = db.get(Topic, topic_id)
    if topic is None or not (topic.is_builtin or topic.teacher_id == student.teacher_id):
        raise LinkError("topic_not_found", "Seçilen müfredat konusu bulunamadı.")
    if db.query(Topic.id).filter(Topic.parent_id == topic.id).first() is not None:
        raise LinkError("topic_is_theme", "Tema/ünite başlığına değil, alt konuya bağla.")
    done = task.status == TaskStatus.COMPLETED
    item = TaskBookItem(
        task_id=task.id, book_id=None, book_section_id=None, topic_id=topic.id,
        label=topic.name, planned_count=int(planned_count),
        completed_count=int(planned_count) if done else 0,
    )
    db.add(item)
    task.type = TaskType.TEST
    db.flush()
    return item
