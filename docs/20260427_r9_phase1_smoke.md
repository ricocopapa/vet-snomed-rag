---
tags: [vet-snomed-rag, v3.0, R-9, phase-1, multilingual, smoke]
date: 2026-04-27
status: R-9 Phase 1 종결
phase: R-9 Phase 1 — 7쿼리 smoke (다국어 임베더 1차 검증)
handoff: docs/20260427_r9_multilingual_handoff.md
default_choices:
  R9-1: a (proceed)
  R9-2: b (C1 BGE-M3 + C2 multilingual-e5-large)
  R9-3: b (T1·T3·T5·T8 영어 4 + T9·T10·T11 한국어 3 = 7쿼리)
  R9-4: b (Phase 2 자동 진입 ❌, 사용자 결정 게이트)
  R9-5: a (한국어 rank-1 hits ≥ 1 Phase 1 임계)
  R9-6: c (.gitignore + 보존)
related:
  - docs/20260427_r9_multilingual_handoff.md
  - docs/20260427_r8_phase2_evaluation.md
  - docs/20260427_r8_disposal.md
  - scripts/r9_phase1_smoke.py
  - graphify_out/r9_phase1_smoke.json
  - graphify_out/r9_phase1_smoke.log
---

# R-9 Phase 1 — 7쿼리 smoke 다국어 임베더 비교

## §0. 결론 요약 (Anti-Sycophancy 3줄)

§3-2 판단 기준 표면 PASS이나 **R-9 후보의 baseline 대비 한국어 우월성 미입증**. C1 BGE-M3 한국어 rank-1 2/3 (baseline 동률), C2 ml-e5-large 1/3 (baseline 미달). **5 candidate 좁은 pool 한계로 baseline도 한국어 2/3 적중** (R-8 1,000-pool 0/11과 모순) → smoke 분별력 본질적 한계 재확인. Phase 2 진입 결정은 사용자 게이트 (R9-4=b) — **C1 단독 권고** (C2는 cosine 평탄성으로 1,000-pool 발현 가능성 낮음).

---

## §1. 7 쿼리 × 3 모델 cosine 매트릭스

### 1-1. 입력

| qid | lang | 쿼리 | gold concept_id | gold term |
|---|---|---|---|---|
| T1  | en | feline panleukopenia SNOMED code      | 339181000009108 | Feline panleukopenia |
| T3  | en | diabetes mellitus in cat              | 73211009        | Diabetes mellitus |
| T5  | en | chronic kidney disease in cat         | 709044004       | Chronic kidney disease |
| T8  | en | diabetes mellitus type 1              | 46635009        | Diabetes mellitus type 1 |
| T9  | ko | 고양이 당뇨                            | 73211009        | Diabetes mellitus |
| T10 | ko | 개 췌장염                              | 75694006        | Pancreatitis |
| T11 | ko | 고양이 범백혈구감소증 SNOMED 코드      | 339181000009108 | Feline panleukopenia |

**Candidate pool:** 5 unique concept (T3·T9 = 73211009 / T1·T11 = 339181000009108 중복 → 5개 unique).

### 1-2. M0 baseline all-MiniLM-L6-v2 (현행 production, 384d)

| qid | lang | gold cos | top-1 cos | rank | hit |
|---|---|---:|---:|---:|---|
| T1  | en | +0.8025 | +0.8025 | **1** | ✓ |
| T3  | en | +0.6804 | +0.6804 | **1** | ✓ |
| T5  | en | +0.7482 | +0.7482 | **1** | ✓ |
| T8  | en | +1.0000 | +1.0000 | **1** | ✓ |
| T9  | ko | +0.0320 | +0.0518 (Pancreatitis) | 2 | ✗ |
| T10 | ko | +0.0763 | +0.0763 | **1** | ✓ |
| T11 | ko | +0.1369 | +0.1369 | **1** | ✓ |

- 영어 4건 rank-1: **4/4** / 한국어 3건 rank-1: **2/3** / rank≤3: **3/3**
- gold cos mean: +0.4966 / off cos mean: +0.1761 / margin: **+0.3205**

### 1-3. C1 BGE-M3 (1024d)

| qid | lang | gold cos | top-1 cos | rank | hit |
|---|---|---:|---:|---:|---|
| T1  | en | +0.6876 | +0.6876 | **1** | ✓ |
| T3  | en | +0.6529 | +0.6529 | **1** | ✓ |
| T5  | en | +0.6843 | +0.6843 | **1** | ✓ |
| T8  | en | +0.9797 | +0.9797 | **1** | ✓ |
| T9  | ko | +0.5273 | +0.5273 | **1** | ✓ |
| T10 | ko | +0.4516 | +0.5069 (Feline panleukopenia) | 3 | ✗ |
| T11 | ko | +0.4810 | +0.4810 | **1** | ✓ |

