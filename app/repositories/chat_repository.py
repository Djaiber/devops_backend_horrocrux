from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import Chat, User


async def ensure_user(
    session: AsyncSession,
    cognito_sub: str,
    email: Optional[str] = None,
    username: Optional[str] = None,
) -> User:
    stmt = select(User).where(User.cognito_sub == cognito_sub)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        user = User(cognito_sub=cognito_sub, email=email, username=username)
        session.add(user)
        await session.flush()
    else:
        if email and user.email != email:
            user.email = email
        if username and user.username != username:
            user.username = username
    return user


async def get_chat(session: AsyncSession, chat_id: int) -> Optional[Chat]:
    return await session.get(Chat, chat_id)


async def create_chat(session: AsyncSession, user_id: int, character: Optional[str] = None) -> Chat:
    chat = Chat(user_id=user_id, character=character or "dumbledore")
    session.add(chat)
    await session.flush()
    return chat


async def get_or_create_chat(session: AsyncSession, user_id: int, chat_id: Optional[int], character: Optional[str] = None) -> Chat:
    if chat_id is not None:
        existing = await session.get(Chat, chat_id)
        if existing is not None and existing.user_id == user_id:
            return existing
    return await create_chat(session, user_id, character=character)
