from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import Message


async def add_message(
    session: AsyncSession,
    chat_id: int,
    role: str,
    content: str,
    trace_id: Optional[str] = None,
) -> Message:
    message = Message(
        chat_id=chat_id,
        role=role,
        content=content,
        trace_id=trace_id,
    )
    session.add(message)
    await session.flush()
    return message


async def list_recent_messages(
    session: AsyncSession,
    chat_id: int,
    limit: int = 10,
) -> List[Message]:
    """Return the last `limit` messages for a chat in chronological order (oldest first)."""
    stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


async def list_messages_for_chat(
    session: AsyncSession,
    chat_id: int,
    limit: Optional[int] = None,
) -> List[Message]:
    """Return messages for a chat in chronological order (oldest first)."""
    stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
