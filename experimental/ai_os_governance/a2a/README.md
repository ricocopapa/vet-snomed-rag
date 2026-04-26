# A2A (Agent-to-Agent) Protocol PoC — AI OS Step 5

> Google A2A Protocol(2025-04 공식)을 Claude 생태계 내에서 실증.
> JSON Schema + 파일시스템 Mailbox + 이종 벤더 브릿지(Claude ↔ Gemini).

---

## 디렉토리 구조

```
~/claude-cowork/.a2a/
├── schema/
│   └── a2a_message.schema.json    # JSON Schema (메시지 검증)
├── inbox/
│   ├── claude_reviewer/
│   └── gemini_independent_judge/
├── outbox/
├── archive/                        # 처리 완료 메시지
├── dead_letter/                    # retry > 3 실패 메시지
├── lifecycle.py                    # 송수신·아카이브·재시도 로직
└── README.md
```

---

## 메시지 스키마 (요약)

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| message_id | uuid | ✅ | 메시지 고유 식별자 |
| sender | string | ✅ | 송신 에이전트 식별자 |
| receiver | string | ✅ | 수신 에이전트 식별자 |
| intent | enum | ✅ | request / response / negotiate / report / error |
| payload | object | ✅ | 본문 (intent별 상이) |
| deadline | datetime | ✅ | 응답 마감 시각 |
| retry_count | int | optional | 재시도 횟수 (default 0) |
| correlation_id | string | optional | 스레드 추적 |
| ts | datetime | optional | 생성 시각 |
| signature | string | optional | 무결성 검증 |

**스키마 파일**: `schema/a2a_message.schema.json`

---

## 사용법

### 1) 메시지 송신 (Claude reviewer → Gemini judge)
```python
import sys
sys.path.insert(0, str(Path.home() / "claude-cowork"))
from a2a.lifecycle import send_message

send_message(
    sender="claude_reviewer@v2.1",
    receiver="gemini_independent_judge",
    intent="request",
    payload={
        "task": "독립 감사",
        "target_doc": "20260423_Resume_v2_final_2page.md",
        "audit_dimensions": ["수치 일치", "Anti-Sycophancy", "JD 키워드"],
    },
    deadline_iso="2026-04-24T15:00:00Z",
)
```

### 2) 메시지 수신
```python
from a2a.lifecycle import receive_messages
msgs = receive_messages("gemini_independent_judge")
```

### 3) 처리 완료 → archive
```python
from a2a.lifecycle import archive_message
archive_message(message_id="...", receiver="gemini_independent_judge")
```

### 4) 실패 시 dead_letter (retry 자동 관리)
```python
from a2a.lifecycle import fail_message
fail_message(message_id="...", receiver="gemini_independent_judge",
             reason="API 호출 timeout 60s")
```

---

## 벤더 간 브릿지 PoC 시나리오

**시나리오**: 동일 산출물(이력서 v2.2)에 대한 이종 LLM 독립 감사 → 일치율 측정

```
Claude reviewer (v2.1)  ─ intent:request ─→ Gemini judge (flash-lite-3.1)
                                                        │
                        ←── intent:report (Gemini 감사 결과) ───
                        │
                        ▼
            교차 비교 (일치 항목 / 불일치 항목)
                        │
                        ▼
            cross_audit_consensus_score 산출
```

---

## LG CNS 면접 답변 연결

면접 QA Q11 답변:

> "MCP 외에 A2A도 들어보셨나요?"
>
> "Google이 2025-04 공식 발표한 Agent-to-Agent Protocol이 MCP(도구 통신)를
> 보완하는 에이전트 간 통신 표준입니다. 저는 이를 Claude 생태계 내에서 실증하기 위해
> JSON Schema 기반 메시지 스키마 + 파일시스템 기반 Mailbox + 벤더 간 브릿지
> (Claude ↔ Gemini 독립 감사) PoC를 구현했습니다. 2026년 현재 국내에서 A2A
> 실무 경험자는 매우 드물며, LG CNS AgenticWorks의 다음 단계 확장에 직접
> 기여 가능한 자산입니다."

---

*PoC 작성: 2026-04-24 | 핸드오프 §7 Step 5 완료 | v0.1.0*
