"""Unit tests for chat_repository — ensure_user and get_or_create_chat logic."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.chat_repository import (
    create_chat,
    ensure_user,
    get_or_create_chat,
)
from app.core.db.models import Chat, User


# ── helpers ────────────────────────────────────────────────────────────────

def _make_user(id: int = 1, cognito_sub: str = "sub-1") -> User:
    u = User()
    u.id = id
    u.cognito_sub = cognito_sub
    u.email = "test@test.com"
    u.username = "tester"
    return u


def _make_chat(id: int = 10, user_id: int = 1, character: str = "harry") -> Chat:
    c = Chat()
    c.id = id
    c.user_id = user_id
    c.character = character
    return c


# ── ensure_user ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ensure_user_creates_new_user_when_not_found():
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    session.flush = AsyncMock()
    session.add = MagicMock()

    user = await ensure_user(session, cognito_sub="new-sub", email="a@b.com", username="alice")

    session.add.assert_called_once()
    session.flush.assert_awaited_once()
    assert user.cognito_sub == "new-sub"


@pytest.mark.asyncio
async def test_ensure_user_returns_existing_user():
    existing = _make_user(cognito_sub="existing-sub")
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing)))
    session.flush = AsyncMock()
    session.add = MagicMock()

    user = await ensure_user(session, cognito_sub="existing-sub")

    session.add.assert_not_called()
    assert user is existing


@pytest.mark.asyncio
async def test_ensure_user_updates_email_if_changed():
    existing = _make_user(cognito_sub="sub-x")
    existing.email = "old@test.com"
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing)))
    session.flush = AsyncMock()

    await ensure_user(session, cognito_sub="sub-x", email="new@test.com")

    assert existing.email == "new@test.com"


# ── get_or_create_chat ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_or_create_chat_returns_existing_when_owned():
    chat = _make_chat(id=5, user_id=1)
    session = MagicMock()
    session.get = AsyncMock(return_value=chat)
    session.flush = AsyncMock()
    session.add = MagicMock()

    result = await get_or_create_chat(session, user_id=1, chat_id=5)

    assert result is chat
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_chat_creates_new_when_chat_belongs_to_other_user():
    other_chat = _make_chat(id=5, user_id=99)
    new_chat = _make_chat(id=6, user_id=1)
    session = MagicMock()
    session.get = AsyncMock(return_value=other_chat)
    session.flush = AsyncMock()
    session.add = MagicMock()

    with patch("app.repositories.chat_repository.create_chat", new=AsyncMock(return_value=new_chat)):
        result = await get_or_create_chat(session, user_id=1, chat_id=5)

    assert result is new_chat


@pytest.mark.asyncio
async def test_get_or_create_chat_creates_new_when_no_chat_id():
    new_chat = _make_chat(id=7, user_id=1)
    session = MagicMock()
    session.flush = AsyncMock()
    session.add = MagicMock()

    with patch("app.repositories.chat_repository.create_chat", new=AsyncMock(return_value=new_chat)):
        result = await get_or_create_chat(session, user_id=1, chat_id=None)

    assert result is new_chat


@pytest.mark.asyncio
async def test_create_chat_uses_default_character():
    session = MagicMock()
    session.flush = AsyncMock()
    session.add = MagicMock()

    chat = await create_chat(session, user_id=1)

    session.add.assert_called_once()
    created: Chat = session.add.call_args[0][0]
    assert created.character == "dumbledore"
    assert created.user_id == 1
