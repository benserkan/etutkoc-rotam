"""Deneme analizi Faz 2 şemaları — gelişim raporu, hedef, gündem kuyruğu, paylaşım."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProgressSectionOption(BaseModel):
    value: str                 # seri anahtarı: "lgs" (genel) | "lgs~matematik" (branş)
    label: str
    count: int
    kind: str = "genel"        # "genel" | "brans"
    section: str | None = None  # gerçek sınav türü


class ProgressExamPoint(BaseModel):
    id: int
    title: str
    exam_date: str
    net: float
    correct: int
    wrong: int
    blank: int
    questions: int


class ProgressStats(BaseModel):
    count: int
    first_net: float
    last_net: float
    best_net: float
    avg_net: float
    avg_last3: float
    change: float
    slope: float | None = None
    last_date: str
    days_since_last: int


class ProgressSubject(BaseModel):
    name: str
    nets: list[float | None]
    first: float | None = None
    last: float | None = None
    avg: float | None = None
    change: float | None = None
    slope: float | None = None
    last_correct: int | None = None
    last_wrong: int | None = None
    last_blank: int | None = None
    target: float | None = None
    gap: float | None = None


class ProgressTarget(BaseModel):
    target_net: float
    target_date: str | None = None
    subjects: dict[str, float] = Field(default_factory=dict)
    note: str | None = None
    set_by_name: str | None = None
    updated_at: str | None = None
    basis: str | None = None
    basis_net: float | None = None
    gap: float | None = None
    progress_pct: float | None = None
    weeks_left: int | None = None
    exams_needed_at_pace: int | None = None
    per_week_needed: float | None = None


class ProgressComment(BaseModel):
    tone: str  # good | warn | info
    text: str


class ProgressAction(BaseModel):
    key: str
    kind: str
    priority: int
    title: str
    detail: str
    subject: str | None = None
    topic_id: int | None = None
    exam_id: int | None = None
    queued: bool = False


class ProgressOpportunity(BaseModel):
    topic_id: int
    topic_name: str
    subject_name: str
    wrong: int
    blank: int
    total: int
    net_gain_per_exam: float


class ExamProgressResponse(BaseModel):
    section: str | None = None
    section_label: str | None = None
    section_options: list[ProgressSectionOption] = Field(default_factory=list)
    series: str | None = None          # seçili seri (genel/branş) — 2026-10-06
    is_branch: bool = False
    target_allowed: bool = True        # hedef net yalnız genel seride
    student_name: str | None = None
    generated_at: str
    exams: list[ProgressExamPoint] = Field(default_factory=list)
    stats: ProgressStats | None = None
    subjects: list[ProgressSubject] = Field(default_factory=list)
    target: ProgressTarget | None = None
    commentary: list[ProgressComment] = Field(default_factory=list)
    actions: list[ProgressAction] = Field(default_factory=list)
    opportunities: list[ProgressOpportunity] = Field(default_factory=list)


class ExamTargetBody(BaseModel):
    section: str
    target_net: float | None = None  # None → hedefi kaldır
    target_date: str | None = None
    subjects: dict[str, float | None] | None = None
    note: str | None = Field(default=None, max_length=300)


class ExamTargetsResponse(BaseModel):
    targets: dict[str, ProgressTarget] = Field(default_factory=dict)
    invalidate: list[str] = Field(default_factory=list)


class AgendaQueueItem(BaseModel):
    id: str
    key: str | None = None
    text: str
    source: str = "exam"
    exam_id: int | None = None
    created_at: str | None = None


class AgendaQueueAddItem(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    key: str | None = Field(default=None, max_length=80)
    source: str | None = None
    exam_id: int | None = None


class AgendaQueueAddBody(BaseModel):
    items: list[AgendaQueueAddItem] = Field(min_length=1, max_length=20)


class AgendaQueueIdsBody(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=50)


class AgendaQueueResponse(BaseModel):
    items: list[AgendaQueueItem] = Field(default_factory=list)
    added: int = 0
    invalidate: list[str] = Field(default_factory=list)


class ExamShareInfo(BaseModel):
    note: str | None = None
    shared_at: str
    first_shared_at: str | None = None
    shared_by_name: str | None = None


class ExamSharesResponse(BaseModel):
    shares: dict[str, ExamShareInfo] = Field(default_factory=dict)  # exam_id → paylaşım


class ExamShareBody(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
    notify: bool = True


class ExamShareResult(BaseModel):
    exam_id: int
    share: ExamShareInfo | None = None
    notified: bool = False
    invalidate: list[str] = Field(default_factory=list)


# ================================================================ Faz 3

class ExamAveragesBody(BaseModel):
    label: str | None = Field(default=None, max_length=60)
    total: float | None = None
    subjects: dict[str, float | None] | None = None


class ExamAveragesResult(BaseModel):
    exam_id: int
    averages: dict | None = None
    invalidate: list[str] = Field(default_factory=list)


class DistractorLetter(BaseModel):
    letter: str
    chosen: int
    key: int
    wrong_chosen: int
    chosen_pct: float
    key_pct: float


class DistractorQuestion(BaseModel):
    subject: str
    question_no: int | None = None
    topic: str | None = None
    correct_answer: str | None = None
    student_answer: str | None = None
    result: str
    peer_count: int
    peer_correct_pct: int
    top_wrong_option: str | None = None
    top_wrong_count: int = 0
    same_as_student: bool = False


class DistractorResponse(BaseModel):
    exam_id: int
    answered: int
    wrong_count: int
    letters: list[DistractorLetter]
    notes: list[str] = Field(default_factory=list)
    peer_count: int = 0
    peer_min: int = 2
    questions: list[DistractorQuestion] = Field(default_factory=list)


class ScoreItem(BaseModel):
    key: str
    label: str
    score: float
    max: int = 500
    based_on: list[int] = Field(default_factory=list)
    detail: str | None = None
    is_student_track: bool = False


class ScoreInput(BaseModel):
    id: int
    title: str
    exam_date: str
    section_label: str
    net: float
    karne_score: float | None = None


class ScoreCalibration(BaseModel):
    exam_id: int
    title: str
    exam_date: str
    karne_score: float
    estimate: float
    diff: float


class ScoreEstimateResponse(BaseModel):
    generated_at: str
    kind: str | None = None  # lgs | yks | None
    scores: list[ScoreItem] = Field(default_factory=list)
    inputs: list[ScoreInput] = Field(default_factory=list)
    calibration: list[ScoreCalibration] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str
