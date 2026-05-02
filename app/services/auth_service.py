from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import User
from app.repositories.chat_repository import ensure_user


@dataclass
class AuthenticatedUser:
    id: int
    cognito_sub: str
    email: Optional[str]
    username: Optional[str]


async def ensure_local_user(
    session: AsyncSession,
    cognito_sub: str,
    email: Optional[str] = None,
    username: Optional[str] = None,
) -> AuthenticatedUser:
    user: User = await ensure_user(session, cognito_sub=cognito_sub, email=email, username=username)
    await session.flush()
    return AuthenticatedUser(id=user.id, cognito_sub=cognito_sub, email=user.email, username=user.username)
