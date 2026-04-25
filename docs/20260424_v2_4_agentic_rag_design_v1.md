---
tags: [design, v2.4, agentic-rag, vet-snomed-rag, wave-1, 2026-04]
date: 2026-04-24
version: v2.4 design v1 (draft)
author: claude-opus-4-7-1m (Wave 1)
parent_version: v2.2 (git tag v2.2 · commit f3ff9c0 on main)
current_branch: feature/v2.3-ai-os-pocs (PR #7)
target_branch: feature/v2.4-agentic-rag (신규 분기 예정)
status: pending_user_approval
---

# v2.4 Agentic RAG 완전 구현 설계서 (Wave 1)

> **목적:** Datasciencedojo "RAG vs Agentic RAG" 기준 11단계 Agentic RAG 루프를 vet-snomed-rag에 완전 구현. 현재 v2.2는 6/11 단계만 구현 → v2.4에서 11/11 달성.
>
> **범위:** 본 문서 = Wave 1 산출물(설계·스펙). Wave 2~5 구현·테스트·벤치마크·문서는 별도 파일.
>
> **작성 원칙:** self-contained — 신규 세션이 본 문서만 읽어도 Wave 2 착수 가능. Anti-Sycophancy — 확정된 것만 확정, 미정은 `[TBD]` 명시.

---

## §0. 본 설계서의 Task Definition (5항목)

| 항목 | 내용 |
|---|---|
| 입력 데이터 | vet-snomed-rag 현 소스(src/retrieval/) + tools/logic_rag/ + tools/objective_drift/ + Agentic RAG 11단계 이미지 |
| 판단 기준 | 이미지 11단계 1:1 대응 + 벤치마크 회귀 0건 + Latency p95 ≤60s(FDA Class II 한계) 유지 |
| 실행 방법 | Goal-Backward 분해 → Wave 2~5 순차 실행 + 각 Wave 별 Exit Criteria 충족 |
| 산출물 포맷 | (Wave 1) 본 설계서 / (Wave 2~5) 코드·테스트·벤치마크·RELEASE_NOTES |
| 성공 기준 | Exit Criteria §10 8항목 전수 PASS + v4 감사 재돌림 Critical 0 |

**검증 출처:**
- Agentic RAG 11단계: Datasciencedojo 인포그래픽 (사용자 제공)
- 현 코드 구조: `src/retrieval/rag_pipeline.py` L399~565 Read 확인 완료
- PoC 재활용 자산: `tools/logic_rag/` + `tools/objective_drift/` + `.a2a/` Read 확인 완료
- 벤치마크 기준선: `benchmark/v2.1_final_e2e_report.md` (Precision 0.891 / Recall 0.772 / F1 0.827 / SNOMED 0.889 / p95 35.4s)

---

## §1. Goal + Acceptance Criteria

### 1.1 Goal (단일 문장)

**vet-snomed-rag v2.4에서 Agentic RAG 11단계를 완전 구현하고, 복잡 질의 품질 개선을 정량 증명하며, Latency p95 60s 한도 내에서 FDA Class II 요건을 유지한다.**

### 1.2 Acceptance Criteria (Exit Criteria §10 축약판)

1. Agentic RAG 11단계 중 **11/11 구현**(현재 6/11)
2. 신규 pytest **15건 이상 + 기존 106/107 regression PASS**
3. v2.2 기준선 대비 **SNOMED Match 동일 이상** (0.889 ≤ v2.4)
4. **Latency p95 ≤60s** (현 35.4s + 루프 overhead 수용 가능 한도)
5. **벤치마크 투명 병기** — v2.2/v2.4 2행 표, 하락 시 사유 기록
6. RELEASE_NOTES_v2.4 + README + 이력서·포폴 §9.6 동기화 완료
7. **v4 Integrity Audit 재돌림 Critical 0 · Warning ≤ 3**
8. **git tag v2.4 + PR merge 준비 완료**

---

## §2. 백업·롤백 전략 (사용자 명시 요구)

### 2.1 3중 백업

| 계층 | 수단 | 복원 명령 | 책임 시점 |
|---|---|---|---|
| L1 (이미 확보) | `git tag v2.2` 존재 | `git checkout v2.2` | 불변 |
| L2 (분기) | 신규 브랜치 `feature/v2.4-agentic-rag` | `git checkout feature/v2.3-ai-os-pocs` (현재 PR #7 브랜치로 복귀) | Wave 2 착수 직전 |
| L3 (물리 스냅샷) | `src/retrieval/` → `src/retrieval_v2_2_snapshot/` 복사 | `rm -rf src/retrieval && mv src/retrieval_v2_2_snapshot src/retrieval` | Wave 2 착수 직전 |

### 2.2 브랜치 전략

```
main (v2.2 baseline)
 └─ feature/v2.3-ai-os-pocs (PR #7, 현재 브랜치, AI OS governance 3 PoC + Logic RAG)
     └─ feature/v2.4-agentic-rag (신규 분기, Agentic RAG 11단계 구현)
         → PR #12 (별도 PR) 또는 PR #7에 승계
```

**권고:** PR #7과 **별도 PR #12** 생성. 이유:
- PR #7은 "Governance Layer PoC"로 스코프 확정
- v2.4 Agentic RAG는 본체 파이프라인 변경 → 리뷰·벤치마크 단위 분리 필요

### 2.3 커밋 단위

원자적 커밋 10개 이상 예상:
1. `chore: branch out feature/v2.4-agentic-rag + snapshot retrieval_v2_2`
2. `feat(v2.4): scaffold AgenticRAGPipeline skeleton`
3. `feat(v2.4): G-1 QueryComplexityAgent + tests`
4. `feat(v2.4): G-2 SourceRouterAgent + tests`
5. `feat(v2.4): G-3 RelevanceJudgeAgent + tests`
6. `feat(v2.4): G-4 RewriteLoopController + tests`
7. `feat(v2.4): AgenticRAGPipeline integration`
8. `test(v2.4): E2E regression + 3 new agentic scenarios`
9. `bench(v2.4): v2.2 vs v2.4 comparison report`
10. `docs(v2.4): RELEASE_NOTES + README + Portfolio §9.6`

---

## §3. 현 상태 vs 목표 11단계 상세 매핑

### 3.1 현 파이프라인 흐름 (v2.2 실측)

```
query (Step 0)
 → 한국어→영어 번역 (Step 0)
 → 메타 불용어 제거 (Step 0.5)
 → Reformulator.reformulate() (Step 0.7)  ← ✅ Agentic #2 구현됨
 → HybridSearchEngine.search(vector + sql + RRF + BGE rerank) (Step 1)
 → build_context (Step 2)
 → SNOMEDGraph.explore (Step 2.5, GraphRAG 확장)
 → generate_with_claude/ollama (Step 3)
 → response
```

### 3.2 목표 v2.4 파이프라인 흐름

```
query
 → [Step A] QueryComplexityAgent  ← ✨ NEW (Agentic #4)
     ├─ simple → direct retrieval
     └─ complex → decompose sub-queries (logic_rag.decompose 재활용)

 → [Step B] SourceRouterAgent  ← ✨ NEW (Agentic #5)
     ├─ 선택 소스: vector / sql / graph / external_tool
     └─ per-subquery 별도 라우팅 허용

 → Reformulator.reformulate()  ← ✅ 유지 (Agentic #2)

 → HybridSearchEngine.search(라우팅된 소스만)

 → build_context + Graph explore (Agentic #6·#7)

 → generate_with_claude/ollama (Agentic #8·#9)

 → [Step D] RelevanceJudgeAgent  ← ✨ NEW (Agentic #10)
     ├─ 판정: PASS / PARTIAL / FAIL
     └─ confidence score

 → [Step E] RewriteLoopController  ← ✨ NEW (Agentic #11)
     ├─ PASS → Final Response
     ├─ PARTIAL + iter < max_iter → Rewrite Query → back to Step A
     └─ FAIL + iter = max_iter → 현재 답변 + "신뢰도 낮음" 경고 병기
```

### 3.3 11단계 1:1 매핑 최종 판정

| # | Agentic RAG 단계 | v2.2 상태 | v2.4 상태 | 구현 주체 |
|---|---|---|---|---|
| 1 | Query | ✅ | ✅ | 기존 유지 |
| 2 | Rewrite Query | ✅ (Reformulator) | ✅ 유지 + 루프 재진입 시 재호출 | `query_reformulator.py` 확장 |
| 3 | Updated Query | ✅ | ✅ | 기존 유지 |
| 4 | Need More Details? | ❌ | ✨ **G-1** 신규 | `agentic/query_complexity.py` |
| 5 | Which Source? | ❌ | ✨ **G-2** 신규 | `agentic/source_router.py` |
| 6 | Sources (Vector+Tools+Internet) | ⚠️ 부분 | ✅ Tools 확장 (SNOMED Graph 명시 + 외부 tool 훅) | `agentic/source_router.py` |
| 7 | Retrieved Context + Updated Query | ✅ | ✅ 유지 | 기존 유지 |
| 8 | LLM | ✅ | ✅ 유지 | 기존 유지 |
| 9 | Response | ✅ | ✅ 유지 | 기존 유지 |
| 10 | Is the answer relevant? | ❌ | ✨ **G-3** 신규 | `agentic/relevance_judge.py` |
| 11 | Final Response / Rewrite Loop | ❌ | ✨ **G-4** 신규 | `agentic/loop_controller.py` + `agentic_pipeline.py` |

**결과: 6/11 → 11/11 (4 gap 해소)**

---

## §4. AgenticRAGPipeline API 명세

### 4.1 클래스 정의

**파일:** `src/retrieval/agentic_pipeline.py` (신규)

```python
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class AgenticRAGResult:
    question: str
    final_answer: str
    iterations: int
    loop_trace: list[dict]          # 각 iter별 {query, complexity, sources, answer, relevance}
    subqueries: list[str] | None    # G-1 분해 결과 (simple이면 None)
    sources_used: list[str]         # G-2 동적 라우팅 결과
    relevance_verdict: Literal["PASS", "PARTIAL", "FAIL"]
    confidence: float               # 0.0~1.0
    latency_ms: dict                # {step_A: ..., total: ...}
    v2_2_compat: bool = True        # 기존 query()와 동일 output 생성 가능 여부


class AgenticRAGPipeline:
    """v2.4 Agentic RAG 11단계 완전 구현.

    v2.2 SNOMEDRagPipeline을 wrapping. 기존 query() API는 pipeline.base로 보존.
    """

    def __init__(
        self,
        base_pipeline: "SNOMEDRagPipeline",
        complexity_agent_backend: str = "gemini-2.5-flash-lite",
        source_router_backend: str = "rule_based",     # "rule_based" | "gemini"
        judge_backend: str = "gemini-2.5-flash-lite",
        max_iter: int = 3,
        relevance_threshold: float = 0.7,
        enable_tracing: bool = True,
    ):
        ...

    def agentic_query(
        self,
        question: str,
        top_k: int = 10,
        rerank: bool = True,
    ) -> AgenticRAGResult:
        """11단계 Agentic RAG 루프 실행."""
        ...

    def query(self, question: str, **kwargs) -> dict:
        """v2.2 호환 API — base_pipeline.query()에 위임."""
        return self.base.query(question, **kwargs)
```

### 4.2 호환성 원칙

- **기존 `SNOMEDRagPipeline.query()`는 절대 변경 금지** — v2.2 벤치마크 회귀 0건 보장
- `AgenticRAGPipeline`은 **신규 wrapper**. 기존 코드는 건드리지 않음
- 기존 app.py / api는 점진 이관. v2.4 초기 릴리즈는 `agentic_query()` 별도 엔드포인트만 제공

---

## §5. Gap 4종 에이전트 인터페이스 스펙

### 5.1 G-1 QueryComplexityAgent (Agentic #4)

**파일:** `src/retrieval/agentic/query_complexity.py`

**책임:** 쿼리가 단일 retrieval로 충분한지, 분해 필요한지 판단.

**인터페이스:**
```python
@dataclass
class ComplexityVerdict:
    is_complex: bool
    subqueries: list[str] | None        # is_complex=True면 2~5개
    reasoning: str
    confidence: float

class QueryComplexityAgent:
    def judge(self, query: str, max_subqueries: int = 5) -> ComplexityVerdict:
        ...
```

**구현 전략:**
- `logic_rag.decompose.decompose_query()` 재활용 (이미 검증됨)
- 단, `max_subqueries=1` 강제 → 응답 subquery가 1개면 `is_complex=False`
- 응답 `depends_on` 메타를 `subqueries` 순서로 변환

**Fallback:** Gemini API 503 발생 시 rule-based:
- 쿼리 길이 < 30자 AND "and/or/vs/compare" 키워드 없음 → `is_complex=False`

**테스트 (5건):**
1. "feline diabetes SNOMED code" → is_complex=False
2. "feline diabetes and parvovirus prevention strategies" → is_complex=True, 2 subqueries
3. "비교" / "차이" / "vs" 포함 케이스 → is_complex=True
4. 500자 장문 → is_complex=True
5. Gemini 503 mock → rule-based fallback 동작

---

### 5.2 G-2 SourceRouterAgent (Agentic #5·#6)

**파일:** `src/retrieval/agentic/source_router.py`

**책임:** 쿼리·서브쿼리별 어떤 소스를 사용할지 동적 결정.

**인터페이스:**
```python
@dataclass
class SourceRoute:
    use_vector: bool = True
    use_sql: bool = True
    use_graph: bool = True
    use_external_tool: bool = False        # 향후 웹 검색 등 확장
    vector_weight: float = 0.6
    sql_weight: float = 0.4
    reasoning: str = ""

class SourceRouterAgent:
    def route(self, query: str) -> SourceRoute:
        ...
```

**구현 전략 (rule_based 기본):**

| 쿼리 패턴 | 라우팅 |
|---|---|
| "SNOMED code" / concept_id 포함 | SQL 가중 (0.7), Vector 0.3 |
| 한국어 자연어 (임상 증상) | Vector 가중 (0.7), SQL 0.3 |
| "관계" / "상위 개념" / "유사 질환" | Graph 활성, Vector+SQL 동등 |
| 영어 의학 용어 정확 매칭 | Vector 0.5, SQL 0.5 |
| 그 외 | 기존 기본값 유지 (V 0.6 / S 0.4) |

**Gemini 옵션:** 복잡 판단 필요 시 `backend="gemini"` → Gemini flash-lite 1회 호출로 route 결정.

**테스트 (4건):**
1. "73211009" → SQL 0.7
2. "고양이 당뇨" → Vector 0.7
3. "feline diabetes의 상위 개념" → use_graph=True
4. "pancreatitis in dog" → 기본값

---

### 5.3 G-3 RelevanceJudgeAgent (Agentic #10)

**파일:** `src/retrieval/agentic/relevance_judge.py`

**책임:** 생성된 답변이 쿼리에 충분히 관련·정확한지 판정.

**인터페이스:**
```python
@dataclass
class RelevanceVerdict:
    verdict: Literal["PASS", "PARTIAL", "FAIL"]
    confidence: float                      # 0.0~1.0
    missing_aspects: list[str]             # PARTIAL/FAIL 시 누락 관점
    reasoning: str

class RelevanceJudgeAgent:
    def judge(
        self,
        query: str,
        answer: str,
        retrieved_concepts: list[dict],    # SearchResult 요약
    ) -> RelevanceVerdict:
        ...
```

**구현 전략:**
- Gemini flash-lite judge (gemini-2.5-flash-lite, 1.0s latency) — 비용 최소
- Prompt: "쿼리·답변·검색 결과 3자를 검토. 누락·불일치가 있으면 PARTIAL, 완전 틀리면 FAIL, 충분하면 PASS"
- JSON schema 강제 + parse 실패 시 `PARTIAL / confidence=0.5` 폴백

**임계값 (relevance_threshold=0.7 기본):**
- PASS + confidence ≥0.7 → 루프 종료
- PARTIAL + confidence ≥0.5 → 루프 계속 (iter < max)
- FAIL → 즉시 rewrite

**테스트 (6건):**
1. 완벽 답변 → PASS / confidence ≥0.8
2. 일부 누락 답변 → PARTIAL
3. 완전 엉뚱 답변 → FAIL
4. Empty answer → FAIL
5. JSON 파싱 실패 mock → PARTIAL / 0.5 폴백
6. Gemini 503 mock → PARTIAL / 0.5 폴백 (안전 기본)

---

### 5.4 G-4 RewriteLoopController (Agentic #11)

**파일:** `src/retrieval/agentic/loop_controller.py`

**책임:** Relevance 결과에 따라 Rewrite 루프 결정 + max_iter 관리 + cycle detection.

**인터페이스:**
```python
@dataclass
class LoopDecision:
    should_continue: bool
    new_query: str | None                  # should_continue=True면 재작성된 쿼리
    reason: str
    iter_count: int

class RewriteLoopController:
    def __init__(self, max_iter: int = 3, threshold: float = 0.7):
        ...

    def decide(
        self,
        original_query: str,
        current_query: str,
        relevance: RelevanceVerdict,
        iter_count: int,
        history: list[str],                # 이전 쿼리들 (cycle detection용)
    ) -> LoopDecision:
        ...
```

**구현 전략:**
- PASS + threshold 충족 → `should_continue=False` (성공 종료)
- PARTIAL + iter < max_iter → Gemini로 `missing_aspects` 반영한 신규 쿼리 생성
- FAIL + iter < max_iter → 원본 쿼리로 복귀 + Gemini reformulation 강화
- iter ≥ max_iter → `should_continue=False` (최대치 도달 종료)
- Cycle detection: `new_query` cosine similarity(history) > 0.95 → 강제 종료 ("동일 패턴 반복")

**테스트 (5건):**
1. iter=0, PASS → continue=False
2. iter=1, PARTIAL → continue=True, new_query != original
3. iter=3, PARTIAL → continue=False (max 도달)
4. 동일 쿼리 2회 반복 → cycle detection 발동
5. FAIL → continue=True, reformulation 강화 프롬프트

---

## §6. 통합 아키텍처

### 6.1 디렉토리 신규 구조

```
src/retrieval/
├── agentic/                         ← ✨ 신규 디렉토리
│   ├── __init__.py
│   ├── query_complexity.py          (G-1)
│   ├── source_router.py             (G-2)
│   ├── relevance_judge.py           (G-3)
│   └── loop_controller.py           (G-4)
├── agentic_pipeline.py              ← ✨ 신규 (AgenticRAGPipeline wrapper)
├── rag_pipeline.py                  ← 기존 유지 (변경 0)
├── hybrid_search.py                 ← 기존 유지 + router 호출 추가 (1~2줄)
├── query_reformulator.py            ← 기존 유지
├── graph_rag.py                     ← 기존 유지
├── reranker.py                      ← 기존 유지
└── cache/                           ← 기존 유지
```

### 6.2 통합 Flow (`AgenticRAGPipeline.agentic_query()`)

```python
def agentic_query(self, question: str, top_k: int = 10, rerank: bool = True):
    t0 = time.time()
    history = []
    current_query = question

    for iter_count in range(self.max_iter + 1):
        # Agentic Step A (#4)
        complexity = self.complexity_agent.judge(current_query)

        # Agentic Step B (#5·#6)
        subqueries = complexity.subqueries or [current_query]
        aggregated_context = []
        sources_used_all = set()
        for sq in subqueries:
            route = self.source_router.route(sq)
            sources_used_all.update(self._route_to_source_names(route))
            # 기존 base_pipeline.engine.search에 route 가중치 전달
            results = self.base.engine.search(
                sq, top_k=top_k, rerank=rerank,
                vector_weight=route.vector_weight,
                sql_weight=route.sql_weight,
                include_relationships=route.use_graph,
            )
            aggregated_context.append(...)  # #7

        # Agentic Step C (#2·#3·#8·#9)
        full_context = self._merge_context(aggregated_context)
        answer = self.base._generate(question, full_context)  # #8·#9

        # Agentic Step D (#10)
        relevance = self.judge.judge(current_query, answer, aggregated_context)

        # Agentic Step E (#11)
        decision = self.loop.decide(question, current_query, relevance, iter_count, history)
        history.append(current_query)
        if not decision.should_continue:
            return AgenticRAGResult(
                final_answer=answer,
                iterations=iter_count + 1,
                relevance_verdict=relevance.verdict,
                confidence=relevance.confidence,
                sources_used=list(sources_used_all),
                subqueries=complexity.subqueries,
                ...
            )
        current_query = decision.new_query

    # Loop max 도달 fallback
    return AgenticRAGResult(..., relevance_verdict="FAIL", ...)
```

### 6.3 외부 의존성

- `google-genai` (기존) — Complexity·Judge·Loop 모두 flash-lite 사용
- `sentence-transformers` (기존) — cycle detection cosine similarity
- 신규 의존성 **0개**

---

## §7. Wave 2~5 체크리스트

### Wave 2 — Gap 4종 구현 (예상 1.5d, 병렬 가능)

**2.1 브랜치 분기 + 스냅샷** (사용자 승인 후 즉시)
- [ ] `git checkout -b feature/v2.4-agentic-rag`
- [ ] `cp -r src/retrieval src/retrieval_v2_2_snapshot` + `.gitignore`에 `retrieval_v2_2_snapshot/` 추가
- [ ] 빈 커밋 "chore: scaffold v2.4 agentic rag branch"

**2.2 G-1 QueryComplexityAgent** (3h)
- [ ] `src/retrieval/agentic/query_complexity.py` 작성 (§5.1 인터페이스)
- [ ] `tests/test_query_complexity.py` 5건 (§5.1 테스트)
- [ ] Commit `feat(v2.4): G-1 QueryComplexityAgent + tests`

**2.3 G-2 SourceRouterAgent** (3h)
- [ ] `src/retrieval/agentic/source_router.py` (§5.2)
- [ ] `tests/test_source_router.py` 4건
- [ ] `hybrid_search.py`의 `search()` 시그니처가 이미 weights 받으므로 수정 최소
- [ ] Commit `feat(v2.4): G-2 SourceRouterAgent + tests`

**2.4 G-3 RelevanceJudgeAgent** (3h)
- [ ] `src/retrieval/agentic/relevance_judge.py` (§5.3)
- [ ] `tests/test_relevance_judge.py` 6건 (mock Gemini 포함)
- [ ] Commit `feat(v2.4): G-3 RelevanceJudgeAgent + tests`

**2.5 G-4 RewriteLoopController** (3h)
- [ ] `src/retrieval/agentic/loop_controller.py` (§5.4)
- [ ] `tests/test_loop_controller.py` 5건
- [ ] Commit `feat(v2.4): G-4 RewriteLoopController + tests`

**Exit:** 신규 pytest 20건 PASS + 기존 106/107 regression PASS

---

### Wave 3 — 통합 + pytest 회귀 (0.5d)

- [ ] `src/retrieval/agentic_pipeline.py` 작성 (§6.2 Flow)
- [ ] `tests/test_agentic_pipeline.py` E2E 시나리오 5건
  1. simple query → iter 1, PASS
  2. complex query → decompose, iter 1~2
  3. partial answer → rewrite loop → PASS
  4. max iter 도달 → FAIL 반환
  5. cycle detection → 조기 종료
- [ ] `.venv/bin/python -m pytest tests/ -v` 전체 PASS 확인
- [ ] Commit `feat(v2.4): AgenticRAGPipeline integration`

**Exit:** 전체 pytest 130+ PASS (기존 106 + 신규 25+)

---

### Wave 4 — 재벤치마크 (1d)

**4.1 v2.2 baseline 재확인** (`scripts/evaluate_e2e.py`)
- [ ] `benchmark/v2_4_baseline_v22_rerun.md` 작성 (v2.1_final_e2e_report.md 재현)

**4.2 v2.4 Agentic 측정**
- [ ] 5 기존 시나리오 재측정 (OPH/GI/ORTHO/DERM/ONCO)
- [ ] Agentic 전용 신규 3 시나리오 작성:
  - S06 복잡 multi-hop: "고양이 당뇨와 췌장염 동반 환자의 SNOMED 태깅 전략"
  - S07 모호 쿼리: "눈 이상한 동물" (rewrite 루프 발동)
  - S08 비관련 쿼리: "미국 대통령 임기" (FAIL 처리 검증)
- [ ] 11-쿼리 회귀 (T1~T11) Agentic 모드로 재측정

**4.3 비교 리포트**
- [ ] `benchmark/v2_4_agentic_comparison.md` — 2행 병기 표 (§9.4 양식)
- [ ] Latency/Cost tradeoff 정량화
- [ ] 하락 지표 원인분석 기록

**Exit:** SNOMED Match ≥ 0.889, Latency p95 ≤ 60s, 투명 병기 표 완성

---

### Wave 5 — 문서·서사 동기화 (0.5d)

- [ ] `RELEASE_NOTES_v2.4.md` 작성 (4단계 개선 서사 포맷 유지)
- [ ] `README.md` v2.4 섹션 추가 + "Agentic RAG 11/11" 표기
- [ ] `docs/20260424_v2_4_agentic_rag_design_v1.md` → 최종본으로 격상 (본 문서)
- [ ] `~/claude-cowork/05_Output_Workspace/Career_Transition/20260423_Resume_v2_final_2page.md`
      §3.1 표기 갱신 (수치 변경 시만, 없으면 "Agentic RAG 11/11" 한 줄 추가)
- [ ] `~/claude-cowork/05_Output_Workspace/Career_Transition/20260422_Portfolio_Technical_Appendix.md`
      §9.6 "Agentic RAG Journey Map (6/11 → 11/11)" 신설
- [ ] `git tag v2.4` + PR #12 생성 (또는 PR #7 승계 결정)
- [ ] v4 Integrity Audit 재돌림 (reviewer 디스패치)

**Exit:** v4 감사 Critical 0 · Warning ≤ 3

---

## §8. 리스크 완화 상세

| 리스크 | 완화책 | 검증 시점 |
|---|---|---|
| R-1 D-6 초과 | Wave 분할 — D-6 전까지 Wave 1~2 완료 목표, Wave 3~5는 면접 전까지 | Wave 2 끝 (D-3) |
| R-2 Latency 60s 초과 | max_iter=2 하향 옵션 + judge flash-lite 고정 (1.0s) + rule-based router 기본값 | Wave 4 초입 |
| R-3 SNOMED 하락 | AgenticRAGPipeline 별도 엔드포인트 → 기존 query() 영향 0. 하락 시 `enable_agentic=False` 토글 | Wave 4 |
| R-4 문서 일관성 붕괴 | 수치 변경 최소화 원칙 — v2.4는 "루프 기능 추가"만, 기존 5 시나리오 수치는 재측정으로 재확인만 | Wave 5 |
| R-5 Gemini 비용 | flash-lite 전용 (1.0s, $0.075/1M input tokens) × max 3 iter × 3 judge call ≈ per-query $0.001 상승 | Wave 4 cost 측정 |
| R-6 회귀 | Wave 3에서 pytest 130+ PASS 강제. 하나라도 FAIL 시 Wave 4 진입 차단 | Wave 3 Exit |

---

## §9. 벤치마크 기준선·증가 지표

### 9.1 v2.2 Baseline (고정, 재측정 금지)

| 메트릭 | v2.2 값 | 출처 |
|---|---|---|
| SNOMED Match | 0.889 | RELEASE_NOTES_v2.1.md L16 |
| Precision | 0.891 | benchmark/v2.1_final_e2e_report.md |
| Recall | 0.772 | 동상 |
| F1 | 0.827 | 동상 |
| Latency p95 | 35.4s (35,435 ms) | 동상 |
| 11-쿼리 회귀 | 10/10 (Gemini) | backend_comparison.md |
| pytest | 106/107 + 59 subtests | 본 세션 직접 실측 |

### 9.2 v2.4 Target (PASS 조건)

| 메트릭 | v2.4 목표 | 달성 시 의미 |
|---|---|---|
| SNOMED Match (Agentic 모드) | ≥ 0.889 | 회귀 없음 |
| SNOMED Match (복잡 질의 한정) | ≥ 0.90 | 루프 이득 |
| Precision (복잡 질의 한정) | ≥ 0.90 | 루프 이득 |
| Latency p95 (simple) | ≤ 37.0s | 단일 패스 +overhead 5% 이내 |
| Latency p95 (complex, max_iter=2) | ≤ 55.0s | FDA Class II 한도 내 |
| 신규 pytest | ≥ 25건 PASS | 커버리지 |
| 기존 pytest regression | 106/107 → 유지 | 회귀 0 |

### 9.3 투명 병기 양식 (Wave 4 산출)

```
| 메트릭 | v2.2 | v2.4 Simple | v2.4 Complex+Loop | Δ | 해석 |
|---|---|---|---|---|---|
| SNOMED Match | 0.889 | 0.889 | 0.92[TBD] | +0.031 | 복잡 질의에서만 개선 |
| Latency p95 | 35.4s | 36.8s[TBD] | 52.1s[TBD] | +16.7s (complex) | max_iter=2 tradeoff |
| ...
```

### 9.4 하락 시 대응

1. **즉시 롤백 조건:** SNOMED Match < 0.85 OR Latency p95 > 60s
2. **원인분석 의무:** 하락 지표별 원인 1개 이상 기록 (JSON log + md 리포트)
3. **투명 공개:** 하락도 RELEASE_NOTES에 기록 — "v2.4 Simple-query는 v2.2 대비 +0.3s 추가 지연 발생(루프 판단 overhead)"

---

## §10. 성공 기준 (Exit Criteria 전수)

| # | 기준 | 검증 방법 | 책임 Wave |
|---|---|---|---|
| 1 | Agentic RAG 11/11 단계 구현 | 코드 grep `src/retrieval/agentic/` 4 파일 실존 + AgenticRAGPipeline class | Wave 2·3 |
| 2 | 신규 pytest ≥ 25건 PASS | `pytest tests/ -v` | Wave 3 |
| 3 | 기존 pytest 106/107 regression PASS | 동상 | Wave 3 |
| 4 | SNOMED Match ≥ 0.889 (Agentic 모드) | `scripts/evaluate_e2e.py --mode agentic` | Wave 4 |
| 5 | Latency p95 ≤ 60s (complex 포함) | 동상 | Wave 4 |
| 6 | RELEASE_NOTES_v2.4 + README 갱신 | 파일 Read | Wave 5 |
| 7 | v4 Integrity Audit Critical 0 · Warning ≤ 3 | reviewer 디스패치 | Wave 5 |
| 8 | git tag v2.4 생성 | `git tag -l v2.4` | Wave 5 |

**모든 8개 PASS 시 → Success. 1개라도 FAIL 시 → Wave 재진입 또는 롤백.**

---

## §11. 미해결·가정 항목 (`[TBD]`)

| 항목 | 상태 | 결정 시점 |
|---|---|---|
| PR #12 신설 vs PR #7 승계 | `[TBD]` — 권고: PR #12 신설 | Wave 5 초입 |
| max_iter 기본값 (2 vs 3) | `[TBD]` — 권고: 2 (latency 안전) | Wave 2 G-4 작업 시 |
| 한국어 cycle detection 임계값 (0.95) | `[TBD]` — 실측 후 튜닝 | Wave 3 |
| 벤치마크 신규 S06~S08 gold label | `[TBD]` — Wave 4 초입에 작성 | Wave 4 |
| 이력서 수치 변경 여부 | `[TBD]` — 유지 원칙, 추가 지표만 병기 | Wave 5 |

---

## §12. 사용자 승인 필요 4가지

1. **본 설계서 전반 방향 승인?** (11단계 매핑·Gap 4종 인터페이스·통합 아키텍처)
2. **백업 전략 §2 승인?** (L1 git tag / L2 브랜치 / L3 물리 스냅샷 3중)
3. **`[TBD]` 5개 권고값 수용?** (PR #12 신설 / max_iter=2 / 등)
4. **Wave 2 착수 타이밍 확인** — 지금 즉시 / 내일 아침 / 다른 시점

---

*작성: 2026-04-24 | 세션: claude-opus-4-7-1m | 상태: pending_user_approval*
*본 설계서 승인 후: Wave 2 브랜치 분기 + G-1~G-4 병렬 구현 착수*
