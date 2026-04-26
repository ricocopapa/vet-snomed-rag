"""A2A 메시지 라이프사이클 관리.

inbox → processing → outbox/archive (성공) | dead_letter (retry > 3)
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

A2A_ROOT = Path.home() / "claude-cowork" / ".a2a"
INBOX = A2A_ROOT / "inbox"
OUTBOX = A2A_ROOT / "outbox"
ARCHIVE = A2A_ROOT / "archive"
DEAD_LETTER = A2A_ROOT / "dead_letter"
SCHEMA_FILE = A2A_ROOT / "schema" / "a2a_message.schema.json"

MAX_RETRY = 3


def _ensure_dirs():
    for p in (INBOX, OUTBOX, ARCHIVE, DEAD_LETTER, SCHEMA_FILE.parent):
        p.mkdir(parents=True, exist_ok=True)


def send_message(
    sender: str,
    receiver: str,
    intent: str,
    payload: dict,
    deadline_iso: str,
    correlation_id: str | None = None,
) -> Path:
    """outbox에 메시지 작성 + receiver inbox에 복사."""
    _ensure_dirs()
    msg = {
        "message_id": str(uuid.uuid4()),
        "sender": sender,
        "receiver": receiver,
        "intent": intent,
        "payload": payload,
        "deadline": deadline_iso,
        "retry_count": 0,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    fname = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{msg['message_id']}.json"
    out_path = OUTBOX / fname
    out_path.write_text(json.dumps(msg, ensure_ascii=False, indent=2), encoding="utf-8")

    receiver_inbox = INBOX / receiver
    receiver_inbox.mkdir(parents=True, exist_ok=True)
    shutil.copy(out_path, receiver_inbox / fname)
    return out_path


def receive_messages(receiver: str) -> list[dict]:
    """receiver inbox 메시지 일괄 로드."""
    _ensure_dirs()
    receiver_inbox = INBOX / receiver
    if not receiver_inbox.exists():
        return []
    msgs = []
    for p in sorted(receiver_inbox.glob("*.json")):
        msgs.append(json.loads(p.read_text(encoding="utf-8")))
    return msgs


def archive_message(message_id: str, receiver: str) -> Path | None:
    """처리 완료 메시지를 archive로 이동."""
    _ensure_dirs()
    receiver_inbox = INBOX / receiver
    for p in receiver_inbox.glob(f"*_{message_id}.json"):
        dest = ARCHIVE / p.name
        shutil.move(str(p), dest)
        return dest
    return None


def fail_message(message_id: str, receiver: str, reason: str) -> Path | None:
    """실패 시 retry_count 증가, MAX 초과 시 dead_letter 이동."""
    _ensure_dirs()
    receiver_inbox = INBOX / receiver
    for p in receiver_inbox.glob(f"*_{message_id}.json"):
        msg = json.loads(p.read_text(encoding="utf-8"))
        msg["retry_count"] = msg.get("retry_count", 0) + 1
        msg["last_failure_reason"] = reason
        msg["last_failure_ts"] = datetime.now(timezone.utc).isoformat()

        if msg["retry_count"] > MAX_RETRY:
            dest = DEAD_LETTER / p.name
            dest.write_text(json.dumps(msg, ensure_ascii=False, indent=2), encoding="utf-8")
            p.unlink()
            return dest
        else:
            p.write_text(json.dumps(msg, ensure_ascii=False, indent=2), encoding="utf-8")
            return p
    return None
