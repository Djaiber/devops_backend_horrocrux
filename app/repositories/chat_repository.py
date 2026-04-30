from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import Chat, User


async def ensure_user(session: AsyncSession, user_id: str) -> User:
    """Get a user by id, creating it if it doesn't exist."""
    user = await session.get(User, user_id)
    if user is None:
        user = User(id=user_id)
        session.add(user)
        await session.flush()
    return user


async def get_chat(session: AsyncSession, chat_id: int) -> Optional[Chat]:
    return await session.get(Chat, chat_id)


async def create_chat(session: AsyncSession, user_id: str) -> Chat:
    chat = Chat(user_id=user_id)
    session.add(chat)
    await session.flush()
    return chat


async def get_or_create_chat(
    session: AsyncSession,
    user_id: str,
    chat_id: Optional[int],
) -> Chat:
    """If chat_id is provided and exists for this user, return it. Otherwise create a new chat."""
    if chat_id is not None:
        existing = await session.get(Chat, chat_id)
        if existing is not None and existing.user_id == user_id:
            return existing
    return await create_chat(session, user_id)
