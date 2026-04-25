# Release Notes — v2.5 (2026-04-25)

> **v2.5 — Agentic RAG ⑤·⑥ 백엔드 분기 활성화 + 외부 도구(UMLS+PubMed) 통합 + 한국어 사전 backend-무관 작동**
>
> v2.4가 Agentic RAG 11단계의 *의사결정 layer*까지 완성했다면, **v2.5는 ⑤·⑥ Sources 단계의 실제 백엔드 분기 호출까지 활성화**한다. Datasciencedojo "RAG vs Agentic RAG" 다이어그램의 마지막 미완성 노드를 종결.

---

## 핵심 메트릭

| 항목 | v2.4 | v2.5 (이번) | 변화 |
|---|---|---|---|
| **11-쿼리 정밀 회귀 (gemini, RERANK=1)** | 10/10* | **10/10** | 유지 (한국어 분리 후 회복) |
| **11-쿼리 정밀 회귀 (none, RERANK=1)** | — | **8/10** | 한국어 사전 치환 효과 (이전 6/10) |
| **단위 테스트** | — | **53건 PASS** | cache 7 + UMLS 8 + PubMed 11 + router 14 + agentic 6 + tier-b 7 |
| **외부 도구 통합** | 미구현 (라우팅 결정만) | **UMLS + PubMed 실제 호출** | ⑥ Sources 활성화 |
| **외부 API 인증** | — | UMLS Affiliate / NCBI API key | 한국 회원국 무료 |
| **Tier A 회귀** | — | **0건** | source_route=None default 동일 동작 |

\* v2.4 메모리상 "10/10" 기준값. v2.5에서 검증 + T11 한국어 케이스 회복.

---

## v2.5 Tier A — 백엔드 분기 활성화

v2.4의 SourceRouter는 "어떤 소스를 쓸지" 결정만 했고 실제 백엔드까지 전달은 미구현. v2.5 Tier A에서 **라우터 결정 → 검색 백엔드 실행**으로 격상.

**변경 지점:**
- `SNOMEDRagPipeline.query()` 시그니처에 `source_route: Optional[SourceRoute]` 파라미터 추가 (default None → v2.4 동일)
- `HybridSearchEngine.search()` 호출에 `vector_weight` / `sql_weight` 동적 전달
- GraphRAG 컨텍스트 확장 블록에 `use_graph` 조건부 분기
- `AgenticRAGPipeline`의 `base.query()` 호출에 `source_route=route` 전달

**회귀 0 보장:**
- `source_route=None` default → v2.4의 0.6/0.4 가중치 + Graph 항상 활성과 100% 동일
- mini regression 실측 — baseline 3쿼리 결과 v2.4와 동일

**정량 효과:**
- `use_graph=False` 시 컨텍스트 길이 −1701 / −471 / −1233 (Graph 컨텍스트 비활성 정량 입증)
- `vector_weight=0.95` vs `0.05` 시 영어 쿼리 Top-5 완전 분기

---

## v2.5 Tier B — UMLS + PubMed 외부 도구 통합

Datasciencedojo Agentic RAG 다이어그램 ⑥ Sources의 "Tools & APIs" 분기 활성화.

### 채택 조합 (Combo Alpha)
도메인 조사 결과 사용자 LOCAL DB가 이미 SNOMED VET March 2026을 색인하고 있어 **Snowstorm fallback은 도메인 가치 낮음**. 대신 한국 EMR ICD-10 호환성 + 수의 임상 문헌 evidence를 직접 보강하는 조합 채택:

| 도구 | 가치 | 인증 | 비용 |
|---|---|---|---|
| **B-3 NLM UMLS REST** | ICD-10/11·MeSH·SNOMEDCT_VET cross-walk | UMLS Affiliate License (한국 회원국 무료) | 무료 |
| **B-5 NCBI PubMed E-utilities** | 수의 임상 문헌 evidence (esearch + esummary) | API Key 무료 (10 rps) | 무료 |

### 핵심 안전장치
- **env 미설정 자동 비활성** — `UMLS_API_KEY` / `NCBI_API_KEY` 미설정 시 클라이언트 자동 비활성, 외부 호출 0
- **5종 graceful fallback** — 401 (인증 실패) / 429 (rate limit) / 5xx / timeout / 네트워크 → 빈 결과
- **토큰 버킷 rate limiter** + 429 exponential backoff (1·2·4s, 3회 후 포기)
- **LRU+TTL cache 24h** — 동일 쿼리 재호출 시 외부 API 호출 0
- **회귀 0 보장** — `source_route.external_tools=[]` default → 외부 호출 0건

### 라우팅 룰
- **UMLS 활성**: `ICD-10/11`, `MeSH`, `RxNorm`, `cross-walk`, `매핑`, `크로스워크`, `코드 변환` 키워드
- **PubMed 활성**: `emerging`, `novel`, `rare`, `최신`, `신규`, `희귀`, `literature`, `논문`, `문헌` 키워드

### 실제 외부 API 호출 검증
사용자 키로 실측:
```
[UMLS]   search('diabetes mellitus') → C0011849 Diabetes Mellitus
         cross-walks: ICD10CM=E08-E13 / MSH=D003920
[PubMed] search('feline diabetes') → PMID 42022391, 42014100 (2026)
         Top-1: 2026 Front Vet Sci — From pathogenesis to prevention...
```

---

## v2.5.1 — 한국어 사전 치환 backend-무관 작동

