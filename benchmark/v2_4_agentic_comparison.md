# v2.4 Agentic RAG vs v2.2 Baseline 비교 리포트

> **생성일**: 2026-04-25 (Wave 4 산출)
> **검증 대상**: Datasciencedojo Agentic RAG 11단계 완전 구현 검증
> **상태**: 루프 동작 smoke 검증 완료, 정량 SOAP+SNOMED E2E 재측정은 v2.4.1로 이관

---

## §1. 요약

v2.4 Agentic RAG 11단계 루프(G-1 Complexity → G-2 Source Router → base.query → G-3 Relevance Judge → G-4 Loop Controller)가 실제 SNOMEDRagPipeline 위에서 **end-to-end로 동작함을 실측**. v2.2 대비 신규 4종 에이전트가 회귀 없이 통합됨.

| 항목 | v2.2 | v2.4 (smoke) | Δ | 해석 |
|---|---|---|---|---|
| Agentic 단계 구현 | 6/11 | **11/11** | +5 | Gap 4종 모두 코드 실존 + 단위 테스트 PASS |
| pytest | 106/107 | **135/136** (+1 skip) | +29 | 신규 23 (G-1~G-4) + 6 (E2E pipeline) |
| 단순 쿼리 latency | 약 30~35s¹ | 6.7s² | -28s² | ¹SOAP+SNOMED E2E / ²검색-only smoke (LLM 생성 생략) — 공정 비교 아님 |
| 복합 쿼리 latency | 미측정 (분해 미지원) | 22.0s² | 신규 | 3 subqueries 자동 분해 |
| Agentic 루프 동작 | ❌ | ✅ trace 검증 | — | iter / verdict / sources_used / loop_trace 정상 기록 |

---

## §2. 11단계 1:1 매핑 검증

| # | 단계 | v2.4 구현 | 실측 trace |
|---|---|---|---|
| 1 | Query | 입력 | `feline diabetes SNOMED code` |
| 2 | Rewrite Query | base.query 내부 reformulator | `feline diabetes → diabetes mellitus (conf=1.00)` |
| 3 | Updated Query | 동상 | reformulated query 적용 |
| 4 | Need More Details? | **G-1 QueryComplexityAgent** | simple → subqueries=None / complex → 3 subqueries 분해 |
| 5 | Which Source? | **G-2 SourceRouterAgent** | sources_used=[graph, sql, vector] 기록 |
| 6 | Sources | Vector + SQL + Graph (External Tool 훅) | 3-track 가용 |
| 7 | Retrieved Context + Updated Query | base.query 내부 build_context | search_results × top_k |
| 8 | LLM | base.generate_with_* | smoke는 llm_backend=none, v2.4.1 측정 시 활성 |
| 9 | Response | base.query 반환 | answer 필드 |
| 10 | Is the answer relevant? | **G-3 RelevanceJudgeAgent** | PASS/PARTIAL/FAIL × confidence |
| 11 | Final Response / Rewrite Loop | **G-4 RewriteLoopController** | iter 종료 또는 cycle/max_iter 종료 |

**결과: 11/11 단계 코드 실존 + smoke 동작 확인.**

---

## §3. 실측 케이스 상세 (Wave 4 smoke)

### 3.1 Case 1 — Simple Query

```
입력:    "feline diabetes SNOMED code"
G-1:     is_complex=False (rule_based, 짧은 단일 개념)
G-2:     vector_weight=0.7 / sql_weight=0.3 (한국어 없음, 단순 영문)
         실제 적용: graph + sql + vector (기본값)
Reform:  feline diabetes → diabetes mellitus (conf=1.00)
G-3:     PASS / confidence=1.00
G-4:     iter=0 PASS → 루프 종료
Result:  iterations=1, verdict=PASS, total_ms=6,734
```

### 3.2 Case 2 — Complex Query (분해)

```
입력:    "feline diabetes and pancreatitis comparison SNOMED tagging"
G-1:     is_complex=True (Gemini 판정), subqueries 3개:
         [1] SNOMED tags for feline diabetes
         [2] SNOMED tags for feline pancreatitis
         [3] Comparison of feline diabetes and pancreatitis
G-2:     각 sub별 라우팅 → graph + sql + vector
Reform:  sub1: tags feline diabetes → diabetes mellitus (conf=1.00)
         sub2: tags feline pancreatitis → pancreatitis (conf=0.95)
         sub3: Comparison ... → 원본 유지 (conf=0.00)
검색:    3 subqueries × 3-track retrieval
G-3:     PASS / confidence=1.00 (병합 답변 평가)
G-4:     iter=0 PASS → 루프 종료
Result:  iterations=1, verdict=PASS, total_ms=22,017
```

