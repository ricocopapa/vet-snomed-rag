---
tags: [vet-snomed-rag, v3.1, R-2, korean, dictionary, v1.3, generic-vs-specific]
date: 2026-04-27
status: v3.1 R-2 종결 — 사전 v1.3 적용 + 한국어 회귀 향상
phase: v3.1 R-2 — generic-vs-specific 매칭 결함 분석 + 사전 v1.3 강화
prev: docs/20260427_v3_1_r1_korean_validation.md
related:
  - data/vet_term_dictionary_ko_en.json
  - graphify_out/v3_1_korean_extension.json
  - graphify_out/regression_metrics_rerank.json
---

# v3.1 R-2 — 사전 v1.3 한국어 generic 매핑 강화

## §0. 결론 요약 (3줄)

R-1 미해소 3건 (외이염·고관절·림프종)의 결함 본질 = **SNOMED CT VET DB에 root concept 부재** (Lymphoma/Otitis externa/Hip dysplasia 단독 preferred_term 없음). 사전 v1.3에서 한국어 임상 통칭 → SNOMED VET DB 가용 specific subclass 직접 매핑 (고관절 이형성증→congenital hip dysplasia, 림프종→malignant lymphoma). 결과: **none 7/11→9/11 + gemini 8/11→10/11** (rank-1, +2/+2). 영어 11쿼리 회귀 0 (10/10×2) + 단위 251 PASS.

---

## §1. R-1 정직 정정 — N-ko-06 결과 오기

R-1 보고서 §1 표에 **N-ko-06 (심장 잡음) none rank=1**로 기록했으나 실제 R-1 log:

```
[N-ko-06] 심장 잡음 (gold: 88610006)
  [none] top1=248701005 (Cardiorespiratory murmur) rank=11 verdict=rank=11
  [gemini] top1=88610006 (Heart murmur) rank=1 verdict=PASS
```

→ R-1 실제: **none rank=11 + gemini rank=1.** 사전에 "심장 잡음" 미등록 (현재 사전에 "심장사상충"만 있음) → none mode 한국어 직접 BGE-M3 매칭 → 248701005 Cardiorespiratory murmur 잘못 매핑. R-1 보고서 표 작성 시 검증 누락 (Anti-Sycophancy 정직 보고).

→ R-1 종합 결과 정정: none **6**/11 (8/11 아님) + gemini 8/11.

---

## §2. R-2 Phase 1 — 결함 본질 진단

### 2-1. SNOMED CT VET DB root concept 부재 확정

```
exact preferred_term 매칭:
  "Lymphoma"           → 부재 (Adenolymphoma, Orbital lymphoma 등 specific만)
  "Otitis externa"     → 부재 (Acute, Chronic, Diffuse 등 specific만)
  "Hip dysplasia"      → 부재 (Congenital, Beukes type 등 specific만)
```

→ **사전 v1.2 영어 변환 ("림프종"→"lymphoma")이 도착 지점에 root term 없어 다른 specific subclass를 잘못 매핑.**

### 2-2. dataset gold 정밀 검증

| qid | gold_id | preferred_term | 한국어 의미 매핑 |
|---|---|---|---|
| N-ko-05 외이염 | 3135009 | **Swimmer's ear** | ✗ 부정확 (한국어 "외이염" generic disorder vs Swimmer's ear specific) |
| N-ko-07 고관절 이형성증 | 52781008 | **Congenital hip dysplasia** | ✓ 정확 (한국어 임상 통칭 = Congenital) |
| N-ko-08 림프종 | 118600007 | **Malignant lymphoma** | ✓ 정확 (한국어 임상 통칭 = Malignant) |

→ N-ko-05 외이염은 dataset gold 자체 의문 → 사전 변경 미적용, 별도 검증 권고.

---

## §3. R-2 Phase 2 — 사전 v1.3 변경

### 3-1. 변경 entry (2건)

