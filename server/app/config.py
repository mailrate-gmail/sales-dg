from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    data_dir: str = "/app/data"

    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    speaker_threshold: float = 0.70
    energy_threshold: float = 0.02
    silence_duration_ms: int = 800
    min_speech_duration_ms: int = 1000

    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
