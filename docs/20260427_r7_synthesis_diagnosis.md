---
tags: [vet-snomed-rag, v2.8, R-7, R-2.1, diagnosis]
date: 2026-04-26
status: 단위 검증 완료 / production smoke 보류
related:
  - docs/20260427_v2_8_roadmap_handoff.md (입력 핸드오프)
  - src/retrieval/agentic_pipeline.py (수정)
  - src/retrieval/agentic/synthesizer.py (수정)
  - tests/test_synthesizer.py (신규 8건)
  - scripts/n3_synthesis_smoke.py (R-2.1 metric 교체)
---

# R-7 synthesis 미트리거 진단 노트

## §1. 핸드오프 추정 vs 실제 관찰

### 1-1. 핸드오프 §3-1 추정
> `agentic_pipeline.py` multi-iter loop에서 `last_external = iter_external` (line 236)으로 **마지막 iter만 보존**. 마지막 iter에서 외부 호출이 없으면 `synthesis_used=False`. 이전 iter에 누적된 외부 결과는 합성에 반영 안 됨.

### 1-2. 진단 실측 (smoke `n3_synthesis_smoke.py` + 합성기 직접 호출)

| 케이스 | external_results | synthesis_used | base_len | synth_len | latency |
|---|---|---|---|---|---|
| T12 `diabetes mellitus ICD-10 cross-walk` | `['umls']` 채워짐 | **False** | 3871 | 3871 (1.00x) | 35583ms |
| T13 `rare feline endocrine literature` | `['pubmed']` 채워짐 | **False** | 1679 | 1679 (1.00x) | 3707ms |
| T14 `고양이 당뇨 ICD-10 매핑` | `['umls']` 채워짐 | **False** | 2345 | 2345 (1.00x) | 3798ms |

### 1-3. 합성기 직접 호출 결과 (mock 프롬프트, real Gemini API)

```
[T13-like] used=False  method=fallback
  reason="ClientError: 429 RESOURCE_EXHAUSTED. Quota exceeded for metric:
          generativelanguage.googleapis.com/generate_content_free_tier_requests,
          limit: 20, model: gemini-2.5-flash-lite. Please retry in 15.030921765s."
[T14-like] used=False  method=fallback  (동일 429)
```

### 1-4. 진짜 근본 원인

**Gemini API Free Tier 일일 한도 (20 RPD) 초과로 합성 LLM 호출이 fallback 경로 진입.**

agentic_pipeline은 단일 query당 다중 Gemini 호출:
- complexity_agent.judge (1)
- source_router.route (rule_based 시 0)
- reformulator (1+)
- synthesizer.synthesize (1)
- judge.judge (1)
- loop_controller.decide rewrite 시 (1+)

⇒ query당 **5+회**, smoke 3건이면 **15+회** → Free Tier 20 RPD 한도 임박/초과.

핸드오프 추정 ("마지막 iter만 보존")은 코드 정독 기반 가설이었으나, 실제 데이터는 **합성기 fallback 경로**가 직접 원인. 핸드오프가 명시한 "external_results 존재 + synthesis_used=False" 조합은 합성기가 호출됐으나 `used=False` 반환한 정황.

### 1-5. 부수 결함 (관찰성)

`SynthesisResult.method` / `fallback_reason`이 `AgenticRAGResult`에 노출되지 않아, 사용자 입장에서 `synthesis_used=False`만 보일 뿐 실패 사유 silent. v2.6 R-2 N-3 smoke 시점에서 **이미 동일 한도 초과가 발생했을 가능성**이 매우 높음 (그때도 silent fallback).

---

## §2. 적용된 fix (옵션 γ — 누적 + retry/관찰성)

핸드오프의 추정 원인 자체는 직접 원인이 아니었으나, multi-iter 누적 부재는 **잠재적 결함**으로 함께 해소.

### 2-1. agentic_pipeline.py — 누적 보존 + 단조 synthesis_used

| 항목 | 이전 | 이후 |
|---|---|---|
| 외부 결과 보존 | `last_external = iter_external` (마지막 iter만) | `accumulated_external` 모든 iter 누적 + source별 dedup |
| 합성 트리거 조건 | `if iter_external and any(iter_external.values())` | `if accumulated_external and any(accumulated_external.values())` |
| 합성기 입력 | `iter_external` (본 iter만) | `accumulated_external` (누적) |
| `synthesis_used` 갱신 | 매 iter `synthesis_used_this_iter`로 덮어씀 | 한 번이라도 True면 단조 유지 |
| `external_results` 필드 | 마지막 iter | 누적 (dedup) |
| 신규 노출 | — | `synthesis_method` + `synthesis_fallback_reason` |

새 헬퍼 `_dedup_external(acc)` — umls cui / pubmed pmid / web url 식별자 기반 중복 제거 (식별자 결측 항목은 보존).

### 2-2. synthesizer.py — 429 retry/backoff (1회)

