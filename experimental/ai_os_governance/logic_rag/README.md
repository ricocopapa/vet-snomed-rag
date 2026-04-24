# Logic RAG PoC — v2.3.4 Roadmap

> **Sionic AI 방법론 자체 구현** (평범한 사업가 채널 #74, 2026)
>
> 사전 그래프 구축 비용 부담 → **질의 시점에 동적 지도 생성**.
> 낯선 도시에서 사람들에게 길을 물어가며 목적지에 도달하는 방식과 유사.

---

## 동작 원리

```
User Query
   │
   ▼
[1] Query Decomposition (LLM)
    └─ N개 sub-query + depends_on 매트릭스
   │
   ▼
[2] DAG Build + Topological Sort (Kahn 알고리즘)
    └─ cyclic 검증 + 해결 순서 산출
   │
   ▼
[3] Recursive Solve (위상 순서대로)
    └─ 각 sub-query에 선행 답변 컨텍스트 주입
   │
   ▼
[4] Synthesize (LLM)
    └─ 모든 sub-answer 통합 → 최종 답변
```

---

## 사용법

### E2E 실행
```python
from logic_rag import run_logic_rag_e2e

result = run_logic_rag_e2e(
    "vet-snomed-rag의 강점을 알려줘",
    max_subqueries=5,
)
print(result["final_answer"])
print(f"DAG depth: {result['max_depth']}")
print(f"Solve order: {result['order']}")
```

### 단계별 호출
```python
from logic_rag import decompose_query, topological_sort, solve_dag, synthesize

sub = decompose_query("디퓨전 업계 핫한 기업의 라이벌 회사", max_subqueries=4)
order = topological_sort(sub)
answers = solve_dag(sub, order)
final = synthesize("디퓨전 업계 핫한 기업의 라이벌 회사", sub, answers)
```

---

## 의존성

- `google-genai` (Gemini 2.5 Flash 기본)
- `GOOGLE_API_KEY` 환경변수 (vet-snomed-rag `.env`에서 자동 로드)

vet-snomed-rag `.venv` 활용 시 추가 설치 불필요.

---

## 테스트

```bash
cd ~/claude-cowork && PYTHONPATH=tools \
  ~/claude-cowork/07_Projects/vet-snomed-rag/.venv/bin/python -m pytest \
  tools/logic_rag/tests/test_dag.py -v
```

**현재 상태 (2026-04-24)**:
- DAG 위상 정렬 단위 테스트 **7/7 PASS** (LLM 호출 없이 순수 알고리즘 검증)
- E2E Gemini 호출은 작성 시점 `gemini-2.5-flash` 503 UNAVAILABLE (과부하)로 미검증 — A2A 브릿지(`../a2a/gemini_bridge.py`)는 동일 모델로 PASS했으므로 모델·API 키 문제 아님. 다음 세션에서 재시도 권장.

---

## v2.3.4 정식 통합 조건

- [ ] Query Decomposition 정확도 ≥ 90% (10건 임상 질의 테스트)
- [ ] DAG 깊이 평균 3-5 (과도한 분해 방지)
- [ ] Static SNOMED + Dynamic Logic RAG hybrid 응답 시간 < 5s
- [ ] LightRAG 등 대안 비교 벤치마크
- [ ] Cost: 단일 query LLM 호출 ≤ 6회 (decompose 1 + solve N + synthesize 1, N ≤ 5)

---

## 한계 (정직한 공개 — v0.1.0)

1. **순수 LLM 의존**: SNOMED CT 정적 그래프와 통합 미완 (v2.3.4 통합 조건)
2. **Cyclic decomposition**: LLM이 cyclic dependency를 만들 수 있음 → `topological_sort()` ValueError로 즉시 거부
3. **Cost**: 단일 query당 N+2 LLM 호출 (decompose 1 + solve N + synthesize 1)
4. **한국어 짧은 질의**: 분해 정확도 측정 미수행
5. **벤치마크 부재**: vet-snomed-rag 기존 RAG 대비 정량 비교 v2.3.4 통합 시 측정

---

## 출처

- 평범한 사업가 채널 #74 (2026): GraphRAG와 온톨로지 — Sionic AI 정세민 ML 리서처 + 박진형 ML 백엔드 엔지니어
- 핸드오프 §추가 적용 권고 F (2026-04-24)

---

*PoC 작성: 2026-04-24 | v0.1.0 Experimental | Issue #11*
