import json
from pathlib import Path
from typing import Any

from app.config import settings


class StorageService:
    def __init__(self) -> None:
        self.base_dir = Path(settings.data_dir)
        self.participants_dir = self.base_dir / "participants"
        self.sessions_dir = self.base_dir / "sessions"
        self.audio_dir = self.base_dir / "audio"
        self.exports_dir = self.base_dir / "exports"
        self.participants_file = self.base_dir / "participants.json"
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for path in [self.base_dir, self.participants_dir, self.sessions_dir, self.audio_dir, self.exports_dir]:
            path.mkdir(parents=True, exist_ok=True)
        if not self.participants_file.exists():
            self.write_json(self.participants_file, [])

    def read_json(self, path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def session_file(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def session_audio_dir(self, session_id: str) -> Path:
        path = self.audio_dir / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path


storage = StorageService()
