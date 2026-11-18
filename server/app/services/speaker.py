from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from speechbrain.inference.speaker import EncoderClassifier

from app.config import settings
from app.models import Participant


@lru_cache(maxsize=1)
def get_classifier() -> EncoderClassifier:
    return EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb")


class SpeakerService:
    def create_embedding(self, wav_path: Path) -> np.ndarray:
        classifier = get_classifier()
        signal = classifier.load_audio(str(wav_path))
        embedding = classifier.encode_batch(signal).squeeze().detach().cpu().numpy()
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

        if best_score < settings.speaker_threshold:
            return None, float(best_score)

        return best_participant, float(best_score)

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a_tensor = torch.tensor(a).flatten().float()
        b_tensor = torch.tensor(b).flatten().float()
        return torch.nn.functional.cosine_similarity(a_tensor, b_tensor, dim=0).item()


speaker_service = SpeakerService()
