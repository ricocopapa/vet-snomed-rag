# vet-snomed-rag 탐색 추천 질문

graphify_lite 분석 기반 코드베이스 탐색을 위한 추천 질문 목록.

1. `main` 수정 시 영향을 받는 함수/메서드는 무엇인가?
2. `src/retrieval/rag_pipeline.py`과 다른 검색 컴포넌트의 결합도는 어느 수준인가?
3. 커뮤니티 C4 (export_obsidian+graph_rag)와 C2 (graph_rag+hybrid_search) 사이의 인터페이스는 무엇인가?
4. `query_reformulator.py` 모듈 추가 시 어느 God Node의 degree_centrality가 가장 많이 변화하는가?
5. `rag_pipeline.py::SNOMEDRagPipeline.query`와 `hybrid_search.py::HybridSearchEngine.search`의 호출 체인을 추적하면 몇 단계인가?
6. `export_obsidian.py`가 SNOMED 온톨로지 그래프(`graph_rag.py`)를 간접적으로 의존하는 경로가 있는가?
7. `preprocess_query`와 `preprocess_for_vector`는 왜 분리되어 있으며, 통합 시 God Node 순위는 어떻게 바뀌는가?

---

## 활용 방법

1. `graph.html`을 브라우저에서 열어 인터랙티브 그래프를 탐색한다.
2. `nodes.csv`에서 degree_centrality 기준 상위 노드를 확인한다.
3. `edges.csv`에서 confidence=1.0(EXTRACTED) 엣지만 필터링하여 확실한 의존 관계를 파악한다.
4. `report.md`의 God Node 섹션과 Community 섹션을 연결하여 모듈 설계 패턴을 분석한다.