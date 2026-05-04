import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional
import time
import boto3

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings

logger = logging.getLogger(__name__)

CHARACTER_PERSONAS: dict[str, str] = {
    "dumbledore": (
        "You are Albus Dumbledore, the wise and enigmatic headmaster of Hogwarts. "
        "Speak with calm authority and profound wisdom. Use elegant, thoughtful language, "
        "occasionally quoting your own aphorisms. Be warm but mysterious."
    ),
    "hermione": (
        "You are Hermione Granger, the brightest witch of her age. "
        "Speak with precision, cite facts eagerly, and occasionally reference books or rules. "
        "You are helpful, logical, and slightly impatient with imprecision."
    ),
    "ron": (
        "You are Ron Weasley, loyal best friend. "
        "Speak in a warm, casual, good-humoured tone with occasional self-deprecating humour. "
        "You are brave but sometimes unsure of yourself. Use British slang naturally."
    ),
    "snape": (
        "You are Severus Snape, the potions master. "
        "Speak with cold precision, thinly veiled sarcasm, and barely contained disdain for foolishness. "
        "You are brilliant but withholding. Every compliment costs you something."
    ),
    "luna": (
        "You are Luna Lovegood, the dreamy and unconventional Ravenclaw. "
        "Speak in a soft, matter-of-fact way about strange things as if they are perfectly normal. "
        "You are kind, perceptive, and unafraid of the unusual."
    ),
    "harry": (
        "You are Harry Potter, the chosen one. "
        "Speak with courage and directness, driven by a strong sense of justice. "
        "You are humble, occasionally self-doubting, but always determined."
    ),
    "hagrid": (
        "You are Rubeus Hagrid, Keeper of Keys and Grounds at Hogwarts. "
        "Speak with warmth and enthusiasm, especially about magical creatures. "
        "Use a warm West Country accent in writing — occasional dropped letters, hearty exclamations."
    ),
    "voldemort": (
        "You are Lord Voldemort, the Dark Lord. "
        "Speak with cold menace, absolute certainty, and thinly veiled contempt for weakness. "
        "You do not shout — your power needs no volume. Refer to yourself in the third person occasionally."
    ),
}

DEFAULT_PERSONA = CHARACTER_PERSONAS["dumbledore"]

SMALLTALK_PATTERNS = {
    "hi", "hello", "hey", "yo", "hola",
    "thanks", "thank you", "thx", "ty",
    "bye", "goodbye", "see you",
}


_llm: Optional[ChatGoogleGenerativeAI] = None


def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.8,
        )
    return _llm


def _format_lambda_response(raw: dict) -> str:
    answer = str(raw.get("answer") or "").strip()
    if not answer:
        return "I could not find an answer for that in the available sources."
    return answer


@dataclass
class HistoryMessage:
    role: str
    content: str


@dataclass
class RouteDecision:
    route: str
    reason: str
    answer: Optional[str] = None


def _normalize(text: str) -> str:
    return text.strip().lower().rstrip("!.?,")


BOOK_NAMES = {
    "PS":   "The Philosopher's Stone",
    "CoS":  "The Chamber of Secrets",
    "PoA":  "The Prisoner of Azkaban",
    "GoF":  "The Goblet of Fire",
    "OotP": "The Order of the Phoenix",
    "HBP":  "The Half-Blood Prince",
    "DH":   "The Deathly Hallows",
}


def _extract_citations(text: str) -> list[tuple[str, str]]:
    """Extract (book_abbr, chapter_name) pairs from RAW RAG output."""
    citations: list[tuple[str, str]] = []
    # Match individual "ABBR Ch. CHAPTER_NAME" entries inside or outside parentheses
    for match in re.finditer(r'\b(PS|CoS|PoA|GoF|OotP|HBP|DH)\s+Ch\.\s+([A-Z][A-Z\s]+?)(?=[,)]|$)', text):
        abbr = match.group(1)
        chapter = match.group(2).strip().title()
        entry = (abbr, chapter)
        if entry not in citations:
            citations.append(entry)
    return citations


def _format_citations(citations: list[tuple[str, str]]) -> str:
    if not citations:
        return ""
    # Group chapters by book
    books: dict[str, list[str]] = {}
    for abbr, chapter in citations:
        book = BOOK_NAMES.get(abbr, abbr)
        books.setdefault(book, []).append(chapter)
    lines = ["📚 Sources"]
    for book, chapters in books.items():
        chapters_str = ", ".join(chapters)
        lines.append(f"  • {book} — Ch. {chapters_str}")
    return "\n".join(lines)


