"""Konusuz test görevlerini konuya bağlama şemaları (2026-10-16)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TopicOptionOut(BaseModel):
    topic_id: int
    name: str
    grade_level: int | None = None
    parent_name: str | None = None
    subject_name: str | None = None


class TopicSuggestionOut(BaseModel):
    subject_id: int | None = None
    subject_name: str | None = None
    test_count: int | None = None
    topic: TopicOptionOut | None = None
    confident: bool = False
    options: list[TopicOptionOut] = []
    reason: str = ""


class TopicSuggestBody(BaseModel):
    subject_id: int
    text: str = Field(default="", max_length=300)
    notes: str | None = Field(default=None, max_length=300)


class SubjectTopicsResponse(BaseModel):
    subject_id: int
    subject_name: str
    topics: list[TopicOptionOut]


class UnlinkedTaskOut(BaseModel):
    task_id: int
    student_id: int
    student_name: str
    date: str
    title: str
    notes: str | None = None
    status: str
    is_draft: bool
    subject_id: int | None = None
    subject_name: str | None = None
    suggestion: TopicSuggestionOut


class UnlinkedTasksResponse(BaseModel):
    total: int
    completed: int
    students: int
    items: list[UnlinkedTaskOut]


class ConvertItemIn(BaseModel):
    task_id: int
    topic_id: int
    planned_count: int = Field(ge=1, le=30)


class ConvertBody(BaseModel):
    items: list[ConvertItemIn] = Field(min_length=1, max_length=400)


class ConvertResultItem(BaseModel):
    task_id: int
    ok: bool
    code: str | None = None
    message: str | None = None


class ConvertResponse(BaseModel):
    converted: int
    failed: int
    results: list[ConvertResultItem]
