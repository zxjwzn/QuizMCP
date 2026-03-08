"""Pydantic schemas for API request/response."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Question
# ---------------------------------------------------------------------------


class QuestionBase(BaseModel):
    type: str
    content: str
    options: list[str] | None = None
    answer: Any | None = None
    explanation: str | None = None


class QuestionCreate(QuestionBase):
    pass


class QuestionRead(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    order_index: int
    user_answer: "AnswerRead | None" = None


# ---------------------------------------------------------------------------
# UserAnswer
# ---------------------------------------------------------------------------


class AnswerSubmit(BaseModel):
    """Payload for submitting one answer."""

    question_id: str
    raw_answer: Any
    time_spent_seconds: int = 0


class BulkAnswerSubmit(BaseModel):
    """Payload for submitting all answers at once."""

    answers: list[AnswerSubmit]


class AnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question_id: str
    raw_answer: Any
    is_correct: bool | None
    grade_comment: str | None
    submitted_at: datetime
    time_spent_seconds: int


class GradeFillRequest(BaseModel):
    is_correct: bool
    comment: str | None = None


# ---------------------------------------------------------------------------
# QuizSession
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    title: str


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: str
    created_at: datetime
    finalized_at: datetime | None


class SessionStats(BaseModel):
    total: int
    correct: int
    wrong: int
    unanswered: int
    fill_pending: int
    time_spent_seconds: int


class SessionDetail(SessionRead):
    questions: list[QuestionRead]
    stats: SessionStats


class SessionList(BaseModel):
    sessions: list[SessionRead]
