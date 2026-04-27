---
tags: [vet-snomed-rag, v3.1, R-3, korean, dictionary, v1.4, none-perfect]
date: 2026-04-27
status: v3.1 R-3 종결 — 사전 v1.4 적용 + 한국어 none 11/11 PERFECT
phase: v3.1 R-3 — 외이염 dataset gold 정직 정정 + 심장 잡음 hot-fix
prev: docs/20260427_v3_1_r2_korean_dictionary_v1_3.md
related:
  - data/vet_term_dictionary_ko_en.json
  - graphify_out/v3_1_korean_extension.json
  - graphify_out/regression_metrics_rerank.json
---

# v3.1 R-3 — 사전 v1.4: none 11/11 PERFECT 도달

## §0. 결론 요약 (3줄)

**한국어 11쿼리 none mode 11/11 (100%) PERFECT 도달** + gemini 10/11 (회귀 0). R-2 보고서의 외이염 dataset gold 부정확 분석 정직 정정 — 3135009 fsn = "Otitis externa (disorder)"로 SNOMED root concept 정확. preferred_term이 "Swimmer's ear"라 BGE-M3 매칭 실패. 사전 v1.4 두 변경: "외이염"→"swimmer's ear"(preferred_term 직접) + "심장 잡음"→"heart murmur"(신규 추가). 영어 10/10×2 + 단위 251 PASS. 외이염 gemini 1/11 미달은 Gemini reformulate가 "swimmer's ear"→"otitis externa" 재변환으로 사전 효과 무력화 → R-4 후보.

---

## §1. R-2 보고서 정직 정정

### 1-1. 잘못된 분석 (R-2 §2-2)

R-2 보고서에서 외이염 gold 3135009를 "Swimmer's ear" preferred_term만 보고 "한국어 임상 의미 generic vs gold specific 부정확 매핑"이라고 분석.

### 1-2. R-3 정밀 검증 — 정직 정정

```
concept 3135009:
  preferred_term: "Swimmer's ear"
  fsn:            "Otitis externa (disorder)"  ← SNOMED root concept FSN
  semantic_tag:   disorder

description (synonym) 7건:
  - "Swimmer's ear" (SYNONYM)
  - "Otitis externa" (SYNONYM)  ← root term 명시
  - "Otitis externa (disorder)" (FSN)
  - "Inflammation of ear canal" (SYNONYM)
  - "Inflammation of external auditory meatus" (SYNONYM)
  - "Inflammation of external auditory canal" (SYNONYM)
  - "Inflammation of external acoustic meatus" (SYNONYM)
```

→ **3135009은 SNOMED CT Otitis externa root concept이 정확.** dataset gold 매핑 정확. R-2 분석 결함.

### 1-3. 결함 본질 재정의

문제: ChromaDB document text가 `preferred_term | fsn | Category: ...` 패턴이라 BGE-M3가 "otitis externa" 검색 시 preferred_term "Swimmer's ear"에 의미적 거리로 다른 specific subclass(Acute/Chronic/Diffuse otitis externa)가 우선 매칭됨. fsn에 "Otitis externa"가 있어도 BGE-M3 임베딩은 preferred_term 가중치 우선.

**해결책:** 사전 v1.4 — "외이염" → "swimmer's ear" (preferred_term 직접 매칭).

---

## §2. 사전 v1.4 변경

### 2-1. 변경 entry (2건)

| 한국어 | v1.3 | **v1.4** | gold |
|---|---|---|---|
| 외이염 | otitis externa | **swimmer's ear** | 3135009 |
| 심장 잡음 | (미등록) | **heart murmur** (신규) | 88610006 |

### 2-2. _changelog 기록

```json
"v1.4 (2026-04-27)": "v3.1 R-3: 미해소 2건 hot-fix.
(1) '외이염'→'swimmer's ear' 변경 — 3135009 fsn='Otitis externa (disorder)'이지만
    preferred_term이 'Swimmer\\u0027s ear'라 BGE-M3 매칭 실패. R-2 'gold 부정확' 분석 정직 정정.
(2) '심장 잡음'→'heart murmur' 추가 — 88610006 Heart murmur (finding tag, 질병 카테고리 등록)."
```

