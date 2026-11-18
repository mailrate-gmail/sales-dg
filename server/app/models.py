from typing import Literal, Optional
from pydantic import BaseModel, Field


Role = Literal["self", "customer", "other", "unknown"]


class Participant(BaseModel):
    id: str
    name: str
    role: Role = "unknown"
    need_reply: bool = False
    display_color: str = "gray"
    voiceprint_file: Optional[str] = None
    sample_audio_file: Optional[str] = None
    remark: str = ""


class ParticipantCreate(BaseModel):
    name: str
    role: Role = "unknown"
    need_reply: bool = False
    remark: str = ""


class ParticipantUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[Role] = None
    need_reply: Optional[bool] = None
    remark: Optional[str] = None


class Message(BaseModel):
    id: str
    session_id: str
    participant_id: Optional[str] = None
    speaker_name: str = "未知说话人"
    role: Role = "unknown"
    text: str
    audio_file: Optional[str] = None
    speaker_score: Optional[float] = None
    need_reply: bool = False
    ai_suggestion: Optional[str] = None
    created_at: str


class Session(BaseModel):
    id: str
    title: str = "未命名会谈"
    goal: str = ""
    started_at: str
    ended_at: Optional[str] = None
    messages: list[Message] = Field(default_factory=list)


class SessionCreate(BaseModel):
    title: str = "未命名会谈"
    goal: str = ""


class SuggestReplyRequest(BaseModel):
    meeting_goal: str
    conversation_history: str
    latest_customer_message: str


class SuggestReplyResponse(BaseModel):
    suggestion: str
