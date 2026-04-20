# vet-snomed-rag 코드베이스 지식 그래프 분석

생성 시각: 2026-04-19 16:57:49

## 요약

- 파일: 5개
- 노드: 총 70개
  - module: 5
  - class: 9
  - function: 31
  - method: 25
- 엣지: 총 458개
  - calls: 354
  - contains: 65
  - imports: 39
- 커뮤니티: 8개 감지됨
- 파싱 에러: 없음

## God Nodes (Top 5)

| 순위 | 노드 ID | degree_centrality | 해석 |
|---|---|---|---|
| 1 | `src/tools/export_obsidian.py::main` | 0.1442 | 공통 유틸 함수 — 여러 곳에서 호출됨 |
| 2 | `src/retrieval/rag_pipeline.py` | 0.1106 | 모듈 전체 참조 허브 |
| 3 | `...etrieval/hybrid_search.py::SQLRetriever::search` | 0.0913 | 핵심 메서드 — 파이프라인 중심 |
| 4 | `src/indexing/vectorize_snomed.py` | 0.0721 | 모듈 전체 참조 허브 |
| 5 | `src/retrieval/hybrid_search.py` | 0.0721 | 모듈 전체 참조 허브 |

## Community 분포 (상위 5)

| 커뮤니티 ID | 크기 | 대표 노드 | 응집 주제 |
|---|---|---|---|
| C4 | 15 | `src/retrieval/rag_pipeline.py` | export_obsidian / graph_rag / hybrid_search |
| C2 | 12 | `generate_concept_note` | export_obsidian / graph_rag / hybrid_search |
| C6 | 10 | `search` | export_obsidian / graph_rag / hybrid_search |
| C1 | 9 | `main` | export_obsidian / hybrid_search / rag_pipeline |
| C3 | 9 | `query` | graph_rag / hybrid_search / rag_pipeline |

## Surprising Connections (간접 2-hop 이상)

- 직접 연결 없는 모듈 간 간접 경로 미발견 (모든 모듈이 직접 연결됨)

## Suggested Questions

1. `main` 수정 시 영향을 받는 함수/메서드는 무엇인가?
2. `src/retrieval/rag_pipeline.py`과 다른 검색 컴포넌트의 결합도는 어느 수준인가?
3. 커뮤니티 C4 (export_obsidian+graph_rag)와 C2 (graph_rag+hybrid_search) 사이의 인터페이스는 무엇인가?
4. `query_reformulator.py` 모듈 추가 시 어느 God Node의 degree_centrality가 가장 많이 변화하는가?
5. `rag_pipeline.py::SNOMEDRagPipeline.query`와 `hybrid_search.py::HybridSearchEngine.search`의 호출 체인을 추적하면 몇 단계인가?
6. `export_obsidian.py`가 SNOMED 온톨로지 그래프(`graph_rag.py`)를 간접적으로 의존하는 경로가 있는가?
7. `preprocess_query`와 `preprocess_for_vector`는 왜 분리되어 있으며, 통합 시 God Node 순위는 어떻게 바뀌는가?