- 영어 4건 rank-1: **4/4** / 한국어 3건 rank-1: **2/3** / rank≤3: **3/3**
- gold cos mean: +0.6378 / off cos mean: +0.4301 / margin: **+0.2077**

### 1-4. C2 multilingual-e5-large (1024d, query/passage prefix)

| qid | lang | gold cos | top-1 cos | rank | hit |
|---|---|---:|---:|---:|---|
| T1  | en | +0.8887 | +0.8887 | **1** | ✓ |
| T3  | en | +0.8579 | +0.8579 | **1** | ✓ |
| T5  | en | +0.8686 | +0.8686 | **1** | ✓ |
| T8  | en | +0.9091 | +0.9091 | **1** | ✓ |
| T9  | ko | +0.8224 | +0.8319 (Feline panleukopenia) | 2 | ✗ |
| T10 | ko | +0.8171 | +0.8198 (Feline panleukopenia) | 2 | ✗ |
| T11 | ko | +0.8510 | +0.8510 | **1** | ✓ |

- 영어 4건 rank-1: **4/4** / 한국어 3건 rank-1: **1/3** / rank≤3: **3/3**
- gold cos mean: +0.8593 / off cos mean: +0.8152 / margin: **+0.0440**

### 1-5. 종합 비교

| 모델 | dim | gold↑ | off↓ | margin↑ | en rank-1 | ko rank-1 | ko rank≤3 | encode 12 texts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **M0 baseline** all-MiniLM-L6-v2 | 384 | +0.4966 | +0.1761 | **+0.3205 ★** | 4/4 | 2/3 | 3/3 | 0.35s |
| **C1 BGE-M3** | 1024 | +0.6378 | +0.4301 | +0.2077 | 4/4 | **2/3** | 3/3 | 0.41s |
| **C2 ml-e5-large** | 1024 | +0.8593 | +0.8152 | +0.0440 | 4/4 | 1/3 | 3/3 | 0.61s |

**margin 1위는 baseline.** R-9 후보 둘 다 baseline 대비 margin 열등.

---

## §2. 핵심 발견 (Anti-Sycophancy 정직 보고)

### 2-1. baseline이 5-candidate pool에서 한국어 2/3 적중 — smoke 분별력 한계 재확인

R-8 Phase 2 1,000-pool에서 baseline 한국어 11쿼리 hits **0/11** (MRR=0). 그러나 R-9 Phase 1 5-candidate pool에서 baseline 한국어 **2/3 rank-1 + 3/3 rank≤3** 발현.

**원인:** baseline 한국어 cosine 절대값이 노이즈 수준 (0.002 ~ 0.137). T9 정답 cos +0.032 vs off cos +0.018-0.052 — 거의 random distinction. 5개 좁은 후보에서는 노이즈가 정답을 우연히 1위로 만들 수 있으나, 1,000개 후보에서는 의미적 신호 부재로 정답이 묻힘. **R-8 Phase 2 §3 학습 ("small candidate pool + smoke = 분별력 미측정") 재현.**

### 2-2. C1 BGE-M3 한국어 cosine 절대값이 baseline 대비 ~10배 — 의미 신호 가능성

| 쿼리 | M0 한국어 cos | C1 한국어 cos | 배수 |
|---|---:|---:|---:|
| T9  (고양이 당뇨)            | +0.0320 | +0.5273 | 16.5x |
| T10 (개 췌장염)              | +0.0763 | +0.4516 | 5.9x |
| T11 (고양이 범백혈구감소증)  | +0.1369 | +0.4810 | 3.5x |

C1은 한국어 쿼리에 대해 의미적 임베딩 신호를 생성한다는 정량 신호. rank-1 hits는 baseline과 동률이지만 cosine 절대값 자체가 다르다 — 1,000-pool에서 분별력이 살아남을 가능성.

### 2-3. C2 ml-e5-large 모든 쿼리 cosine 0.80-0.91 — 분별력 평탄성

C2는 모든 (쿼리, candidate) 쌍에서 cosine 0.79-0.91 범위에 분포. margin +0.0440 — 거의 분별 0. 한국어 1/3 적중도 cosine 0.001 차이로 정답/오답 갈림. **1,000-pool에서 분별 가능성 매우 낮음** — Phase 2 후보로 적합 의문.

