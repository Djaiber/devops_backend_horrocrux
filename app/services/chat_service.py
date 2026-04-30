import logging
import uuid
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db.models import Message
from app.repositories import chat_repository, message_repository
from app.services import router_agent
from app.services.lambda_service import LambdaServiceError, call_rag_lambda

logger = logging.getLogger(__name__)


@dataclass
class ChatTurnResult:
    chat_id: int
    user_message: Message
    assistant_message: Message


def _to_history(messages: List[Message]) -> List[router_agent.HistoryMessage]:
    return [router_agent.HistoryMessage(role=m.role, content=m.content) for m in messages]


async def _generate_assistant_reply(
    query: str,
    history: List[router_agent.HistoryMessage],
    trace_id: str,
) -> str:
    """Route the query through the agent and produce the assistant's reply text."""
    decision = router_agent.decide_route(query, history)
    logger.info(
        "router_agent decision trace_id=%s route=%s reason=%s history_len=%d",
        trace_id, decision.route, decision.reason, len(history),
    )

    if decision.answer is not None:
        return decision.answer

    if decision.route == "rag":
        try:
            raw = await call_rag_lambda(query, timeout=120.0)
        except LambdaServiceError as exc:
            logger.warning("RAG Lambda unavailable trace_id=%s err=%s", trace_id, exc)
            raise
        answer = str(raw.get("answer") or "").strip()
        if not answer:
            answer = "I could not find an answer for that in the available sources."
        return answer

    return "Sorry, I'm not sure how to handle that yet."


async def handle_message(
    session: AsyncSession,
    content: str,
    chat_id: Optional[int] = None,
    user_id: Optional[str] = None,
) -> ChatTurnResult:
    """
    Persist the incoming user message, route it through the agent, persist the
    assistant reply, and return both message records.
    """
    effective_user_id = user_id or settings.DEFAULT_USER_ID
    trace_id = str(uuid.uuid4())

    await chat_repository.ensure_user(session, effective_user_id)
    chat = await chat_repository.get_or_create_chat(session, effective_user_id, chat_id)

    user_message = await message_repository.add_message(
        session,
        chat_id=chat.id,
        role="user",
        content=content,
        trace_id=trace_id,
    )

    history_records = await message_repository.list_recent_messages(
        session, chat_id=chat.id, limit=settings.HISTORY_LIMIT
    )
    history = _to_history(history_records)

    try:
        reply_text = await _generate_assistant_reply(content, history, trace_id)
    except LambdaServiceError:
        await session.commit()
        raise

    assistant_message = await message_repository.add_message(
        session,
        chat_id=chat.id,
        role="assistant",
        content=reply_text,
        trace_id=trace_id,
    )

    await session.commit()
    await session.refresh(user_message)
    await session.refresh(assistant_message)

    return ChatTurnResult(
        chat_id=chat.id,
        user_message=user_message,
        assistant_message=assistant_message,
    )
