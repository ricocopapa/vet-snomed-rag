# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.5.1] — 2026-04-25

### Fixed
- **T11 한국어 SNOMED 쿼리 PASS 회복** — `rag_pipeline.py`의 한국어 사전 치환 로직이 `llm_backend == "ollama"`일 때만 호출되어 gemini/none/claude 백엔드에서 한국어 임상 용어를 영어 SNOMED 검색에 매칭하지 못하는 문제 수정.
- 11-쿼리 정밀 회귀: gemini 9/10 → **10/10** 회복 (RERANK=1, 게이트 충족).

### Changed
- `translate_query_to_english(use_ollama_fallback: bool = True)` 파라미터 신규. False 시 사전 치환만 시도 (LLM 무관).
- `SNOMEDRagPipeline.query()` Step 0 분기를 `_contains_korean(question)` 단독 조건으로 완화. ollama 백엔드일 때만 LLM fallback 활성.

### Quality Metrics (v2.5.1)
- **정밀 회귀 (RERANK=1)**: gemini **10/10** / none 8/10 (이전 9/10 / 6/10 대비 +1 / +2)
- **단위 테스트 53건 PASS** 유지 (회귀 0)

## [2.5.0] — 2026-04-25

### Added

**v2.5 Tier A — Agentic RAG ⑤·⑥ 백엔드 분기 활성화**
- `SourceRoute` 라우팅 결정값을 실제 검색 백엔드까지 전달하는 시그니처 확장
- `SNOMEDRagPipeline.query()`에 `source_route: Optional[SourceRoute]` 파라미터 추가 (default None → v2.4 동일 동작 보장)
- HybridSearchEngine `vector_weight`/`sql_weight` 동적 주입 (cross-walk 키워드 → SQL-heavy / 한국어 자연어 → Vector-heavy)
- GraphRAG 조건부 분기 (`use_graph` False 시 graph 컨텍스트 비활성)

**v2.5 Tier B — ⑥ Sources의 "Tools & APIs" 외부 도구 통합**
- `src/tools/_cache.py`: LRU + TTL 결합 thread-safe 캐시 (max 1000, 24h TTL)
- `src/tools/umls_client.py`: NLM UMLS REST 클라이언트 (search / get_concept / get_cross_walks / search_with_cross_walks). 401·429·timeout graceful fallback. UMLS Affiliate License 한국 회원국 무료.
- `src/tools/pubmed_client.py`: NCBI E-utilities 클라이언트 (esearch + esummary). 토큰 버킷 rate limiter (3 rps without key / 10 rps with key) + 429 exponential backoff (1·2·4s).
- `SourceRoute.external_tools: list[str]` 필드 + 라우팅 룰 (ICD-10/MeSH/cross-walk 키워드 → ["umls"] / 신규·희귀·문헌 키워드 → ["pubmed"])
- `AgenticRAGPipeline`에 UMLS/PubMed 클라이언트 통합. 라우터 결정에 따라 외부 도구 호출 → `[UMLS Cross-Walk]` / `[PubMed Evidence]` markdown 섹션을 base.answer에 합류
- `AgenticRAGResult.external_results` 필드 (관찰성)
- `.env.example`에 `UMLS_API_KEY` + `NCBI_API_KEY` 템플릿 + 발급 가이드 주석

**Tests**
- `tests/test_cache.py` (7 케이스), `tests/test_umls_client.py` (8), `tests/test_pubmed_client.py` (11)
- `tests/test_source_router.py` 9 케이스 추가 (external_tools 라우팅), `tests/test_agentic_tier_b.py` (7) 신규
- 단위 테스트 누적 53건 PASS

**Smoke / Regression Scripts**
- `scripts/v2_5_tier_a_smoke.py`: 정적 검증 12 케이스
- `scripts/v2_5_tier_a_regression.py`: 인덱스 기반 mini regression (LLM 무관)
- `scripts/v2_5_tier_b_external_smoke.py`: 실제 UMLS / PubMed API 호출 검증
- `scripts/run_regression.py`에 `RERANK=1` 환경변수 분기 추가

**Docs**
- `docs/20260425_v2_5_tier_b_external_tools_design_v1.md` (신규 설계서)

### Changed
- `AgenticRAGPipeline.__init__`에 `umls_client`, `pubmed_client` Optional 파라미터 (None 시 env 기반 자동 init, 키 미설정 → 비활성)
- `_route_to_names`가 `external_tools` list 기반으로 정확한 도구명(`"umls"`, `"pubmed"`) 사용 (이전 `"external_tool"` 일반명에서 분리)

### Quality Metrics (v2.5.0)
- **단위 테스트 53건 PASS** (회귀 0)
- **mini regression PASS** (Tier A 가중치/Graph 분기 정량 입증, ctx_delta −1701/−471/−1233)
- **외부 API 실제 호출 PASS** (UMLS C0011849 + ICD10CM=E08-E13 / MeSH=D003920, PubMed PMID 42022391 2026 Vet Sci)
- **9/9 성공 기준 충족** (B-S1 ~ B-S9, 설계서 §3-5)

## [2.0.0] — 2026-04-22

### Added

**End-to-End Clinical Encoding Pipeline**
- `src/pipeline/stt_wrapper.py`: Whisper STT 래퍼 (faster-whisper / openai-whisper fallback, mp3/m4a/wav/ogg 4포맷)
- `src/pipeline/soap_extractor.py`: SOAP 추출기 — Gemini 3.1 Flash Lite Preview / Claude Haiku+Sonnet 멀티 백엔드. Step 0(정규화)+1(도메인 탐지)+2(필드 추출)+3(검증) 4단계 파이프라인
- `src/pipeline/snomed_tagger.py`: SNOMED 자동 태깅 — MRCM 25도메인 64패턴 검증 + 후조합 SCG 빌더
- `src/pipeline/e2e.py`: `ClinicalEncoder` — STT→SOAP→SNOMED 오케스트레이션. JSONL 출력, 에러 전파 명시
- `scripts/evaluate_e2e.py`: E2E 평가 스크립트 (strict / superset / synonym 3모드)
- `scripts/eval/metrics.py`: 필드 추출 Precision/Recall + SNOMED 일치율 계산

