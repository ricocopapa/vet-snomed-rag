---
tags: [vet-snomed-rag, v3.1, R-4, reformulate, dictionary-skip, perfect]
date: 2026-04-27
status: v3.1 R-4 종결 — 한국어 11/11 PERFECT (none + gemini 둘 다)
phase: v3.1 R-4 — 사전 변환 결과 reformulate skip 로직
prev: docs/20260427_v3_1_r3_korean_dictionary_v1_4.md
related:
  - src/retrieval/rag_pipeline.py
  - graphify_out/v3_1_korean_extension.json
  - graphify_out/regression_metrics_rerank.json
---

# v3.1 R-4 — 사전 변환 결과 reformulate skip: 한국어 PERFECT 11/11×2 도달

## §0. 결론 요약 (3줄)

R-3 외이염 gemini 1건 미달 — Gemini reformulator가 사전 결과 "swimmer's ear"를 "otitis externa"로 일반화하면서 사전 효과 무력화. R-4: `rag_pipeline.py:530-548` Step 0.7에 **사전 변환 시 reformulate skip 로직** 1줄 추가 (`dict_applied_korean` flag). 결과: **한국어 11쿼리 none 11/11 + gemini 11/11 PERFECT** (R-3 11+10 → R-4 11+11). 영어 10/10×2 + 단위 251 PASS (회귀 0). v3.1 한국어 cycle 1차 완전 종결.

---

## §1. R-3 미해소 결함 분석

### 1-1. R-3 외이염 gemini flow

```
[N-ko-05] 외이염 (gold: 3135009)
  Step 0   사전: 외이염 → swimmer's ear  ← 정확 (preferred_term 직접 매칭)
  Step 0.5 전처리: swimmer's ear  ← 변동 없음
  Step 0.7 Gemini: swimmer's ear → otitis externa (conf=0.95)  ← 일반화로 사전 효과 무력화 ★
  Step 1   BGE-M3 검색: "otitis externa" → top1=Acute otitis externa
  → rank=11 ✗
```

### 1-2. 결함 본질

Gemini reformulator의 prompt (query_reformulator.py:60-83)는 **임상 용어 정규화 (root term 우선)**가 기본 동작. SNOMED preferred_term 보존을 명시하지 않음. 이로 인해 사전이 specific preferred_term ("swimmer's ear")으로 변환한 결과를 root term ("otitis externa")으로 다시 일반화. 사전 매핑의 정확성(SNOMED concept_id 직접 매핑)이 reformulate 단계에서 무력화.

---

## §2. 해결책 비교 (R-4 Phase 1)

| 옵션 | 변경 | 장점 | 단점 |
|---|---|---|---|
| 1 | Gemini prompt 수정 (preferred_term 보존 명시) | 단일 prompt 변경 | 다른 reformulate 동작 영향 위험 (T7 등) |
| **2 (채택)** | **사전 변환 시 reformulate skip** | rag_pipeline.py 1줄 변수 + 1 분기. 영향 범위 좁음 (사전 등록 한국어만) | 사전 결과의 추가 reformulate (post_coord_hint 등) 손실 — 검색 결과 영향 0 |
| 3 | ChromaDB description 인덱싱 추가 | 영구 해결 | ~2시간 재빌드 + 디스크 +500MB-1GB |

### 2-1. 옵션 2 채택 근거

- **단순:** `translated_query is not None and translated_query != question` 조건 추가
- **안전:** 사전 변환 발생 케이스만 영향 (영어 쿼리는 무관)
- **검증:** R-3 결과에서 한국어 사전 적용된 모든 케이스 [none] mode로 PASS → reformulate skip 시 [none] = [gemini] 동등 결과
- **회귀 0:** R-3 한국어 11쿼리 [none] 11/11 = R-4 한국어 [gemini] 11/11 (수렴)

---

## §3. 변경 — `src/retrieval/rag_pipeline.py:530-548`

### 3-1. Before (R-3)

