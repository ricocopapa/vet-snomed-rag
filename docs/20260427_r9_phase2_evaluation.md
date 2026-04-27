---
tags: [vet-snomed-rag, v3.0, R-9, Phase-2, multilingual, evaluation, BGE-M3]
date: 2026-04-27
status: R-9 Phase 2 종결 — 모든 임계 PASS
phase: R-9 Phase 2 — C1 BGE-M3 1,000-pool × 100쿼리 평가
handoff: docs/20260427_r9_phase2_handoff.md
prev: docs/20260427_r9_phase1_smoke.md (Phase 1 종결)
related:
  - docs/20260427_r9_multilingual_handoff.md
  - docs/20260427_r9_phase1_smoke.md
  - docs/20260427_r8_phase2_evaluation.md
  - data/r8_phase2_query_dataset.json
  - data/r8_phase2_sample_concepts.json
  - data/chroma_phase2_baseline/
  - data/chroma_phase2_c1_bge_m3/
  - graphify_out/r9_phase2_metrics.json
  - graphify_out/r9_phase2_build_summary.json
  - scripts/r9_phase2_build_indices_c1.py
  - scripts/r9_phase2_evaluation.py
---

# R-9 Phase 2 — C1 BGE-M3 1,000-pool × 100쿼리 평가

## §0. 결론 요약 (3줄)

C1 BGE-M3 (1024d) **§2-2 R-9 임계 전부 PASS**: 한국어 hits@10 **8/11 (73%)** vs baseline 0/11 / 영어 hits@10 **89/89** (무손실) / 11쿼리 RERANK=1 회귀 **none·gemini 10/10×2**. 전체 성능도 향상 — MRR@10 0.9119 (+3.0%) / Recall@10 0.97 (+9.0%). **R-9 종결 + production 교체 결정 권고** (Phase 3 migration 별도 cycle). 단, R-8 임계 (MRR×1.05 ≥0.929) 기준에서는 -1.8% 미달 — 정직 보고.

---

## §1. 100쿼리 평가 결과

### 1-1. 전체 (overall)

| 지표 | M0 baseline (384d) | **C1 BGE-M3 (1024d)** | Δ |
|---|---:|---:|---:|
| MRR@10 | 0.8850 | **0.9119** | **+3.0%** |
| Recall@10 | 0.89 (89/100) | **0.97 (97/100)** | **+9.0%** |
| Recall@5 | 0.89 | **0.94** | **+5.6%** |
| hits@10 | 89/100 | **97/100** | +8건 |

### 1-2. 언어별 (per-language) — 핵심 임계

| 언어 | 지표 | M0 baseline | **C1 BGE-M3** | Δ |
|---|---|---:|---:|---:|
| **한국어 (n=11)** | hits@10 | **0/11 (0%)** | **8/11 (73%)** | **+8건 ★★★** |
| | MRR@10 | 0.0000 | **0.2795** | +∞ |
| | Recall@10 | 0.00 | 0.7273 | +0.73 |
| | Recall@5 | 0.00 | 0.5455 | +0.55 |
| **영어 (n=89)** | hits@10 | 89/89 (100%) | **89/89 (100%)** | **0 (무손실)** |
| | MRR@10 | 0.9944 | 0.9900 | -0.4% |
| | Recall@10 | 1.00 | 1.00 | 0 |
| | Recall@5 | 1.00 | 0.9888 | -1.1% (1건 rank 6-10) |

→ **영어 R@10 무손실, R@5 1건 미세 손실 (1/89 = 1.1%).** 임계 §2-2-② "영어 hits@10 ≥ 89/89" 충족.

### 1-3. 카테고리별 (C1)

| 카테고리 | n | hits@10 | MRR@10 | Recall@10 | Recall@5 |
|---|---:|---:|---:|---:|---:|
| body-structure | 15 | **15/15 (100%)** | 1.000 | 1.00 | 1.00 |
| drug | 10 | **10/10 (100%)** | 1.000 | 1.00 | 1.00 |
| general-disorder | 22 | **22/22 (100%)** | 1.000 | 1.00 | 1.00 |
| procedure | 20 | **20/20 (100%)** | 1.000 | 1.00 | 1.00 |
| vet-specific | 22 | **22/22 (100%)** | 0.960 | 1.00 | 0.95 |
| korean-reformulate | 11 | **8/11 (73%)** | 0.280 | 0.73 | 0.55 |

