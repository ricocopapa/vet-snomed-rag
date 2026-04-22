# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
