---
tags: [vet-snomed-rag, v3.0, R-8, phase2, evaluation, disposal]
date: 2026-04-27
status: R-8 폐기 결정 (Phase 2 §3-2 disjunction 충족)
prev_state: R-8 Phase 2 핸드오프 (commit cafbc9a)
next_target: R-8 종결 + R-9 한국어 임베더 후보 검토 또는 budget_guard 영속화
related:
  - docs/20260427_r8_phase2_handoff.md
  - docs/20260427_r8_phase1_smoke.md
  - docs/20260427_r8_embedder_candidates.md
  - graphify_out/r8_phase2_metrics.json
  - graphify_out/r8_phase2_build_summary.json
  - graphify_out/regression_metrics_rerank.json
  - data/r8_phase2_query_dataset.json
  - data/r8_phase2_sample_concepts.json
---

# R-8 Phase 2 평가 보고서 — 1,000 샘플 + 100쿼리 결과 + R-8 폐기 결정

## §0. 결론 요약

| 판단 | 결과 |
|---|---|
| §3-2 4 지표 conjunction | **M2/M3 모두 FAIL** (MRR@10 ≥ baseline×1.05 미달) |
| §3-2 R-8 폐기 disjunction | **충족** (MRR +5% 미달) |
| 11쿼리 RERANK=1 회귀 | none **10/10** · gemini **10/10** (본체 무손상) |
| 권고 | **R-8 폐기**. baseline `all-MiniLM-L6-v2` 유지. v3.0 종결 선언. |
| 후속 R&D 후보 | 한국어 11쿼리 3 모델 모두 0% 적중 → 다국어 임베더(BGE-M3, multilingual-e5) 별도 검토 |

---

## §1. 1,000 샘플 + 100쿼리 분포 검증 (P2-S1·P2-S2)

### 1-1. 1,000 샘플 (Gold-Forced Inclusion 재설계)

핸드오프 §3-3 Step 1 원안(`ORDER BY RANDOM()`)은 setup 결함을 내포함이 실증으로 확인되어 **옵션 A**(Gold-Forced Inclusion)로 재설계됨. 구체적으로 random 1,000 샘플 안에 T1-T11 gold concept 11건 중 적중 0/11. 100쿼리 평가 시 모든 모델이 N/A로 수렴.

해결: 100쿼리 unique gold 96 concept을 1,000 샘플에 강제 포함 + 904 tag-stratified random 보충.

| semantic_tag | target | gold | random+ | actual |
|---|---:|---:|---:|---:|
| disorder | 300 | 44 | 256 | 300 ✓ |
| procedure | 200 | 20 | 180 | 200 ✓ |
| body structure | 150 | 15 | 135 | 150 ✓ |
| finding | 150 | 2 | 148 | 150 ✓ |
| organism | 100 | 5 | 95 | 100 ✓ |
| substance | 100 | 10 | 90 | 100 ✓ |
| **합계** | **1,000** | **96** | **904** | **1,000** ✓ |

- 재현성: `random.seed(20260427)` 결정론적 `random.sample` 사용
- 산출: `data/r8_phase2_sample_concepts.json` (commit `4ae55f7`)
- vet-specific 비율: 2.30% (production 366,570 약 3.57% 대비 -1.27pp; 평가 영향 미미 — 가드는 §3-2 Vet Recall@5)

### 1-2. 100쿼리 dataset

| 카테고리 | 수 | 출처 |
|---|---:|---|
| vet-specific | 22 | T1·T2·T6·T7 + T3·T4 (vet-context) + 16 신규 |
| general-disorder | 22 | T5·T8 + 20 신규 |
| procedure | 20 | 20 신규 |
| body-structure | 15 | 15 신규 |
| drug | 10 | 10 신규 (substance) |
| korean-reformulate | 11 | T9·T10·T11 + 8 신규 |
| **합계** | **100** | 96 unique gold |

