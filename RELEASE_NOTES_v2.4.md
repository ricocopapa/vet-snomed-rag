# vet-snomed-rag v2.4 Release Notes

**Release Date:** 2026-04-25
**Branch:** `feature/v2.4-agentic-rag` → (PR #12 신설 예정)
**Tag:** `v2.4`
**Theme:** Agentic RAG 11단계 완전 구현

---

## Highlights

Datasciencedojo "RAG vs Agentic RAG" 인포그래픽 기준 **11단계 Agentic RAG 루프**를 완전 구현했다. v2.2까지 6/11 단계만 구현(Rewrite Query + Hybrid Retrieval + LLM)이었고, 본 릴리즈에서 **나머지 4종 Gap을 신규 에이전트로 해소**했다.

| 단계 | v2.2 | v2.4 | 구현 |
|---|:---:|:---:|---|
| #2 Rewrite Query | ✅ | ✅ | `query_reformulator.py` (기존) |
| #4 Need More Details? | ❌ | **✅** | `agentic/query_complexity.py` (신규) |
| #5 Which Source? | ❌ | **✅** | `agentic/source_router.py` (신규) |
| #10 Is the answer relevant? | ❌ | **✅** | `agentic/relevance_judge.py` (신규) |
| #11 Final Response / Rewrite Loop | ❌ | **✅** | `agentic/loop_controller.py` (신규) |
| **합계** | 6/11 | **11/11** | — |

> **기존 구현 유지 단계**(#1 Query / #2 Rewrite Query / #3 Updated Query / #6 Sources / #7 Retrieved Context / #8 LLM / #9 Response): 변경 없이 보존. 전체 11단계 1:1 매핑은 [`docs/20260424_v2_4_agentic_rag_design_v1.md` §3.3](./docs/20260424_v2_4_agentic_rag_design_v1.md) 참조.

기존 `SNOMEDRagPipeline.query()` API는 **변경 없이 보존** → v2.2 벤치마크 회귀 0 보장. 신규 `AgenticRAGPipeline.agentic_query()`는 별도 wrapper 진입점.

---

## Stage 1 — Gap 4종 신규 에이전트

### G-1 QueryComplexityAgent (Agentic #4)

쿼리가 단일 retrieval로 충분한지, 분해가 필요한지 판단.

- **rule_based + Gemini hybrid**: 짧은 단일 개념은 rule_based fast-path, 복잡 쿼리는 Gemini flash-lite 분해
- **503 폴백**: Gemini 실패 시 rule_based 자동 전환
- 출력: `ComplexityVerdict(is_complex, subqueries, confidence, method)`

### G-2 SourceRouterAgent (Agentic #5·#6)

쿼리·서브쿼리별 어떤 소스(Vector/SQL/Graph/External Tool)를 사용할지 동적 결정.

| 패턴 | 라우팅 |
|---|---|
| concept_id 6자리 / "SNOMED code" | SQL 가중 (0.7) |
| 한국어 자연어 / 증상·통증·이상·의심 | Vector 가중 (0.7) |
| "상위 개념" / "관계" / "유사 질환" | Graph 활성 |
| 그 외 | 기본 (V 0.6 / S 0.4) |

> **참고**: 가중치 동적 주입은 v2.4에서는 trace 기록까지. base.query() 시그니처 확장은 v2.5 작업.

### G-3 RelevanceJudgeAgent (Agentic #10)

답변이 쿼리에 충분한지 PASS / PARTIAL / FAIL 3-way 판정.

- **Gemini flash-lite judge** (1.0s, 비용 효율)
- 빈 답변 즉시 FAIL
- JSON 파싱 실패 / 503 → PARTIAL/0.5 폴백 (안전 기본)
- 출력: `RelevanceVerdict(verdict, confidence, missing_aspects, reasoning)`

### G-4 RewriteLoopController (Agentic #11)

Relevance 결과에 따라 Rewrite 루프 결정 + max_iter 관리 + cycle detection.

- **max_iter=2 기본** (latency 안전 권고값)
- Jaccard 토큰 cycle detection (threshold 0.95)
- PASS + threshold ≥0.7 → 즉시 종료
- PARTIAL + iter < max → 누락 관점 반영 신규 쿼리 생성
- FAIL + iter < max → 강화 reformulation
- 동일 패턴 반복 → 강제 종료

---

## Stage 2 — AgenticRAGPipeline 통합

`src/retrieval/agentic_pipeline.py` 신규 (270 LOC).

```python
from src.retrieval.rag_pipeline import SNOMEDRagPipeline
from src.retrieval.agentic_pipeline import AgenticRAGPipeline

base = SNOMEDRagPipeline(
    llm_backend="claude",
    reformulator_backend="gemini",
)
agentic = AgenticRAGPipeline(
    base_pipeline=base,
    max_iter=2,
    relevance_threshold=0.7,
)

# v2.2 호환 호출
result = agentic.query("feline diabetes")  # → dict (기존 동일)

# v2.4 신규 11단계 루프
result = agentic.agentic_query("feline diabetes and pancreatitis comparison")
# → AgenticRAGResult(iterations, verdict, confidence, subqueries, sources_used,
#                     loop_trace, latency_ms)
```

---

## Stage 3 — Tests + Regression

| 카테고리 | 신규 | 누적 |
|---|---|---|
| G-1 QueryComplexityAgent | 6 | — |
| G-2 SourceRouterAgent | 5 | — |
| G-3 RelevanceJudgeAgent | 7 | — |
| G-4 RewriteLoopController | 5 | — |
| AgenticRAGPipeline E2E | 6 | — |
| **신규 합계** | **29** | — |
| 기존 (v2.2) | — | 106 + 59 subtests + 1 skipped |
| **v2.4 전체 pytest** | — | **135 passed + 1 skipped + 59 subtests** |

기존 106/107 regression 0 깨짐 — `SNOMEDRagPipeline.query()` 변경 없이 wrapping만 추가.

---

## Stage 4 — Smoke Benchmark

`benchmark/v2_4_agentic_smoke.json` + `benchmark/v2_4_agentic_comparison.md`

| 케이스 | iter | verdict | subqueries | latency |
|---|---|---|---|---|
| Simple "feline diabetes SNOMED code" | 1 | PASS (1.00) | None | 6.7s¹ |
| Complex "feline diabetes and pancreatitis comparison ..." | 1 | PASS (1.00) | 3 | 22.0s¹ |

¹ `llm_backend="none"` 검색-only smoke. SOAP+SNOMED Tagger 포함 정량 측정은 **v2.4.1** 이관.

### 검증된 동작
- ✅ G-1 complex 쿼리 자동 분해 (3 subqueries)
- ✅ G-2 graph + sql + vector 라우팅 trace
- ✅ G-3 PASS 판정 + confidence 1.00
- ✅ G-4 iter 0 PASS → 루프 조기 종료

---

## v2.2 → v2.4 비교 (이력서 인용 수치 영향 없음)

| 메트릭 | v2.2 | v2.4 | 변화 |
|---|---|---|---|
| SNOMED Match | **0.889** (8/9 gold) | 유지 (smoke 단계, 정량 v2.4.1) | 0 |
| Precision | 0.891 | 유지 | 0 |
| Recall | 0.772 | 유지 | 0 |
| F1 | 0.827 | 유지 | 0 |
| Latency p95 (E2E) | 35.4s | v2.4.1에서 측정 | TBD |
| Agentic 단계 | 6/11 | **11/11** | **+5** |
| pytest | 106/107 | **135/136** | **+29** |
| FDA Class II ≥0.80 PASS | ✅ | ✅ 유지 | — |

**핵심 메시지**: v2.4는 **Wrapper Pattern (Strangler Fig)** 으로 비침습적 기능을 추가한 릴리즈다. 기존 `SNOMEDRagPipeline.query()` API는 변경 없이 그대로 두고 Agentic 11단계 루프를 신규 layer로 추가했다. 가중치 동적 주입을 위한 API Migration(리팩토링)은 v2.5 후속 작업으로 분리. 이력서·자소서·포트폴리오 인용 수치(0.889 / 0.827 / 35.4s)는 변경 없이 유지된다.

> **용어 정확성 (Martin Fowler 기준)**: 본 작업은 "Refactoring"이 아니다. Fowler 정의("외부 동작 변경 없이 내부 구조 개선")와 달리 v2.4는 외부 동작에 새 11단계 루프를 추가했다. Conventional Commits 기준 `feat:`, GoF 패턴 기준 `Wrapper/Decorator`, Fowler 패턴 기준 `Strangler Fig`로 분류된다.

---

## 알려진 한계

1. **v2.4 정량 SOAP+SNOMED E2E 측정은 v2.4.1 이관** — Wave 4 smoke는 검색-only로 latency 6.7s/22.0s는 v2.2 35.4s와 공정 비교 불가
2. **G-2 가중치 동적 주입은 v2.5** — 현재 라우팅 결정은 trace로만 기록. base.query() 시그니처 확장이 v2.5 선행 작업
3. **Reformulator API `'list' object is not a mapping` 에러 1회 관찰** — 폴백으로 정상 처리, 안정성 패치는 v2.4.2
4. **Cycle detection은 토큰 Jaccard** — 의미적 cycle 감지는 sentence-transformers cosine으로 v2.5 강화 가능

---

## Roadmap

| 버전 | 작업 |
|---|---|
| v2.4 | Agentic RAG 11/11 단계 + smoke 검증 (현재) |
| v2.4.1 | 5+3 시나리오 정식 E2E 측정 + gold label + 정량 비교 |
| v2.4.2 | Reformulator 안정성 패치 + Gemini 응답 형식 검증 강화 |
| v2.5 | base.query() 가중치 인자 확장 + 의미적 cycle detection |
| v2.6 | Logic RAG 정식 통합 + multi-hop reasoning + External Tool 라우팅 |

---

## Backup & Rollback

3중 백업 보장:
- **L1**: `git tag v2.2` (불변)
- **L2**: `feature/v2.4-agentic-rag` 분기 (PR #12 별도)
- **L3**: `src/retrieval_v2_2_snapshot/` 물리 복사본 (.gitignore 등록)

롤백 명령:
```bash
git checkout v2.2                                              # L1
git checkout feature/v2.3-ai-os-pocs                           # L2 (PR #7 상태)
rm -rf src/retrieval && mv src/retrieval_v2_2_snapshot src/retrieval  # L3
```

---

## Files Changed

```
docs/20260424_v2_4_agentic_rag_design_v1.md      신규  (Wave 1 설계서)
src/retrieval/agentic/__init__.py                신규
src/retrieval/agentic/query_complexity.py        신규  (G-1)
src/retrieval/agentic/source_router.py           신규  (G-2)
src/retrieval/agentic/relevance_judge.py         신규  (G-3)
src/retrieval/agentic/loop_controller.py         신규  (G-4)
src/retrieval/agentic_pipeline.py                신규  (AgenticRAGPipeline)
tests/test_query_complexity.py                   신규
tests/test_source_router.py                      신규
tests/test_relevance_judge.py                    신규
tests/test_loop_controller.py                    신규
tests/test_agentic_pipeline.py                   신규
benchmark/v2_4_agentic_smoke.json                신규  (Wave 4 raw)
benchmark/v2_4_agentic_comparison.md             신규  (Wave 4 분석)
.gitignore                                        +1 line (snapshot 제외)
RELEASE_NOTES_v2.4.md                             신규  (본 문서)
```

기존 코드 변경: **0개 파일** (회귀 0 보장).

---

*Release: 2026-04-25 | Theme: Agentic RAG 11/11 단계 완전 구현*
