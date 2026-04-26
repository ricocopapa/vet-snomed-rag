"""sentence-transformers 임베딩 유틸. 한국어·영어 혼용 지원."""
from __future__ import annotations

import numpy as np

_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed(text: str) -> np.ndarray:
    if not text or not text.strip():
        raise ValueError("embed: empty text")
    model = get_model()
    return model.encode(text, normalize_embeddings=True)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a)
    b = np.asarray(b)
    return float(np.dot(a, b))