```python
# Step 0.7: SNOMED 쿼리 리포매팅 (reformulator_backend != "none" 시 활성화)
reformulation_info = None
final_search_query = english_query
if self.reformulator is not None:
    reformulation = self.reformulator.reformulate(english_query)
    if reformulation.confidence >= 0.5:
        final_search_query = reformulation.reformulated
    reformulation_info = asdict(reformulation)
    print(...)
```

### 3-2. After (R-4)

```python
# Step 0.7: SNOMED 쿼리 리포매팅 (reformulator_backend != "none" 시 활성화)
# v3.1 R-4: 한국어 사전 변환 발생 시 reformulate skip
reformulation_info = None
final_search_query = english_query
dict_applied_korean = (translated_query is not None and translated_query != question)
if self.reformulator is not None and not dict_applied_korean:
    reformulation = self.reformulator.reformulate(english_query)
    if reformulation.confidence >= 0.5:
        final_search_query = reformulation.reformulated
    reformulation_info = asdict(reformulation)
    print(...)
elif self.reformulator is not None and dict_applied_korean:
    print(f"  [Reformulate-{self.reformulator_backend}] 한국어 사전 변환 결과 보존 (skip): {english_query}")
```

---

## §4. R-4 회귀 결과

### 4-1. 한국어 11쿼리 RERANK=1

| qid | 쿼리 | none rank | gemini rank | R-3 → R-4 |
|---|---|---:|---:|---|
| T9 | 고양이 당뇨 | **1** | **1** | 동일 (R-3에서도 PASS) |
| T10 | 개 췌장염 | **1** | **1** | 동일 |
| T11 | 고양이 범백혈구감소증 | **1** | **1** | 동일 |
| N-ko-01 | 갑상선 기능 저하증 | **1** | **1** | 동일 |
| N-ko-02 | 갑상선 기능 항진증 | **1** | **1** | 동일 |
| N-ko-03 | 백내장 | **1** | **1** | 동일 |
| N-ko-04 | 녹내장 | **1** | **1** | 동일 |
| **N-ko-05** | **외이염** | **1** | **1 ★** | **gemini 회복** (R-3: rank=11 → R-4: rank=1) |
| N-ko-06 | 심장 잡음 | **1** | **1** | 동일 |
| N-ko-07 | 고관절 이형성증 | **1** | **1** | 동일 |
| N-ko-08 | 림프종 | **1** | **1** | 동일 |

### 4-2. 종합 메트릭 — R-1 → R-4 누적

| backend | R-1 (정정) | R-2 | R-3 | **R-4** | 누적 Δ |
|---|---:|---:|---:|---:|---:|
| **none rank-1** | 6/11 | 9/11 | 11/11 ★ | **11/11 ★** | **+5** |
| **gemini rank-1** | 8/11 | 10/11 | 10/11 | **11/11 ★** | **+3** |
| **양쪽 PERFECT** | ❌ | ❌ | ❌ | **✓** | — |

**한국어 production 회귀 양쪽 backend PERFECT 도달.** v3.1 한국어 cycle 1차 완전 종결.

### 4-3. 회귀 가드

| # | 항목 | 결과 | 판정 |
|---|---|---|---|
| 1 | 영어 11쿼리 [none] | 10/10 | **PASS ✓** |
| 2 | 영어 11쿼리 [gemini] | 10/10 | **PASS ✓** |
| 3 | T7 핵심 (feline diabetes) | none 1 + gemini 1 (reformulated=diabetes mellitus) | **PASS ✓** |
| 4 | 단위 테스트 | **251 + 59 subtests** (81.99s) | **PASS ✓** |
| 5 | data/chroma_db/ 무변경 | production 1024d 보존 | **PASS ✓** |
| 6 | data/vet_term_dictionary 무변경 | v1.4 보존 | **PASS ✓** |

→ src/ 1 파일 (rag_pipeline.py) 변경 외 회귀 위험 0.

---

## §5. R4-S1 ~ R4-S6 1:1 PASS

