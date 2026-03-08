"""MCP server definition with all Quiz tools."""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from config import settings
from database import AsyncSessionLocal
from crud import sessions as session_crud
from crud import questions as question_crud

mcp = FastMCP(
    name="QuizMCP",
    instructions=(
        "You are a quiz authoring assistant. "
        "Use the provided tools to create quiz sessions, add questions, "
        "and review student answers. "
        "Always finalize a session before sharing the link with users."
    ),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _quiz_url(session_id: str) -> str:
    return f"http://{settings.host if settings.host != '0.0.0.0' else 'localhost'}:{settings.port}/quiz/{session_id}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_quiz_session(title: str) -> str:
    """
    Create a new quiz session.

    Args:
        title: A descriptive title for the quiz (e.g. "Chapter 3 Physics Test").

    Returns:
        JSON with session_id and quiz_url to share with the user.
    """
    async with AsyncSessionLocal() as db:
        session = await session_crud.create_session(db, title)
        return json.dumps(
            {"session_id": session.id, "quiz_url": _quiz_url(session.id)},
            ensure_ascii=False,
        )


@mcp.tool()
async def add_question(
    session_id: str,
    type: str,
    content: str,
    options: list[str] | None = None,
    answer: Any = None,
    explanation: str | None = None,
) -> str:
    """
    Add a question to an existing quiz session.

    Args:
        session_id: The session's UUID returned by create_quiz_session.
        type: Question type. One of: "choice", "multi", "judge", "fill", "sort".
        content: The question text.
        options: For choice/multi/sort types: list of option strings (e.g. ["A. ...", "B. ..."]).
                 For sort type: the list of items to be sorted.
                 Leave null for judge and fill types.
        answer: The correct answer.
                - choice/judge: a string matching one of the options (e.g. "A" or "True").
                - multi: a list of correct option identifiers (e.g. ["A", "C"]).
                - sort: a list of options in the correct order.
                - fill: leave null — LLM grades manually via grade_fill_answer.
        explanation: Optional explanation shown after the user submits.

    Returns:
        JSON with the new question_id.
    """
    async with AsyncSessionLocal() as db:
        q = await question_crud.add_question(
            db,
            session_id=session_id,
            type_=type,
            content=content,
            options=options,
            answer=answer,
            explanation=explanation,
        )
        return json.dumps({"question_id": q.id}, ensure_ascii=False)


@mcp.tool()
async def finalize_session(session_id: str) -> str:
    """
    Finalize (lock) a quiz session so that no more questions can be added.
    The session status changes from "draft" to "active".
    You MUST call this before sharing the quiz link with the user.

    Args:
        session_id: The session's UUID.

    Returns:
        JSON with ok=true and the quiz_url to share.
    """
    async with AsyncSessionLocal() as db:
        try:
            session = await session_crud.finalize_session(db, session_id)
            if session is None:
                return json.dumps({"ok": False, "error": "Session not found"})
            return json.dumps(
                {"ok": True, "quiz_url": _quiz_url(session.id)}, ensure_ascii=False
            )
        except ValueError as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_session_stats(session_id: str) -> str:
    """
    Get answering statistics for a quiz session.
    Use this after the user says they have submitted their answers.

    Args:
        session_id: The session's UUID.

    Returns:
        JSON with total, correct, wrong, unanswered, fill_pending count,
        time_spent_seconds, fill_pending_list, and questions_detail containing
        each question's content, options, correct answer, and user's answer.
    """
    async with AsyncSessionLocal() as db:
        stats = await session_crud.get_session_stats(db, session_id)
        if stats is None:
            return json.dumps({"error": "Session not found"})
        pending = await session_crud.get_fill_pending(db, session_id)
        
        session = await session_crud.get_session(db, session_id)
        questions_detail = []
        if session:
            for q in session.questions:
                ua = q.user_answer
                questions_detail.append({
                    "question_id": q.id,
                    "type": q.type,
                    "content": q.content,
                    "options": q.options,
                    "correct_answer": q.answer,
                    "user_answer": ua.raw_answer if ua else None,
                    "is_correct": ua.is_correct if ua else None,
                    "grade_comment": ua.grade_comment if ua else None
                })

        result = stats.model_dump()
        result["fill_pending_list"] = pending
        result["questions_detail"] = questions_detail
        return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def grade_fill_answer(
    session_id: str,
    question_id: str,
    is_correct: bool,
    comment: str | None = None,
) -> str:
    """
    Grade a fill-in-the-blank answer submitted by the user.
    Call get_session_stats first to retrieve the pending fill answers.

    Args:
        session_id: The session's UUID (for context / validation).
        question_id: The question's UUID.
        is_correct: Whether the user's answer is correct.
        comment: Optional feedback comment shown to the user.

    Returns:
        JSON with ok=true on success.
    """
    async with AsyncSessionLocal() as db:
        ua = await question_crud.grade_fill(db, question_id, is_correct, comment)
        if ua is None:
            return json.dumps(
                {"ok": False, "error": "Answer not found — user may not have submitted yet"}
            )
        # Refresh session status (pending → finished when all fills graded)
        await session_crud.refresh_session_status(db, session_id)
        return json.dumps({"ok": True}, ensure_ascii=False)


@mcp.tool()
async def list_sessions() -> str:
    """
    List all quiz sessions with basic stats.

    Returns:
        JSON array of sessions with id, title, status, created_at, and stats.
    """
    async with AsyncSessionLocal() as db:
        sessions = await session_crud.list_sessions(db)
        result = []
        for s in sessions:
            stats = await session_crud.get_session_stats(db, s.id)
            result.append(
                {
                    "session_id": s.id,
                    "title": s.title,
                    "status": s.status,
                    "created_at": s.created_at.isoformat(),
                    "quiz_url": _quiz_url(s.id),
                    "stats": stats.model_dump() if stats else None,
                }
            )
        return json.dumps(result, ensure_ascii=False, default=str)
