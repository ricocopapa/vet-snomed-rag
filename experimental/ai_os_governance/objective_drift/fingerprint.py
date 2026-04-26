"""세션 시작 시 user_intent 임베딩 fingerprint 저장/로드."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .embeddings import embed

FINGERPRINT_DIR = Path.home() / "claude-cowork" / ".ai_os" / "intent_fingerprint"


def save_intent(session_id: str, user_intent: str) -> Path:
    FINGERPRINT_DIR.mkdir(parents=True, exist_ok=True)
    vec = embed(user_intent)
    payload = {
        "session_id": session_id,
        "user_intent": user_intent,
        "embedding": vec.tolist(),
        "model": "paraphrase-multilingual-mpnet-base-v2",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    path = FINGERPRINT_DIR / f"{session_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_intent(session_id: str) -> dict:
    path = FINGERPRINT_DIR / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Intent fingerprint not found: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))