핸드오프 §3-1 분포(vet 20 / disorder 25 / proc 20 / body 15 / drug 10 / korean 10)와 미세 편차. 카테고리별 metric 분리 평가로 영향 격리.

- 산출: `data/r8_phase2_query_dataset.json` (commit `4ae55f7`)
- gold concept SQL 검증: **100/100 PASS** (96 unique, 4 중복: T1·T11 / T3·T7·T9 / T4·T10)
- T5 gold 신규 부여: `709044004 Chronic kidney disease` (regression_metrics.json에 None이었음)

---

## §2. MRR@10 / Recall@10 비교 (P2-S4)

### 2-1. 100쿼리 Overall

| 모델 | dim | MRR@10 | Recall@10 | Recall@5 | hits@10 |
|---|---:|---:|---:|---:|---:|
| **M0 baseline** all-MiniLM-L6-v2 | 384 | **0.8850** | 0.8900 | 0.8900 | 89/100 |
| M2 SapBERT mean | 768 | 0.8820 (Δ−0.34%) | 0.8900 | 0.8900 | 89/100 |
| M3 NeuML pubmedbert | 768 | 0.8767 (Δ−0.94%) | 0.8900 | 0.8800 | 89/100 |

세 모델 모두 hits@10 = 89/100. 11건 미적중 = 한국어 11건 + ε. 영어 89건은 세 모델 모두 100% 적중.

### 2-2. Per-language 분리

| 언어 | n | M0 MRR@10 | M2 MRR@10 | M3 MRR@10 |
|---|---:|---:|---:|---:|
| en | 89 | **0.9944** | 0.9910 | 0.9850 |
| ko | 11 | **0.0000** | 0.0000 | 0.0000 |

영어 한정: 세 모델 모두 거의 perfect. 영어 차이만으로 보면 baseline이 +0.34%/+0.94% 우월하나 절대 차이 < 1pp. 한국어: 세 모델 모두 0%.

### 2-3. Per-category Recall@10

| 카테고리 | n | M0 | M2 | M3 |
|---|---:|---:|---:|---:|
| body-structure | 15 | 1.0000 | 1.0000 | 1.0000 |
| drug | 10 | 1.0000 | 1.0000 | 1.0000 |
| general-disorder | 22 | 1.0000 | 1.0000 | 1.0000 |
| procedure | 20 | 1.0000 | 1.0000 | 1.0000 |
| vet-specific | 22 | 1.0000 | 1.0000 | 1.0000 |
| **korean-reformulate** | 11 | **0.0000** | **0.0000** | **0.0000** |

영어 5 카테고리: 3 모델 모두 100%. 한국어: 3 모델 모두 0%.

---

## §3. 수의학 쿼리 손실 측정 (§3-2 vet 가드)

| 모델 | vet-specific (n=22) Recall@5 | baseline 대비 |
|---|---:|---|
| M0 baseline | 1.0000 | (기준) |
| M2 SapBERT mean | 1.0000 | 동일 |
| M3 NeuML pubmedbert | 0.9545 | −4.55% (임계 0.95 간신히 통과) |

§3-2 임계값 `vet_recall@5 ≥ baseline × 0.95 = 0.9500`:
- M2: 1.0000 ≥ 0.9500 ✓
- M3: 0.9545 ≥ 0.9500 ✓ (마진 +0.0045)

수의학 손실 가드는 두 후보 모두 PASS. **vet 손실은 R-8 폐기의 사유가 아님.**

---

## §4. 11쿼리 RERANK=1 회귀 (P2-S6)

### 4-1. 본체 무손상 (production ChromaDB 366,570)

`scripts/run_regression.py` RERANK=1 실행 (gemini cached 사용):

| backend | PASS | NA | 비고 |
|---|---:|---:|---|
| none | **10/10** | 1 | T5 gold None — NA 제외 |
| gemini | **10/10** | 1 | 동일 |

산출: `graphify_out/regression_metrics_rerank.json` (gitignored, 단 cached 결과는 `graphify_out/regression_metrics.json`)

