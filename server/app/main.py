from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    Message,
    Participant,
    ParticipantCreate,
    ParticipantUpdate,
    Session,
    SessionCreate,
    SuggestReplyRequest,
    SuggestReplyResponse,
)
from app.services.asr import asr_service
from app.services.audio import audio_service
from app.services.llm_client import llm_client
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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/participants", response_model=list[Participant])
def get_participants() -> list[Participant]:
    return load_participants()


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
    session = Session(
        id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
        title=payload.title,
        goal=payload.goal,
        started_at=now_iso(),
    )
    save_session(session)
    return session


@app.get("/api/sessions/{session_id}", response_model=Session)
def get_session(session_id: str) -> Session:
    return load_session(session_id)


@app.post("/api/audio/process", response_model=Message)
async def process_audio(
    session_id: str = Form(...),
    file: UploadFile = File(...),
) -> Message:
    session = load_session(session_id)
    message_id = f"message_{uuid4().hex[:10]}"
    audio_dir = storage.session_audio_dir(session_id)
    raw_path = audio_dir / f"{message_id}.webm"
    wav_path = audio_dir / f"{message_id}.wav"

    raw_path.write_bytes(await file.read())
    audio_service.convert_to_wav(raw_path, wav_path)

    text = asr_service.transcribe(str(wav_path))
    if not text:
        raise HTTPException(status_code=400, detail="未识别到有效语音")

    participants = load_participants()
    speaker, score = speaker_service.identify(wav_path, participants)

    if speaker:
        speaker_name = speaker.name
        participant_id = speaker.id
        role = speaker.role
        need_reply = speaker.need_reply
    else:
        speaker_name = "未知说话人"
        participant_id = None
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
    return message


@app.post("/api/ai/suggest-reply", response_model=SuggestReplyResponse)
async def suggest_reply(payload: SuggestReplyRequest) -> SuggestReplyResponse:
    suggestion = await llm_client.suggest_reply(
        payload.meeting_goal,
        payload.conversation_history,
        payload.latest_customer_message,
    )
    return SuggestReplyResponse(suggestion=suggestion)


@app.post("/api/sessions/{session_id}/export")
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

    export_path = storage.exports_dir / f"{session_id}.md"
    export_path.write_text("\n".join(lines), encoding="utf-8")
    return {"file": str(export_path)}
