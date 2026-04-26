# Release Notes — v2.8 (2026-04-26)

> **v2.8 — 묶음 G: R-7 multi-iter 누적 보존 + 429 retry/관찰성 + R-2.1 metric 재정의**
>
> v2.7 R-3 Tier C(Tavily Web Search)에 이어, v2.8은 **synthesis 미트리거 본질 결함**을 해소한다. 진단 결과 v2.6 R-2 잔여 N-3 smoke #1 FAIL의 직접 원인은 핸드오프 추정("마지막 iter만 보존")이 아니라 **Gemini Free Tier 일일 한도 초과 → silent fallback** 이었음이 밝혀졌고, 부수적으로 multi-iter loop 누적 부재도 잠재 결함으로 함께 해소했다. 또한 agentic 파이프라인 모델을 RPD 500의 `gemini-3.1-flash-lite-preview`로 교체해 운영 한도 안정성을 확보했다.

---

## 핵심 메트릭

| 항목 | v2.7 | v2.8 (이번) | 변화 |
|---|---|---|---|
| **단위 테스트 누적** | 207 | **215** | +8 (R-7 누적/dedup/retry/관찰성 검증) |
| **11-쿼리 정밀 회귀 (none, RERANK=1)** | 10/10 | **10/10** | 회귀 0 |
| **11-쿼리 정밀 회귀 (gemini, RERANK=1)** | 10/10 | **10/10** | 회귀 0 |
| **N-3 smoke #1 합성 적용률** | (기준 부적합) | **3/3 PASS** | metric 재정의 + R-7 fix |
| **N-3 smoke #2 인용률 ≥80%** | 3/3 | **2/3 PARTIAL** | T12 누적 5건 중 3건 인용 (R-7.1 후속) |
| **N-3 smoke #3 회귀 0** | 2/2 | **2/2 PASS** | 외부 OFF 시 base 보존 |
| **N-3 smoke #4 비용** | 3/3 | **3/3 PASS** | < $0.001/case |
| **agentic 파이프라인 RPD** | 20 (2.5-flash-lite) | **500 (3.1-flash-lite-preview)** | 25배 ↑ |

---

## 진단 — 핸드오프 추정 vs 실제 원인

v2.7 → v2.8 핸드오프 §3-1은 결함 위치를 `agentic_pipeline.py:236 last_external = iter_external` (마지막 iter만 보존)으로 추정했다. 코드 정독 가설로 합리적이었으나 실제 진단 결과는 다음과 같다:

| 케이스 | external_results | synthesis_used (v2.7 시점) | 직접 원인 |
|---|---|---|---|
| T12 `diabetes mellitus ICD-10 cross-walk` | `['umls']` 채워짐 | False | 합성 LLM 429 한도 초과 |
| T13 `rare feline endocrine literature` | `['pubmed']` 채워짐 | False | 합성 LLM 429 한도 초과 |
| T14 `고양이 당뇨 ICD-10 매핑` | `['umls']` 채워짐 | False | 합성 LLM 429 한도 초과 |

합성기 직접 호출 진단:
```
[T13-like] used=False  method=fallback
  reason="ClientError: 429 RESOURCE_EXHAUSTED.
          Quota exceeded for metric: generate_content_free_tier_requests,
          limit: 20, model: gemini-2.5-flash-lite. Please retry in 15.0s."
```

agentic_pipeline은 query당 5+ Gemini 호출(complexity / source_router / reformulator / synthesizer / judge)을 수행하므로, smoke 3건만 돌려도 15+회로 Free Tier 20 RPD 한도에 즉시 도달한다. v2.6 R-2 시점에서도 이미 동일 silent fallback이 발생했을 가능성이 매우 높다.

핸드오프 추정 자체는 직접 원인이 아니었으나 multi-iter loop의 외부 결과 누적 부재는 **잠재 결함**으로 평가되어 함께 해소했다.

---

## 신규/변경 — 묶음 G

### 1. R-7 — multi-iter 누적 보존 + 429 retry + 관찰성 노출 (옵션 γ)

