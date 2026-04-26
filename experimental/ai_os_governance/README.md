# Experimental — AI OS Governance Layer (v2.3 Roadmap)

> **상태**: 🔬 **Experimental PoC** (v0.1.0, 2026-04-24).
> 본 폴더는 vet-snomed-rag 코어와 독립된 **AI OS 거버넌스 PoC 3종** (Observability + IAM-Lite + A2A)이다.
> 본격 통합 여부는 v2.3 마일스톤 결정 시점에 평가한다.

---

## 목적

LG CNS JD 우대 3.2 ("Evaluation, Observability, Guardrails/PII") 정면 매칭 + 2026 hot topic
선행 자산 확보. 핸드오프 §5·§6·§7 Step 3·4·5 PoC 구현.

---

## 구성

| 디렉토리 | PoC | 핸드오프 출처 | 상태 |
|---|---|---|---|
| `objective_drift/` | Sentence-Transformer cosine drift 감지 + HITL | §5 (Step 3) | 캘리브레이션 9/10 (90%) |
| `pii_masking/` | 정규식 4종 PII 자동 마스킹 + round-trip | §6 (Step 4 일부) | pytest 5/5 PASS |
| `a2a/` | JSON Schema + Mailbox + Claude↔Gemini 브릿지 | §7 (Step 5) | pytest 8/8 PASS, gemini-2.5-flash 실호출 PASS |

---

## Quick Start

### 의존성
프로젝트 루트의 `.venv`로 충분 (sentence-transformers, jsonschema, google-genai 모두 설치됨).

### 테스트 실행
```bash
cd ~/claude-cowork/07_Projects/vet-snomed-rag

# PII 마스킹 (5/5 PASS)
PYTHONPATH=experimental/ai_os_governance .venv/bin/python -m pytest \
  experimental/ai_os_governance/pii_masking/tests/ -v

# A2A JSON Schema 검증 (8/8 PASS)
PYTHONPATH=experimental/ai_os_governance .venv/bin/python -m pytest \
  experimental/ai_os_governance/a2a/tests/ -v

# Objective Drift 캘리브레이션 (실측 모델 로드, ~470MB 다운로드)
PYTHONPATH=experimental/ai_os_governance .venv/bin/python -c \
  "from objective_drift import save_intent, check_drift; \
   save_intent('demo','이력서 수정'); \
   print(check_drift('demo','§3.2 격상'))"

# Claude ↔ Gemini A2A 브릿지 E2E (GOOGLE_API_KEY 필요)
PYTHONPATH=experimental/ai_os_governance .venv/bin/python \
  experimental/ai_os_governance/a2a/gemini_bridge.py \
  README.md
```

---

## v2.3 통합 평가 기준

다음 조건 충족 시 v2.3에서 정식 모듈로 승격:
1. **Objective Drift**: 한국어 특화 모델(`jhgan/ko-sroberta-multitask`) 캘리브레이션 100% 달성
2. **IAM-Lite**: 5+ Sub Agent 실 운영 + Audit Trail 100건+ 누적
3. **A2A**: Claude ↔ Gemini cross-audit consensus_score ≥ 0.85 (10건 평균)

---

## 한계 (정직한 공개)

- 본 PoC는 **AI OS 자체 거버넌스 자산**이며 vet-snomed-rag SNOMED 인코딩 코어 기능과 직접 결합하지 않는다.
- 운영 환경 적용 전 보안 감사·로드 테스트·다중 사용자 권한 분리 추가 필요.
- Objective Drift는 다국어 임베딩 한계로 정상/이상 boundary overlap 존재 (drift_score ~0.667).

---

## 관련 Issue

- [#8](https://github.com/ricocopapa/vet-snomed-rag/issues/8) Add Objective Drift Detection (Observability layer)
- [#9](https://github.com/ricocopapa/vet-snomed-rag/issues/9) Add IAM-Lite Permission Scope + PII Masking
- [#10](https://github.com/ricocopapa/vet-snomed-rag/issues/10) Add A2A Protocol Mailbox + Cross-Vendor Bridge PoC
- PR: [#7](https://github.com/ricocopapa/vet-snomed-rag/pull/7)

---

*작성: 2026-04-24 | 핸드오프 §5·§6·§7 Step 3·4·5 통합 | v0.1.0 Experimental*
