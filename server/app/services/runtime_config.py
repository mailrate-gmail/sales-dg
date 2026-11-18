import json
from pathlib import Path

from app.config import settings
from app.models import ModelConfig


class RuntimeConfigService:
    def __init__(self) -> None:
        self.path = Path(settings.data_dir) / "model_config.json"

    def default_config(self) -> ModelConfig:
        return ModelConfig(
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model,
            llm_base_url=settings.llm_base_url,
            llm_api_key=settings.llm_api_key,
            llm_timeout_seconds=settings.llm_timeout_seconds,
            whisper_model=settings.whisper_model,
            whisper_device=settings.whisper_device,
            whisper_compute_type=settings.whisper_compute_type,
            speaker_threshold=settings.speaker_threshold,
            energy_threshold=settings.energy_threshold,
            silence_duration_ms=settings.silence_duration_ms,
            min_speech_duration_ms=settings.min_speech_duration_ms,
        )

    def get(self) -> ModelConfig:
        if not self.path.exists():
            return self.default_config()
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return self.default_config().model_copy(update=data)

    def save(self, config: ModelConfig) -> ModelConfig:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)
        return config


runtime_config = RuntimeConfigService()