§3-2 4 지표 중 **회귀 PASS** ✓. 본체 src/ 무변경(scripts/data만 추가)이므로 자명.

### 4-2. T1-T11 × 3 모델 매트릭스 (1,000-pool top-10)

| qid | category | M0 (1k) | M2 (1k) | M3 (1k) | query |
|---|---|---:|---:|---:|---|
| T1 | vet-specific | 1 | 1 | 1 | feline panleukopenia SNOMED code |
| T2 | vet-specific | 1 | 1 | 1 | canine parvovirus enteritis |
| T3 | vet-specific | 1 | 1 | 2 | diabetes mellitus in cat |
| T4 | vet-specific | 1 | 1 | 1 | pancreatitis in dog |
| T5 | general-disorder | 1 | 1 | 1 | chronic kidney disease in cat |
| T6 | vet-specific | 1 | 1 | 1 | cat bite wound |
| T7 | vet-specific | **2** | **5** | **6** | feline diabetes |
| T8 | general-disorder | 1 | 1 | 1 | diabetes mellitus type 1 |
| T9 | korean-reformulate | >10 | >10 | >10 | 고양이 당뇨 |
| T10 | korean-reformulate | >10 | >10 | >10 | 개 췌장염 |
| T11 | korean-reformulate | >10 | >10 | >10 | 고양이 범백혈구감소증 SNOMED 코드 |

핵심:
- T1-T8 영어 8건: 거의 전부 rank 1 (M3가 T3에서 1단계 열세)
- **T7 "feline diabetes"**: baseline rank 2 / M2 rank 5 / M3 rank 6 — baseline 우위 가장 큰 사례
- T9-T11 한국어 3건: 3 모델 모두 >10 — 영문 임베더 공통 한계

T7은 production ChromaDB(366,570)에서는 rank 1을 회복(graphify_out/regression_metrics.json reformulated→"diabetes mellitus" PASS)하지만, 1,000-pool에서는 후보 부족으로 rank 변동. baseline의 분포 강건성이 우월.

---

## §5. §3-2 판단 기준 1:1 PASS/FAIL

| 지표 | 임계값 | M2 SapBERT mean | M3 NeuML | 결과 |
|---|---|---|---|---|
| MRR@10 | ≥ baseline × 1.05 = 0.9293 | 0.8820 | 0.8767 | **둘 다 FAIL** |
| Recall@10 | ≥ baseline = 0.8900 | 0.8900 ✓ | 0.8900 ✓ | 둘 다 PASS |
| vet Recall@5 | ≥ baseline × 0.95 = 0.9500 | 1.0000 ✓ | 0.9545 ✓ | 둘 다 PASS |
| 11쿼리 회귀 | none·gemini 모두 10/10 | 10/10 ✓ | 10/10 ✓ | PASS (본체 무손상) |
| **conjunction (Phase 3 진입)** | 4 지표 모두 PASS | **FAIL** | **FAIL** | Phase 3 부적합 |
| **disjunction (R-8 폐기)** | MRR +5% 미달 OR vet 손실 >5% | MRR FAIL | MRR FAIL | **R-8 폐기 조건 충족** |

---

## §6. Phase 3 진입 결정 → **R-8 폐기**

### 6-1. 결정

**R-8 폐기.** baseline `sentence-transformers/all-MiniLM-L6-v2` 유지. v3.0 R-8 (도메인 특화 임베더 후보 검증) 종결 선언.

### 6-2. 결정 근거

