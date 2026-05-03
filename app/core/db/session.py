import logging
from typing import Any, AsyncGenerator, Dict, Tuple
from urllib.parse import parse_qs, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.db.models import Base


def _build_async_url_and_connect_args(url: str) -> Tuple[str, Dict[str, Any]]:
    """
    Convert a standard postgres URL into an asyncpg-compatible URL and pull
    sslmode out of the query string into asyncpg connect_args (asyncpg uses
    `ssl=...` instead of the libpq-style `sslmode=...`).
    """
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    split = urlsplit(url)
    params = parse_qs(split.query)

    connect_args: Dict[str, Any] = {}
    sslmode = params.pop("sslmode", [None])[0]
    if sslmode in ("require", "verify-ca", "verify-full"):
        connect_args["ssl"] = True
    elif sslmode == "disable":
        connect_args["ssl"] = False
    # "prefer" / "allow" / unset → leave default

    flat_query_pairs = []
    for k, values in params.items():
        for v in values:
            flat_query_pairs.append(f"{k}={v}")
    new_query = "&".join(flat_query_pairs)
    cleaned_url = urlunsplit(
        (split.scheme, split.netloc, split.path, new_query, split.fragment)
    )

    return cleaned_url, connect_args


ASYNC_DATABASE_URL, CONNECT_ARGS = _build_async_url_and_connect_args(settings.DATABASE_URL)

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=CONNECT_ARGS,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Create tables if they do not exist. Safe to call on every startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            logger.exception("DB session error, rolling back")
            await session.rollback()
            raise