| # | 항목 | 결과 | 판정 |
|---|---|---|---|
| R4-S1 | reformulate flow 분석 | rag_pipeline.py:530-543 + query_reformulator.py prompt 식별 | **PASS ✓** |
| R4-S2 | 해결책 옵션 3개 비교 | prompt vs skip vs description 인덱싱 | **PASS ✓** |
| R4-S3 | 옵션 2 (skip) 적용 | rag_pipeline.py:530-548 변경 | **PASS ✓** |
| R4-S4 | 한국어 11쿼리 PERFECT | none 11/11 + gemini 11/11 | **PASS ✓** |
| R4-S5 | 영어 11쿼리 + 단위 회귀 | 10/10×2 + 251 PASS | **PASS ✓** |
| R4-S6 | T9·N-ko-* gemini 동작 검증 | 모든 한국어 사전 변환 케이스 reformulate skip + PASS | **PASS ✓** |

---

## §6. R-1 → R-4 cycle 종합 종결

| 단계 | 변경 | 한국어 hits |
|---|---|---|
| R-9 Phase 2 (단독 BGE-M3) | — | 8/11 |
| R-1 (production 통합) | 사전 v1.2 | none 6/11 + gemini 8/11 |
| R-2 (사전 v1.3) | 고관절·림프종 specific 매핑 | none 9/11 + gemini 10/11 |
| R-3 (사전 v1.4) | 외이염 swimmer's ear + 심장 잡음 | none 11/11 + gemini 10/11 |
| **R-4 (reformulate skip)** | **rag_pipeline.py 1 분기 추가** | **none 11/11 + gemini 11/11 ★★** |

**누적 진전:** 사전 4 entry 변경/추가 + src/ 1 분기 → 한국어 hits 8/11 (R-9 Phase 2 단독) → **22/22 (R-4 production 통합 PERFECT)**. Gemini API 의존 X (none 단독으로도 PERFECT).

---

## §7. 산출물

| 분류 | 경로 | 변경 |
|---|---|---|
| src | `src/retrieval/rag_pipeline.py` | Step 0.7 reformulate 분기 추가 (~5줄) |
| graphify_out | `graphify_out/v3_1_korean_extension.json` | R-4 측정 결과 |
| graphify_out | `graphify_out/v3_1_r4_korean_validation.log` | R-4 실행 로그 (gitignored) |
| graphify_out | `graphify_out/regression_metrics_rerank.json` | 영어 회귀 갱신 |
| graphify_out | `graphify_out/backend_comparison.md` | 영어 비교 갱신 |
| docs | `docs/20260427_v3_1_r4_reformulate_skip.md` | 본 보고서 |

---

## §8. v3.1 milestone 진전 + 다음 후보

### 8-1. v3.1 한국어 cycle (R-1 ~ R-4) 1차 종결

- 한국어 production 회귀 PERFECT 11/11×2 도달
- v3.0 release 정직 지적사항 본질적 해소
- src/ 변경 최소 (rag_pipeline.py 1 분기) + 사전 4 entry — 회귀 위험 매우 낮음

### 8-2. v3.1.0 release 권고 (사용자 결정 게이트)

R-1~R-4 cycle 누적 5 commit 종합. v3.1.0 release tag publish 권고 시점.

| 옵션 | 내용 |
|---|---|
| A | GitHub Release v3.1.0 publish (R-1~R-4 누적 narrative) |
| B | v3.1.0-rc → 외부 검증 후 정식 publish |
| C | v3.1.0 보류, 다른 milestone 후보와 묶기 |

### 8-3. 다른 v3.1 후보

- budget_guard 영속화 (v2.9 R-10 미완)
- SNOMED VET 2026-09-30 release 갱신
- hybrid retrieval 정량화 (이력서 자료)

---

**v3.1 R-4 종결 (2026-04-27).**
**한국어 production 회귀 양쪽 backend PERFECT 11/11 도달.**
**v3.1 한국어 cycle 1차 완전 종결, v3.1.0 release publish 사용자 결정 대기.**