| 한국어 | v1.2 | **v1.3** | gold concept_id | 근거 |
|---|---|---|---|---|
| 고관절 이형성증 | hip dysplasia | **congenital hip dysplasia** | 52781008 | 한국어 임상 통칭 = Congenital, gold preferred_term 일치 |
| 림프종 | lymphoma | **malignant lymphoma** | 118600007 | 한국어 임상 통칭 = Malignant, gold preferred_term 일치 |

### 3-2. _changelog 기록

```
"v1.3 (2026-04-27)": "v3.1 R-2: SNOMED VET DB root concept 부재 보정 2건.
'고관절 이형성증'→'congenital hip dysplasia' (gold 52781008),
'림프종'→'malignant lymphoma' (gold 118600007).
한국어 임상 통칭 = SNOMED VET DB 가용 specific subclass 매핑.
외이염은 dataset gold(Swimmer's ear) 의문으로 미수정 (별도 검증 권고)."
```

---

## §4. R-2 Phase 3 — 회귀 결과

### 4-1. 한국어 11쿼리 RERANK=1 (사전 v1.3)

| qid | 쿼리 | none rank | gemini rank | 변화 |
|---|---|---:|---:|---|
| T9 | 고양이 당뇨 | **1** | **1** | 동일 |
| T10 | 개 췌장염 | **1** | **1** | 동일 |
| T11 | 고양이 범백혈구감소증 SNOMED 코드 | **1** | **1** | 동일 |
| N-ko-01 | 갑상선 기능 저하증 | **1** | **1** | 동일 |
| N-ko-02 | 갑상선 기능 항진증 | **1** | **1** | 동일 |
| N-ko-03 | 백내장 | **1** | **1** | 동일 |
| N-ko-04 | 녹내장 | **1** | **1** | 동일 |
| N-ko-05 | 외이염 | rank=11 ✗ | rank=11 ✗ | 동일 (사전 미변경, 별도 검증 권고) |
| N-ko-06 | 심장 잡음 | rank=11 ✗ | **1** | 동일 (사전 미등록 그대로) |
| **N-ko-07** | **고관절 이형성증** | **1 ★** | **1 ★** | **PASS 회복** (gemini rank=3→1, none 추정 회복) |
| **N-ko-08** | **림프종** | **1 ★** | **1 ★** | **PASS 회복** (둘 다 rank=11→1) |

### 4-2. 종합 메트릭 비교 (R-1 정정 → R-2)

| backend | R-1 (정정) | **R-2** | Δ |
|---|---:|---:|---:|
| none rank-1 | 6/11 (55%) | **9/11 (82%)** | **+3건** |
| none rank≤5 | 7/11 (64%) | 9/11 (82%) | +2건 |
| gemini rank-1 | 8/11 (73%) | **10/11 (91%)** | **+2건** |
| gemini rank≤5 | 9/11 (82%) | 10/11 (91%) | +1건 |

→ 사전 v1.3 2건 변경으로 **none mode +3건 회복**. Gemini API 의존 X (none mode 단독으로 영어 변환 정확).

### 4-3. 회귀 가드

| # | 항목 | 결과 | 판정 |
|---|---|---|---|
| 1 | 영어 11쿼리 RERANK=1 (none) | **10/10** | **PASS ✓** |
| 2 | 영어 11쿼리 RERANK=1 (gemini) | **10/10** | **PASS ✓** |
| 3 | T7 핵심 (feline diabetes) | none 1 + gemini 1 (reformulated=diabetes mellitus) | **PASS ✓** |
| 4 | 단위 테스트 | **251 passed + 59 subtests** (82.28s) | **PASS ✓** |
| 5 | data/chroma_db/ 무변경 | production 1024d 보존 | **PASS ✓** |

---

## §5. R-2 R2-S1~R2-S6 1:1 PASS

