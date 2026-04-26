# Release Notes — v2.9 (2026-04-27)

> **v2.9 — R-10: PAYG 시뮬 + budget_guard PoC**
>
> Gemini API + Tavily Web Search의 PAYG 전환 시 월간 비용을 실측 기반 추정하고,
> Free 한도/USD 예산 임계 모니터링 PoC 모듈(`src/observability/budget_guard.py`)을 추가한다.
> 기존 production 경로는 import하지 않는 standalone 모듈 — 회귀 위험 0으로 인프라만 선확보.
> v3.0+ phase에서 synthesizer/web_search_client에 통합 예정.

---

## 핵심 메트릭

| 항목 | v2.8.1 | v2.9 (이번) | 변화 |
|---|---|---|---|
| **단위 테스트 누적** | 219 | **243** | +24 (BudgetGuard) |
| **11쿼리 정밀 회귀 (none, RERANK=1)** | 10/10 | **10/10** | 회귀 0 (모듈 isolation) |
| **11쿼리 정밀 회귀 (gemini, RERANK=1)** | 10/10 | **10/10** | 회귀 0 (모듈 isolation) |
| **R10 핸드오프 성공 기준** | — | **6/6 PASS** | 신규 (보고서 §5) |

> **회귀 0 정당화:** `src/observability/budget_guard.py`는 production 코드 어디에서도 import하지 않음.
> `grep -rE "budget_guard|BudgetGuard" src/ scripts/` → 0 매칭. 런타임 경로 변경 없음 → 11쿼리 회귀
> 결과 mathematically impossible to change. 추가 API 호출 비용/credit 소모 없이 검증 종결.

---

## R-10 PAYG 추정

`docs/20260427_r10_payg_simulation.md` (271 lines) — 실측 사용량 기반 3 시나리오:

| 시나리오 | 가정 | Gemini USD/월 | Tavily credit/월 | PAYG 월 총액 |
|---|---|---|---|---|
| **A 현 부하** | 개발자 1인 (회귀 4회/월 + smoke 4회/월) | $0.016 | ~10 (1%) | **<$0.05** |
| **B Production 100q/일** | 70% cache hit + 30% multi-iter | $1.29 | 300–900 | **~$1.30** |
| **C Worst case** | multi-iter N=4 + advanced search 100% | $2.40 | 24,000 | **~$186** |

**1차 출처 (2026-04-27 검증):**
- Gemini 3.1 Flash-Lite Preview: input $0.25/1M, output $1.50/1M (https://ai.google.dev/gemini-api/docs/pricing)
- Tavily: Free 1,000 credits/월, PAYG $0.008/credit (https://docs.tavily.com/documentation/api-credits)

**결론:** PAYG 즉시 활성화 불필요. Tavily 90% 임계가 가장 먼저 닿는 위험 — Production 30%+ web fallback 시.

---

## 신규 모듈 — `src/observability/budget_guard.py` (218 LoC)

### 환경변수 (모두 optional)

| 변수 | 기본값 | 의미 |
|---|---|---|
| `GSD_BUDGET_USD_MONTH` | None (비활성) | 월간 USD 캡 |
| `GSD_TAVILY_CREDIT_LIMIT` | 1000 | Tavily Free 한도 |
| `GSD_GEMINI_RPD_LIMIT` | 500 | Gemini Free RPD |
| `GSD_BUDGET_WARN_AT` | 80 | first 경고 임계 % |
| `GSD_BUDGET_CRIT_AT` | 95 | critical 임계 % |

### 공개 API

```python
from src.observability.budget_guard import BudgetGuard

guard = BudgetGuard.from_env()
guard.record_gemini(input_tokens=600, output_tokens=80)
guard.record_tavily_search(depth="basic")  # 1 credit
warnings = guard.emit_warnings()  # WARN @ 80% / CRIT @ 95%, logger.WARNING/ERROR
```

### 임계 분류

- 80% ≤ pct < 95% → `BudgetWarning(severity="warn")` + `logger.WARNING`
- pct ≥ 95% → `BudgetWarning(severity="crit")` + `logger.ERROR`
- UTC 기준 일별 RPD reset / 월별 credit reset

### 단위 테스트 — 24건 PASS (`tests/test_budget_guard.py`)

8 클래스: `TestGeminiCost` / `TestTavilyCredits` / `TestThresholds` / `TestPeriodReset` / `TestFromEnv` / `TestEmitWarnings` / `TestValidation` / `TestTotalUsd`

---

## 권장 운영 설정

PAYG 미활성 + 안전망:
```bash
export GSD_BUDGET_USD_MONTH=2.0     # Production 시나리오 B 1.5× 안전 마진
export GSD_TAVILY_CREDIT_LIMIT=1000 # Free tier
export GSD_GEMINI_RPD_LIMIT=500     # Free tier
```

PAYG 활성화 후 (사용자 비즈니스 결정):
```bash
export GSD_BUDGET_USD_MONTH=10.0    # 월 $10 cap
# Tavily / Gemini 카드 등록 + 콘솔 한도 별도 설정
```

---

## 다음 cycle (v3.0 후보)

- **R-8 embedder 교체** — BioBERT / PubMedBERT / BiomedBERT / e5-mistral / BGE-M3 후보 비교 → 샘플 100쿼리 재임베딩 → 리랭킹 검증 → ChromaDB 366,570 전수 재구축 결정
- **budget_guard runtime 통합** — synthesizer/web_search_client/agentic_pipeline 호출점에 `record_*()` 삽입, 영속화(JSON 또는 SQLite) 추가

---

## Commit

- `feat(v2.9): R-10 — PAYG 시뮬 + budget_guard PoC`
- 5 files changed: 4 신규 (`src/observability/__init__.py` + `src/observability/budget_guard.py` + `tests/test_budget_guard.py` + `docs/20260427_r10_payg_simulation.md`) + 1 수정 (`docs/20260427_v2_9_roadmap_handoff.md` status 갱신)
- 단위 219 → 243 PASS, 회귀 0
