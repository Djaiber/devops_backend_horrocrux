import asyncio
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import Character as CharacterModel
from app.core.db.session import get_db
from app.services.router_agent import _get_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz", tags=["quiz"])

CHARACTER_HOUSES: dict[str, str] = {
    "dumbledore": "Gryffindor",
    "hermione":   "Gryffindor",
    "ron":        "Gryffindor",
    "harry":      "Gryffindor",
    "hagrid":     "Gryffindor",
    "snape":      "Slytherin",
    "voldemort":  "Slytherin",
    "luna":       "Ravenclaw",
}


class QuizAnswers(BaseModel):
    reaccion_peligro: Optional[str] = None
    valor_principal: Optional[str] = None
    rasgos: Optional[List[str]] = None
    materia_favorita: Optional[str] = None
    primer_anio: Optional[str] = None
    patronus: Optional[str] = None
    ante_injusticia: Optional[str] = None
    mayor_temor: Optional[str] = None
    lema_vida: Optional[str] = None


class QuizResult(BaseModel):
    personaje: str
    casa: str
    descripcion: str
    match_percentage: int
    traits: List[str]
    quote: str
    icon: str = ""
    character_id: str = ""


def _run_llm(answers: dict, characters: list[dict]) -> QuizResult:
    llm = _get_llm()

    characters_text = "\n".join(
        f"- {c['id']}: {c['label']} — {c['description']}" for c in characters
    )
    character_ids = [c["id"] for c in characters]

    answers_text = "\n".join(f"  {k}: {v}" for k, v in answers.items() if v)

    response = llm.invoke([
        SystemMessage(content=(
            "You are a Harry Potter personality quiz analyzer. "
            "Based on the user's quiz answers, determine which character from the provided list best matches them.\n\n"
            f"Available characters:\n{characters_text}\n\n"
            "Return ONLY a valid JSON object with these exact fields:\n"
            "{\n"
            f'  "character_id": "<one of: {", ".join(character_ids)}>",\n'
            '  "personaje": "<character full name>",\n'
            '  "descripcion": "<2-3 sentence personalized description of why the user matches this character>",\n'
            '  "match_percentage": <integer 75-98>,\n'
            '  "traits": ["<trait1>", "<trait2>", "<trait3>", "<trait4>"],\n'
            '  "quote": "<an iconic or fitting quote from the matched character>"\n'
            "}\n"
            "No explanation, no markdown, only the JSON object."
        )),
        HumanMessage(content=f"Quiz answers:\n{answers_text}"),
    ])

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw.strip())

    character_id = data.get("character_id", "")
    casa = CHARACTER_HOUSES.get(character_id, "Gryffindor")
    char_data = next((c for c in characters if c["id"] == character_id), None)
    icon = char_data["icon"] if char_data and "icon" in char_data else ""

    return QuizResult(
        personaje=data["personaje"],
        casa=casa,
        descripcion=data["descripcion"],
        match_percentage=data["match_percentage"],
        traits=data["traits"],
        quote=data["quote"],
        icon=icon,
        character_id=character_id,
    )


@router.post("/analyze", response_model=QuizResult)
async def analyze_quiz(
    answers: QuizAnswers,
    session: AsyncSession = Depends(get_db),
) -> QuizResult:
    result = await session.execute(select(CharacterModel))
    characters = [
        {"id": c.id, "label": c.label, "description": c.description, "icon": c.icon}
        for c in result.scalars().all()
    ]

    answers_dict = answers.model_dump(exclude_none=True)

    try:
        return await asyncio.to_thread(_run_llm, answers_dict, characters)
    except Exception as exc:
        logger.error("Quiz LLM failed: %s", exc)
        # fallback: pick first character
        char = characters[0] if characters else {"label": "Harry Potter", "description": ""}
        return QuizResult(
            personaje=char["label"],
            casa="Gryffindor",
            descripcion="Your answers reveal a brave and loyal spirit.",
            match_percentage=80,
            traits=["Brave", "Loyal", "Determined", "Kind"],
            quote="«It is our choices that show what we truly are, far more than our abilities.»",
        )
