"""CRUD operations for QuizSession."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Question, QuizSession, UserAnswer
from schemas import SessionStats


async def create_session(db: AsyncSession, title: str) -> QuizSession:
    session = QuizSession(title=title, status="draft")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: str) -> QuizSession | None:
    result = await db.execute(
        select(QuizSession)
        .where(QuizSession.id == session_id)
        .options(
            selectinload(QuizSession.questions).selectinload(Question.user_answer)
        )
    )
    return result.scalar_one_or_none()


async def list_sessions(db: AsyncSession) -> list[QuizSession]:
    result = await db.execute(
        select(QuizSession).order_by(QuizSession.created_at.desc())
    )
    return list(result.scalars().all())


async def finalize_session(db: AsyncSession, session_id: str) -> QuizSession | None:
    session = await db.get(QuizSession, session_id)
    if session is None:
        return None
    session.status = "active"
    session.finalized_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_stats(db: AsyncSession, session_id: str) -> SessionStats | None:
    """Compute answer statistics for a session."""
    session = await get_session(db, session_id)
    if session is None:
        return None

    total = len(session.questions)
    correct = 0
    wrong = 0
    unanswered = 0
    fill_pending = 0
    time_spent = 0

    for q in session.questions:
        ua: UserAnswer | None = q.user_answer
        if ua is None:
            unanswered += 1
        else:
            time_spent += ua.time_spent_seconds
            if q.type == "fill" and ua.is_correct is None:
                fill_pending += 1
            elif ua.is_correct is True:
                correct += 1
            else:
                wrong += 1

    return SessionStats(
        total=total,
        correct=correct,
        wrong=wrong,
        unanswered=unanswered,
        fill_pending=fill_pending,
        time_spent_seconds=time_spent,
    )


async def get_fill_pending(db: AsyncSession, session_id: str) -> list[dict[str, Any]]:
    """Return fill questions that have a submitted answer but not yet graded."""
    session = await get_session(db, session_id)
    if session is None:
        return []

    pending = []
    for q in session.questions:
        if q.type == "fill" and q.user_answer is not None and q.user_answer.is_correct is None:
            pending.append(
                {
                    "question_id": q.id,
                    "content": q.content,
                    "user_answer": q.user_answer.raw_answer,
                }
            )
    return pending
