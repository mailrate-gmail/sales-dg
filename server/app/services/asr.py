from functools import lru_cache
from typing import TypedDict

from faster_whisper import WhisperModel

from app.config import settings


class TranscribeSegment(TypedDict):
    text: str
    start: float
    end: float


@lru_cache(maxsize=1)
def get_model() -> WhisperModel:
    return WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


class ASRService:
    def transcribe_segments(self, audio_path: str) -> list[TranscribeSegment]:
        model = get_model()
        segments, _ = model.transcribe(
            audio_path,
            language="zh",
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": settings.silence_duration_ms,
                "speech_pad_ms": 200,
            },
            condition_on_previous_text=False,
            beam_size=5,
        )
        results: list[TranscribeSegment] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                results.append({"text": text, "start": float(segment.start), "end": float(segment.end)})
        return results

    def transcribe(self, audio_path: str) -> str:
        text_parts = [segment["text"] for segment in self.transcribe_segments(audio_path)]
        return "".join(text_parts).strip()


asr_service = ASRService()
