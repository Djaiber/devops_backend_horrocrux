from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MessageIn(BaseModel):
    content: str = Field(..., description="The user's message text.")
    chat_id: Optional[int] = Field(
        default=None,
        description="Existing chat id to continue. Omit to start a new chat.",
    )
    character: Optional[str] = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    role: str
    content: str
    trace_id: Optional[str] = None
    created_at: datetime


class ChatTurnResponse(BaseModel):
    chat_id: int
    user_message: MessageOut
    assistant_message: MessageOut


class ChatHistoryResponse(BaseModel):
    chat_id: int
    messages: List[MessageOut]


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    character: str
    created_at: datetime


class UserChatsResponse(BaseModel):
    chats: List[ChatOut]