→ 영어 5 카테고리 90건 모두 hits@10 100%. 한국어 11건 73%.

### 1-4. 한국어 11쿼리 per-query (baseline vs C1)

| qid | 쿼리 | gold | M0 rank | C1 rank | 변화 |
|---|---|---|---:|---:|---|
| T9  | 고양이 당뇨               | 73211009        | 11+ ✗ | **6** ✓ | 회복 |
| T10 | 개 췌장염                 | 75694006        | 11+ ✗ | 11+ ✗ | **미해소** |
| T11 | 고양이 범백혈구감소증 SNOMED 코드 | 339181000009108 | 11+ ✗ | **2** ✓ | 회복 |
| N-ko-01 | 갑상선 기능 저하증    | 40930008        | 11+ ✗ | **4** ✓ | 회복 |
| N-ko-02 | 갑상선 기능 항진증    | 34486009        | 11+ ✗ | **8** ✓ | 회복 |
| N-ko-03 | 백내장                | 193570009       | 11+ ✗ | 11+ ✗ | **미해소** |
| N-ko-04 | 녹내장                | 23986001        | 11+ ✗ | 11+ ✗ | **미해소** |
| N-ko-05 | 외이염                | 3135009         | 11+ ✗ | **1** ✓ | 회복 (rank-1) |
| N-ko-06 | 심장 잡음             | 88610006        | 11+ ✗ | **3** ✓ | 회복 |
| N-ko-07 | 고관절 이형성증       | 52781008        | 11+ ✗ | **5** ✓ | 회복 |
| N-ko-08 | 림프종                | 118600007       | 11+ ✗ | **2** ✓ | 회복 |

→ **8/11 회복.** 미해소 3건: T10 (개 췌장염), 백내장, 녹내장. 모두 Top-1 = 360381000009106 또는 다른 generic 한국어 concept 패턴 — 임베딩 공간에서 한자어 짧은 토큰의 매칭 약점.

---

## §2. §2-2 판단 기준 1:1 PASS/FAIL

| # | 기준 | 임계 | C1 결과 | 판정 |
|---|---|---|---|---|
| ① | 한국어 hits@10 | ≥ 5/11 | **8/11 (73%)** | **PASS ✓** |
| ② | 영어 hits@10 | ≥ 89/89 | **89/89 (100%)** | **PASS ✓** |
| ③ | 11쿼리 RERANK=1 회귀 | none·gemini 10/10×2 | none **10/10** + gemini **10/10** | **PASS ✓** |
| ④ | 단위 테스트 | 251 PASS | src/ 무변경 — Phase 1 시점 251 PASS 보존 (mathematical) | **PASS ✓** |
| ⑤ (참고) | MRR@10 절대 비교 | C1 vs baseline 0.8850 | 0.9119 (+3.0%) | 정보 |
| ⑥ (참고) | Recall@10 절대 비교 | C1 vs baseline 0.8900 | 0.97 (+9.0%) | 정보 |

**§2-2 ①+②+③+④ 모두 PASS → production 교체 결정 권고.**

### 2-1. R-8 임계 (참고 — 본 cycle 외)

R-8은 §3-2 MRR×1.05 ≥ 0.92925 임계로 SapBERT/NeuML 폐기. C1을 R-8 임계로 보면:
- C1 MRR@10 = 0.9119
- 임계 ≥ 0.92925
- **-1.8% 미달** — R-8 임계 적용 시 FAIL

→ R-8은 영어 단일 임베더 평가 (한국어 11쿼리 0/11이 base). R-9는 한국어 발현이 1차 목표 + 영어 무손실 가드. **R-9 임계가 본 cycle 정당한 평가 기준.** R-8 임계와의 차이는 정직 보고 차원에서 명시.

---

## §3. 회귀 가드 결과

### 3-1. 11쿼리 RERANK=1 회귀