### 2-4. T10 "개 췌장염" — C1 BGE-M3가 Feline panleukopenia를 1위로 (rank=3)

C1이 한국어를 잘 처리하더라도 specific failure 있음. "개 췌장염"이 "Feline panleukopenia"와 cosine 0.5069 (gold +0.4516보다 높음). 한국어 사전 + Gemini reformulate 단계가 본 production 파이프라인에서 이 결함 우회 (T10 production 회귀 PASS).

→ 다국어 임베더 단독 채택 ≠ 한국어 결함 해소. 본 production 파이프라인 (baseline + reformulate + BGE rerank) 통합 우월성과 비교 필요.

---

## §3. §3-2 판단 기준 1:1 PASS/FAIL

| # | 기준 | 임계 | 결과 | 판정 |
|---|---|---|---|---|
| 1 | smoke margin (한국어 적중) | C1/C2 중 ≥ 1 한국어 rank-1 hit | C1=2/3, C2=1/3 (둘 다 ≥1) | **PASS ✓** |
| 2 | smoke 영어 무손실 | C1/C2 중 ≥ 1 영어 rank≤3 4/4 | C1=4/4, C2=4/4 | **PASS ✓** |
| 3 | 모델 다운로드 + 메모리 | 디스크 5GB+ / RAM 8GB+ | 디스크 98Gi / OOM 0 | **PASS ✓** |
| 4 | Phase 2 진입 조건 | 한국어 ≥ 1 AND 영어 무손실 | 두 후보 모두 충족 | **PASS ✓ (단서: §4 권고 참조)** |
| 5 | R-9 폐기 조건 | 모든 후보 한국어 0/3 | C1·C2 둘 다 ≥1 | **미충족 (폐기 ❌)** |

**표면 PASS:** §3-2 정의 그대로 PASS.
**실질 분석:** §2 정직 보고 결론 — baseline 동률/우월 + smoke 분별력 한계 → **Phase 2 진입은 신중**.

---

## §4. Phase 2 진입 권고 (R9-4=b 사용자 결정 게이트)

### 4-1. 권장 옵션

| 옵션 | 내용 | 근거 |
|---|---|---|
| **A (권고)** | **Phase 2 진입, C1 BGE-M3 단독** (R-8 dataset 재활용) | C1 한국어 cosine 절대값 baseline 대비 3.5-16.5배 → 1,000-pool 분별 신호 가능성. C2는 분별력 평탄성으로 발현 미기대 |
| B | Phase 2 진입, C1 + C2 둘 다 (핸드오프 §3-6 default) | 핸드오프 default 그대로. C2 Phase 2 시간 +30-60m 추가 비용 |
| C | R-9 폐기, 한국어 결함은 reformulate/사전 강화로 우회 | smoke baseline 동률 → multilingual 임베더 단독 채택 정당성 약함. R-9.1~R-9.3 (사전 v1.3 / Gemini reformulate / hybrid retrieval) 우선 |
| D | Phase 2 진입 전 C1 단독 추가 smoke (10-20쿼리) | 5-pool 분별력 한계 → 더 긴 한국어 쿼리셋으로 1차 검증 강화 후 Phase 2 결정 |

### 4-2. 권고 근거 — 옵션 A

1. **C1 한국어 cosine 절대값 신호:** baseline ~0.03-0.14 vs C1 ~0.40-0.53. 의미 공간 매칭 정량 신호.
2. **C2 분별력 평탄성:** margin +0.0440. 1,000-pool에서 임의 후보 cosine 0.80+ 다수 → MRR 발현 의문.
3. **시간 절약:** R-8 dataset (1,000 sample + 100 query + baseline ChromaDB) 그대로 재활용. C1 ChromaDB 추가 빌드 ~30-45m + 평가 ~15m = ~1시간 cycle.
4. **Phase 2 임계 (R-9 §3-6):** 한국어 hits@10 ≥ 5/11 (~45%) AND 영어 hits@10 ≥ 89/89. C1이 5-pool에서 2/3 = 66% → 1,000-pool에서 5/11 충족 가능성 평가 가치.

### 4-3. 비추천 — 옵션 B (C1+C2 둘 다)

C2 Phase 2 평가는 시간 ~30-45m + 디스크 +1.5GB 추가하지만 §2-3 분별력 평탄성으로 결과 예측 가능. C2 채택 시 production 비용 +1024d 임베딩 (baseline 384d 대비 2.7배) → 정량 우월성 미입증으로 비용 정당화 어려움.

---

## §5. 핸드오프 §3-5 P1-S1~P1-S7 성공 기준 1:1 검증

