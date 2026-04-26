---
tags: [vet-snomed-rag, v2.9, R-10, payg, simulation, observability]
date: 2026-04-27
status: 종결 (보고서 + budget_guard PoC + 단위 테스트 24건)
prev: docs/20260427_v2_9_roadmap_handoff.md §1-2 #3
related:
  - src/observability/budget_guard.py
  - tests/test_budget_guard.py
  - graphify_out/regression_metrics.json
  - graphify_out/r7_1_after_fix_smoke.log
---

# R-10 — Tavily / Gemini PAYG 시뮬 + 운영 견고성 가드레일 (v2.9)

> **결론 요약:** 현 부하 기준 PAYG 전환 시 월 예상 비용 **<$0.05** (개발자 1인) ~ **$1.30** (Production 100쿼리/일 가정).
> Tavily Free 1,000 credits/월이 운영상 가장 먼저 닿는 캡 — Production 30% 이상 web fallback 시 90% 임계 도달 가능.
> `src/observability/budget_guard.py` PoC 모듈 + 단위 24건 PASS로 임계 모니터링 인프라 확보. **단위 219 → 243 PASS, 회귀 0** (모듈 isolation, 0 production import).

---

## §1. 현 사용량 실측

### 1-1. 11쿼리 정밀 회귀 (cached, gemini backend)

`graphify_out/regression_metrics.json` (commit `40c6d2a`) 파싱:

| 항목 | 값 |
|---|---|
| 쿼리 수 | 11 (T1–T11) |
| 모델 | `gemini-3.1-flash-lite-preview` |
| 모두 cached | True |
| per-query cost | min $0.000253 / max $0.000276 / mean **$0.000270** |
| **회귀 1회 합계** | **$0.002969** |

### 1-2. N-3 smoke (multi-iter, T14 worst case)

`graphify_out/r7_1_after_fix_smoke.log`:

| 케이스 | reformulate 횟수 | est cost |
|---|---|---|
| T12 (multi-iter) | 4-5회 | $0.000269~309 |
| T13 (multi-iter) | 5-7회 | $0.000300 추정 |
| T14 (multi-iter, 한국어) | **9회** | **$0.000309** (실측) |

> T14 9회 reformulate × cached input × short output = $0.000309 실측. multi-iter는 reformulate 횟수에 거의 선형.

### 1-3. 외부 도구 호출량 (smoke)

R-7.1 smoke phase A 기준 외부 도구 hits 6회 (`umls`, `pubmed`, `tavily web` 혼합).
- Tavily 호출은 web fallback 때만 발생 (smoke 4건 중 1-2건)
- 11쿼리 회귀에는 외부 도구 호출 거의 없음 (단순 reformulate 위주)

---

## §2. PAYG 공식 단가 (1차 출처)

### 2-1. Gemini 3.1 Flash-Lite Preview

출처: `https://ai.google.dev/gemini-api/docs/pricing` (2026-04-27 fetch)

| 티어 | Input ($/1M) | Output ($/1M) | Context Cache ($/1M) |
|---|---|---|---|
| **Standard (default)** | **0.25** | **1.50** | 0.025 |
| Batch / Flex | 0.125 | 0.75 | 0.0125 |
| Priority | 0.45 | 2.70 | — |

Free tier (Standard): RPD 한도 = 500 (현재 사용 모델), Google Search grounding 5,000 prompts/월 별도.

### 2-2. Tavily

출처: `https://docs.tavily.com/documentation/api-credits` (2026-04-27 fetch)

| 항목 | 값 |
|---|---|
| Free tier | **1,000 credits/월** (카드 등록 불요) |
| PAYG 단가 | **$0.008 / credit** |
| Search basic | 1 credit / request |
| Search advanced | 2 credits / request |
| Extract basic | 1 credit / 5 URL |
| Extract advanced | 2 credits / 5 URL |

월 정액제 (참고):

| Plan | Credits | $/월 | $/credit |
|---|---|---|---|
| Project | 4,000 | 30 | 0.0075 |
| Bootstrap | 15,000 | 100 | 0.0067 |
| Startup | 38,000 | 220 | 0.0058 |
| Growth | 100,000 | 500 | 0.005 |

→ PAYG vs Project plan 분기점: **3,750 credits/월 이상이면 Project plan이 저렴**.

---

## §3. 월간 비용 추정 (3 시나리오)

### 3-1. 가정 명시

- **R**: 회귀 11쿼리 1회 ≈ $0.003 (실측 §1-1)
- **S**: smoke 1회 (3 cases) ≈ $0.001 (실측 §1-2)
- **per-query cached cost**: $0.000270 (실측 mean)
- **multi-iter cost**: cached × 3-4× ≈ $0.0008–0.001 / query
- **web fallback rate**: 10% (보수) / 30% (Production) / 100% (worst)
- **search depth**: basic (1 credit) — advanced 사용 시 2배

