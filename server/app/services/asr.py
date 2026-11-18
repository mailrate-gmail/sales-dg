from functools import lru_cache

from faster_whisper import WhisperModel

from app.config import settings


@lru_cache(maxsize=1)
def get_model() -> WhisperModel:
    return WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


class ASRService:
    def transcribe(self, audio_path: str) -> str:
        model = get_model()
        segments, _ = model.transcribe(audio_path, language="zh", vad_filter=True)
        text_parts = [segment.text.strip() for segment in segments if segment.text.strip()]
        return "".join(text_parts).strip()


asr_service = ASRService()
