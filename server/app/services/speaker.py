import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
from speechbrain.inference.speaker import EncoderClassifier

from app.models import Participant
from app.services.runtime_config import runtime_config

# 分类器为全局共享实例，多线程推理时串行化 encode_batch，避免内部状态竞争。
_classifier_lock = threading.Lock()


@lru_cache(maxsize=1)
def get_classifier() -> EncoderClassifier:
    # 固定 savedir，避免每次从 HuggingFace 重复拉取/校验模型。
    # /root/.cache/huggingface 在 docker-compose.yml 中挂载到 hf_cache/，容器重建不丢失。
    savedir = os.getenv(
        "SPEAKER_MODEL_SAVEDIR",
        "/root/.cache/huggingface/speechbrain/spkrec-ecapa-voxceleb",
    )
    return EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=savedir,
    )


class SpeakerService:
    def create_embedding(self, wav_path: Path) -> np.ndarray:
        classifier = get_classifier()
        signal = classifier.load_audio(str(wav_path))
        with _classifier_lock:
            embedding = classifier.encode_batch(signal).squeeze().detach().cpu().numpy()
        # ECAPA 向量归一化后存储：相似度更稳定，也便于后续做向量检索。
        norm = float(np.linalg.norm(embedding))
        if norm > 0:
            embedding = embedding / norm
        return embedding

    def save_embedding(self, wav_path: Path, embedding_path: Path) -> None:
        embedding = self.create_embedding(wav_path)
        embedding_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(embedding_path, embedding)

    def identify(self, wav_path: Path, participants: list[Participant]) -> tuple[Optional[Participant], float]:
        available = [p for p in participants if p.voiceprint_file and Path(p.voiceprint_file).exists()]
        if not available:
            return None, 0.0

        current = self.create_embedding(wav_path)
        best_participant: Optional[Participant] = None
        best_score = -1.0

        for participant in available:
            saved = np.load(participant.voiceprint_file)  # type: ignore[arg-type]
            score = self.cosine_similarity(current, saved)
            if score > best_score:
                best_score = score
                best_participant = participant

        if best_score < runtime_config.get().speaker_threshold:
            return None, float(best_score)

        return best_participant, float(best_score)

    def identify_embedding(self, wav_path: Path, embedding_files: dict[str, Path], threshold: float) -> tuple[Optional[str], float, np.ndarray]:
        current = self.create_embedding(wav_path)
        best_id: Optional[str] = None
        best_score = -1.0

        for speaker_id, embedding_path in embedding_files.items():
            if not embedding_path.exists():
                continue
            saved = np.load(embedding_path)
            score = self.cosine_similarity(current, saved)
            if score > best_score:
                best_score = score
                best_id = speaker_id

        if best_id is None or best_score < threshold:
            return None, float(max(best_score, 0.0)), current
        return best_id, float(best_score), current

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        # 手动归一化后点积即为 cosine；相比 torch 实现更轻，且对未归一化的旧 embedding 文件兼容。
        av = np.asarray(a, dtype=np.float64).flatten()
        bv = np.asarray(b, dtype=np.float64).flatten()
        denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
        if denom == 0:
            return 0.0
        return float(np.dot(av, bv) / denom)


speaker_service = SpeakerService()
