"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    title: Mapped[str] = mapped_column(String, nullable=False)
    # "draft" | "active" | "finished"
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    questions: Mapped[list["Question"]] = relationship(
        "Question",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # "choice" | "multi" | "judge" | "fill" | "sort"
    type: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    # JSON: list[str] for choice/multi/sort, null for judge/fill
    options: Mapped[Any] = mapped_column(JSON, nullable=True)
    # JSON: str for choice/judge, list[str] for multi/sort, null for fill (graded by LLM)
    answer: Mapped[Any] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str | None] = mapped_column(String, nullable=True)

    session: Mapped["QuizSession"] = relationship("QuizSession", back_populates="questions")
    user_answer: Mapped["UserAnswer | None"] = relationship(
        "UserAnswer",
        back_populates="question",
        cascade="all, delete-orphan",
        uselist=False,
    )


class UserAnswer(Base):
    __tablename__ = "user_answers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    question_id: Mapped[str] = mapped_column(
        String, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # JSON: any structure matching the question type
    raw_answer: Mapped[Any] = mapped_column(JSON, nullable=False)
    # null until graded (auto for non-fill, LLM for fill)
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    grade_comment: Mapped[str | None] = mapped_column(String, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # seconds from first open to submission
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    question: Mapped["Question"] = relationship("Question", back_populates="user_answer")