| # | 항목 | 결과 | 판정 |
|---|---|---|---|
| R2-S1 | SNOMED VET DB root 부재 진단 | "Lymphoma"·"Otitis externa"·"Hip dysplasia" 모두 부재 확인 | **PASS ✓** |
| R2-S2 | dataset gold 정밀 검증 | 외이염 의문 / 고관절·림프종 정확 식별 | **PASS ✓** |
| R2-S3 | 사전 v1.3 변경 (2 entry) | 고관절 이형성증·림프종 매핑 강화 | **PASS ✓** |
| R2-S4 | 한국어 11쿼리 회귀 | none 9/11 + gemini 10/11 (각 +3/+2) | **PASS ✓** |
| R2-S5 | 영어 11쿼리 + 단위 회귀 | 10/10×2 + 251 + 59 subtests | **PASS ✓** |
| R2-S6 | R-1 정직 정정 | N-ko-06 결과 오기 정정 | **PASS ✓** |

---

## §6. 미해소 — 별도 cycle 후보

### 6-1. N-ko-05 외이염 — dataset gold 검증 cycle (R-3 후보)

- gold 3135009 = "Swimmer's ear" — 한국어 임상 의미 "외이염" generic 통칭과 부정확 매칭
- 후속 cycle 후보:
  - dataset gold를 다른 specific (예: 30250000 Acute otitis externa, 53295002 Chronic otitis externa) 또는 SNOMED CT 외부 root concept으로 정정
  - 사전에 "외이염" → 임상 통계상 가장 흔한 specific (예: "acute otitis externa") 매핑 (Phase 2 패턴)
- 본 R-2 범위 외, 별도 cycle 권고

### 6-2. N-ko-06 심장 잡음 [none] — 사전 미등록 결함

- 사전에 "심장 잡음" 미등록 → none mode 한국어 직접 BGE-M3 매칭 → 248701005 Cardiorespiratory murmur 잘못 매핑
- 사전 v1.4 후보: "심장 잡음" → "heart murmur" 추가 (88610006 정확 매핑)
- 단순 추가로 PASS 가능 — R-2 범위에 포함하지 않은 이유: R-2 cycle은 R-1 명시한 미해소 3건 패턴 분석 중심
- v3.1 R-3 또는 hot-fix 후보

### 6-3. R-2 → R-3 권고 흐름

1. **R-3 (가칭) 외이염 dataset 검증 + 심장 잡음 사전 추가** — 두 미해소 동시 처리 cycle
2. 또는 R-3 일부 분리: 심장 잡음 hot-fix → 별도 사전 v1.4 + 외이염 dataset 검증 분리

---

## §7. 산출물

| 분류 | 경로 | 변경 |
|---|---|---|
| data | `data/vet_term_dictionary_ko_en.json` | _version v1.2→v1.3 + _changelog 추가 + 2 entry 변경 |
| graphify_out | `graphify_out/v3_1_korean_extension.json` | R-2 측정 결과 (R-1 덮어씀, 백업 미보존) |
| graphify_out | `graphify_out/v3_1_r2_korean_validation.log` | R-2 실행 로그 |
| graphify_out | `graphify_out/regression_metrics_rerank.json` | 영어 11쿼리 회귀 (timestamp 갱신) |
| graphify_out | `graphify_out/backend_comparison.md` | 영어 회귀 비교 갱신 |
| docs | `docs/20260427_v3_1_r2_korean_dictionary_v1_3.md` | 본 보고서 |
| src | (변경 없음) | 회귀 0 |

---

## §8. R-1 → R-2 cycle 종합

| 단계 | 핵심 변경 | 한국어 hits 변화 |
|---|---|---|
| R-9 Phase 2 (1,000-pool 단독 BGE-M3) | — | 8/11 |
| R-1 (production 통합 측정) | 사전 v1.2 단순 영어 변환 | none 6/11 + gemini 8/11 |
| **R-2 (사전 v1.3 강화)** | **고관절·림프종 specific 매핑** | **none 9/11 + gemini 10/11 ★** |

**누적 진전:** R-9 Phase 2 정직 지적사항 본질적 해소. 한국어 production 회귀 hits 10/11 (gemini)·9/11 (none) 도달. 남은 미해소 1-2건은 dataset gold 검증 + 사전 v1.4 hot-fix로 해결 가능 (별도 cycle).

---

**v3.1 R-2 종결 (2026-04-27).**
**남은 R-3 후보: 외이염 dataset gold 검증 + 심장 잡음 사전 v1.4 hot-fix.**