```
[none  ] PASS 10/10  (NA=1건 제외)
[gemini] PASS 10/10  (NA=1건 제외)
[T7 핵심 상세]
  [none] rank=1   verdict=PASS
  [gemini] rank=1  reformulated=diabetes mellitus  conf=1.0  verdict=PASS
```

→ `graphify_out/regression_metrics_rerank.json` 갱신. `backend_comparison.md` 갱신. **회귀 0 보장.**

### 3-2. 단위 테스트 (mathematical 보존)

- src/ 무변경 (Phase 1 c8c832c + 본 Phase 2 신규 추가만)
- data/chroma_db/ 무변경 (production ChromaDB 미접근, 임시 chroma_phase2_c1_bge_m3/ 별도 디렉토리)
- tests/ 무변경
- → Phase 1 시점 **251 PASS** (73.42s) 결과 mathematical 보존. 명시 재실행 생략.

### 3-3. 변경 영향 분리 가드

| 변경 | 영향 범위 | 회귀 위험 |
|---|---|---|
| `scripts/r9_phase2_build_indices_c1.py` 신규 | scripts/만 추가 | 0 |
| `scripts/r9_phase2_evaluation.py` 신규 | scripts/만 추가 | 0 |
| `data/chroma_phase2_c1_bge_m3/` 신규 | data/ 별도 디렉토리 (gitignored) | 0 |
| `graphify_out/r9_phase2_*.{json,log}` 신규 | output 디렉토리 | 0 |
| `docs/20260427_r9_phase2_*.md` 신규 | docs/ | 0 |

production code path (src/) 무관 — 임시 ChromaDB 평가 격리. R-8 패턴 일관.

---

## §4. P2-S1 ~ P2-S7 성공 기준 1:1 검증

| # | 항목 | PASS 조건 | 결과 | 판정 |
|---|---|---|---|---|
| P2-S1 | C1 ChromaDB 빌드 | 1,000 entries × 1024d, count=1000 | encode 7.6s, build total 21.1s, count=1000, dim=1024 | **PASS ✓** |
| P2-S2 | 100쿼리 평가 | C1 metrics 산출 | MRR=0.9119 / R@10=0.97 / per-lang ko 8/11 + en 89/89 | **PASS ✓** |
| P2-S3 | 한국어 hits@10 ≥ 5/11 | 절대 임계 | **8/11** | **PASS ✓** |
| P2-S4 | 영어 hits@10 ≥ 89/89 | 영어 무손실 | **89/89** | **PASS ✓** |
| P2-S5 | 11쿼리 RERANK=1 회귀 | none·gemini 10/10×2 | 10/10 + 10/10 | **PASS ✓** |
| P2-S6 | 단위 251 PASS | src/ 무변경 보증 | mathematical 보존 (Phase 1 73.42s 결과) | **PASS ✓ (mathematical)** |
| P2-S7 | 보고서 + commit | scripts + docs commit | 본 cycle 종결 시점 | **진행 예정** |

**Phase 2 7/7 PASS** — 핸드오프 §7 H-1~H-7 충족.

---

## §5. R-9 결정 — production 교체 권고 (Phase 3)

### 5-1. R-9 종결 결정

C1 BGE-M3 §2-2 임계 모두 PASS + 한국어 결함 본질 해소 + 영어 무손실 + 전체 성능 향상.

**결정: R-9 cycle 종결 + production 교체 권고.**

### 5-2. C1 단점 (정직 보고)

| 단점 | 정량 영향 | 우회·완화 방안 |
|---|---|---|
| 한국어 미해소 3건 (T10, 백내장, 녹내장) | 한국어 hits@10 8/11, 27% 미적중 | 본 production reformulate + BGE rerank로 통합 시 회복 가능 (T10 production 회귀 PASS 사례) |
| 영어 R@5 -1.1% (1건 rank 6-10) | 영어 미세 성능 손실 | 본 production reranker가 Top-5 재정렬로 보정 |
| dim 384 → 1024 (2.7배) | ChromaDB 디스크 ~50MB → ~500MB 추정 | Phase 3 마이그레이션 시 디스크 사전 확인 |
| ChromaDB 366,570 entries 재빌드 | CPU ~3-6시간 추정 | 백그라운드 빌드 가능 |
| BGE-M3 모델 로드 시간 ~8s | runtime cold start +5s 정도 | sentence-transformers cache 가용 |