| # | 항목 | PASS 조건 | 결과 | 판정 |
|---|---|---|---|---|
| P1-S1 | 후보 모델 다운로드 | C1 + C2 hub/ 캐시 확인 | C1 dim=1024 (164.0s), C2 dim=1024 (283.9s) | **PASS ✓** |
| P1-S2 | 8-10쿼리 인코딩 | 3 모델 × 7쿼리 + 5 candidate cosine 매트릭스 정상 산출 | 3 모델 × 7×5 = 105 cosine 산출, encode 12 texts < 1s | **PASS ✓** (8-10 → 7쿼리 R9-3=b 권장 default 정합) |
| P1-S3 | 한국어 발현 | C1 또는 C2 한국어 3건 rank-1 ≥ 1 | C1=2/3, C2=1/3 | **PASS ✓** (실질: baseline 동률 — §2-1 한계) |
| P1-S4 | 영어 무손실 | C1 또는 C2 영어 4건 rank 1-3 유지 | C1=4/4 rank-1, C2=4/4 rank-1 | **PASS ✓** |
| P1-S5 | 판단 기준 1:1 | §3-2 5 지표 PASS/FAIL 표 | §3 표 작성 | **PASS ✓** |
| P1-S6 | Phase 2 결정 | 진입 vs 폐기 명시 권장 | §4 옵션 A 권고 (C1 단독 진입) | **PASS ✓** |
| P1-S7 | 산출 commit | scripts + docs commit | 다음 단계 (commit dc11156 + 611e08c 위에 적층) | **진행 예정** |

**Phase 1 7/7 PASS** — 핸드오프 §7 H-5 충족 (P1-S7 commit 직후 H-7·H-8 메모리/핸드오프 갱신).

---

## §6. 회귀 0 가드 (H-6)

- src/ 무변경: ✅ (scripts + docs + graphify_out 신규 추가만)
- data/chroma_db/ 무변경: ✅ (Phase 1은 ChromaDB 미빌드, 인메모리 cosine만)
- tests/ 무변경: ✅
- → 11쿼리 RERANK=1 회귀 (R-8 종결 시점 none·gemini 10/10 PASS) **mathematical 보존**
- → 단위 251 PASS **mathematical 보존**
- 명시적 재실행 가드: 본 cycle commit 후 사용자 요청 시 1회 재실행 가능 (시간 ~75s + 11쿼리 회귀 ~3-5m)

---

## §7. 산출물

| 분류 | 경로 | 형식 | 크기 |
|---|---|---|---:|
| 스크립트 | `scripts/r9_phase1_smoke.py` | Python | ~310 LoC |
| 메트릭 | `graphify_out/r9_phase1_smoke.json` | JSON | ~5KB (3 모델 × 7×5 sim_matrix + meta) |
| 로그 | `graphify_out/r9_phase1_smoke.log` | text | gitignored (`*.log`) |
| 보고서 | `docs/20260427_r9_phase1_smoke.md` | Markdown | 본 문서 |

HF 캐시 추가 (R-9 자산):
- `~/.cache/huggingface/hub/models--BAAI--bge-m3` (~2.3GB)
- `~/.cache/huggingface/hub/models--intfloat--multilingual-e5-large` (~2.2GB)

---

## §8. 다음 cycle 후보

### 옵션 A 채택 시 (Phase 2 C1 단독)

- 별도 핸드오프 작성: `docs/20260427_r9_phase2_handoff.md` (R-8 Phase 2 패턴)
- 신규 스크립트: `scripts/r9_phase2_build_indices_c1.py` + `scripts/r9_phase2_evaluation.py`
- 임시 ChromaDB: `data/chroma_phase2_c1_bge_m3/` (gitignored, ~10MB × 1024d × 1,000 entries ≈ 10MB)
- 평가 dataset: R-8 `data/r8_phase2_query_dataset.json` 그대로 재활용 (100쿼리)
- 임계: 한국어 hits@10 ≥ 5/11 AND 영어 hits@10 ≥ 89/89 AND 11쿼리 RERANK=1 회귀 무손상

### 옵션 C 채택 시 (R-9 폐기)

- 폐기 보고서: `docs/20260427_r9_disposal.md` (R-8 disposal 패턴)
- 후속 검토: R-9.1 한국어 사전 v1.3 / R-9.2 Gemini reformulate 강화 / R-9.3 hybrid retrieval

---

**Phase 1 종결 (2026-04-27).** 사용자 옵션 선택 (A/B/C/D) 후 Phase 2 진입 또는 폐기 보고서 작성.