### 문제
v2.4까지 `rag_pipeline.py`의 한국어 → 영어 사전 치환 로직(`translate_query_to_english`)이 **`llm_backend == "ollama"`일 때만 호출**됐다. gemini / none / claude 백엔드에서는 한국어 임상 용어 → 영어 SNOMED 매칭 안 됨. 결과: T11 `고양이 범백혈구감소증 SNOMED 코드` FAIL.

### 수정
- `translate_query_to_english(use_ollama_fallback: bool = True)` 파라미터 신규
  - True (default, ollama backend): dict + ollama 번역 (기존 동작)
  - False (gemini/none/claude): dict 치환만, 잔여 한국어 그대로 반환
- `rag_pipeline.py:482` Step 0 분기를 `_contains_korean(question)` 단독 조건으로 완화

### 결과
- **T11 PASS**: `"고양이 범백혈구감소증 SNOMED 코드"` → 사전 치환 → `"feline panleukopenia SNOMED 코드"` → 전처리 → `"feline panleukopenia"` → 검색 + reranker → 339181000009108 PASS
- **부수 효과 (none backend +2)**: T10 `"개 췌장염"` + T11도 reformulator 없이 사전만으로 PASS
- **사용자 도메인 직접 가치** — 한국어 임상 용어가 LLM 백엔드 무관 정상 검색 (향남병원 STT 출력 등 한국어 임상 환경)

---

## 마이그레이션 가이드

### 신규 환경변수 (v2.5 Tier B 사용 시)
```bash
# .env 추가
UMLS_API_KEY=발급받은_UMLS_키       # 36자 UUID
NCBI_API_KEY=발급받은_NCBI_키       # 36자 hex
```

### API 키 발급
- **UMLS**: [uts.nlm.nih.gov/uts/signup-login](https://uts.nlm.nih.gov/uts/signup-login) → My Profile → Edit Profile → "Generate new API Key" 체크 → Save Profile (한국 회원국 무료, 1~3 영업일 승인)
- **NCBI**: [ncbi.nlm.nih.gov/account](https://www.ncbi.nlm.nih.gov/account/) → Account Settings → API Key Management → Create (즉시 발급)

### 코드 마이그레이션
- 외부 도구를 사용하지 않는 기존 코드는 **변경 0** (모든 신규 파라미터 default가 v2.4 동작 보장)
- 외부 도구 사용 시: `AgenticRAGPipeline()` 자동 init하거나 명시적으로 `umls_client=...`, `pubmed_client=...` 주입

---

## Breaking Changes
**없음.** 모든 변경은 backward-compatible:
- `SNOMEDRagPipeline.query()`의 `source_route` 파라미터: default None → v2.4 동일
- `AgenticRAGPipeline.__init__`의 `umls_client`/`pubmed_client`: default None → 자동 init (env 기반)
- `SourceRoute.external_tools` 필드: default empty list → 기존 코드 영향 0
- `translate_query_to_english`의 `use_ollama_fallback`: default True → 기존 호출자(ollama backend) 영향 0

---

## Known Limitations

1. **agentic_query 경로 회귀 미작성** — `run_regression.py`는 `base.query()` 기반이라 외부 도구 효과 정량화 미반영. v2.6에서 별도 회귀 스크립트 작성 예정.
2. **Web Search (Tavily/Brave) 미통합** — Combo Beta·Gamma 후보였으나 v2.5 범위에서 제외. v2.6+ 예정.
3. **agentic Step C에서 외부 도구 결과는 `base.answer`에 markdown append만** — LLM context로 합류는 안 됨 (별도 합성 LLM 호출 v2.6+ 예정).

---

## 산출물 통계 (v2.5 누적)

| 분류 | 파일 수 |
|---|---|
| 신규 모듈 | 4 (`_cache.py`, `umls_client.py`, `pubmed_client.py`, `tools/__init__.py`) |
| 확장 모듈 | 4 (`rag_pipeline.py`, `agentic_pipeline.py`, `source_router.py`, `run_regression.py`) |
| 신규/확장 테스트 | 5 (cache, UMLS, PubMed, source_router 확장, agentic_tier_b) — 53건 PASS |
| 신규 스크립트 | 3 (`v2_5_tier_a_smoke.py`, `v2_5_tier_a_regression.py`, `v2_5_tier_b_external_smoke.py`) |
| 설계서 | 1 (`docs/20260425_v2_5_tier_b_external_tools_design_v1.md`) |
| 회귀 산출물 | 2 (`graphify_out/regression_metrics.json`, `regression_metrics_rerank.json`) |

---

## Acknowledgements
- **NLM UMLS Terminology Services** — UMLS REST API + Affiliate License
- **NCBI E-utilities** — PubMed esearch / esummary
- **VTSL (Virginia Tech)** — SNOMED VET Extension March 2026 Production
- **Datasciencedojo** — "RAG vs Agentic RAG" 11단계 인포그래픽 (구현 가이드라인)

---

## Links
- Repository: [github.com/ricocopapa/vet-snomed-rag](https://github.com/ricocopapa/vet-snomed-rag)
- v2.5 설계서: `docs/20260425_v2_5_tier_b_external_tools_design_v1.md`
- 이전 릴리즈: [v2.4](./RELEASE_NOTES_v2.4.md) · [v2.2](./RELEASE_NOTES_v2.2.md) · [v2.1](./RELEASE_NOTES_v2.1.md) · [v2.0](./RELEASE_NOTES_v2.0.md)
