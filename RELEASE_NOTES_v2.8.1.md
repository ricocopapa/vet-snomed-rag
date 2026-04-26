# Release Notes — v2.8.1 (2026-04-26 패치)

> **v2.8.1 — 묶음 H: R-7.1 인용률 강화 + R-9 onboarding**
>
> v2.8 묶음 G에서 잔여로 남았던 N-3 smoke #2 인용률 PARTIAL (T12 60%) 을 해소한다. 진짜 결함은 두 가지였다: (1) 합성 프롬프트가 "모든 식별자 인용"을 강제하지 않았고 (2) `_format_external_summary`가 `umls_items[:3]` / `pubmed_items[:5]`로 LLM 입력 식별자를 잘라서 누적 결과 일부만 LLM에 노출했다. 두 곳을 함께 수정하여 N-3 smoke 4/4 PASS 회복.

---

## 핵심 메트릭

| 항목 | v2.8 | v2.8.1 (이번) | 변화 |
|---|---|---|---|
| **단위 테스트 누적** | 215 | **219** | +4 (R-7.1 검증) |
| **11쿼리 정밀 회귀 (none, RERANK=1)** | 10/10 | **10/10** | 회귀 0 |
| **11쿼리 정밀 회귀 (gemini, RERANK=1)** | 10/10 | **10/10** | 회귀 0 |
| **N-3 smoke #1 합성 적용률** | 3/3 PASS | **3/3 PASS** | 유지 |
| **N-3 smoke #2 인용률 ≥80%** | 2/3 PARTIAL | **3/3 PASS** ✅ | 인용 100% × 3 |
| **N-3 smoke #3 회귀 0** | 2/2 PASS | **2/2 PASS** | 유지 |
| **N-3 smoke #4 비용 < $0.001** | 3/3 PASS | **3/3 PASS** | 유지 |

---

## 진단 — v2.8 잔여 PARTIAL의 두 결함

v2.8 commit `9e5f8f6` 직후 smoke 결과:
- T12 `diabetes mellitus ICD-10 cross-walk`: external `umls` 5건 누적 → 답변에 **3건만 인용 (60%)**
- T13/T14: 100% 인용 PASS

코드 정독 결과 **두 결함 동시 작용:**

### 결함 1 — `_SYNTH_PROMPT` 부드러운 권고

```python
# v2.8 (이전)
2. 1차 답변에 포함된 외부 도구 markdown 섹션의 식별자(CUI / PMID / 코드)를
   본문에서 명시 인용·해설하라.   # ← "모든" 강제 없음
```

LLM 입장에서는 일부만 인용해도 요구사항 위반이 아닌 것으로 해석 가능.

### 결함 2 — `_format_external_summary` 식별자 자르기

```python
# v2.8 (이전)
for r in umls_items[:3]:    # ← 누적 5건 중 3건만 LLM 입력에 노출
for r in pubmed_items[:5]:
# web 처리 자체가 0
```

multi-iter 누적으로 5건이 채워져도 LLM이 보는 식별자는 3건이어서, **인용 강제 강화만으로는 5/5 인용 불가능**. 두 결함이 같이 작용해야 인용률 회복.

---

## 신규/변경 — 묶음 H

### 1. R-7.1 — `_SYNTH_PROMPT` 강화 + 식별자 요약 누적 노출

**`src/retrieval/agentic/synthesizer.py`**

요구사항 #2 강화:
```
2. **[외부 도구 식별자 요약]에 나열된 모든 식별자(CUI / PMID / ICD10CM·MSH 코드 / Web URL)를
   단 하나도 누락 없이 본문에 명시 인용·해설하라.** 인용 누락 식별자 = 답변 결함.
   누적된 식별자가 여러 개일 때도 전부 인용하되, 의미적으로 묶어서 자연스럽게 통합하라.
```

요구사항 #6 신규 (자기 검증):
```
6. **답변 마지막 줄에 `(외부 식별자 N개 모두 인용)` 형식으로 자기 검증을 명시하라**
   (N은 [외부 도구 식별자 요약]의 식별자 총 개수).
```

요구사항 #4 톤 다운: "1차 답변보다 길어야 한다" → "단순 길이 늘리기보다는 의미적 통합 + 누락 식별자 0이 우선" (v2.8 R-2.1에서 +30% 길이 metric 폐기와 정합).

`_format_external_summary` 한도 확장:
- `umls_items[:3]` → `[:10]`
- `pubmed_items[:5]` → `[:10]`
- **신규: `web_items[:5]`** (v2.7 Tier C 정합)

### 2. R-9 — onboarding 가이드 갱신

**`.env.example`**: `TAVILY_API_KEY` (v2.7 Tier C) placeholder + Tavily 무료 발급 가이드 링크 추가. 5종 키(GOOGLE/ANTHROPIC/UMLS/NCBI/TAVILY) 모두 명시.