**Evaluation & Benchmark**
- `data/synthetic_scenarios/`: 합성 임상 시나리오 5건 (안과/위장관/정형/피부/종양) + gold-label
- `data/synthetic_scenarios/GOLD_AUDIT.md`: 역공학 감사 기록 (30건 변경, 0건 역공학 확인)
- `benchmark/v2_e2e_report_text.md`: 텍스트 모드 E2E 결과 (Precision 0.938 / Recall 0.737 / SNOMED 0.584 / p95 33,368ms)
- `benchmark/v2_e2e_report_audio.md`: 오디오 모드 E2E 결과 (Precision 0.826 / Recall 0.774 / SNOMED 0.250 / p95 60,461ms)
- `benchmark/v2_headline_metrics.md`: 핵심 지표 요약 (이력서·인용용)
- `benchmark/v2_reranker_report.md`: BGE Reranker 실험 결과 (기본 경로 비활성화 결정)
- `benchmark/v2_snomed_analysis.md`: SNOMED 미달 원인 분석
- `benchmark/v2_b2_gemini_port.md`: 3모델 비교 보고서
- `benchmark/charts/`: v2.0 차트 6종 (PNG)

**Streamlit UI**
- `app.py`: "Clinical Encoding" 탭 추가 — 음성/텍스트 파일 업로드 → JSONL 다운로드

**Tests**
- `tests/`: pytest 86건 (85 passed, 1 skipped) — B1~B4 + Remediation 3건 통합

### Changed
- 기본 RAG 파이프라인: M2 설정 (rerank=False, reformulator=gemini) 적용
- Gemini 리포뮬레이터 모델: 2.5 Flash → **3.1 Flash Lite Preview** (RPD 500, 25× 높은 할당량)
- MRCM 규칙 확장: 5도메인 → **25도메인**, 64필드 패턴
- `data/mrcm_rules_v1.json`: 25도메인 MRCM 규칙 (신규)
- `data/field_schema_v26.json`: 필드 스키마 v26 (외부화)

### Fixed
- SNOMED RAG 초기화 silent fallback 제거 — 에러 시 JSONL `errors[]`에 명시적 기록
- Gemini API 503/429/500 재시도 로직 추가 (3회, 지수 백오프 2s/4s/8s)
- `scripts/eval/metrics.py` synonym 모드 DB 테이블명 버그 (`relationships` → `relationship`)
- `scripts/evaluate_e2e.py` superset 모드 추가 (스키마 실존 추가 필드 neutral 처리)

### Quality Metrics (v2.0 Final)
- **텍스트 모드**: Precision 0.938 / Recall 0.737 / SNOMED 일치율 0.584 / Latency p95 33,368ms
- **오디오 모드**: Precision 0.826 / Recall 0.774 / SNOMED 일치율 0.250 / Latency p95 60,461ms
- **미달 항목**: SNOMED 일치율 목표 0.700 미달 (텍스트 0.584 / 오디오 0.250), 오디오 Latency 목표 60,000ms 대비 461ms 초과
- **pytest**: 85 passed, 1 skipped (86건 전체)

### Security
- Gold-label 역공학 감사 완료 — 30건 변경 중 0건 역공학 (GOLD_AUDIT.md §6)
- API 키 git 이력 검증 완료 — 0건 매치
- 실환자 데이터 0건 확인

[2.0.0]: https://github.com/ricocopapa/vet-snomed-rag/releases/tag/v2.0

## [1.0.0] — 2026-04-20

### Added — 초기 공개 릴리즈

**Core Features**
- Hybrid Retrieval 엔진: ChromaDB vector + SQLite SQL + RRF merging (α=0.6, β=0.4)
- Korean→English 번역 레이어: 수의학 용어 사전 160+ terms + Ollama LLM fallback
- Gemini 2.5 Flash Reformulator: 쿼리 재정식화 + post-coordination hints
- Dual LLM Backends: Ollama (local, gemma2:9b) + Claude Sonnet (cloud)
- Streamlit Demo UI + CLI interactive mode

**Benchmark — 11-query Regression Test (Before/After Gemini Reformulator)**
- PASS rate: 6/10 → 10/10 (+4건)
- Top-10 miss (NF): 5 → 1 (-4건)
- 평균 latency: 1,247 ms → 1,064 ms (−14.7%)

**Data Pipeline**
- graphify_lite: 경량 지식 그래프 빌더 + 회귀 테스트 자동화
- 11-query regression metrics (`graphify_out/regression_metrics.json`)
- Before/After 시각화 차트 3종 (matplotlib)

**Documentation**
- README: Mermaid 아키텍처 + 벤치마크 차트 임베드 + TOC
- MIT License (프로젝트 코드) + SNOMED CT 별도 라이선스 공지
- 6건 Streamlit 데모 스크린샷 수록
- CONTRIBUTING.md / SECURITY.md 가이드

### Excluded (SNOMED International Licensing)

- `data/` — 원본 RF2 DB, ChromaDB 벡터, 매핑 JSON 전체
- `docs/snomed_graph/`, `docs/snomed_graph_v2/` — 개념별 파생 MD 문서
- 사용자는 소속 국가의 Affiliate Licence 취득 후 로컬 재생성 필요

[1.0.0]: https://github.com/ricocopapa/vet-snomed-rag/releases/tag/v1.0
