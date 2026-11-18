from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    AgentMemory,
    AgentRunResponse,
    ExportResponse,
    ConnectionTestResponse,
    MeetingCreate,
    Message,
    ModelConfig,
    Participant,
    ParticipantCreate,
    ParticipantUpdate,
    Session,
    SessionCreate,
    SessionSummary,
    SpeakerBindRequest,
    SpeakerBindResponse,
    SpeakerCorrectionRequest,
    SuggestReplyRequest,
    SuggestReplyResponse,
    SummaryResponse,
)
from app.services.asr import asr_service
from app.services.audio import audio_service
from app.services.context_manager import context_manager
from app.services.llm_client import llm_client
from app.services.runtime_config import runtime_config
from app.services.speaker import speaker_service
from app.services.storage import storage

app = FastAPI(title="AI Meeting Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_participants() -> list[Participant]:
    return [Participant(**item) for item in storage.read_json(storage.participants_file, [])]


def save_participants(participants: list[Participant]) -> None:
    storage.write_json(storage.participants_file, [p.model_dump() for p in participants])


def load_session(session_id: str) -> Session:
    path = storage.session_file(session_id)
    data = storage.read_json(path)
    if not data:
        raise HTTPException(status_code=404, detail="会话不存在")
    return Session(**data)


def save_session(session: Session) -> None:
    storage.write_json(storage.session_file(session.id), session.model_dump())


def create_session_from_title_goal(title: str, goal: str) -> Session:
    session = Session(
        id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
        title=title,
        goal=goal,
        started_at=now_iso(),
    )
    save_session(session)
    return session


def participant_to_message_fields(participant: Participant) -> dict:
    return {
        "participant_id": participant.id,
        "speaker_name": participant.name,
        "role": participant.role,
        "need_reply": participant.need_reply,
    }


async def process_audio_file(session_id: str, file: UploadFile) -> Message:
    session = load_session(session_id)
    message_id = f"message_{uuid4().hex[:10]}"
    audio_dir = storage.session_audio_dir(session_id)
    raw_path = audio_dir / f"{message_id}.webm"
    wav_path = audio_dir / f"{message_id}.wav"

    raw_path.write_bytes(await file.read())
    try:
        audio_service.convert_to_wav(raw_path, wav_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"音频格式无法解析：{exc}") from exc

    text = asr_service.transcribe(str(wav_path))
    if not text:
        raise HTTPException(status_code=400, detail="未识别到有效语音")

    participants = load_participants()
    speaker, score = speaker_service.identify(wav_path, participants)

    if speaker:
        speaker_name = speaker.name
        participant_id = speaker.id
        speaker_identity_id = speaker.id
        role = speaker.role
        need_reply = speaker.need_reply
    else:
        speaker_name = "未知说话人"
        participant_id = None
        speaker_identity_id = f"voice_{uuid4().hex[:8]}"
        role = "unknown"
        need_reply = False

    suggestion = None
    if need_reply:
        history = "\n".join([f"{m.speaker_name}: {m.text}" for m in session.messages[-8:]])
        suggestion = await llm_client.suggest_reply(session.goal, history, text)

    message = Message(
        id=message_id,
        session_id=session_id,
        participant_id=participant_id,
        speaker_identity_id=speaker_identity_id,
        speaker_name=speaker_name,
        role=role,  # type: ignore[arg-type]
        text=text,
        audio_file=str(wav_path),
        speaker_score=score,
        need_reply=need_reply,
        ai_suggestion=suggestion,
        created_at=now_iso(),
    )
    session.messages.append(message)
    save_session(session)
    context_manager.update_with_message(session, message)
    return message


def bind_speaker_identity(session_id: str, speaker_identity_id: str, payload: SpeakerBindRequest) -> SpeakerBindResponse:
    session = load_session(session_id)
    updated_count = 0
    for index, message in enumerate(session.messages):
        identity = message.speaker_identity_id or message.participant_id or f"voice_{message.id}"
        if identity != speaker_identity_id:
            continue
        data = message.model_dump()
        data["speaker_identity_id"] = speaker_identity_id
        data["speaker_name"] = payload.speaker_name
        data["role"] = payload.role
        data["need_reply"] = payload.need_reply
        data["corrected"] = True
        session.messages[index] = Message(**data)
        updated_count += 1

    if updated_count == 0:
        raise HTTPException(status_code=404, detail="识别个体 ID 不存在")

    save_session(session)
    context_manager.rebuild(session)
    return SpeakerBindResponse(
        speaker_identity_id=speaker_identity_id,
        speaker_name=payload.speaker_name,
        updated_count=updated_count,
    )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/participants", response_model=list[Participant])
def get_participants() -> list[Participant]:
    return load_participants()


@app.get("/api/config", response_model=ModelConfig)
def get_config() -> ModelConfig:
    return runtime_config.get()


@app.put("/api/config", response_model=ModelConfig)
def update_config(payload: ModelConfig) -> ModelConfig:
    return runtime_config.save(payload)


@app.post("/api/config/test", response_model=ConnectionTestResponse)
async def test_config_connection(payload: ModelConfig | None = Body(default=None)) -> ConnectionTestResponse:
    config = payload or runtime_config.get()
    result = await llm_client.test_connection(config)
    return ConnectionTestResponse(**result)


@app.post("/api/meetings", response_model=Session)
def create_meeting(payload: MeetingCreate) -> Session:
    title = f"{payload.customer_name.strip()}会谈"
    return create_session_from_title_goal(title, payload.goal)


@app.get("/api/meetings", response_model=list[SessionSummary])
def list_meetings() -> list[SessionSummary]:
    return list_sessions()


@app.get("/api/meetings/{meeting_id}", response_model=Session)
def get_meeting(meeting_id: str) -> Session:
    return load_session(meeting_id)


@app.post("/api/meetings/{meeting_id}/audio", response_model=Message)
async def upload_meeting_audio(meeting_id: str, file: UploadFile = File(...)) -> Message:
    return await process_audio_file(meeting_id, file)


@app.put("/api/meetings/{meeting_id}/speakers/{speaker_identity_id}", response_model=SpeakerBindResponse)
def bind_meeting_speaker(
    meeting_id: str,
    speaker_identity_id: str,
    payload: SpeakerBindRequest,
) -> SpeakerBindResponse:
    return bind_speaker_identity(meeting_id, speaker_identity_id, payload)


@app.post("/api/meetings/{meeting_id}/end", response_model=Session)
def end_meeting(meeting_id: str) -> Session:
    session = load_session(meeting_id)
    session.ended_at = session.ended_at or now_iso()
    save_session(session)
    return session


@app.post("/api/meetings/{meeting_id}/summary", response_model=SummaryResponse)
async def summarize_meeting(meeting_id: str) -> SummaryResponse:
    return await summarize_session(meeting_id)


@app.post("/api/meetings/{meeting_id}/export", response_model=ExportResponse)
def export_meeting(meeting_id: str) -> ExportResponse:
    data = export_session(meeting_id)
    return ExportResponse(**data)


@app.get("/api/meetings/{meeting_id}/agent/memory", response_model=AgentMemory)
def get_agent_memory(meeting_id: str) -> AgentMemory:
    session = load_session(meeting_id)
    return context_manager.load_memory(session.id, session.goal)


@app.post("/api/meetings/{meeting_id}/agent/run", response_model=AgentRunResponse)
def run_meeting_agent(meeting_id: str) -> AgentRunResponse:
    session = load_session(meeting_id)
    memory = context_manager.rebuild(session)
    return AgentRunResponse(memory=memory, actions=memory.decisions[-20:])


@app.post("/api/participants", response_model=Participant)
def create_participant(payload: ParticipantCreate) -> Participant:
    participant_id = f"participant_{uuid4().hex[:8]}"
    color = "yellow" if payload.role == "self" else "white" if payload.role == "customer" else "gray"
    participant = Participant(
        id=participant_id,
        name=payload.name,
        role=payload.role,
        need_reply=payload.need_reply,
        display_color=color,
        remark=payload.remark,
    )
    participants = load_participants()
    participants.append(participant)
    save_participants(participants)
    return participant


@app.put("/api/participants/{participant_id}", response_model=Participant)
def update_participant(participant_id: str, payload: ParticipantUpdate) -> Participant:
    participants = load_participants()
    for index, participant in enumerate(participants):
        if participant.id == participant_id:
            data = participant.model_dump()
            for key, value in payload.model_dump(exclude_unset=True).items():
                data[key] = value
            if data.get("role") == "self":
                data["display_color"] = "yellow"
            elif data.get("role") == "customer":
                data["display_color"] = "white"
            else:
                data["display_color"] = "gray"
            updated = Participant(**data)
            participants[index] = updated
            save_participants(participants)
            return updated
    raise HTTPException(status_code=404, detail="参会人不存在")


@app.post("/api/participants/{participant_id}/voiceprint", response_model=Participant)
async def upload_voiceprint(participant_id: str, file: UploadFile = File(...)) -> Participant:
    participants = load_participants()
    participant = next((p for p in participants if p.id == participant_id), None)
    if not participant:
        raise HTTPException(status_code=404, detail="参会人不存在")

    raw_path = storage.participants_dir / f"{participant_id}_sample.webm"
    wav_path = storage.participants_dir / f"{participant_id}_sample.wav"
    embedding_path = storage.participants_dir / f"{participant_id}.embedding.npy"

    raw_path.write_bytes(await file.read())
    audio_service.convert_to_wav(raw_path, wav_path)
    speaker_service.save_embedding(wav_path, embedding_path)

    participant.sample_audio_file = str(wav_path)
    participant.voiceprint_file = str(embedding_path)

    for index, item in enumerate(participants):
        if item.id == participant_id:
            participants[index] = participant
            break
    save_participants(participants)
    return participant


@app.post("/api/sessions", response_model=Session)
def create_session(payload: SessionCreate) -> Session:
    return create_session_from_title_goal(payload.title, payload.goal)


@app.get("/api/sessions", response_model=list[SessionSummary])
def list_sessions() -> list[SessionSummary]:
    sessions: list[SessionSummary] = []
    for path in sorted(storage.sessions_dir.glob("*.json"), reverse=True):
        if path.name.endswith(".memory.json"):
            continue
        data = storage.read_json(path)
        if not data:
            continue
        session = Session(**data)
        sessions.append(
            SessionSummary(
                id=session.id,
                title=session.title,
                goal=session.goal,
                started_at=session.started_at,
                ended_at=session.ended_at,
                message_count=len(session.messages),
                has_summary=bool(session.summary),
            )
        )
    return sessions


@app.get("/api/sessions/{session_id}", response_model=Session)
def get_session(session_id: str) -> Session:
    return load_session(session_id)


@app.put("/api/sessions/{session_id}/messages/{message_id}/speaker", response_model=Message)
async def correct_message_speaker(
    session_id: str,
    message_id: str,
    payload: SpeakerCorrectionRequest,
) -> Message:
    session = load_session(session_id)
    participants = load_participants()
    participant = None
    if payload.participant_id:
        participant = next((p for p in participants if p.id == payload.participant_id), None)
        if not participant:
            raise HTTPException(status_code=404, detail="参会人不存在")

    for index, message in enumerate(session.messages):
        if message.id != message_id:
            continue

        data = message.model_dump()
        if participant:
            data.update(participant_to_message_fields(participant))
        else:
            data["participant_id"] = None
            data["speaker_name"] = payload.speaker_name or "未知说话人"
            data["role"] = payload.role or "unknown"
            data["need_reply"] = False
        data["corrected"] = True

        updated = Message(**data)
        if updated.need_reply and not updated.ai_suggestion:
            history = "\n".join([f"{m.speaker_name}: {m.text}" for m in session.messages[max(0, index - 8):index]])
            updated.ai_suggestion = await llm_client.suggest_reply(session.goal, history, updated.text)

        session.messages[index] = updated
        save_session(session)
        return updated

    raise HTTPException(status_code=404, detail="消息不存在")


@app.post("/api/audio/process", response_model=Message)
async def process_audio(
    session_id: str = Form(...),
    file: UploadFile = File(...),
) -> Message:
    return await process_audio_file(session_id, file)


@app.post("/api/ai/suggest-reply", response_model=SuggestReplyResponse)
async def suggest_reply(payload: SuggestReplyRequest) -> SuggestReplyResponse:
    suggestion = await llm_client.suggest_reply(
        payload.meeting_goal,
        payload.conversation_history,
        payload.latest_customer_message,
    )
    return SuggestReplyResponse(suggestion=suggestion)


@app.post("/api/sessions/{session_id}/summary", response_model=SummaryResponse)
async def summarize_session(session_id: str) -> SummaryResponse:
    session = load_session(session_id)
    if not session.messages:
        raise HTTPException(status_code=400, detail="当前会话还没有可总结的内容")

    history = "\n".join([f"{m.speaker_name}: {m.text}" for m in session.messages])
    summary = await llm_client.summarize(session.goal, history)
    session.summary = summary
    session.ended_at = session.ended_at or now_iso()
    save_session(session)
    return SummaryResponse(summary=summary)


@app.post("/api/sessions/{session_id}/export", response_model=ExportResponse)
def export_session(session_id: str) -> dict:
    session = load_session(session_id)
    lines = [
        f"# {session.title}",
        "",
        f"- 会晤目标：{session.goal}",
        f"- 开始时间：{session.started_at}",
        f"- 结束时间：{session.ended_at or ''}",
        "",
        "## 会话记录",
        "",
    ]
    for message in session.messages:
        lines.append(f"### {message.speaker_name}")
        lines.append("")
        lines.append(message.text)
        lines.append("")
        if message.ai_suggestion:
            lines.append(f"> AI 建议：{message.ai_suggestion}")
            lines.append("")

    if session.summary:
        lines.extend(["## 会后总结", "", session.summary, ""])

    export_path = storage.exports_dir / f"{session_id}.md"
    export_path.write_text("\n".join(lines), encoding="utf-8")
    return {"file": str(export_path)}