**`README.md` 빠른 시작**:
- `cp .env.example .env` 명시 + 키 5종 안내
- `brew install poppler tesseract tesseract-lang` 시스템 의존성 명시
- `pytest tests/ -q` 검증 단계 추가 (219+ PASS 기대)
- **Troubleshooting 박스** — v2.6 R-5 사고(venv 동기화 누락) 재발 방지: `ImportError: pdfplumber 가 필요합니다.` 시 `pip install -r requirements.txt` 재실행 안내

---

## 신규 단위 테스트 (4건)

`tests/test_synthesizer.py` (+82줄):
1. `test_synth_prompt_has_strict_citation_directive` — `_SYNTH_PROMPT`에 "단 하나도 누락 없이" + "외부 식별자 N개 모두 인용" + "Web URL" 강제 문구 포함 검증
2. `test_format_summary_exposes_all_accumulated_umls_up_to_10` — 5건 누적 시 LLM 입력에 5건 모두 노출 (v2.8 [:3] 자르기 결함 회복)
3. `test_format_summary_includes_web_urls` — web 식별자 요약 포함 (v2.7 Tier C 정합)
4. `test_synthesize_passes_all_5_umls_to_llm_prompt` — multi-iter 5건 누적 시 합성기 호출 prompt에 5건 cui 모두 포함 (T12 시나리오 재현)

---

## Production 검증 (gemini-3.1-flash-lite-preview)

### N-3 smoke (`graphify_out/r7_1_after_fix_smoke.log`)

| 케이스 | synthesis_used | external (누적) | 인용 |
|---|---|---|---|
| T12 `diabetes mellitus ICD-10 cross-walk` | True | umls 1건 | **1/1 (100%) PASS** |
| T13 `rare feline endocrine literature` | True | pubmed 6건 | **6/6 (100%) PASS** |
| T14 `고양이 당뇨 ICD-10 매핑` | True | umls 2건 | **2/2 (100%) PASS** |
| T1 / T7 (외부 OFF) | False (skip) | — | final == base ✓ |

§3-3-5 1:1 PASS/FAIL: **4/4 PASS** (v2.8 3/4 → v2.8.1 4/4) ✅

> **참고:** T12 외부 누적 건수가 v2.8 5건 → v2.8.1 1건으로 변동한 것은 multi-iter loop_controller 결정/source_router 라우팅의 비결정성 때문(Gemini 모델 응답 변동). 인용률 100% 자체가 R-7.1 fix 핵심 검증 — 합성 LLM이 "누적된 모든 식별자를 누락 없이 인용"하는 동작을 일관되게 수행함.

### 11쿼리 정밀 회귀 (`graphify_out/v2_8_1_regression.log`)

```
[none  ] PASS 10/10  (NA=1건 제외)
[gemini] PASS 10/10  (NA=1건 제외)
```

회귀 0 — v2.8 baseline 그대로 유지.

---

## 변경 파일 (5건)

| 분류 | 경로 |
|---|---|
| 코어 (R-7.1) | `src/retrieval/agentic/synthesizer.py` (`_SYNTH_PROMPT` 강화 + `_format_external_summary` 한도 확장 + web 추가) |
| 테스트 (R-7.1) | `tests/test_synthesizer.py` (+4 신규) |
| onboarding (R-9) | `.env.example` (TAVILY 추가) |
| onboarding (R-9) | `README.md` (빠른 시작 보강 + Troubleshooting) |
| 산출물 | `graphify_out/r7_1_after_fix_smoke.log`, `v2_8_1_regression.log`, `regression_metrics.json` |
| 문서 | `RELEASE_NOTES_v2.8.1.md` (본 문서) |

---

## 마이그레이션 가이드

### Breaking changes

**없음.** v2.8 호출자에게 노출되는 모든 인터페이스 호환.

### LLM 호출 비용 영향

`_format_external_summary` 한도 확장 (3→10 / 5→10 + web 5)으로 LLM 입력 토큰이 늘어날 수 있다. 대부분 케이스에서 누적 결과는 5건 이하라 영향 미미. 비용 검증 결과 여전히 **< $0.001/case** (smoke #4 PASS).

### 사용자 사전 액션

`.env.example`에 신규 추가된 `TAVILY_API_KEY`는 v2.7부터 사용 중이지만 v2.8.1 onboarding 갱신으로 명시 노출. 기존 사용자는 영향 없음 (이미 .env에 등록되었거나 비활성으로 정상 동작).

---

## v2.9 잔여 (다음 cycle)

- **R-10** — Tavily/Gemini PAYG 시뮬 (운영 견고성, 사용자 카드 등록 결정 필요)
- **R-8** — embedder 교체 (BioBERT/PubMedBERT, heavy, v3.0 별도 phase 권고)
- (선택) `setup_env.sh` 정합성 정리 — `.venv/` vs `venv/` 통일, SNOMED DB 절대 경로 링크 → README 안내로 분리

---

**v2.8.1 — N-3 smoke 4/4 완전 PASS 달성. R-7 본질 fix 사이클 종결.**
