"""Question 和 UserAnswer 的 CRUD 操作。"""

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
    """创建或更新题目的用户答案，非填空题自动判分。"""
    result = await db.execute(
        select(UserAnswer).where(UserAnswer.question_id == question.id)
    )
    existing: UserAnswer | None = result.scalar_one_or_none()

    is_correct: bool | None = None
    if question.type != "fill":
        if raw_answer is None or raw_answer == "" or raw_answer == []:
            # Unanswered choice/multi/sort/judge is explicitly marked as wrong
            is_correct = False
        elif question.answer is not None:
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
# 内部评分辅助函数
# ---------------------------------------------------------------------------


def _grade(q_type: str, correct: Any, given: Any) -> bool:
    """自动批改答案。如果正确则返回 True。"""
    if q_type in ("choice", "judge"):
        return str(correct).strip().lower() == str(given).strip().lower()

    if q_type == "multi":
        # 两者都是列表；与顺序无关
        if not isinstance(correct, list) or not isinstance(given, list):
            return False
        return sorted(str(x).strip().lower() for x in correct) == sorted(
            str(x).strip().lower() for x in given
        )

    if q_type == "sort":
        # 两者都是列表；与顺序相关
        if not isinstance(correct, list) or not isinstance(given, list):
            return False
        return [str(x).strip().lower() for x in correct] == [
            str(x).strip().lower() for x in given
        ]

    return False
