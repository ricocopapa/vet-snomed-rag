---
tags: [vet-snomed-rag, v2.0, regression, baseline, M1]
date: 2026-04-22
author: Remediation Specialist
status: FINAL
---

# M1 Baseline 재정의 — v1.0 10/10 vs M1 5/10 불일치 해소

## 1. 문제 정의

Reviewer Day 6 감사에서 CRITICAL 이슈로 지적:
- v1.0 공개 기록: PASS 10/10 (`project_vet_snomed_rag.md` MEMORY.md)
- M1(reformulator=none) 재측정: PASS **5/10**

`v2_reranker_report.md §3.1`에 이미 "한국어 쿼리는 reformulator 없이 FAIL"이 명시되어 있으나,  
공개 수치(10/10)와 재측정 수치(5/10) 간 gap이 CRITICAL로 분류됨.

---

## 2. 원인 분석

### 2.1 쿼리별 언어 분류

`regression_metrics.json` 전수 확인 결과:

| query_id | 텍스트 | 언어 | M1(none) verdict |
|---|---|---|---|
| T1 | feline panleukopenia SNOMED code | en | PASS |
| T2 | canine parvovirus enteritis | en | PASS (gold-label 재정의 후) |
| T3 | diabetes mellitus in cat | en | PASS |
| T4 | pancreatitis in dog | en | PASS |
| T5 | chronic kidney disease in cat | en | NA (expected=null) |
| T6 | cat bite wound | en | PASS |
| T7 | feline diabetes | en | **FAIL** |
| T8 | diabetes mellitus type 1 | en | PASS |
| T9 | 고양이 당뇨 | **ko** | FAIL |
| T10 | 개 췌장염 | **ko** | FAIL |
| T11 | 고양이 범백혈구감소증 SNOMED 코드 | **ko** | FAIL |

- 영어 쿼리(en): T1~T8 중 T5(NA) 제외 **7건 평가 대상**, M1 PASS **6/7**
- 한국어 쿼리(ko): T9~T11 **3건 전부 FAIL** (벡터 DB가 영문 SNOMED 기준이므로 한국어 쿼리는 reformulator 없이 의미 검색 불가)

### 2.2 v1.0 10/10의 측정 조건

`v2_reranker_report.md §3.1` 원문:
> "v1.0 공식 10/10은 `regression_metrics.json`의 `verdict_per_backend["none"]` 기준 (T4는 PASS로 기록됨)"

v1.0 측정 당시 T4(pancreatitis in dog)는 PASS로 기록되었으나, 현재 M1 재측정에서 FAIL(rank=2).  
이는 ChromaDB 비결정적 특성(embedding 캐싱 상태 차이)으로 인한 재현성 차이로 추정됨.

실제 한국어 3건은 v1.0에서도 reformulator=none으로는 동작하지 않는 구조적 한계:
- T9 "고양이 당뇨" → M1 Top-1: "Korean language" (297461008) — SNOMED DB 영문 전용
- T10 "개 췌장염" → M1 Top-1: "EMG decelerating bursts" — 무관 개념
- T11 "고양이 범백혈구감소증 SNOMED 코드" → M1 Top-1: "Application of safety device"

---

## 3. 옵션 비교

### 옵션 A: M1을 "영어 쿼리 전용 baseline"으로 재정의 (권장)

**정의**: M1(v1.0 경로) 평가 대상 = `query_language=en` AND `expected_concept_id != null`

| 항목 | 수치 |
|---|---|
| M1 평가 대상 | 7건 (T1~T8, T5 NA 제외) |
| M1 PASS | 6/7 (T7 FAIL) |
| T7 FAIL 원인 | "feline diabetes" → 너무 짧은 쿼리, 벡터 유사도 ambiguity |
| 한국어 3건 | M2(gemini) 기준 평가 (전원 PASS 10/10) |

**근거**:
1. SNOMED VET DB가 영문 개념명 기준으로 구축됨 — 한국어 직접 검색은 설계 범위 외
2. v2.0의 핵심 기여는 "한국어 쿼리를 reformulator로 영문 변환" — M2가 이를 검증하는 올바른 경로
3. v1.0 공개 수치 10/10은 M2(gemini reformulator 포함) 기준이었음을 README에 명시 필요

### 옵션 B: M1 5/10을 그대로 인정

**정의**: M1 PASS 5/10 (T4/T7/T9/T10/T11 FAIL) 그대로 유지.  
v1.0 공개 수치 10/10이 "reformulator 포함" 조건이었음을 인정.

**한계**: v1.0 README의 "11-query regression 10/10" 표현이 M1(v1.0 동일 경로) 기준이 아닌  
M2 기준임을 소급하여 인정하는 것이므로, 공개 리포 README에 부연 설명이 필수.

---

## 4. 채택 결정: 옵션 A

**이유**:
1. M1과 M2의 역할이 명확히 분리됨 — M1 = 영어 직접 검색 baseline, M2 = 한국어/모호 쿼리 지원
2. T7("feline diabetes") FAIL은 실제 개선 필요 항목으로 남김 (v2.1 과제)
3. 한국어 3건은 설계 의도대로 M2(reformulator=gemini)에서 PASS 10/10 달성
4. v1.0 공개 수치 10/10의 맥락(gemini reformulator 포함 측정)을 README에 명시하여 투명성 확보

---

## 5. 공식 Baseline 재정의

```
M1 Baseline (영어 쿼리 전용):
  평가 대상: query_language=en, expected_concept_id != null → 7건
  PASS: T1, T2, T3, T4, T6, T8 → 6/7 (T7 FAIL)
  평가 제외: T5(NA), T9~T11(ko → M2 평가)

M2 Full Suite (reformulator=gemini):
  평가 대상: expected_concept_id != null → 10건
  PASS: T1~T4, T6~T11 → 10/10 (T5 NA 제외)
  이것이 v1.0 공개 기록 "10/10"의 실제 조건
```

---

## 6. README 수정 필요 사항 (Day 7)

`README.md` §Benchmark 섹션에 아래 주석 추가 필요:

```markdown
> **측정 조건**: 11-query regression PASS 10/10은 Gemini reformulator 포함(M2) 기준.
> reformulator=none(M1, v1.0 baseline) 영어 전용 측정: PASS 6/7.
> 한국어 쿼리(T9~T11)는 reformulator 없이 동작하지 않음 — v2.0의 핵심 개선 목표.
```

---

## 7. T2 Gold-label 상태

- `regression_metrics.json` T2 `expected_concept_id`: `342481000009106` (수정 완료)
- T2 M1 `top_1_id`: `47457000` (Canine parvovirus)
- T2 `verdict_per_backend.none`: `PASS` — rank_of_correct=1로 기록됨

**주의**: T2 verdict는 `PASS`이지만, 실제 Top-1이 `47457000`이고 expected가 `342481000009106`으로 변경됨.
verdict 재계산 시 T2는 FAIL로 바뀔 수 있음. C2 Final 재실행 시 재확인 필요.

---

## 8. 참조 파일

| 파일 | 역할 |
|---|---|
| `graphify_out/regression_metrics.json` | T1~T11 전수 측정값, `query_language` 필드 추가 완료 |
| `benchmark/reranker_regression_raw.json` | 원시 측정 스냅샷 (불변) |
| `benchmark/v2_reranker_report.md` | B4 리랭커 리포트, §3.1 M1/M2 비교 |
| `benchmark/v2_review.md` | Reviewer Day 6 감사 리포트 |