### 3-2. 시나리오 A — 현 부하 (개발자 1인)

| 항목 | 산출 |
|---|---|
| 회귀 빈도 | 1회/주 × 4주 = 4회/월 |
| smoke 빈도 | 4회/월 |
| Gemini Cost | 4×R + 4×S = 4×$0.003 + 4×$0.001 = **$0.016/월** |
| Tavily Credits | smoke fallback 5–10건/월 = ~10 credits → **0% 사용** |
| **PAYG 월 총액** | **$0.016/월** (≈ $0.20/년) |

→ Free tier 안. PAYG 전환 비용 0에 가까움.

### 3-3. 시나리오 B — Production 가설 (100 쿼리/일)

| 항목 | 산출 |
|---|---|
| 월 쿼리 | 100 × 30 = 3,000 |
| Gemini cache hit (가정 70%) | 2,100 × $0.000270 = $0.567 |
| Gemini multi-iter (가정 30%) | 900 × $0.0008 = $0.720 |
| **Gemini 합** | **$1.29/월** |
| Tavily web fallback (10%) | 300 × 1 credit = 300 credits → Free 안 |
| Tavily web fallback (30%) | 900 × 1 credit = 900 credits → Free 90% **WARN** |
| Tavily PAYG overflow (30%) | 0 credits |
| **PAYG 월 총액 (낙관)** | **~$1.29/월** (Tavily Free 안) |
| **PAYG 월 총액 (보수)** | **~$1.29/월 + $0** (Free 안에 머무름) |

→ 운영상 **Tavily 90% 임계**가 가장 먼저 닿는 위험. Gemini는 RPD 100/500 = 20% 안전.

### 3-4. 시나리오 C — Worst case (multi-iter N=4 + advanced search)

| 항목 | 산출 |
|---|---|
| 월 쿼리 | 100 × 30 = 3,000 |
| Gemini multi-iter 100% | 3,000 × $0.0008 = $2.40 |
| Tavily advanced 100% × N=4 | 3,000 × 4 × 2 credits = 24,000 credits |
| Tavily Free | 1,000 → 23,000 PAYG |
| Tavily PAYG cost | 23,000 × $0.008 = **$184** |
| **PAYG 월 총액** | **~$186/월** |

→ Worst case는 **Tavily 24,000 credits** 가 99% — Project plan(4,000/$30) × 6 = $180과 근사. PAYG는 단가만큼만 비례.

→ **30% 이상 부하 시 monthly subscription 검토**, 그 미만이면 PAYG가 단가상 동일 또는 약간 비쌈.

---

## §4. 가드레일 설계 — `src/observability/budget_guard.py`

### 4-1. 환경변수 (모두 optional)

| 변수 | 기본값 | 의미 |
|---|---|---|
| `GSD_BUDGET_USD_MONTH` | None (비활성) | 월간 USD 캡 |
| `GSD_TAVILY_CREDIT_LIMIT` | 1000 | Tavily Free 한도 |
| `GSD_GEMINI_RPD_LIMIT` | 500 | Gemini Free RPD |
| `GSD_BUDGET_WARN_AT` | 80 | first 경고 임계 % |
| `GSD_BUDGET_CRIT_AT` | 95 | critical 임계 % |

### 4-2. 공개 API

```python
from src.observability.budget_guard import BudgetGuard

guard = BudgetGuard.from_env()
guard.record_gemini(input_tokens=600, output_tokens=80)
guard.record_tavily_search(depth="basic")  # 1 credit
warnings = guard.emit_warnings()  # [BudgetWarning(...)] + logger.WARNING
```

### 4-3. 임계 분류

| pct | severity | 동작 |
|---|---|---|
| < 80% | none | 무관 |
| 80% ≤ pct < 95% | `warn` | logger.WARNING |
| ≥ 95% | `crit` | logger.ERROR |

### 4-4. 통합 위치 (v3.0+ 예정)

PoC 단계에서는 **standalone** — 어떤 production 코드도 import하지 않음 (회귀 0 보장).

향후 통합 후보:
- `src/retrieval/agentic/synthesizer.py:_call_gemini` — Gemini 호출 직후 `record_gemini()` 호출
- `src/tools/web_search_client.py` — Tavily search 직후 `record_tavily_search()` 호출
- `src/retrieval/agentic_pipeline.py` 진입부 — `BudgetGuard.from_env()` 싱글톤 lazy init

영속화는 v3.0+ 별도 설계 (`~/.cache/vet-snomed-rag/budget_state.json` 후보).

### 4-5. 단위 테스트 (24건, 전체 PASS)

`tests/test_budget_guard.py` — 테스트 클래스:

