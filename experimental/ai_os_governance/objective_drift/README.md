# Objective Drift Detection — AI OS Step 3 PoC

> LG CNS JD 우대 3.2 "Observability" 정면 매칭. AI 에이전트의 가장 큰 리스크인
> Objective Drift를 정량 감지 시스템으로 구현.

---

## 아키텍처

```
Session Start
└─ user_intent (원본 요청)
    └─ intent_embedding (768d, paraphrase-multilingual-mpnet-base-v2)
        └─ stored: ~/claude-cowork/.ai_os/intent_fingerprint/{session_id}.json

Each Agent Task Definition
└─ task_description
    └─ task_embedding (768d)
        └─ cosine_similarity(intent, task)
            └─ drift_score = 1 - similarity
                └─ if > 0.3:
                    - log to ~/claude-cowork/.ai_os/drift_log.jsonl
                    - emit_alert() → HITL trigger
                    - pause agent
```

---

## 사용법

### 1) 세션 시작 시 의도 등록
```python
from objective_drift import save_intent
save_intent("session_20260424_001", "이력서를 LG CNS AI PM/PL에 맞게 수정해줘")
```

### 2) 에이전트 디스패치 전 drift 체크
```python
from objective_drift import check_drift, emit_alert

event = check_drift("session_20260424_001", "이력서 §3.2를 학술 표준으로 격상한다")
if event["alert"]:
    emit_alert(event)  # HITL 트리거
    # 사용자 승인 후 진행
```

---

## 검증 시나리오 (실측 — 2026-04-24 캘리브레이션)

10건 시나리오 (정상 5 + 이상 5) `paraphrase-multilingual-mpnet-base-v2` 실측 결과:

| 카테고리 | drift_score 범위 | mean | THRESHOLD 0.65 alert |
|---|---|---|---|
| **정상** (의미 정렬) | 0.372 ~ 0.668 | 0.512 | 1 FP / 5 (cal_n2 boundary) |
| **이상** (의미 분리) | 0.667 ~ 0.852 | 0.765 | 5 TP / 5 |

**검출 정확도**: 9/10 (90%) · 실측 로그: `~/claude-cowork/.ai_os/drift_log.jsonl`

### Threshold Calibration & 한계 (정직한 공개)

`paraphrase-multilingual-mpnet-base-v2`는 다국어 모델이라 **한국어 짧은 문장 의미 변별력에 한계**가 있어, 정상/이상 drift_score 분포가 0.667 부근에서 overlap한다.

| THRESHOLD | False Positive | False Negative | 권장 환경 |
|---|---|---|---|
| **0.65** (현재) | 1/5 | 0/5 | **Enterprise** (보수적, FN 0 우선) |
| 0.70 | 0/5 | 1/5 | 개발 (FP 0, 알림 피로 ↓) |

**개선 경로 (v0.2.0 로드맵)**:
1. 한국어 특화 모델: `jhgan/ko-sroberta-multitask`로 재캘리브레이션
2. Task description 더 긴 컨텍스트 (현재 한 줄 → 다중 문장 + Self-Verification 블록)
3. Ensemble: 다중 모델 cosine 평균 + variance 기반 confidence

---

## 의존성 설치

```bash
pip install sentence-transformers numpy pytest
```

첫 실행 시 모델 다운로드 (~470MB). 또는 vet-snomed-rag 레포의 `.venv` 활용 (이미 모든 의존성 설치됨):

```bash
~/claude-cowork/07_Projects/vet-snomed-rag/.venv/bin/python --version
~/claude-cowork/07_Projects/vet-snomed-rag/.venv/bin/pip list | grep -E "sentence-transformers|numpy|pytest"
```

---

## 실행

```bash
cd ~/claude-cowork
PYTHONPATH=tools python -m pytest tools/objective_drift/tests/ tools/pii_masking/tests/ -v
```

**현재 상태 (2026-04-24)**:
- PII 마스킹 round-trip: **5/5 PASS**
- Drift PoC import + smoke test: **PASS**
- Drift 캘리브레이션 (10건 실측): **9/10 detection accuracy**

---

## LG CNS 면접 답변 연결

자소서 문항 4 (입사 후 포부) 추가 문장:

> 입사 후 제 AI OS의 다음 로드맵은 **Objective Drift 자동 감지 시스템**입니다.
> 사용자 원본 요청의 임베딩 벡터와 에이전트 Task Definition의 임베딩 간
> 코사인 유사도로 Drift Score를 측정하고, 임계값 초과 시 HITL을 트리거하는
> 구조입니다. 이는 Enterprise AI가 실제 프로덕션에서 가장 두려워하는
> "AI가 엉뚱한 방향으로 일하는" 리스크를 정량 감지 시스템으로 해소하는
> 실증입니다.

---

*PoC 작성: 2026-04-24 | 핸드오프 §5 Step 3 완료 | v0.1.0*
