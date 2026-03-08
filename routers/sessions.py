"""题组路由 — 题组记录的 CRUD REST 端点。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import verify_token
from crud import questions as question_crud
from crud import sessions as session_crud
from database import get_db
from schemas import (
    AnswerRead,
    BulkAnswerSubmit,
    GradeFillRequest,
    SessionCreate,
    SessionDetail,
    SessionList,
    SessionRead,
    SessionStats,
)

router = APIRouter(
    prefix="/api/sessions",
    tags=["sessions"],
    dependencies=[Depends(verify_token)],
)


@router.get("", response_model=SessionList)
async def list_sessions(db: AsyncSession = Depends(get_db)) -> SessionList:
    sessions = await session_crud.list_sessions(db)
    return SessionList(sessions=[SessionRead.model_validate(s) for s in sessions])


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate, db: AsyncSession = Depends(get_db)
) -> SessionRead:
    session = await session_crud.create_session(db, body.title)
    return SessionRead.model_validate(session)


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> SessionDetail:
    session = await session_crud.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    stats = await session_crud.get_session_stats(db, session_id)
    assert stats is not None
    from schemas import QuestionRead

    return SessionDetail(
        **SessionRead.model_validate(session).model_dump(),
        questions=[QuestionRead.model_validate(q) for q in session.questions],
        stats=stats,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a quiz session by ID."""
    success = await session_crud.delete_session(db, session_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


@router.get("/{session_id}/stats", response_model=SessionStats)
async def get_session_stats(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> SessionStats:
    stats = await session_crud.get_session_stats(db, session_id)
    if stats is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return stats


@router.post("/{session_id}/submit", response_model=list[AnswerRead])
async def bulk_submit(
    session_id: str,
    body: BulkAnswerSubmit,
    db: AsyncSession = Depends(get_db),
) -> list[AnswerRead]:
    """一次性提交会话的所有答案。"""
    session = await session_crud.get_session(db, session_id)
    if not session or session.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quiz is not active")

    results: list[AnswerRead] = []
    for item in body.answers:
        question = await question_crud.get_question(db, item.question_id)
        if question is None or question.session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question {item.question_id} not found in session",
            )
        ua = await question_crud.upsert_answer(
            db, question, item.raw_answer, item.time_spent_seconds
        )
        results.append(AnswerRead.model_validate(ua))

    # 更新题组状态: active → pending/finished
    await session_crud.refresh_session_status(db, session_id)
    return results


@router.post(
    "/{session_id}/questions/{question_id}/grade",
    response_model=AnswerRead,
)
async def grade_fill(
    session_id: str,
    question_id: str,
    body: GradeFillRequest,
    db: AsyncSession = Depends(get_db),
) -> AnswerRead:
    """批改填空题答案（由 LLM 通过 MCP 调用，但也作为 REST 接口提供）。"""
    ua = await question_crud.grade_fill(db, question_id, body.is_correct, body.comment)
    if ua is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer not found",
        )

    # 再次检查: 如果所有填空题都已出分，状态由 pending 转换为 finished
    await session_crud.refresh_session_status(db, session_id)
    return AnswerRead.model_validate(ua)
