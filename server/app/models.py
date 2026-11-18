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
    speaker_identity_id: Optional[str] = None
    speaker_name: str = "未知说话人"
    role: Role = "unknown"
    text: str
    audio_file: Optional[str] = None
    speaker_score: Optional[float] = None
    need_reply: bool = False
    ai_suggestion: Optional[str] = None
    created_at: str
    corrected: bool = False


class Session(BaseModel):
    id: str
    title: str = "未命名会谈"
    goal: str = ""
    started_at: str
    ended_at: Optional[str] = None
    messages: list[Message] = Field(default_factory=list)
    summary: Optional[str] = None


class SessionCreate(BaseModel):
    title: str = "未命名会谈"
    goal: str = ""


class MeetingCreate(BaseModel):
    customer_name: str
    goal: str


class SessionSummary(BaseModel):
    id: str
    title: str = "未命名会谈"
    goal: str = ""
    started_at: str
    ended_at: Optional[str] = None
    message_count: int = 0
    has_summary: bool = False


class SuggestReplyRequest(BaseModel):
    meeting_goal: str
    conversation_history: str
    latest_customer_message: str


class SuggestReplyResponse(BaseModel):
    suggestion: str


class SpeakerCorrectionRequest(BaseModel):
    participant_id: Optional[str] = None
    speaker_name: Optional[str] = None
    role: Optional[Role] = None


class SpeakerBindRequest(BaseModel):
    speaker_name: str
    role: Role = "customer"
    need_reply: bool = True


class SpeakerBindResponse(BaseModel):
    speaker_identity_id: str
    speaker_name: str
    updated_count: int


class ExportResponse(BaseModel):
    file: str


class ModelConfig(BaseModel):
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 30
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    speaker_threshold: float = 0.70
    energy_threshold: float = 0.02
    silence_duration_ms: int = 800
    min_speech_duration_ms: int = 1000


class SummaryResponse(BaseModel):
    summary: str
