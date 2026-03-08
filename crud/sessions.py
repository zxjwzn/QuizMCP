"""QuizSession 的 CRUD 操作。"""

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
    session = await get_session(db, session_id)
    if session is None:
        return None
        
    if not session.questions:
        raise ValueError("Cannot finalize an empty session. Add at least one question first.")
        
    session.status = "active"
    session.finalized_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_stats(db: AsyncSession, session_id: str) -> SessionStats | None:
    """计算会话的答题统计信息。"""
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
            
            if ua.raw_answer is None or ua.raw_answer == "" or ua.raw_answer == []:
                unanswered += 1
            elif q.type == "fill" and ua.is_correct is None:
                fill_pending += 1
            elif ua.is_correct is True:
                correct += 1
            elif ua.is_correct is False:
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
    """返回已提交答案但尚未判分的填空题。"""
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


async def refresh_session_status(db: AsyncSession, session_id: str) -> None:
    """根据当前答题状态更新题组状态。

    状态转换说明:
      - active(活动) → pending(待判分) (答案已提交，有填空题等待 LLM 判分)
      - active(活动) → finished(已完成) (所有答案自动批改完毕，且无填空题待判分)
      - pending(待判分) → finished(已完成) (所有填空题均已完成批改)
    """
    session = await get_session(db, session_id)
    if session is None or session.status == "draft":
        return

    stats = await get_session_stats(db, session_id)
    if stats is None:
        return

    # 若所有题目都既无作答且会话状态为 active, 表示只打开了没有作答
    # 如果用户真的提交了空卷，前端会发送 bulk_submit。我们需要判断是正常 active 状态还是已经 submit 的状态
    # 但是因为所有提交都直接调用 refresh_session_status，所以在这里我们直接如果还没提交过，就返回
    # 然而，bulk_submit 调用时，意味着哪怕全空也应切换状态。
    # 怎么区分是从 get_session 调用还是 bulk_submit?
    # 不依赖 unanswered 的数量。只要进入 refresh，说明刚刚发生过了 submit 或 grade。
    # 但是，我们不需要拦截 unanswered == total 了，只要调用 refresh，必然是从 submit_bulk 或 grade 来的
    # 所以无论如何应该更新到 pending 或 finished。

    if stats.fill_pending > 0:
        new_status = "pending"
    else:
        new_status = "finished"

    raw_session = await db.get(QuizSession, session_id)
    if raw_session is not None and raw_session.status != new_status:
        raw_session.status = new_status
        await db.commit()

