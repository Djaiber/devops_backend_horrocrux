"""
Simple rules-based router agent.

For now, every non-empty user message is routed to the RAG Lambda. This module
exists as a clean seam where smarter routing (intent classification, tool
selection, LLM-driven planning) can be added later without touching the
chat_service or the lambda_service.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class HistoryMessage:
    role: str
    content: str


@dataclass
class RouteDecision:
    route: str           # "rag" | "smalltalk" | "empty"
    reason: str
    answer: Optional[str] = None  # set when the agent answers locally


SMALLTALK_PATTERNS = {
    "hi", "hello", "hey", "yo", "hola",
    "thanks", "thank you", "thx", "ty",
    "bye", "goodbye", "see you",
}


def _normalize(text: str) -> str:
    return text.strip().lower().rstrip("!.?,")


def decide_route(query: str, history: Optional[List[HistoryMessage]] = None) -> RouteDecision:
    """
    Decide how to handle a user query.

    `history` is the recent conversation context (oldest first). It is currently
    used only for short-circuit smalltalk detection but is part of the contract
    so future routing strategies can leverage it without further refactors.
    """
    normalized = _normalize(query)

    if not normalized:
        return RouteDecision(route="empty", reason="empty query", answer=None)

    if normalized in SMALLTALK_PATTERNS:
        return RouteDecision(
            route="smalltalk",
            reason="matched smalltalk pattern",
            answer="Hello! Ask me anything about the Harry Potter books.",
        )

    return RouteDecision(
        route="rag",
        reason="default route to RAG Lambda",
        answer=None,
    )
