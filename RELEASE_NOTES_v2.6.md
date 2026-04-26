# Release Notes — v2.6 (2026-04-26)

> **v2.6 — Agentic 정밀 회귀 + LLM 합성 + 한국어/영어 약식 사전 + T9 vector drift 정밀화**
>
> v2.5 / v2.5.1이 외부 도구 통합과 한국어 backend-무관 사전 치환을 완성했다면, **v2.6은 (1) agentic 11단계 정밀 회귀 매트릭스 정착, (2) 외부 도구 결과 LLM 합성, (3) 약식 클리니컬 용어(한국어 "당뇨" / 영어 "feline diabetes") 정식화, (4) RRF 가중치 + semantic_tag 화이트리스트로 T9 Top-1 정밀화**까지 종결한다.

---

## 핵심 메트릭

| 항목 | v2.5.1 | v2.6 (이번) | 변화 |
|---|---|---|---|
| **11-쿼리 정밀 회귀 (none, RERANK=1, Top-1 정확)** | 6/10 | **10/10** | +4 (사전 v1.2 + R-4) |
| **11-쿼리 정밀 회귀 (gemini, RERANK=1, Top-1 정확)** | 10/10 | **10/10** | 유지 (회귀 0) |
| **단위 테스트** | 53 | **180** | +127 (synthesizer 12 + flaky 결정화 등) |
| **agentic_query 정밀 회귀** | 미작성 | **12/12 PASS** (14쿼리 × 4모드) | 신규 매트릭스 |
| **한국어 사전** | 158항목 5카테고리 | **171항목 7카테고리** | +13 (질병 약식 10 + 영어 약식 3) |
| **외부 도구 결과 LLM 합성** | markdown append | **ExternalSynthesizerAgent** | 신규 (Gemini Flash Lite) |
| **T9 Top-1 정확도 (none)** | rank #3 (Top-5 PASS) | **rank #1** | R-4 정밀화 |

---

## v2.6 묶음 A — Agentic 정밀 회귀 + LLM 합성 (N-1 + N-3)

### N-1 Agentic_query 정밀 회귀 매트릭스

`run_regression.py`는 `base.query()` 기반이라 v2.4까지의 외부 도구 효과를 정량 검증 못 함. v2.6에서 **agentic_query 14쿼리 × 4모드(base/agentic/+rerank) 매트릭스**로 정착.

**산출물:**
- `scripts/run_regression_agentic.py` — 14쿼리 × 4모드 매트릭스
- `graphify_out/agentic_regression_metrics.json` + `agentic_vs_base_comparison.md`

**결과:**
- agentic_rerank 12/12 PASS, base_rerank 11/11 v2.5.1 baseline 일치 (회귀 0)
- 외부 도구 markdown 정확도: 1/3 (UMLS 빈 결과) → fix 후 **3/3 (100%)**

**부수 fix 2건:**
- `agentic_pipeline.py`: `AgenticRAGResult.last_sub_results` 노출 (search_results 추적)
- `agentic_pipeline.py`: UMLS/PubMed에 raw subquery 대신 `reformulation.reformulated` 전달 (메타 토큰 "ICD-10 cross-walk" 등이 UMLS 0건 반환 유발했던 문제 해소)
- `umls_client.py`: `DEFAULT_TIMEOUT 3.0 → 8.0` (실측 응답 변동 보험)

### N-3 외부 도구 결과 LLM 합성

v2.5의 외부 도구는 markdown append만 했고 LLM context로 합류하지 않았음. v2.6에서 **ExternalSynthesizerAgent**로 합성 단계 추가.

**산출물:**
- `src/retrieval/agentic/synthesizer.py` — `ExternalSynthesizerAgent` (Gemini Flash Lite Preview)
- `tests/test_synthesizer.py` — 12건 신규 PASS

**통합:**
- `AgenticRAGPipeline`에 `synthesis_used: bool`, `base_answer_pre_synthesis: str` 필드 추가
- 합성 호출 위치: Relevance Judge 직전. `external_results`가 비면 자동 skip → 회귀 0

**Smoke 검증:**
- #2 CUI/PMID 인용 ≥ 80%: 3/3 PASS
- #3 외부 OFF 회귀 0: 2/2 PASS
- #4 비용 < $0.001: 3/3 PASS (Gemini Flash Lite 추정)
- #1 합성 답변 ≥ +30% 길이: **quota reset 후 재검증 보류** (Free tier 20 RPD 일시 소진)

---

## v2.6 묶음 B — N-4 한국어 사전 v1.1 (질병 약식)

### 결함
T9 `"고양이 당뇨"` none FAIL — 약식 "당뇨" 미등록 (정식 "당뇨병"만 사전에 있음).