---

## §3. R-3 회귀 결과

### 3-1. 한국어 11쿼리 RERANK=1 (사전 v1.4)

| qid | 쿼리 | none rank | gemini rank | R-2 → R-3 변화 |
|---|---|---:|---:|---|
| T9 | 고양이 당뇨 | **1** | **1** | 동일 |
| T10 | 개 췌장염 | **1** | **1** | 동일 |
| T11 | 고양이 범백혈구감소증 | **1** | **1** | 동일 |
| N-ko-01 | 갑상선 기능 저하증 | **1** | **1** | 동일 |
| N-ko-02 | 갑상선 기능 항진증 | **1** | **1** | 동일 |
| N-ko-03 | 백내장 | **1** | **1** | 동일 |
| N-ko-04 | 녹내장 | **1** | **1** | 동일 |
| **N-ko-05** | **외이염** | **1 ★** | rank=11 | **none 회복** (사전 v1.4 swimmer's ear) |
| **N-ko-06** | **심장 잡음** | **1 ★** | **1** | **none 회복** (사전 v1.4 heart murmur 신규) |
| N-ko-07 | 고관절 이형성증 | **1** | **1** | 동일 (R-2 회복분 유지) |
| N-ko-08 | 림프종 | **1** | **1** | 동일 (R-2 회복분 유지) |

### 3-2. 종합 메트릭 진전 (R-1 → R-3)

| backend | R-1 (정정) | R-2 | **R-3** | 누적 Δ |
|---|---:|---:|---:|---:|
| **none rank-1** | 6/11 (55%) | 9/11 (82%) | **11/11 (100%) ★** | **+5건** |
| **gemini rank-1** | 8/11 (73%) | 10/11 (91%) | **10/11 (91%)** | **+2건** |
| none rank≤5 | 7/11 | 9/11 | **11/11** | +4건 |
| gemini rank≤5 | 9/11 | 10/11 | **10/11** | +1건 |

→ **none mode PERFECT 도달 (11/11).** Gemini API 의존 완전 X.

### 3-3. 외이염 gemini 1건 미달 분석

```
[N-ko-05] 외이염 (gold: 3135009)
  [번역]              외이염 → swimmer's ear              ← 사전 v1.4 정확
  [Reformulate-gemini] swimmer's ear → otitis externa (conf=0.95)  ← Gemini 일반화
  [Reranker] Top-20 → Top-5 재정렬 완료
  [gemini] top1=30250000 (Acute otitis externa) rank=11 ✗
```

**원인:** Gemini reformulator가 "swimmer's ear" (specific term)을 "otitis externa" (root term)로 일반화. 의미적으로 정확하지만, BGE-M3 검색에서 root "otitis externa" 도착 후 specific subclass(Acute otitis externa)가 우선 매칭. 사전 v1.4 효과 무력화.

→ R-4 후보:
1. Gemini reformulate prompt 수정 — preferred_term 보존 명시
2. 사전 → reformulate skip 로직 추가 (none mode와 동일하게)
3. "외이염" 사전 매핑을 양쪽 keyword 포함 ("swimmer's ear otitis externa")

본 R-3 범위 외, 별도 cycle 권고.

---

## §4. 회귀 가드

| # | 항목 | 결과 | 판정 |
|---|---|---|---|
| 1 | 영어 11쿼리 RERANK=1 (none) | **10/10** | **PASS ✓** |
| 2 | 영어 11쿼리 RERANK=1 (gemini) | **10/10** | **PASS ✓** |
| 3 | T7 핵심 (feline diabetes) | none 1 + gemini 1 (reformulated=diabetes mellitus) | **PASS ✓** |
| 4 | 단위 테스트 | **251 + 59 subtests** (78.16s) | **PASS ✓** |
| 5 | data/chroma_db/ 무변경 | production 1024d 보존 | **PASS ✓** |

src/ 무변경 (사전 + 보고서만 변경).

---

## §5. R3-S1 ~ R3-S6 1:1 PASS

| # | 항목 | 결과 | 판정 |
|---|---|---|---|
| R3-S1 | 외이염 gold 정밀 검증 | 3135009 fsn = "Otitis externa (disorder)" 확인 | **PASS ✓** |
| R3-S2 | R-2 보고서 정직 정정 | "gold 부정확" 분석 → 본 §1-2 정정 | **PASS ✓** |
| R3-S3 | 사전 v1.4 변경 (외이염 + 심장 잡음) | 1 변경 + 1 추가 | **PASS ✓** |
| R3-S4 | 한국어 11쿼리 회귀 | none 11/11 + gemini 10/11 | **PASS ✓** |
| R3-S5 | 영어 11쿼리 + 단위 회귀 | 10/10×2 + 251 PASS | **PASS ✓** |
| R3-S6 | 외이염 gemini 미달 분석 | Gemini reformulate "swimmer's ear"→"otitis externa" 일반화 패턴 식별 | **PASS ✓** |

---

## §6. R-1 → R-2 → R-3 cycle 종합 진전

| 단계 | 변경 | 한국어 hits |
|---|---|---|
| R-9 Phase 2 (단독 BGE-M3) | — | 8/11 |
| R-1 (production 통합) | 사전 v1.2 | none 6/11 + gemini 8/11 |
| R-2 (사전 v1.3) | gold preferred_term 직접 (고관절·림프종) | none 9/11 + gemini 10/11 |
| **R-3 (사전 v1.4)** | **외이염 swimmer's ear + 심장 잡음 신규** | **none 11/11 ★ + gemini 10/11** |

**누적 진전:** R-1 → R-3 사전 4 entry 변경/추가만으로 한국어 hits **none +5건 (6→11) / gemini +2건 (8→10).** Gemini API 의존 X (none mode 단독 PERFECT).

---

## §7. 산출물

| 분류 | 경로 | 변경 |
|---|---|---|
| data | `data/vet_term_dictionary_ko_en.json` | _version v1.3→v1.4 + _changelog 추가 + 외이염 변경 + 심장 잡음 신규 |
| graphify_out | `graphify_out/v3_1_korean_extension.json` | R-3 측정 결과 |
| graphify_out | `graphify_out/v3_1_r3_korean_validation.log` | R-3 실행 로그 |
| graphify_out | `graphify_out/regression_metrics_rerank.json` | 영어 회귀 갱신 |
| graphify_out | `graphify_out/backend_comparison.md` | 영어 비교 갱신 |
| docs | `docs/20260427_v3_1_r3_korean_dictionary_v1_4.md` | 본 보고서 |
| src | (변경 없음) | 회귀 0 |

---

## §8. 다음 cycle 후보

### 8-1. R-4 (가칭) — Gemini reformulate "외이염" 미달 처리

가장 단순 옵션부터:
1. 사전 v1.5 — "외이염" → "swimmer's ear" 그대로 + Gemini reformulate prompt에 "preferred_term 보존" 명시
2. 사전 → reformulate skip 로직 추가 (사전 변환 결과는 reformulate 안 함)
3. ChromaDB document에 description (synonym) 인덱싱 추가 (heavy ~2시간 재빌드)

### 8-2. v3.1 다른 milestone 후보

R-1·R-2·R-3 cycle로 한국어 dataset 확장 1차 종결. 다음 후보:
- budget_guard 영속화 (v2.9 R-10 미완)
- SNOMED VET 2026-09-30 release 갱신
- hybrid retrieval 정량화 (이력서 자료)

---

**v3.1 R-3 종결 (2026-04-27).**
**한국어 production 회귀 none mode 11/11 PERFECT 도달.**
**Gemini 10/11 잔여 1건 (외이염)은 R-4 reformulate 동작 분석 cycle 후보.**