```python
try:
    response = client.models.generate_content(...)
except Exception as e:
    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
        retry_seconds = _parse_retry_delay(str(e))  # "retryDelay: '15s'" 파싱
        if retry_seconds is not None and 0 < retry_seconds <= 30:
            time.sleep(retry_seconds + 1)
            response = client.models.generate_content(...)  # 1회 재시도
        else:
            raise
    else:
        raise
```

retryDelay 파싱: `_parse_retry_delay` — `retryDelay: 'X.Xs'` 또는 `retry in Xs` 두 형식 모두 지원. 상한 30초 (그 이상은 즉시 fallback).

### 2-3. AgenticRAGResult — 관찰성 필드 추가

```python
synthesis_method: str = "skip"          # "skip" | "gemini" | "fallback"
synthesis_fallback_reason: str = ""     # 429 quota / empty response / API error 등
```

---

## §3. R-2.1 metric 교체 (`scripts/n3_synthesis_smoke.py`)

§3-3-5 #1 metric을 **(a)+(b) 결합**으로 교체:

| | 구 metric (v2.6) | 신 metric (v2.8 R-2.1) |
|---|---|---|
| #1 | 합성 답변 ≥ +30% 길이 | **외부 결과 있을 때 synthesis_used=True 비율 100%** |
| 본질 적합성 | LLM 합성의 통합·압축 본질과 어긋남 (T12 0.38x 사례) | 합성 적용 자체를 측정 |
| 인용 검증 | #2에서 별도 (CUI/PMID 80%) | #2 그대로 유지 + URL(web) 인용 추가 |

`_citations_in_answer`가 이제 web URL도 인용 카운트에 포함 (v2.7 R-3 Tier C 정합).

---

## §4. 검증 결과

### 4-1. 단위 테스트 (한도 무관)

| 항목 | 결과 |
|---|---|
| pytest 전체 | **215 passed** (baseline 207 + 신규 8) |
| 신규 테스트 | `test_dedup_external_*` (4) + `test_pipeline_accumulates_external_across_iters` (1) + `test_pipeline_exposes_synthesis_method_and_reason` (1) + `test_synthesize_429_retry_succeeds` (1) + `test_parse_retry_delay_variants` (1) |
| 회귀 0 | test_synthesizer + test_agentic_pipeline + test_agentic_tier_b 무손상 |

### 4-2. Production smoke + 11쿼리 회귀

**보류** — Gemini Free Tier 일일 한도 소진 상태에서 즉시 재실행 불가. 다음 중 하나로 검증 진행 권고:

(i) **한도 reset 후 재실행** — UTC 자정 이후 (KST 09:00 추정)
(ii) **R-10 PAYG 활성화** — 핸드오프 §1-2 [3] / §3-5 — Gemini Pay As You Go 전환

검증 명령:
```bash
venv/bin/python scripts/n3_synthesis_smoke.py | tee graphify_out/r7_after_fix_smoke.log
venv/bin/python scripts/run_regression.py
```

기대값:
- N-3 smoke #1 (synthesis 적용률) 3/3 PASS, #2 (인용 80%) 3/3 PASS, #3 (회귀 0) 2/2 PASS
- 11쿼리 회귀 none·gemini 10/10 유지

---

## §5. v2.8 핸드오프 §7 체크리스트 매핑

| # | 항목 | 본 fix 결과 |
|---|---|---|
| H-1 | git status clean / 단위 207 PASS / 11쿼리 10/10 baseline | ✓ 시작 시점 검증 |
| H-2 | R-x 또는 묶음 명확 선택 | ✓ 묶음 G (R-7 → R-2.1) |
| H-3 | Task Definition 5항목 사용자 승인 | ✓ 본 fix 계획서 승인 후 진행 |
| H-4 | 사용자 사전 액션 — R-7 옵션 (γ) 결정 | ✓ |
| H-5 | §3-1-5 / §3-2-5 성공 기준 1:1 PASS | 단위 PASS / production 보류 |
| H-6 | 회귀 0 (단위 ≥207 + 11쿼리 10/10) | 단위 PASS / 11쿼리 보류 |
| H-7 | `project_vet_snomed_rag.md` v2.8 진입 사실 갱신 | (별도) |
| H-8 | 핸드오프 status 갱신 + v2.8→v2.9 핸드오프 신규 | production 검증 후 |

---

## §6. 미해결 (다음 액션)

1. **Production smoke** + **11쿼리 회귀** — 한도 reset 또는 R-10 PAYG 후 즉시 재실행
2. **R-10 PAYG 활성화 의사결정** — 사용자 카드 등록 (Gemini + Tavily 동시 전환 권고)
3. **RELEASE_NOTES_v2.8.md** 신규 — production 검증 PASS 확인 후 작성
4. **GitHub Release v2.8 publish** — 위 3건 모두 PASS 후

---

**작성 완료 — 2026-04-26.** 단위 fix는 안정. production 검증은 한도/PAYG 결정 후.
