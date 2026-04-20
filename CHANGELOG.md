# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
