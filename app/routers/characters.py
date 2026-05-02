from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import Character as CharacterModel
from app.core.db.session import get_db

router = APIRouter(prefix="/characters", tags=["characters"])


class Character(BaseModel):
    id: str
    label: str
    description: str
    icon: str


@router.get("", response_model=List[Character])
async def list_characters(session: AsyncSession = Depends(get_db)) -> List[Character]:
    result = await session.execute(select(CharacterModel))
    characters = result.scalars().all()
    return [
        Character(
            id=c.id,
            label=c.label,
            description=c.description,
            icon=c.icon
        )
        for c in characters
    ]