1. **MRR@10 임계 미달.** M2 0.882 / M3 0.877 모두 0.929 임계 미달. 차이는 -5pp 이상.
2. **분포 강건성 baseline 우위.** T7 "feline diabetes" 1,000-pool rank 2(M0) vs 5(M2)/6(M3). baseline이 후보 부족 환경에서 분별력 가장 좋음.
3. **alpha transfer 가설 reject.** SapBERT의 UMLS entity-linking 강점이 본 setup(짧은 영어 쿼리, preferred_term 표면 일치 다수)에서 미발현. NeuML PubMedBERT도 동일 패턴.
4. **production setup 우월성 부산물.** baseline + Gemini reformulate + BGE rerank 조합이 11쿼리 RERANK=1에서 10/10 PASS. 임베더 단일 교체로 얻을 이득 < 본체 RAG 파이프라인의 통합 분별력.

### 6-3. 본 실험이 측정하지 못한 것 (한계)

| 한계 | 함의 |
|---|---|
| 1,000-pool 제한 | production 366,570 분포 분별력 직접 측정 불가. 추정만. |
| 영어 쿼리 89%가 preferred_term 자체 변형 | cross-walk(약어, 동의어)·불완전 spelling·intent reformulate 케이스 < 5%. SapBERT entity-linking 강점 발현 환경 부재. |
| 한국어 11쿼리 3 모델 모두 0% | 영문 임베더의 한계 노출 — 별도 다국어 후보 필요. |
| MRR ×1.05 임계가 너무 빡셈 | baseline 0.885 → 0.929 목표는 rank 평균 1.077로 거의 perfect 요구. 임계 자체가 보수적이었음. |

**해석:** 본 결과는 "baseline이 절대 우월" 보다는 "본 setup에서 후보 모델의 도메인 강점 발현 기회가 부재"에 가깝다. R-8 폐기는 setup 한계와 결합한 결정이며, 도메인 특화 임베더 자체의 reject를 의미하지 않는다.

---

## §7. 본 실험 산출 인덱스

| 분류 | 경로 | commit | 내용 |
|---|---|---|---|
| 스크립트 | `scripts/r8_phase2_sample_extract.py` | 4ae55f7 | Gold-Forced Inclusion sample 추출 |
| 스크립트 | `scripts/r8_phase2_query_dataset.py` | 4ae55f7 | 100쿼리 dataset 생성 |
| 스크립트 | `scripts/r8_phase2_build_indices.py` | 53ae57a | 3 모델 × 1,000 임시 ChromaDB 빌드 |
| 스크립트 | `scripts/r8_phase2_evaluation.py` | 53ae57a | 100쿼리 × 3 setup 평가 |
| 데이터 | `data/r8_phase2_sample_concepts.json` | 4ae55f7 | 1,000 sample (96 gold + 904 random) |
| 데이터 | `data/r8_phase2_query_dataset.json` | 4ae55f7 | 100쿼리 (96 unique gold) |
| 임시 인덱스 | `data/chroma_phase2_{baseline,sapbert_mean,neuml}/` | (gitignored) | 22.5 MB 합계, 수동 정리 시점 사용자 결정 |
| 메트릭 | `graphify_out/r8_phase2_build_summary.json` | 53ae57a | 빌드 메타 (29.6s 합) |
| 메트릭 | `graphify_out/r8_phase2_metrics.json` | 53ae57a | per-query + per-category + per-language + decision |
| 회귀 | `graphify_out/regression_metrics_rerank.json` | (gitignored) | 11쿼리 × {none, gemini} RERANK=1 10/10·10/10 |
| 보고서 | `docs/20260427_r8_phase2_evaluation.md` | (본 문서) | Phase 2 평가 + R-8 폐기 결정 |

---

## §8. 후속 R&D 후보 (Phase 2 부산물)

### 8-1. R-9 (가칭) — 다국어 임베더 검증

본 실험에서 **한국어 reformulate 11쿼리 3 모델 모두 0% 적중**으로 노출된 영문 임베더 한계.

후보:
| 후보 | dim | 강점 | 비용 (CPU) |
|---|---:|---|---|
| BAAI/bge-m3 | 1024 | dense+sparse+colbert hybrid, 100+ languages, 멀티 retrieval mode | 중 |
| intfloat/multilingual-e5-large | 1024 | 100+ languages, 임베딩 품질 우수 | 중 |
| sentence-transformers/paraphrase-multilingual-mpnet-base-v2 | 768 | 50+ languages, 균형형 | 낮음 |