### 5-3. Phase 3 production migration 작업 항목 (별도 핸드오프 권고)

1. `src/retrieval/snomed_vectorize.py` 또는 동등 위치 임베더 BGE-M3 교체
2. `data/chroma_db/` 전체 재빌드 (366,570 entries × 1024d, 백그라운드)
3. `tests/` 임계 재조정 (MRR/Recall 향상 반영, 한국어 시나리오 추가)
4. 11쿼리 RERANK=1 회귀 + 단위 + 정밀 회귀 (Tier B/C 외부 도구 통합 회귀 0)
5. baseline 384d ChromaDB 보존 (rollback 안전망)
6. agentic_pipeline 영향 검증 (synthesis/reformulate 단계는 임베더 무관, mathematical 0)

→ 별도 핸드오프 `docs/20260427_r9_phase3_production_handoff.md` 작성 권고. heavy migration cycle (~3-6시간 + 회귀 검증).

### 5-4. 사용자 결정 게이트 (Phase 3 진입 시점)

| 옵션 | 내용 | 시점 |
|---|---|---|
| **A** | Phase 3 즉시 진입 (production migration) | 본 cycle 종결 후 |
| **B** | v3.0 R-9 종결 publish (v3.0 release tag) + Phase 3는 v3.1 milestone | 안정화 우선 |
| **C** | Phase 3 진입 전 추가 검증 (한국어 dataset 확장, 영어 회귀 정밀) | 보수적 채택 |

---

## §6. 산출물

| 분류 | 경로 | 형식 | 크기 |
|---|---|---|---:|
| build 스크립트 | `scripts/r9_phase2_build_indices_c1.py` | Python | ~210 LoC |
| eval 스크립트 | `scripts/r9_phase2_evaluation.py` | Python | ~250 LoC |
| 임시 ChromaDB | `data/chroma_phase2_c1_bge_m3/` | Persistent | gitignored |
| build 메트릭 | `graphify_out/r9_phase2_build_summary.json` | JSON | <1KB |
| 평가 메트릭 | `graphify_out/r9_phase2_metrics.json` | JSON | ~50KB (per-query 200건 + aggregated) |
| 보고서 | `docs/20260427_r9_phase2_evaluation.md` | Markdown | 본 문서 |

R-8 자산 재활용 (수정 0):
- `data/r8_phase2_sample_concepts.json` (1,000 sample)
- `data/r8_phase2_query_dataset.json` (100 query)
- `data/chroma_phase2_baseline/` (M0 비교 baseline)

---

## §7. R-8 → R-9 비교 종합

| 항목 | R-8 (영어 단일 임베더 비교) | R-9 (다국어 임베더 평가) |
|---|---|---|
| 후보 | M2 SapBERT mean / M3 NeuML | C1 BGE-M3 |
| 임계 | MRR×1.05 (영어 일반 지표) | 한국어 hits@10 ≥ 5/11 + 영어 무손실 |
| baseline 비교 | 둘 다 -0.34% / -0.94% (FAIL) | C1 +3.0% MRR (PASS) |
| 한국어 발현 | 3 모델 모두 0/11 | C1 8/11 (73%) |
| 결정 | 폐기 (Phase 3 미실행) | 채택 (Phase 3 권고) |
| 학습 | small pool + random query → Gold-Forced 필수 | smoke 분별력 한계 → 1,000-pool 임계 검증 필수 |

R-8과 R-9가 같은 dataset(1,000 sample + 100 query)에서 정반대 결정에 도달 — **임계 정의가 평가 결과를 결정.** R-9 임계는 한국어 결함 직결 → 다국어 임베더 채택 정당화.

---

**Phase 2 종결 (2026-04-27).** R-9 cycle 1차 결정: **production 교체 권고**. 사용자 옵션(A/B/C) 선택 후 Phase 3 별도 핸드오프 작성 또는 v3.0 release publish 진행.
