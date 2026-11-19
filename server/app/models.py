from typing import Literal, Optional
from pydantic import BaseModel, Field


Role = Literal["self", "customer", "other", "unknown"]
LLMApiType = Literal["chat_completions", "responses"]
ASRProvider = Literal["funasr_streaming", "faster_whisper", "oci_speech"]
AgentActionType = Literal[
    "suggest_reply",
    "extract_pain_point",
    "record_commitment",
    "record_todo",
    "mark_risk",
    "capture_question",
    "ignore",
]


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
    start_time: Optional[float] = None
    end_time: Optional[float] = None
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


class AgentDecision(BaseModel):
    id: str
    type: AgentActionType
    reason: str
    content: str
    message_id: Optional[str] = None
    speaker_name: str = "未知说话人"
    created_at: str


class AgentMemory(BaseModel):
    meeting_id: str
    goal: str = ""
    short_term_context: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    commitments: list[str] = Field(default_factory=list)
    todos: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    decisions: list[AgentDecision] = Field(default_factory=list)
    updated_at: str = ""


class AgentRunResponse(BaseModel):
    memory: AgentMemory
    actions: list[AgentDecision] = Field(default_factory=list)


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


class CustomModelConfig(BaseModel):
    id: str
    name: str
    model: str
    base_url: str
    api_type: LLMApiType = "chat_completions"
    description: str = "用户自定义模型"


class ModelConfig(BaseModel):
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_api_type: LLMApiType = "chat_completions"
    llm_timeout_seconds: int = 30
    model_availability: dict[str, bool] = Field(
        default_factory=lambda: {
            "deepseek": True,
            "gpt": False,
            "qwen": False,
            "grok": False,
        }
    )
    custom_models: list[CustomModelConfig] = Field(default_factory=list)
    asr_provider: ASRProvider = "funasr_streaming"
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    funasr_model: str = "paraformer-zh-streaming"
    funasr_device: str = "cpu"
    oci_speech_region: str = ""
    oci_speech_compartment_id: str = ""
    oci_speech_language: str = "zh-CN"
    oci_speech_profile: str = "DEFAULT"
    oci_speech_config_file: str = "/root/.oci/config"
    oci_speech_realtime_endpoint: str = ""
    speaker_threshold: float = 0.30
    energy_threshold: float = 0.008
    silence_duration_ms: int = 800
    min_speech_duration_ms: int = 1000


class SummaryResponse(BaseModel):
    summary: str


class ConnectionTestResponse(BaseModel):
    ok: bool
    provider: str
    model: str
    message: str
    latency_ms: int = 0