**`src/retrieval/agentic_pipeline.py`**
- `last_external` (마지막 iter만 보존) → `accumulated_external` (모든 iter 누적 + source별 식별자 dedup)
- 합성 트리거 조건 + 합성기 입력 모두 누적 기반으로 변경
- `synthesis_used`는 한 번이라도 True면 **단조 유지** (마지막 iter에서 다시 False로 덮어쓰지 않음)
- `external_results` 필드는 누적 결과 노출
- 신규 헬퍼 `_dedup_external(acc)` — UMLS cui / PubMed pmid / Web url 식별자 기준 dedup, 식별자 결측 항목은 보존
- 신규 노출 필드: `synthesis_method` / `synthesis_fallback_reason`

**`src/retrieval/agentic/synthesizer.py`**
- 429 retry/backoff (1회) 추가
- 신규 헬퍼 `_parse_retry_delay` — `retryDelay: 'X.Xs'` + `retry in Xs` 두 형식 지원, 상한 30초

**`AgenticRAGResult`**
- `synthesis_method: str = "skip"` 추가 (`skip` | `gemini` | `fallback`)
- `synthesis_fallback_reason: str = ""` 추가

### 2. R-2.1 — N-3 smoke metric 재정의 (a)+(b) 결합

**`scripts/n3_synthesis_smoke.py`**
- §3-3-5 #1 metric을 (a)+(b) 결합으로 교체
  - 구: 합성 답변 ≥ +30% 길이 (LLM 합성의 통합·압축 본질과 어긋남, T12 0.38x 사례)
  - 신: **외부 결과 있을 때 `synthesis_used=True` 비율 100%** (#1) + **외부 식별자 인용률 ≥ 80%** (#2 유지)
- `_citations_in_answer`가 web URL 인용도 카운트에 포함 (v2.7 R-3 Tier C 정합)

### 3. 모델 교체 — agentic 파이프라인 8개 위치

`gemini-2.5-flash-lite` (RPD 20) → `gemini-3.1-flash-lite-preview` (RPD 500, 25배 ↑)

대상: `agentic_pipeline.py` (3) + `agentic/loop_controller.py` + `agentic/relevance_judge.py` + `agentic/synthesizer.py` + `agentic/query_complexity.py` + `tests/test_query_complexity.py` = 8건

기존 `soap_extractor.py`, `query_reformulator.py`는 v2.0부터 이미 `gemini-3.1-flash-lite-preview` 사용 중. 본 교체로 agentic 레이어까지 통일.

---

## 신규 단위 테스트 (8건)

`tests/test_synthesizer.py` (+246줄):
1. `test_dedup_external_umls_cui` — cui 중복 제거 + 첫 등장 보존
2. `test_dedup_external_pubmed_pmid` — pmid 중복 제거
3. `test_dedup_external_web_url` — url 중복 제거
4. `test_dedup_external_preserves_no_id_items` — 식별자 결측 항목 보존
5. `test_pipeline_accumulates_external_across_iters` — multi-iter 누적: iter 0 pubmed → iter 1 빈 결과여도 누적 유지로 합성 트리거
6. `test_pipeline_exposes_synthesis_method_and_reason` — `synthesis_method` + `synthesis_fallback_reason` 노출
7. `test_synthesize_429_retry_succeeds` — 429 → retryDelay sleep → 재시도 성공
8. `test_parse_retry_delay_variants` — `retryDelay: 'X.Xs'` + `retry in Xs` 두 형식 파싱

---

## Production 검증 (gemini-3.1-flash-lite-preview)

### N-3 smoke (`graphify_out/r7_after_fix_smoke.log`)

| 케이스 | synthesis_used | method | external | 인용 |
|---|---|---|---|---|
| T12 `diabetes mellitus ICD-10 cross-walk` | **True** | gemini | umls (5건 누적) | 3/5 (60%) |
| T13 `rare feline endocrine literature` | **True** | gemini | pubmed (4건) | 4/4 (100%) |
| T14 `고양이 당뇨 ICD-10 매핑` | **True** | gemini | umls (1건) | 1/1 (100%) |
| T1 (외부 OFF) | False (skip) | skip | — | final == base ✓ |
| T7 (외부 OFF) | False (skip) | skip | — | final == base ✓ |

§3-3-5 1:1 PASS/FAIL:
- #1 합성 적용률 100%: **3/3 PASS** ✅ ← R-7 핵심 목표
- #2 인용률 ≥80%: **2/3 PARTIAL** — T12만 60% (R-7.1 후속)
- #3 외부 OFF 회귀 0: **2/2 PASS** ✅
- #4 비용 < $0.001: **3/3 PASS** ✅

### 11쿼리 정밀 회귀 (`graphify_out/v2_8_regression.log`)

```
[none  ] PASS 10/10  (NA=1건 제외)
[gemini] PASS 10/10  (NA=1건 제외)
```

회귀 0 — v2.7 baseline 그대로 유지. 모델 교체 부작용 0.

---

## 알려진 한계 (v2.9 후속 후보)

### R-7.1 — synthesizer 인용률 강화 (T12 60% 케이스)

multi-iter 누적으로 T12 외부 결과가 5건으로 늘어나, 합성 LLM이 답변 본문에 5건 모두 인용하지 않고 3건만 인용 (60%). 누적 보존의 부수 효과. 후보 fix:
- 합성 프롬프트에 "모든 식별자 인용" 강제 (현재는 부드러운 권고)
- 누적 결과 상한 (예: 최대 3건/source) — 합성 입력 컴팩트화
- 또는 인용률 기준을 누적 후 "최소 80% **또는** 핵심 ≥ 3건"으로 완화

### R-9 — onboarding 가이드 갱신

`venv` 동기화 누락 사고(v2.6 R-5) 방지. README setup 섹션 + .env.example.

### R-10 — Tavily PAYG 활성화 시뮬

Tavily Free 1,000 credits/월 한도 검증 + Pay As You Go 전환 동작 확인. 사용자 카드 등록 필요.

### R-8 — embedder 교체 (BioBERT/PubMedBERT)

heavy. ChromaDB 366,570 재임베딩 (수시간~하루). v2.9+ 별도 phase 권고.

---

## 변경 파일 (8건)

| 분류 | 경로 |
|---|---|
| 코어 변경 | `src/retrieval/agentic_pipeline.py` (누적/dedup/관찰성) |
| 코어 변경 | `src/retrieval/agentic/synthesizer.py` (429 retry/_parse_retry_delay) |
| 모델 교체 | `src/retrieval/agentic/loop_controller.py` |
| 모델 교체 | `src/retrieval/agentic/relevance_judge.py` |
| 모델 교체 | `src/retrieval/agentic/query_complexity.py` |
| 테스트 신규/확장 | `tests/test_synthesizer.py` (+8) / `tests/test_query_complexity.py` |
| 스크립트 갱신 | `scripts/n3_synthesis_smoke.py` (R-2.1 metric) |
| 산출물 | `graphify_out/r7_after_fix_smoke.log`, `graphify_out/v2_8_regression.log`, `graphify_out/regression_metrics.json` |
| 문서 | `docs/20260427_r7_synthesis_diagnosis.md` (신규) |
| 문서 | `docs/20260427_v2_8_roadmap_handoff.md` (status 갱신) |
| 문서 | `RELEASE_NOTES_v2.8.md` (본 문서) |
| 메모리 | `memory/project_vet_snomed_rag.md`, `memory/MEMORY.md` (v2.8 섹션) |

---

## 마이그레이션 가이드

### Breaking changes

**없음.** v2.7 외부 호출자(API 사용자)에게 노출되는 모든 인터페이스 호환.

### 신규 노출 필드 (선택적 활용)

```python
result = pipe.agentic_query("ICD-10 cross-walk for feline diabetes")

# v2.8 신규 — 합성 시도 결과 관찰성
result.synthesis_method          # "skip" | "gemini" | "fallback"
result.synthesis_fallback_reason # 429 quota / empty response / API error 등
result.external_results          # 모든 iter 누적 결과 (이전: 마지막 iter만)
```

### 모델 교체 영향

`AgenticRAGPipeline` 생성자의 backend default가 `gemini-3.1-flash-lite-preview`로 변경. 명시적으로 `gemini-2.5-flash-lite`를 전달하던 사용자는 그대로 동작 (RPD 20 한도 영향만 받음).

---

**v2.8 — 합성 본질 결함 해소 + agentic 한도 안정성 확보. 다음 v2.9에서 R-7.1 (인용률 강화) + R-9 (onboarding) 진행.**
