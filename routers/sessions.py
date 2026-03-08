"""Sessions router — CRUD REST endpoints for quiz sessions."""

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
    """Submit all answers for a session at once."""
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
    """Grade a fill-in-the-blank answer (called from LLM via MCP, but also available as REST)."""
    ua = await question_crud.grade_fill(db, question_id, body.is_correct, body.comment)
    if ua is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer not found",
        )
    return AnswerRead.model_validate(ua)