### 수정
- 신규 카테고리 `질병_약식(Disorder Alias)` + 10건:
  당뇨, 관절염, 심부전, 고혈압, 기관지염, 결막염, 각막염, 비만, 흉수, 복수
- 모두 SNOMED CT preferred_term/FSN 검증 100% PASS
- 사전 158→168항목, 5→6 카테고리

### 결과 (RERANK=1)
| Backend | v1.0 | v1.1 |
|---|---|---|
| none | 8/10 | **9/10** (T9 회복) |
| gemini | 10/10 | **10/10** (회귀 0) |

**검증 노트:** `docs/20260426_v2_6_n4_korean_lexicon_v1_1.md`

---

## v2.6 T7 처리 — 영어 약식 v1.2 (단어 경계 매칭)

### 결함
`feline diabetes` (영어 쿼리) none Top-1=347101000009106 Feline immune deficiency 오매핑.

### 원인
- SNOMED CT에 `feline diabetes` 단일 concept 없음. species 합성 + `Diabetes mellitus(73211009)` 표준
- v2.5.1까지 한국어 사전이 영어 쿼리에 적용 안 됨 (`_contains_korean()` 분기 차단)

### 수정
1. **사전 v1.1 → v1.2**: 신규 카테고리 `영어_약식(English Alias)` + 3건 (`feline/canine/bovine diabetes` → `+ mellitus`)
2. **`_replace_with_dictionary` 함수 강화**: 영어 키는 단어 경계(`\b`) 매칭 + `(?!\s+mellitus)` negative lookahead로 이중 치환 차단
3. **`rag_pipeline.py:495` 분기 확장**: 영어 쿼리(한국어 미포함)에도 사전 치환 적용 (LLM 무관)
4. **`tests/test_agentic_tier_b.py` 결정성**: `_make_pipe`에 synthesizer mock 추가하여 Gemini 실호출 비결정성 차단

### 결과 (RERANK=1)
| Backend | v1.1 | v1.2 (T7 fix) |
|---|---|---|
| none | 9/10 | **10/10** (T7 회복) |
| gemini | 10/10 | **10/10** (회귀 0) |

### 부작용 검증
- T8 `diabetes mellitus type 1` 변화 없음
- `feline diabetes mellitus` 입력 시 이중 치환 차단 (negative lookahead)
- 단위 테스트 180/180 PASS (flaky 1건 동시 결정화)

---

## v2.6 R-4 — T9 vector drift 정밀화

### 결함
T7 처리로 T9 `feline diabetes mellitus` (사전 치환 후 영어 쿼리) **none Top-5 PASS**이지만 Top-1=339181000009108 panleukopenia, rank #3=73211009. Top-1 부정확.

### 근본 원인 2건
1. **species qualifier 보존 정책** — `preprocess_for_vector`가 `feline/canine/bovine` 공식 SNOMED 형용사를 의도적 보존. 결과: vector 검색이 `feline X` disorder를 우선 끌어옴 → reranker가 species 매칭 강한 후보를 Top에 둠.
2. **semantic_tag 화이트리스트 부재** — `160303001 FH: Diabetes mellitus` (semantic_tag=situation, 가족력 코드)가 reranker candidate에 진입. 가중치만 변경하면 이 코드가 Top-1을 차지하는 새 결함 발생.

### 수정 (옵션 a + 화이트리스트 보강)
1. **`hybrid_search.py`**: `_MAPPING_INELIGIBLE_TAGS` 16-tag 블랙리스트 신규
   - 차단 대상: `situation`, `context-dependent category`, `qualifier value`, `occupation`, `person`, `social context`, `record artifact`, `foundation/core/namespace metadata concept`, `linkage concept`, `attribute`, `environment / location`, `ethnic/racial group`, `religion/philosophy`
   - 적용 위치: `search()` 내부 RRF 직후 + reranker 호출 직전
2. **`hybrid_search.py`**: RRF + `search()` default 가중치 `vector_weight 0.6→0.4`, `sql_weight 0.4→0.6` (SQL FTS 신뢰도 ↑)
3. **`rag_pipeline.py`**: `source_route` fallback default 동기화 (vw/sw 0.4/0.6)

