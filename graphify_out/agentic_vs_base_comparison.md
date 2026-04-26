# N-1 agentic_query vs base.query 회귀 비교

생성: 2026-04-26 15:12:19
핸드오프: docs/20260426_v2_6_roadmap_handoff.md §3-1

## 모드별 PASS율 (외부 도구 OFF 케이스 + ON 케이스 합산)

| 모드 | PASS / 판정대상 |
|---|---|
| agentic_rerank | 12/12 |
| agentic_norerank | 12/12 |
| base_rerank | 12/12 |
| base_norerank | 12/12 |

## 외부 도구 활성 케이스 검증 (T12-T14)

| qid | 쿼리 | 기대 도구 | 실제 호출 | UMLS md | PubMed md |
|---|---|---|---|---|---|
| T12 | `diabetes mellitus ICD-10 cross-walk` | umls | 없음 | ✗ | ✗ |
| T13 | `rare feline endocrine literature` | pubmed | pubmed | ✗ | ✓ |
| T14 | `고양이 당뇨 ICD-10 매핑` | umls | 없음 | ✗ | ✗ |

## 쿼리별 상세 (Top-1 비교)

| qid | query | 기대 | agentic_rerank | base_rerank | iter | latency(agentic, ms) |
|---|---|---|---|---|---|---|
| T1 | `feline panleukopenia SNOMED code` | 339181000009108 | #1 PASS | #1 PASS | 1 | 12665 |
| T2 | `canine parvovirus enteritis` | 47457000 | #2 PASS | #2 PASS | 1 | 3822 |
| T3 | `diabetes mellitus in cat` | 73211009 | #1 PASS | #1 PASS | 1 | 3083 |
| T4 | `pancreatitis in dog` | 75694006 | #1 PASS | #1 PASS | 1 | 33369 |
| T5 | `chronic kidney disease in cat` | 복수 | 없음 NA | 없음 NA | 1 | 3190 |
| T6 | `cat bite wound` | 283782004 | #1 PASS | #1 PASS | 1 | 4283 |
| T7 | `feline diabetes` | 73211009 | #1 PASS | #1 PASS | 1 | 5264 |
| T8 | `diabetes mellitus type 1` | 46635009 | #1 PASS | #1 PASS | 1 | 2022 |
| T9 | `고양이 당뇨` | 73211009 | #1 PASS | #1 PASS | 1 | 1400 |
| T10 | `개 췌장염` | 75694006 | #1 PASS | #1 PASS | 1 | 1745 |
| T11 | `고양이 범백혈구감소증 SNOMED 코드` | 339181000009108 | #1 PASS | #1 PASS | 1 | 3182 |
| T12 | `diabetes mellitus ICD-10 cross-walk` | 73211009 | #1 PASS | #1 PASS | 1 | 7786 |
| T13 | `rare feline endocrine literature` | 복수 | 없음 NA | 없음 NA | 1 | 11956 |
| T14 | `고양이 당뇨 ICD-10 매핑` | 73211009 | #1 PASS | #1 PASS | 1 | 8503 |

## base 모드 회귀 (v2.5.1 정밀 회귀 baseline 대비)

v2.5.1 baseline: graphify_out/regression_metrics_rerank.json (gemini 10/10)

- 본 실행의 base_rerank 결과가 11쿼리 baseline과 동일하면 회귀 0 (T12-T14는 신규).


## 성공 기준 (§3-1-5) 1:1 PASS/FAIL

| # | 항목 | 결과 | 판정 |
|---|---|---|---|
| 1 | agentic Top-1 ≥ 9/10 | 12/12 | PASS |
| 2 | 외부 도구 markdown ≥ 95% | 1/3 (33%) | FAIL |
| 3 | base_rerank 회귀 0 (≥ 9/10) | 12/12 | PASS |

---
*생성: scripts/run_regression_agentic.py (N-1)*