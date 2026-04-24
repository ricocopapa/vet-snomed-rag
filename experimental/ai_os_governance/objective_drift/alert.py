"""drift_score 임계값 초과 시 HITL 알림."""
from __future__ import annotations

import sys


def emit_alert(event: dict) -> None:
    if not event.get("alert"):
        return
    msg = (
        "\n[OBJECTIVE DRIFT ALERT]\n"
        f"  session    : {event['session_id']}\n"
        f"  drift_score: {event['drift_score']:.3f} (threshold={event['threshold']})\n"
        f"  intent     : {event['user_intent'][:120]}\n"
        f"  task       : {event['task_description'][:120]}\n"
        "  → HITL 승인 필요. 작업 일시 중단 권장.\n"
    )
    print(msg, file=sys.stderr)
