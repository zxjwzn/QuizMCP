"""CRUD operations for Question and UserAnswer."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Question, UserAnswer


async def count_questions_in_session(db: AsyncSession, session_id: str) -> int:
    result = await db.execute(
        select(Question).where(Question.session_id == session_id)
    )
    return len(result.scalars().all())


async def add_question(
    db: AsyncSession,
    session_id: str,
    type_: str,
    content: str,
    options: list[str] | None,
    answer: Any | None,
    explanation: str | None,
) -> Question:
    next_index = await count_questions_in_session(db, session_id)
    question = Question(
        session_id=session_id,
        order_index=next_index,
        type=type_,
        content=content,
        options=options,
        answer=answer,
        explanation=explanation,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question


async def get_question(db: AsyncSession, question_id: str) -> Question | None:
    return await db.get(Question, question_id)


async def upsert_answer(
    db: AsyncSession,
    question: Question,
    raw_answer: Any,
    time_spent_seconds: int,
) -> UserAnswer:
    """Create or update the user's answer for a question, auto-grading non-fill types."""
    existing: UserAnswer | None = await db.get(UserAnswer, question.id)

    is_correct: bool | None = None
    if question.type != "fill" and question.answer is not None:
        is_correct = _grade(question.type, question.answer, raw_answer)

    if existing is not None:
        existing.raw_answer = raw_answer
        existing.is_correct = is_correct
        existing.time_spent_seconds = time_spent_seconds
        await db.commit()
        await db.refresh(existing)
        return existing

    ua = UserAnswer(
        question_id=question.id,
        raw_answer=raw_answer,
        is_correct=is_correct,
        time_spent_seconds=time_spent_seconds,
    )
    db.add(ua)
    await db.commit()
    await db.refresh(ua)
    return ua


async def grade_fill(
    db: AsyncSession,
    question_id: str,
    is_correct: bool,
    comment: str | None,
) -> UserAnswer | None:
    result = await db.execute(
        select(UserAnswer).where(UserAnswer.question_id == question_id)
    )
    ua = result.scalar_one_or_none()
    if ua is None:
        return None
    ua.is_correct = is_correct
    ua.grade_comment = comment
    await db.commit()
    await db.refresh(ua)
    return ua


# ---------------------------------------------------------------------------
# Internal grading helpers
# ---------------------------------------------------------------------------


def _grade(q_type: str, correct: Any, given: Any) -> bool:
    """Auto-grade an answer. Returns True if correct."""
    if q_type in ("choice", "judge"):
        return str(correct).strip().lower() == str(given).strip().lower()

    if q_type == "multi":
        # Both are lists; order-insensitive
        if not isinstance(correct, list) or not isinstance(given, list):
            return False
        return sorted(str(x).strip().lower() for x in correct) == sorted(
            str(x).strip().lower() for x in given
        )

    if q_type == "sort":
        # Both are lists; order-sensitive
        if not isinstance(correct, list) or not isinstance(given, list):
            return False
        return [str(x).strip().lower() for x in correct] == [
            str(x).strip().lower() for x in given
        ]

    return False