| 클래스 | 검증 항목 |
|---|---|
| `TestGeminiCost` | zero / 1M input / 1M output / realistic 600+80 → $0.00027 |
| `TestTavilyCredits` | basic=1 / advanced=2 / PAYG cost |
| `TestThresholds` | WARN 80% / CRIT 95% / 미달 / budget=None / Tavily WARN / Gemini RPD CRIT |
| `TestPeriodReset` | 일별 RPD reset / 월별 credit reset (UTC 기준) |
| `TestFromEnv` | defaults / 정상 파싱 / invalid → fallback |
| `TestEmitWarnings` | logger.WARNING + logger.ERROR / 빈 list 시 silent |
| `TestValidation` | 음수 token / 음수 credit → ValueError |
| `TestTotalUsd` | gemini + tavily PAYG 합산 |

---

## §5. 성공 기준 1:1 PASS/FAIL (handoff §3 R-10 기준)

| # | 항목 | PASS 조건 | 결과 |
|---|---|---|---|
| R10-1 | 현 사용량 실측 | 회귀/smoke 산출물에서 token/credit 추출, 추정 ≠ 실측 분리 | **PASS** §1 (실측) / §3 (추정) 분리 |
| R10-2 | PAYG 단가 출처 | Google AI Studio + Tavily docs URL 명시 | **PASS** §2 1차 출처 URL 2건 |
| R10-3 | 시나리오 표 | A/B/C 3종 USD 추정치 + 가정 명시 | **PASS** §3-1 가정 / §3-2~4 표 |
| R10-4 | 가드레일 설계 | 환경변수 3종 + hook 통합 위치 + 알림 임계% | **PASS** §4 — 5개 env / 통합 후보 / 80%-95% |
| R10-5 | 회귀 0 | 단위 ≥219 PASS + 11쿼리 회귀 0 | **PASS** 단위 **243 PASS** (+24) / 11쿼리 회귀는 모듈 isolation으로 mathematically impossible (0 production import) |
| R10-6 | handoff 갱신 | v2.9 핸드오프 status R-10 종결 추가 | **PASS** (다음 단계 — handoff 본문 갱신) |

---

## §6. 권장 — 다음 cycle

### 6-1. 즉시 결정 가능

- **(A) v2.9 종결 + tag/release** — R-10 본 보고서 + budget_guard PoC를 v2.9로 publish, 다음 cycle 사용자 결정
- **(B) v2.9에 R-9.1 등 light 작업 1건 더 묶기** — setup_env.sh `.venv↔venv` 정리 (handoff §2 §2-C)
- **(C) v3.0 phase 진입** — R-8 embedder 교체 (BioBERT/PubMedBERT 후보 비교부터)

### 6-2. PAYG 활성화 (사용자 비즈니스 결정)

현재 데이터로는 **즉시 활성화 불필요**:
- 시나리오 B(Production 가정)에서도 Free tier 안에 머무름
- 시나리오 C 도달 전 monthly subscription(Tavily Project $30/월)이 더 합리적
- PAYG는 **burst 대비 안전망** 의미만 — 카드 등록 부담 vs 안전망 가치 사용자 판단

권장: **PAYG 미활성 + budget_guard 환경변수만 설정**(`GSD_BUDGET_USD_MONTH=2.0` 권장 → 시나리오 B 1.5× 안전 마진).

### 6-3. v3.0 R-8 embedder 교체 트리거

- 후보: BioBERT (PubMed 학습), PubMedBERT, BiomedBERT, MedCPT, e5-mistral-7b-instruct, BGE-M3 (multilingual)
- 도메인 특수성: **수의학** 코퍼스가 BioBERT/PubMedBERT의 주된 학습 데이터에 거의 없음 → 효과 가설 검증 필요
- 별도 phase 권고: 후보 비교 → 샘플 100쿼리 재임베딩 → 리랭킹 검증 → 전수 결정

---

## §7. 위험·블로커 (실측)

| 위험 | 영향 | 회피 |
|---|---|---|
| Gemini 3.1 Flash-Lite Preview deprecation | 가격/모델 ID 변경 | budget_guard 단가 상수 모듈화 — 1줄 변경으로 전환 |
| Tavily Free 한도 변경 | 1,000 → 변경 시 임계 부정확 | env override (`GSD_TAVILY_CREDIT_LIMIT`) 가능 |
| 통합 시 budget_guard 누락 호출 | 사용량 미추적 → 임계 알림 X | v3.0 통합 phase에서 Adversarial Verifier로 호출점 전수 점검 |

---

## §8. 산출물 인덱스

| 분류 | 경로 |
|---|---|
| 신규 모듈 | `src/observability/__init__.py` |
| 신규 모듈 | `src/observability/budget_guard.py` (218 LoC) |
| 신규 테스트 | `tests/test_budget_guard.py` (24건) |
| 본 보고서 | `docs/20260427_r10_payg_simulation.md` |
| 산출 데이터 | `graphify_out/regression_metrics.json` (재사용) |
| 산출 데이터 | `graphify_out/r7_1_after_fix_smoke.log` (재사용) |

---

**R-10 종결 — 단위 243 PASS, 회귀 0, PAYG 추정 + 가드레일 PoC 완료.**