### 3.3 Raw Output

저장: `benchmark/v2_4_agentic_smoke.json`

---

## §4. 한계 및 알려진 차이

### 4.1 측정 한계 (정량 비교 불가 사유)

본 Wave 4는 **smoke 검증** 단계로 다음 제약 하 측정:

| 제약 | 사유 | 영향 |
|---|---|---|
| `llm_backend="none"` | SOAP/SNOMED Tagger LLM 생성 단계 생략 | latency 6.7s/22s는 v2.2의 35.4s와 **공정 비교 불가** (검색 only) |
| `enable_rerank=False` | BGE Reranker 비활성 | v2.1 정식 측정과 다른 경로 |
| Gold label 없음 | Wave 4 신규 시나리오 S06~S08 작성 보류 | SNOMED Match 정량 측정 불가 |
| Reformulator 3회 retry FAIL 1회 | Gemini API `'list' object is not a mapping` 에러 → 폴백 동작 | 최종 결과 영향 없으나 안정성 추후 패치 필요 |

### 4.2 정식 측정 이관 (v2.4.1 RoadMap)

- 5 시나리오 OPHTHALMOLOGY/GASTROINTESTINAL/ORTHOPEDICS/DERMATOLOGY/ONCOLOGY 재측정
- Agentic 신규 3 시나리오 S06 (multi-hop) / S07 (모호 → rewrite 발동) / S08 (비관련 → FAIL)
- LLM 답변 생성 포함 E2E latency
- gold label 추가 + SNOMED Match / Precision / Recall / F1 정량
- v2.2 대비 2행 병기 표 (설계서 §9.3 양식)

### 4.3 이력서·자소서 영향

설계서 §11 [TBD] "이력서 수치 변경 여부" 권고값(유지)에 따라:
- **v2.2 인용 수치(0.889 / 0.827 / 35.4s)는 그대로 유지**
- 신규 추가 표기: "Agentic RAG 11/11 단계 구현 (v2.4)"
- 정량 수치 갱신은 v2.4.1 정식 측정 후

---

## §5. v2.2 baseline 인용 (변경 없음)

| 메트릭 | v2.2 값 | 출처 |
|---|---|---|
| SNOMED Match | 0.889 (8/9 gold) | RELEASE_NOTES_v2.1.md L16 |
| Precision | 0.891 | benchmark/v2.1_final_e2e_report.md §3 |
| Recall | 0.772 | 동상 |
| F1 | 0.827 | 동상 |
| Latency p95 | 35.4s | 동상 |
| 11-쿼리 회귀 | 10/10 (Gemini) | benchmark/backend_comparison.md |
| pytest | 106/107 + 59 subtests | 본 세션 직접 실측 |

---

## §6. v2.4 PASS / FAIL 판정 (Exit Criteria 매핑)

| # | Exit Criteria | 판정 | 근거 |
|---|---|---|---|
| 1 | Agentic RAG 11/11 단계 구현 | ✅ PASS | §2 매핑 표 |
| 2 | 신규 pytest ≥ 25건 | ✅ PASS | 23 (G-1~G-4) + 6 (Pipeline) = 29건 |
| 3 | 기존 pytest 106/107 regression | ✅ PASS | 135 passed + 1 skipped |
| 4 | SNOMED Match ≥ 0.889 | ⏸ DEFERRED | Wave 4 smoke로는 측정 불가, v2.4.1 이관 |
| 5 | Latency p95 ≤ 60s | ⏸ DEFERRED | smoke 6.7s/22.0s는 `llm_backend="none"` 검색-only. FDA Class II 기준 SOAP+SNOMED Tagger 포함 E2E latency 측정은 v2.4.1 이관(§4.1 한계와 일관) |
| 6 | RELEASE_NOTES_v2.4 + README | Wave 5 | 진행 예정 |
| 7 | v4 Integrity Audit | Wave 5 | 진행 예정 |
| 8 | git tag v2.4 | Wave 5 | 진행 예정 |

**3종 PASS / 2종 DEFERRED (#4 SNOMED Match · #5 Latency) / 3종 Wave 5 진행 → CONDITIONAL_PASS (smoke 단계).**

---

*Wave 4 완료: 2026-04-25 | 다음: Wave 5 문서·서사 동기화*
*저장: `~/claude-cowork/07_Projects/vet-snomed-rag/benchmark/v2_4_agentic_comparison.md`*
