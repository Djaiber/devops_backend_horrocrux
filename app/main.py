import logging
import time
import uuid
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.lambda_service import LambdaServiceError, call_rag_lambda


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logging.getLogger("app").setLevel(logging.INFO)


app = FastAPI(
    title="HORROCRUXES Backend Preview",
    description="API proxy/facade for the external Lambda RAG API.",
    version="0.1.0",
)

cors_origins = settings.cors_origins_list or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
