import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db.models import Character as CharacterModel
from app.core.db.session import AsyncSessionLocal, engine, init_db
from app.routers.chat import router as chat_router
from app.routers.characters import router as characters_router
from app.routers.quiz import router as quiz_router
from app.services.lambda_service import LambdaServiceError, call_rag_lambda


DEFAULT_CHARACTERS = [
    {"id": "dumbledore", "label": "Dumbledore", "description": "Wise and enigmatic headmaster of Hogwarts, always speaking in riddles and profound wisdom.", "icon": f"{settings.CHARACTERS_S3_BASE_URL}/dumbledore.webp"},
    {"id": "hermione", "label": "Hermione", "description": "Brilliant and studious witch, always ready with facts, rules, and logical solutions.", "icon": f"{settings.CHARACTERS_S3_BASE_URL}/hermione.webp"},
    {"id": "ron", "label": "Ron", "description": "Loyal and good-humoured best friend, brings warmth and humour to every conversation.", "icon": f"{settings.CHARACTERS_S3_BASE_URL}/ron.webp"},
    {"id": "snape", "label": "Snape", "description": "Stern and sarcastic potions master with a hidden depth, speaks with cold precision.", "icon": f"{settings.CHARACTERS_S3_BASE_URL}/snape.webp"},
    {"id": "luna", "label": "Luna", "description": "Dreamy and unconventional, sees the world in a unique way and embraces the extraordinary.", "icon": f"{settings.CHARACTERS_S3_BASE_URL}/luna.webp"},
    {"id": "harry", "label": "Harry", "description": "Brave and determined chosen one, speaks with courage and a sense of justice.", "icon": f"{settings.CHARACTERS_S3_BASE_URL}/harry.webp"},
    {"id": "hagrid", "label": "Hagrid", "description": "Warm-hearted gamekeeper with a passion for magical creatures and steadfast loyalty.", "icon": f"{settings.CHARACTERS_S3_BASE_URL}/hagrid.webp"},
    {"id": "voldemort", "label": "Voldemort", "description": "Dark and terrifying Dark Lord, speaks with cold menace and absolute certainty of power.", "icon": f"{settings.CHARACTERS_S3_BASE_URL}/voldemort.webp"},
]


async def init_characters(session: AsyncSession) -> None:
    for char in DEFAULT_CHARACTERS:
        existing = await session.get(CharacterModel, char["id"])
        if existing is None:
            session.add(CharacterModel(**char))
        else:
            existing.label = char["label"]
            existing.description = char["description"]
            existing.icon = char["icon"]
    await session.commit()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logging.getLogger("app").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("initializing database schema")
    await init_db()
    async with engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE characters ALTER COLUMN icon TYPE TEXT")
        )
    logger.info("database ready")
    async with AsyncSessionLocal() as session:
        await init_characters(session)
    logger.info("characters seeded")
    yield


app = FastAPI(
    title="HORROCRUXES Backend",
    description="Chat backend with persistent storage that proxies a RAG Lambda.",
    version="0.2.0",
    lifespan=lifespan,
)

cors_origins = settings.cors_origins_list or ["http://localhost:4200", "http://localhost:3000","https://www.horrocruxes-harrypotter-rag.me","https://horrocruxes-harrypotter-rag.me"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(characters_router)
app.include_router(quiz_router)


class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language question for the RAG system.")


class QueryResponse(BaseModel):
    trace_id: str
    latency_seconds: float
    query: str
    answer: str
    books_consulted: List[Any]
    citations: List[Any]
    partial_answers_count: int
    raw: Dict[str, Any]


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "horrocruxes-backend-preview"}


@app.post("/api/demo/query", response_model=QueryResponse)
async def demo_query(payload: QueryRequest) -> QueryResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must not be empty")

    trace_id = str(uuid.uuid4())
    start = time.perf_counter()

    try:
        raw: Dict[str, Any] = await call_rag_lambda(query)
    except LambdaServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"RAG Lambda unavailable: {exc}",
        ) from exc

    latency_seconds = round(time.perf_counter() - start, 6)

    answer = str(raw.get("answer", ""))
    books_consulted = raw.get("books_consulted") or []
    citations = raw.get("citations") or []
    partial_answers_count = int(raw.get("partial_answers_count") or 0)

    if not isinstance(books_consulted, list):
        books_consulted = [books_consulted]
    if not isinstance(citations, list):
        citations = [citations]

    return QueryResponse(
        trace_id=trace_id,
        latency_seconds=latency_seconds,
        query=query,
        answer=answer,
        books_consulted=books_consulted,
        citations=citations,
        partial_answers_count=partial_answers_count,
        raw=raw if isinstance(raw, dict) else {},
    )
