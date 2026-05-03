"""Unit tests for router_agent.decide_route — routing logic without LLM calls."""
from unittest.mock import MagicMock, patch

import pytest

import app.services.router_agent as router_agent_module
from app.services.router_agent import decide_route, HistoryMessage


def _history(*msgs):
    return [HistoryMessage(role="user", content=m) for m in msgs]


@pytest.fixture(autouse=True)
def reset_llm_singleton():
    """Reset the module-level LLM singleton before/after each test so mocks take effect."""
    original = router_agent_module._llm
    router_agent_module._llm = None
    yield
    router_agent_module._llm = original


@pytest.fixture
def mock_llm():
    """Patch ChatGoogleGenerativeAI and return the mock instance."""
    with patch("app.services.router_agent.ChatGoogleGenerativeAI") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance


# ── smalltalk pattern matching ─────────────────────────────────────────────

def test_greeting_routes_to_smalltalk(mock_llm):
    """A word in SMALLTALK_PATTERNS triggers the smalltalk path and calls the LLM."""
    mock_llm.invoke.return_value = MagicMock(content="Hello! I am Dumbledore.")
    result = decide_route("hello", _history())
    assert result.route == "smalltalk"
    assert result.answer == "Hello! I am Dumbledore."


def test_greeting_with_exclamation_routes_to_smalltalk(mock_llm):
    """Trailing punctuation is stripped before pattern-matching."""
    mock_llm.invoke.return_value = MagicMock(content="Greetings!")
    result = decide_route("Hello!", _history())
    assert result.route == "smalltalk"


def test_smalltalk_llm_error_returns_fallback_answer(mock_llm):
    """When the smalltalk LLM call fails, a fallback answer is returned (route still smalltalk)."""
    mock_llm.invoke.side_effect = Exception("LLM unavailable")
    result = decide_route("hello", _history())
    assert result.route == "smalltalk"
    assert result.answer is not None
    assert len(result.answer) > 0


# ── default RAG route ──────────────────────────────────────────────────────

def test_harry_potter_question_routes_to_rag():
    """Non-smalltalk queries with no history fall through to RAG without LLM call."""
    result = decide_route("Who is Voldemort?", _history())
    assert result.route == "rag"
    assert result.answer is None


def test_arbitrary_question_routes_to_rag():
    """Any query that is not a smalltalk pattern routes to RAG by default."""
    result = decide_route("Tell me about Hogwarts", _history())
    assert result.route == "rag"


# ── edge cases ─────────────────────────────────────────────────────────────

def test_empty_query_routes_to_empty():
    """An empty (or whitespace-only) query returns route='empty'."""
    result = decide_route("", _history())
    assert result.route == "empty"
    assert result.answer is None


# ── character context ──────────────────────────────────────────────────────

def test_decide_route_passes_character_context(mock_llm):
    """Character kwarg is forwarded; LLM is called once for a smalltalk query."""
    mock_llm.invoke.return_value = MagicMock(content="Indeed, Hogwarts is magnificent.")
    result = decide_route("hello", _history(), character="dumbledore")
    assert result.route == "smalltalk"
    mock_llm.invoke.assert_called_once()