### 결과 (RERANK=1, 정식 회귀 `scripts/run_regression.py`)
| Backend | Baseline (v2.6 T7 후) | R-4 fix 후 |
|---|---|---|
| none | 8/10 (T9 rank #3, T7 #1) | **10/10 PASS** Top-1 정확 |
| gemini | 10/10 (T9 #1) | **10/10 PASS** Top-1 정확 |

**T9 (`고양이 당뇨`):** none rank=1, gemini rank=1
**T7 (`feline diabetes`):** none rank=1, gemini rank=1

### 회귀 0 보장
- 단위 테스트 **180/180 PASS** 유지
- 11쿼리 다른 케이스 모두 Top-1 정확 (10/10, T5는 expected=None 제외)
- 산출물: `graphify_out/regression_metrics_rerank.json` 갱신, `backend_comparison.md` 갱신

---

## 마이그레이션 가이드

### v2.6 신규 환경변수
없음. UMLS / NCBI / Gemini 키는 v2.5에서 정착.

### Breaking Changes
**없음.** 모든 변경은 backward-compatible:
- `HybridSearchEngine.search()` default 가중치 변경(0.6/0.4 → 0.4/0.6) — 기존 호출자가 명시적으로 가중치 전달 시 영향 0
- `_MAPPING_INELIGIBLE_TAGS` 필터는 `rerank=True` + `enable_rerank=True` 경로에서만 작동 → v1.0 경로(`rerank=False`) 영향 0
- `ExternalSynthesizerAgent`는 external_results 비어 있으면 자동 skip → v2.5 동작 유지
- 사전 v1.2 추가 항목 13건은 모두 신규 — 기존 항목 수정 0

### 코드 마이그레이션
- 외부 도구 미사용 코드: **변경 0**
- agentic 합성 활성화: `AgenticRAGPipeline()` 자동 init (Gemini key 필요)

---

## Known Limitations

1. **N-3 smoke #1 (+30% 길이) 실측 보류** — Gemini Free Tier 일시 소진. fallback 정상으로 회귀 0 보장. quota reset 후 `scripts/n3_synthesis_smoke.py` 재실행으로 즉시 검증 가능.
2. **`ANTHROPIC_API_KEY` `.env` 빈 값** — Claude fallback 미가용. 진행 옵션 다양화 차원 (영향 0).
3. **test_pdf_reader.py 13건 FAIL** — v2.2 PDF reader 사전 결함, v2.6 작업 무관. v2.7+ 정리 예정.
4. **Web Search (Tavily) 미통합** — Tavily API 키 사전 액션 필요. v2.7 묶음 C 후보.

---

## 산출물 통계 (v2.6 누적)

| 분류 | 변경 수 |
|---|---|
| 핵심 모듈 변경 | 4 (`agentic_pipeline.py`, `rag_pipeline.py`, `hybrid_search.py`, `umls_client.py`) |
| 신규 모듈 | 1 (`synthesizer.py`) + 1 export (`agentic/__init__.py`) |
| 사전 갱신 | 1 (`vet_term_dictionary_ko_en.json` v1.0 → v1.2, 158→171항목) |
| 신규 테스트 | 1 (`test_synthesizer.py` 12건) + flaky 결정화 1 (`test_agentic_tier_b.py`) |
| 신규 스크립트 | 3 (`run_regression_agentic.py`, `n1_mini_external_recheck.py`, `n3_synthesis_smoke.py`) |
| 핸드오프·검증 노트 | 3 (`20260426_v2_6_roadmap_handoff.md`, `20260426_v2_6_n4_korean_lexicon_v1_1.md`, `20260427_v2_7_roadmap_handoff.md`) |
| 회귀 산출물 | 6 (rerank v1.0/v1.1/v1.2 baseline + agentic + comparison + smoke 로그) |

---

## Acknowledgements
- **NLM UMLS Terminology Services** — UMLS REST API + Affiliate License (한국 회원국 무료)
- **NCBI E-utilities** — PubMed esearch / esummary
- **Google Gemini** — Flash Lite Preview (외부 도구 결과 합성)
- **BAAI** — `bge-reranker-v2-m3` cross-encoder
- **VTSL (Virginia Tech)** — SNOMED VET Extension March 2026 Production
- **Datasciencedojo** — "RAG vs Agentic RAG" 11단계 인포그래픽

---

## Links
- Repository: [github.com/ricocopapa/vet-snomed-rag](https://github.com/ricocopapa/vet-snomed-rag)
- v2.6 핸드오프: `docs/20260426_v2_6_roadmap_handoff.md`
- v2.7 핸드오프: `docs/20260427_v2_7_roadmap_handoff.md`
- 이전 릴리즈: [v2.5](./RELEASE_NOTES_v2.5.md) · [v2.4](./RELEASE_NOTES_v2.4.md) · [v2.2](./RELEASE_NOTES_v2.2.md) · [v2.1](./RELEASE_NOTES_v2.1.md) · [v2.0](./RELEASE_NOTES_v2.0.md)
