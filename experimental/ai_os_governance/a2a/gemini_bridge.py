"""A2A Claude ↔ Gemini 브릿지 — Step 5 §7.4 PoC.

Claude reviewer가 보낸 A2A request를 Gemini가 독립 감사 → A2A report로 응답.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# vet-snomed-rag .env 로드 (GOOGLE_API_KEY)
_ENV_PATH = Path.home() / "claude-cowork" / "07_Projects" / "vet-snomed-rag" / ".env"
if _ENV_PATH.exists():
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, str(Path.home() / "claude-cowork" / "tools"))
from a2a.lifecycle import send_message, receive_messages, archive_message  # noqa: E402

GEMINI_MODEL = "gemini-2.5-flash"  # 빠른 응답, 비용 효율


def gemini_independent_audit(audit_request_payload: dict) -> dict:
    """Gemini로 독립 감사 수행. payload: {task, target_doc, audit_dimensions, target_text}"""
    from google import genai

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    target = audit_request_payload.get("target_text", "(target 텍스트 미제공)")
    dimensions = audit_request_payload.get("audit_dimensions", [])

    prompt = f"""당신은 독립 감사관입니다. Claude reviewer와 별개로 다음 텍스트를 감사하세요.

[감사 대상 텍스트]
{target[:2000]}

[감사 축]
{', '.join(dimensions)}

다음 JSON 스키마로만 응답하세요 (다른 텍스트 금지):
{{
  "audit_result": "PASS / PASS_WITH_NOTE / FAIL",
  "notes": ["...", "..."],
  "consensus_estimate": 0.0 ~ 1.0
}}"""

    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    text = response.text.strip()

    # JSON 추출 (markdown 코드블록 제거)
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(line for line in lines if not line.startswith("```"))

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "audit_result": "PARSE_ERROR",
            "notes": [f"Gemini 응답 JSON 파싱 실패: {text[:200]}"],
            "consensus_estimate": 0.0,
            "raw_response": text,
        }


def run_bridge_e2e(target_doc_path: str | Path, audit_dimensions: list[str]) -> dict:
    """E2E 브릿지 시나리오: Claude reviewer → A2A → Gemini → A2A report."""
    target_path = Path(target_doc_path)
    if not target_path.exists():
        raise FileNotFoundError(f"감사 대상 파일 없음: {target_path}")

    target_text = target_path.read_text(encoding="utf-8")[:5000]
    correlation_id = f"bridge_e2e_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"

    # 1) Claude reviewer → Gemini judge (request)
    req_path = send_message(
        sender="claude_reviewer@v2.1",
        receiver="gemini_independent_judge",
        intent="request",
        payload={
            "task": "독립 감사",
            "target_doc": str(target_path.name),
            "audit_dimensions": audit_dimensions,
            "target_text": target_text,
        },
        deadline_iso=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        correlation_id=correlation_id,
    )

    # 2) Gemini가 inbox에서 메시지 수신
    inbox = receive_messages("gemini_independent_judge")
    target_msg = next((m for m in inbox if m["correlation_id"] == correlation_id), None)
    if not target_msg:
        raise RuntimeError("Gemini inbox에 메시지 도착 안 함")

    # 3) Gemini 실 API 호출
    audit_result = gemini_independent_audit(target_msg["payload"])

    # 4) Gemini → Claude reviewer (report)
    rep_path = send_message(
        sender="gemini_independent_judge",
        receiver="claude_reviewer@v2.1",
        intent="report",
        payload=audit_result,
        deadline_iso=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        correlation_id=correlation_id,
    )

    # 5) archive
    archive_message(target_msg["message_id"], "gemini_independent_judge")

    return {
        "correlation_id": correlation_id,
        "request_path": str(req_path),
        "report_path": str(rep_path),
        "audit_result": audit_result,
        "model": GEMINI_MODEL,
    }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else (
        Path.home() / "claude-cowork" / "05_Output_Workspace" /
        "Career_Transition" / "20260423_Resume_v2_final_2page.md"
    )
    dims = ["수치 일치", "Anti-Sycophancy", "JD 키워드 매칭"]
    print(f"[BRIDGE] target = {target}")
    print(f"[BRIDGE] model  = {GEMINI_MODEL}")
    result = run_bridge_e2e(target, dims)
    print(json.dumps(result, ensure_ascii=False, indent=2))