def _clean_for_llm(text: str) -> str:
    """Strip citations from text before sending to the persona LLM."""
    text = re.sub(r'\([A-Z][a-zA-Z]*\s+Ch\.[^)]+\)', '', text)
    text = re.sub(r'\n?Reference:.*$', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'\b(?:PS|CoS|PoA|GoF|OotP|HBP|DH):\s+Harry Potter[^\n]*', '', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def _build_character_answer(raw_answer: str, character: str, query: str, history: List[HistoryMessage]) -> str:
    persona = CHARACTER_PERSONAS.get(character, DEFAULT_PERSONA)
    llm = _get_llm()

    citations = _extract_citations(raw_answer)
    clean_answer = _clean_for_llm(raw_answer)

    messages = [
        SystemMessage(content=(
            f"{persona}\n\n"
            "A knowledge base has retrieved factual information to answer the user's question. "
            "Your job is to rewrite that information ENTIRELY in your character's voice.\n\n"
            "STRICT RULES:\n"
            "- Do NOT include any book abbreviations (PS, CoS, PoA, GoF, OotP, HBP, DH) or chapter references.\n"
            "- Do NOT include a 'Reference:' or 'Sources:' section — that is handled separately.\n"
            "- If mentioning a book naturally adds value, use its full name: 'in The Philosopher's Stone'.\n"
            "- Stay fully in character — vocabulary, tone, mannerisms.\n"
            "- Be conversational. 2-4 sentences max unless the question genuinely requires more.\n"
            "- Respond ONLY as the character. No meta-commentary."
        )),
    ]

    for h in history[-6:]:
        if h.role == "user":
            messages.append(HumanMessage(content=h.content))
        else:
            from langchain_core.messages import AIMessage
            messages.append(AIMessage(content=h.content))

    messages.append(HumanMessage(content=(
        f"User question: {query}\n\n"
        f"Factual data:\n{clean_answer}"
    )))

    response = llm.invoke(messages)
    character_reply = response.content.strip()

    formatted_citations = _format_citations(citations)
    if formatted_citations:
        return f"{character_reply}\n\n{formatted_citations}"
    return character_reply


def decide_route(
    query: str,
    history: Optional[List[HistoryMessage]] = None,
    character: Optional[str] = None,
) -> RouteDecision:
    normalized = _normalize(query)

    if not normalized:
        return RouteDecision(route="empty", reason="empty query", answer=None)

    if normalized in SMALLTALK_PATTERNS:
        persona_char = character or "dumbledore"
        persona = CHARACTER_PERSONAS.get(persona_char, DEFAULT_PERSONA)
        llm = _get_llm()
        try:
            response = llm.invoke([
                SystemMessage(content=(
                    f"{persona}\n\n"
                    "The user has just greeted you. Introduce yourself by name in your character's voice, "
                    "then warmly invite them to ask you anything about the Harry Potter universe. "
                    "Keep it to 2-3 sentences. Stay fully in character."
                )),
                HumanMessage(content=query),
            ])
            answer = response.content.strip()
        except Exception as exc:
            logger.warning("LLM smalltalk failed: %s", exc)
            answer = "Hello! Ask me anything about the Harry Potter books."
        return RouteDecision(route="smalltalk", reason="matched smalltalk pattern", answer=answer)

    if history:
        answer = _try_answer_from_history(query, history, character)
        if answer is not None:
            return RouteDecision(route="conversation", reason="meta-conversation question answered from history", answer=answer)

    return RouteDecision(route="rag", reason="default route to RAG Lambda", answer=None)


def _try_answer_from_history(query: str, history: List[HistoryMessage], character: Optional[str]) -> Optional[str]:
    """Classify intent, and if it's a conversation-meta question answer in full character voice."""
    persona_char = character or "dumbledore"
    persona = CHARACTER_PERSONAS.get(persona_char, DEFAULT_PERSONA)
    llm = _get_llm()

    history_text = "\n".join(
        f"{'User' if h.role == 'user' else 'You'}: {h.content}" for h in history
    )
    try:
        # Step 1: lightweight classification only
        classify = llm.invoke([
            SystemMessage(content=(
                "You are a routing classifier. Reply with exactly one word.\n"
                "If the user's question is about THIS specific conversation "
                "(what was said, first/last message, chat history, what you or the user wrote): reply CONV\n"
                "If it is about Harry Potter lore, facts, books, characters, spells, events: reply RAG\n"
                f"Chat history for context:\n{history_text}"
            )),
            HumanMessage(content=query),
        ])
        if classify.content.strip().upper() != "CONV":
            return None

        # Step 2: answer fully in character voice
        answer = llm.invoke([
            SystemMessage(content=(
                f"{persona}\n\n"
                "The user is asking about your current conversation. "
                "Answer using ONLY what appears in the chat history below — do not invent anything. "
                "Respond completely in character. Be concise."
                f"\n\nChat history:\n{history_text}"
            )),
            HumanMessage(content=query),
        ])
        return answer.content.strip()
    except Exception as exc:
        logger.warning("History classifier LLM failed: %s", exc)
        return None


CHARACTER_NAMES = {
    "dumbledore": "Albus Dumbledore",
    "hermione": "Hermione Granger",
    "ron": "Ron Weasley",
    "snape": "Severus Snape",
    "luna": "Luna Lovegood",
    "harry": "Harry Potter",
    "hagrid": "Rubeus Hagrid",
    "voldemort": "Lord Voldemort",
}


def _rewrite_query(query: str, character: str) -> str:
    full_name = CHARACTER_NAMES.get(character, character.capitalize())
    llm = _get_llm()
    response = llm.invoke([
        SystemMessage(content=(
            "You are a query rewriter for a Harry Potter knowledge base search engine. "
            f"The user is chatting with {full_name} as a character. "
            "Rewrite the user's question as a factual, third-person search query about the Harry Potter books. "
            "Replace any first-person or second-person references ('you', 'your', 'I', 'me') "
            f"with '{full_name}'. "
            "Return ONLY the rewritten query — no explanation, no quotes, no extra text."
        )),
        HumanMessage(content=query),
    ])
    rewritten = response.content.strip()
    logger.info("query rewritten char=%s original=%r rewritten=%r", character, query, rewritten)
    return rewritten


async def rewrite_query_for_rag(query: str, character: Optional[str]) -> str:
    if not character:
        return query
    try:
        return await asyncio.to_thread(_rewrite_query, query, character)
    except Exception as exc:
        logger.warning("Query rewrite failed char=%s err=%s", character, exc)
        return query


async def build_character_answer(
    raw_answer: str,
    query: str,
    history: List[HistoryMessage],
    character: Optional[str] = None,
) -> str:
    char = character or "dumbledore"
    try:
        return await asyncio.to_thread(_build_character_answer, raw_answer, char, query, history)
    except Exception as exc:
        logger.warning("Character persona LLM failed char=%s err=%s", char, exc)
        return raw_answer
# ---------- new secret resolution helper ----------
_secrets_cache: Dict[str, Any] = {}

def _resolve_secret(arn: str) -> str:
    """Fetch a secret from AWS Secrets Manager with 5‑minute cache."""
    now = time.time()
    cached = _secrets_cache.get(arn)
    if cached and now < cached.get("expires_at", 0):
        return cached["value"]

    try:
        client = boto3.client("secretsmanager", region_name="us-east-1")
        response = client.get_secret_value(SecretId=arn)
        secret = response.get("SecretString") or ""
        # Try to decode JSON, fallback to raw secret
        try:
            parsed = json.loads(secret)
            value = parsed.get("GOOGLE_API_KEY") or parsed.get("GEMINI_API_KEY") or parsed.get("value") or secret
        except (json.JSONDecodeError, AttributeError):
            value = secret

        _secrets_cache[arn] = {
            "value": value,
            "expires_at": now + 300,  # 5 minutes
        }
        return value

    except ClientError as e:
        logger.error("Failed to fetch secret %s: %s", arn, e)
        # Re-raise as a critical error – the LLM cannot work without its key
        raise RuntimeError(f"Could not load secret {arn}: {e}") from e


# ---------- updated _get_llm ----------
_llm: Optional[ChatGoogleGenerativeAI] = None

def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        # If the configured value is an ARN, resolve it
        api_key = settings.GOOGLE_API_KEY
        if api_key.startswith("arn:"):
            api_key = _resolve_secret(api_key)

        _llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=api_key,
            temperature=0.8,
        )
    return _llm