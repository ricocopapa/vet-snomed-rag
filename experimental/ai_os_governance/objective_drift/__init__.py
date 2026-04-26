"""Objective Drift 자동 감지 PoC — AI OS Step 3 (G-6).

Sentence-Transformer 임베딩 기반 코사인 유사도로
사용자 원본 의도와 에이전트 Task Definition 간 drift_score 측정.
임계값 초과 시 HITL 알림 트리거.
"""
from .embeddings import embed, cosine_similarity
from .fingerprint import save_intent, load_intent
from .monitor import check_drift, DRIFT_THRESHOLD
from .alert import emit_alert

__version__ = "0.1.0"
__all__ = [
    "embed",
    "cosine_similarity",
    "save_intent",
    "load_intent",
    "check_drift",
    "DRIFT_THRESHOLD",
    "emit_alert",
]
