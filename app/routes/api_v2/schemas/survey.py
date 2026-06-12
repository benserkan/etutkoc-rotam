"""Anket sistemi Pydantic şemaları (Faz 1)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Katalog ---

class SurveyTemplateBrief(BaseModel):
    id: int
    code: str
    title: str
    description: str = ""
    category: str
    category_label: str
    scoring_type: str
    question_count: int = 0
    estimated_minutes: int = 10
    source_attribution: str = ""


class SurveyCatalogResponse(BaseModel):
    items: list[SurveyTemplateBrief]
    categories: dict[str, str]  # key → TR etiket


# --- Sorular / doldurma ---

class SurveyQuestionModel(BaseModel):
    id: int
    order_no: int
    text: str
    qtype: str
    dimension_key: str | None = None
    options: list[dict] = Field(default_factory=list)


# --- Sonuç ---

class SurveyDimensionScore(BaseModel):
    key: str
    label: str
    description: str = ""
    score_pct: float
    level: str
    level_label: str
    high_is_good: bool = True
    comment: str = ""


class SurveyQualitativeBlock(BaseModel):
    key: str
    label: str
    description: str = ""
    entries: list[dict] = Field(default_factory=list)


class SurveyResultModel(BaseModel):
    scoring_type: str
    dimensions: list[SurveyDimensionScore] = Field(default_factory=list)
    top_dimensions: list[str] = Field(default_factory=list)
    qualitative: list[SurveyQualitativeBlock] = Field(default_factory=list)
    open_answers: list[dict] = Field(default_factory=list)
    report_note: str = ""
    source_attribution: str = ""
    disclaimer: str


# --- Atamalar ---

class SurveyAssignmentRow(BaseModel):
    id: int
    template: SurveyTemplateBrief
    status: str
    status_label: str
    note: str = ""
    assigned_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    teacher_name: str | None = None
    student_name: str | None = None
    answered_count: int = 0


class SurveyAssignmentDetail(BaseModel):
    assignment: SurveyAssignmentRow
    result: SurveyResultModel | None = None


# --- Koç yüzeyi ---

class TeacherStudentSurveysResponse(BaseModel):
    assignments: list[SurveyAssignmentRow]
    catalog: list[SurveyTemplateBrief]
    categories: dict[str, str]


class SurveyAssignBody(BaseModel):
    template_id: int
    note: str = Field(default="", max_length=500)


class SurveyAssignResult(BaseModel):
    ok: bool = True
    assignment_id: int


class SurveyCancelResult(BaseModel):
    ok: bool = True


# --- AI Kariyer Sentezi ---

class CareerSuggestionModel(BaseModel):
    title: str
    field: str = ""
    why: str = ""
    example_departments: list[str] = Field(default_factory=list)


class CareerSynthesisModel(BaseModel):
    summary: str
    career_suggestions: list[CareerSuggestionModel] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    agenda: list[str] = Field(default_factory=list)
    watch_outs: list[str] = Field(default_factory=list)
    based_on_surveys: list[str] = Field(default_factory=list)  # anket başlıkları
    exam_count: int = 0
    generated_at: datetime | None = None


class CareerSynthesisCacheResponse(BaseModel):
    insight: CareerSynthesisModel | None = None
    is_stale: bool = False
    # Üretim için zorunlu anketler tamam mı; eksikse hangileri (başlıklar)
    ready: bool = False
    missing_surveys: list[str] = Field(default_factory=list)
    disclaimer: str


# --- Öğrenci yüzeyi ---

class StudentSurveysResponse(BaseModel):
    pending: list[SurveyAssignmentRow]
    completed: list[SurveyAssignmentRow]


class StudentSurveyFillResponse(BaseModel):
    assignment: SurveyAssignmentRow
    questions: list[SurveyQuestionModel]
    answers: dict[str, Any] = Field(default_factory=dict)
    result: SurveyResultModel | None = None  # tamamlandıysa öğrenci de görür
    disclaimer: str


class StudentSurveyAnswersBody(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    complete: bool = False


class StudentSurveySaveResult(BaseModel):
    ok: bool = True
    status: str
    completed: bool = False
    missing_question_ids: list[int] = Field(default_factory=list)
