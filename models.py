"""SQLAlchemy ORM 模型。"""

import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from database import Base


def _new_id() -> str:
    # 8 bytes of entropy = 11 characters (base64url)
    return secrets.token_urlsafe(8)


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String, nullable=False)
    # "draft"（草稿） | "active"（进行中） | "finished"（已完成）
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

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # "choice"（单选） | "multi"（多选） | "judge"（判断） | "fill"（填空） | "sort"（排序）
    type: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    # JSON 格式: choice/multi/sort 为 list[str]，judge/fill 为 null
    options: Mapped[Any] = mapped_column(JSON, nullable=True)
    # JSON 格式: choice/judge 为 str，multi/sort 为 list[str]，fill 为 null（由 LLM 判分）
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

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    question_id: Mapped[str] = mapped_column(
        String, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # JSON 格式: 匹配题目类型的任意结构
    raw_answer: Mapped[Any] = mapped_column(JSON, nullable=False)
    # 判分前为 null（非填空题自动判分，填空题由 LLM 判分）
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    grade_comment: Mapped[str | None] = mapped_column(String, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # 从首次打开到提交所花费的秒数
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    question: Mapped["Question"] = relationship("Question", back_populates="user_answer")
