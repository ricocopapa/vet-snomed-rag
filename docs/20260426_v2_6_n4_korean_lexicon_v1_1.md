---
tags: [vet-snomed-rag, v2.6, n4, korean, lexicon, validation]
date: 2026-04-26
status: 종결
parent_handoff: docs/20260426_v2_6_roadmap_handoff.md §3-4
related:
  - data/vet_term_dictionary_ko_en.json (v1.0 → v1.1)
  - graphify_out/regression_metrics_rerank.json (v1.1 결과)
  - graphify_out/regression_metrics_rerank_v1_0_baseline.json (v1.0 백업)
---

# N-4 한국어 사전 강화 (v1.1) 검증 노트

## §1. 작업 범위

핸드오프 §3-4 N-4 한국어 사전 강화. v2.5.1 baseline `none` backend 8/10 PASS 상태에서 임상 빈출 한국어 약식/일반명 누락이 원인인 FAIL 케이스를 식별·해소.

### 1-1. baseline FAIL 케이스 분석 (v1.0)

| qid | 쿼리 | none Top-1 | 결함 분류 |
|---|---|---|---|
| T7 | `feline diabetes` (영어) | 347101000009106 Feline immune deficiency | **N-4 범위 외** — 영어 약식, 한국어 사전 영향 없음 |
| T9 | `고양이 당뇨` (한국어) | 132391009 Kui Mlk dog | **N-4 대상** — `당뇨` 약식 미등록 (정식 `당뇨병`만 있음) |

### 1-2. 결정

- **N-4 범위:** T9 회복 + 임상 빈출 약식 일괄 추가 (확장 안 B 채택)
- **T7:** 영어 쿼리 + none reformulator 미사용 본질적 한계로 알려진 한계 기록 (별도 작업으로 분리)

---

## §2. 사전 추가 항목 (v1.1, 신규 카테고리 `질병_약식(Disorder Alias)`)

| 한국어 약식 | 영어 매핑 | SNOMED concept_id | preferred_term |
|---|---|---|---|
| 당뇨 | diabetes mellitus | 73211009 | Diabetes mellitus |
| 관절염 | Arthritis | 3723001 | Arthritis |
| 심부전 | Heart failure | 84114007 | Heart failure |
| 고혈압 | high blood pressure | 38341003 | High blood pressure |
| 기관지염 | Bronchitis | 32398004 | Bronchitis |
| 결막염 | Conjunctivitis | 9826008 | Conjunctivitis |
| 각막염 | Keratitis | 5888003 | Keratitis |
| 비만 | Obesity | 414916001 | Obesity |
| 흉수 | Pleural effusion | 60046008 | Pleural effusion |
| 복수 | Ascites | 389026000 | Ascites |

**검증 방법:** `data/snomed_ct_vet.db` `concept` 테이블에 `LOWER(preferred_term) = LOWER(en) AND semantic_tag = 'disorder'` 조건으로 매칭. 10/10 PASS.

**고혈압 매핑 결정:** SNOMED preferred_term은 `Hypertensive disorder, systemic arterial`이지만, 일반 명칭 `High blood pressure`(concept_id 38341003) 매칭이 자연어 검색에 더 안정적. preferred_term 직접 매칭 사용.

---

## §3. 회귀 결과 (v1.0 vs v1.1, RERANK=1)

| Backend | v1.0 baseline | v1.1 결과 | 변화 |
|---|---|---|---|
| **none** | 8/10 PASS (T7·T9 FAIL) | **9/10 PASS** (T7만 FAIL) | T9 PASS 회복 ✅ |
| **gemini** | 10/10 PASS | **10/10 PASS** | 회귀 0 ✅ |

### 3-1. T9 동작 트레이스

```
원본:           고양이 당뇨
사전 치환:       feline diabetes mellitus       (← v1.0은 'feline 당뇨'로 부분 치환)
none Top-1:     339181000009108 panleukopenia  (vec drift)
none rank:      #3 (73211009 Diabetes mellitus, ≤5 PASS)
gemini reform:  feline diabetes mellitus → diabetes mellitus
gemini Top-1:   #1 73211009 ✓
```

### 3-2. T7 잔여 FAIL (N-4 범위 외)

```
원본:           feline diabetes (영어)
사전 치환:       해당 없음 (한국어 사전이라 영어 무관)
none Top-1:     347101000009106 Feline immune deficiency (drift)
gemini reform:  feline diabetes → diabetes mellitus → Top-1 #1 PASS
```

→ 본질: `feline diabetes` 자체는 SNOMED CT에 단일 concept로 없고 사전 조합 필요. none backend는 reformulator 미사용 → 영어 약식·합성어 한계. **알려진 한계**로 기록.

---

## §4. §3-4-5 성공 기준 1:1 PASS/FAIL

| # | 항목 | PASS 조건 | 결과 | 판정 |
|---|---|---|---|---|
| 1 | none 회귀 | ≥ 9/10 | 9/10 | ✅ PASS |
| 2 | gemini 회귀 0 | = 10/10 유지 | 10/10 | ✅ PASS |
| 3 | 추가 항목 SNOMED 검증 | 100% | 10/10 | ✅ PASS |

---

## §5. 변경 산출물

| 분류 | 파일 | 변경 |
|---|---|---|
| 사전 | `data/vet_term_dictionary_ko_en.json` | v1.0(158항목 5카테고리) → **v1.1(168항목 6카테고리)**. 신규 `질병_약식(Disorder Alias)` 카테고리. `_version`/`_changelog` 메타 추가 |
| 회귀 산출물 | `graphify_out/regression_metrics_rerank.json` | v1.1 결과로 갱신 |
| baseline 백업 | `graphify_out/regression_metrics_rerank_v1_0_baseline.json` | v1.0 결과 보존 (감사 이력) |
| 검증 로그 | `graphify_out/n4_regression_run.log` | 회귀 stdout |
| 검증 노트 | 본 문서 | 종결 |

---

## §6. 알려진 한계 (다음 작업 후보)

1. **T7 영어 약식 fail** — `feline diabetes` 같은 영어 합성어가 none backend에서 fail. 해결 옵션:
   - (a) 영어 사전 추가 (`feline diabetes` → `diabetes mellitus`) — 빠르지만 종-합성 패턴 유지보수 부담
   - (b) none backend에 lightweight 합성어 정규화 룰 (e.g., `feline X` → `X` if X exists alone) — 일반화
   - (c) 현 상태 그대로 ("none은 단순 검색, 정밀 검색은 gemini 권장"으로 documented)
2. **T9 none Top-1 drift** (73211009가 Top-1 아닌 #3) — Vector 임베딩에서 `feline diabetes mellitus`가 `feline panleukopenia`와 근접. RERANK ON으로 해소되지 않음. 별도 reranker 튜닝 또는 vector index 재학습 필요.

---

**N-4 종결 (2026-04-26).**
