from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.security import get_current_user
from app.repositories import chat_repository, message_repository
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatTurnResponse,
    MessageIn,
    MessageOut,
)
from app.services import chat_service
from app.services.lambda_service import LambdaServiceError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatTurnResponse)
async def post_message(
    payload: MessageIn,
    session: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> ChatTurnResponse:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content must not be empty")

    try:
        result = await chat_service.handle_message(
            session=session,
            content=content,
            chat_id=payload.chat_id,
            user_id=current_user.id,
            character=payload.character,
        )
    except LambdaServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"RAG Lambda unavailable: {exc}",
        ) from exc

    return ChatTurnResponse(
        chat_id=result.chat_id,
        user_message=MessageOut.model_validate(result.user_message),
        assistant_message=MessageOut.model_validate(result.assistant_message),
    )


@router.get("/{chat_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    chat_id: int = Path(..., ge=1),
    session: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> ChatHistoryResponse:
    chat = await chat_repository.get_chat(session, chat_id)
    if chat is None or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="chat not found")

    messages = await message_repository.list_messages_for_chat(session, chat_id=chat_id)
    return ChatHistoryResponse(
        chat_id=chat_id,
        messages=[MessageOut.model_validate(m) for m in messages],
    )