검증 setup (Phase 2 학습 반영):
- Gold-Forced Inclusion 그대로 (1,000 sample = 96 unique gold + 904 random)
- 100쿼리 그대로 (영어 89 + 한국어 11)
- 한국어 11쿼리 hits@10 비교를 1차 지표로
- 영어 89쿼리는 무손실 보장만 (≥ baseline)

이는 별도 R-9 핸드오프로 분리 권장.

### 8-2. budget_guard 영속화

핸드오프 §2 우선순위 ★★. R-8과 무관, 별도 cycle 30-60m. v3.0 종결 후 진행 가능.

### 8-3. Reformulate 강화 (한국어 ↔ 영어)

본 production 파이프라인의 Gemini reformulate 단계가 한국어 입력을 영어로 변환. 본체 11쿼리 RERANK=1 회귀 10/10은 reformulate 효과가 작동 중임을 시사. R-9 다국어 임베더 검토 시 비교 대상으로 "current production (영문 임베더 + Gemini reformulate)" vs "다국어 임베더 (reformulate 없이)" 셋업 필요.

---

## §9. 핸드오프 §3-5 P2-S + §7 H 1:1 PASS/FAIL

### 9-1. §3-5 P2-S (Phase 2 작업 성공)

| # | 항목 | 결과 | 근거 |
|---|---|---|---|
| P2-S1 | 1,000 샘플 추출 + 분포 + sanity | ✓ PASS | §1-1 표 + 6 tag actual=target |
| P2-S2 | 100쿼리 dataset + gold SQL | ✓ PASS | §1-2 + 100/100 SQL hit |
| P2-S3 | 임시 ChromaDB 빌드 | ✓ PASS | 3 모델 × 1,000 entries × dim 검증 |
| P2-S4 | MRR@10 측정 | ✓ PASS | §2-1 표 |
| P2-S5 | §3-2 1:1 PASS/FAIL | ✓ PASS | §5 표 (M2/M3 둘 다 conjunction FAIL 산출) |
| P2-S6 | 11쿼리 회귀 무손상 | ✓ PASS | §4-1 (none 10/10, gemini 10/10) |
| P2-S7 | Phase 3 결정 | ✓ PASS | §6-1 R-8 폐기 권고 |
| P2-S8 | 산출물 commit | ✓ PASS | commit 4ae55f7 + 53ae57a (본 보고서 commit 예정) |

### 9-2. §7 H (핸드오프 자체 성공)

| # | 항목 | 결과 |
|---|---|---|
| H-1 | 현 상태 검증 | ✓ git clean / 251 PASS / becdd45 / SapBERT+NeuML+MiniLM 캐시 / 11쿼리 metrics 존재 |
| H-2 | 사용자 P2-1~P2-6 선택 | ✓ 권장 default 채택 (a)/(b)/(b)/(b)/(a)/(c) |
| H-3 | §3 Task Definition 사용자 승인 | ✓ "권장 사항으로 진행해줘" 응답 |
| H-4 | 사용자 사전 액션 | ✓ 디스크 96Gi 여유 자동 검증 |
| H-5 | §3-5 P2-S1~P2-S8 1:1 PASS | ✓ §9-1 표 (8/8 PASS) |
| H-6 | 회귀 0 보장 | ✓ 단위 251 + 11쿼리 RERANK 10/10·10/10 |
| H-7 | 메모리 갱신 | ✓ memory/project_vet_snomed_rag.md 업데이트 (commit 예정) |
| H-8 | 다음 핸드오프 또는 종결 | ✓ R-8 폐기 종결 + R-9 후보 §8-1 명시 |

---

**보고서 작성 완료 (2026-04-27).** R-8 폐기 결정으로 v3.0 1차 종결 가능. 후속 cycle은 사용자 결정.
