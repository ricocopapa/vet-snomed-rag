"""에이전트 Task Definition 디스패치 전 drift_score 계산.

drift_score = 1 - cosine_similarity(intent_vec, task_vec)
- 0.0 ~ 0.3: 정상 (의도와 정렬)
- > 0.3:    ALERT — HITL 트리거 권장
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .embeddings import cosine_similarity, embed
from .fingerprint import load_intent

DRIFT_LOG = Path.home() / "claude-cowork" / ".ai_os" / "drift_log.jsonl"

# Calibrated 2026-04-24 with paraphrase-multilingual-mpnet-base-v2:
#   NORMAL drift range : 0.372 ~ 0.668 (mean 0.512, n=5)
#   ANOMALY drift range: 0.667 ~ 0.852 (mean 0.765, n=5)
# Boundary overlap due to multilingual model's limited Korean short-text discrimination.
# Tradeoff: 0.65 → 1 FP / 0 FN (보수적, Enterprise 권장)
#           0.70 → 0 FP / 1 FN (관대)
# 한국어 특화 모델(jhgan/ko-sroberta-multitask) 또는 긴 문장 컨텍스트로 개선 가능.
DRIFT_THRESHOLD = 0.65


def check_drift(session_id: str, task_description: str) -> dict:
    intent = load_intent(session_id)
    intent_vec = np.array(intent["embedding"])
    task_vec = embed(task_description)
    sim = cosine_similarity(intent_vec, task_vec)
    drift_score = 1.0 - sim
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "user_intent": intent["user_intent"],
        "task_description": task_description,
        "similarity": sim,
        "drift_score": drift_score,
        "threshold": DRIFT_THRESHOLD,
        "alert": drift_score > DRIFT_THRESHOLD,
    }
    DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DRIFT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event
