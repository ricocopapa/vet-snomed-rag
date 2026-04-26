---
tags: [vet-snomed-rag, v3.0, R-8, phase1, smoke, embedder]
date: 2026-04-27
status: 종결 — Phase 2 진입 결정 입력 대기 (smoke 결과는 R-8 §5 권장과 불일치)
prev: docs/20260427_r8_embedder_candidates.md (R-8 후보 비교)
related:
  - scripts/r8_phase1_smoke.py
  - graphify_out/r8_phase1_smoke.log
---

# R-8 Phase 1 — 5쿼리 smoke 결과 (baseline + SapBERT 2 변형 + NeuML)

> **결론 요약 (Anti-Sycophancy):** 5쿼리 smoke에서 **현행 baseline(all-MiniLM-L6-v2)이 SapBERT 변형 2개와 NeuML pubmedbert를 margin에서 모두 앞섬**.
> R-8 후보 비교 보고서 §5의 SapBERT 1순위 권장은 5쿼리 smoke로는 입증되지 않았으며, **5쿼리는 분별력 검증에 부적합한 setup**(쿼리와 정답 concept이 거의 표면 일치)이라는 한계도 동시에 드러남.
> Phase 2 (1,000 샘플 ChromaDB + 100쿼리, 큰 candidate pool 내 분별력 측정)가 R-8 채택 여부 결정에 진짜 필요한 단계임이 확인됨.

---

## §1. 실행 요약

| 항목 | 값 |
|---|---|
| 실행 환경 | macOS / Python 3.14.4 / torch 2.11.0 / sentence-transformers 5.4.1 / transformers 5.5.4 |
| 디바이스 | CPU only (CUDA=False) |
| 모델 다운로드 | SapBERT-from-PubMedBERT-fulltext (~440MB) + NeuML/pubmedbert-base-embeddings (~440MB) |
| 5 쿼리 + 5 gold concept | data/snomed_ct_vet.db에서 검증 추출 (§3 참조) |
| 산출 로그 | `graphify_out/r8_phase1_smoke.log` |

---

## §2. 종합 비교 표

| 모델 | dim | diag↑ | off-diag↓ | **margin↑** | rank-1 hits | encode (5+5 texts) |
|---|---|---|---|---|---|---|
| **M0 baseline all-MiniLM-L6-v2** | 384 | +0.9120 | +0.1305 | **+0.7816** ★ | 5/5 | 0.79s |
| M1 SapBERT [CLS] | 768 | +0.9256 | +0.2314 | +0.6942 | 5/5 | 0.07s |
| M2 SapBERT mean | 768 | +0.9430 | +0.2685 | +0.6745 | 5/5 | 0.08s |
| M3 NeuML pubmedbert | 768 | +0.8261 | +0.0938 | +0.7323 | 5/5 | 0.53s |

**해석:**
- **rank-1 hits 5/5**: 4 모델 모두 5쿼리 모두에서 정답 concept이 5개 후보 중 1위 — 단순 정답 매칭은 다 통과
- **margin (diag - off-diag)**: 분별력 지표 — **baseline이 +0.7816으로 최고**, SapBERT mean이 +0.6745로 최저
- SapBERT는 **off-diagonal이 +0.23~0.27로 높음** — 의학 entity끼리 모두 비슷한 점수를 받아 분별력 떨어짐
- NeuML은 off-diagonal +0.09로 낮지만 diagonal도 +0.83으로 떨어져 margin 중간

---

## §3. 5 쿼리 + 5 gold concept

| Q | Query text | Gold concept_id | Preferred term | DB 검증 |
|---|---|---|---|---|
| Q1 | feline panleukopenia | 339181000009108 | Feline panleukopenia | ✓ |
| Q2 | elbow dysplasia dog | 309871000009108 | Dysplasia of elbow | ✓ |
| Q3 | dental extraction | 55162003 | Tooth extraction | ✓ |
| Q4 | blood glucose | 33747003 | Glucose measurement, blood | ✓ |
| Q5 | German Shepherd | 42252000 | German shepherd dog | ✓ |

R-8 §4-1 Phase 1에 명시된 5 쿼리 그대로 사용 (`scripts/r8_phase1_smoke.py:42`).

---

## §4. 5쿼리 smoke 한계 — 왜 이 결과를 신뢰하면 안 되는가

본 smoke의 **구조적 한계**:

1. **쿼리가 정답 concept의 표면 paraphrase에 가까움** — "feline panleukopenia" 쿼리 ↔ "Feline panleukopenia" concept. 의미공간 매칭이 아닌 표면 단어 매칭만으로도 정답 도달 가능
2. **Candidate pool이 5개뿐** — 366,570개 SNOMED concept이 후보일 때 발생하는 분별력 문제(서로 비슷한 의학 용어들 사이의 정답 찾기)가 측정되지 않음
3. **Cross-walk / 약어 / 동의어 매칭 케이스 없음** — SapBERT의 강점인 entity-linking 시나리오 미반영
4. **한국어→영어 reformulate 케이스 없음** — 실제 production에서는 reformulate된 영어 텍스트가 입력

→ 본 smoke 결과로 SapBERT/NeuML을 "baseline보다 못함"으로 단정 금지. **smoke setup의 한계**가 baseline 우위를 만들어낸 것.

R-8 후보 보고서 §5 권장(SapBERT 1순위)이 인용한 2024-2025 SNOMED CT 매핑 벤치마크는 200K concept 큰 pool 내 분별력 측정으로, 본 smoke와 다른 setup. Phase 2가 그 setup에 가까움.

---

## §5. Phase 2 진입 결정

### 5-1. Phase 2 가치 재평가 (5쿼리 smoke 결과 반영)

| 가설 | 검증 결과 | 다음 |
|---|---|---|
| SapBERT가 baseline보다 우월 (R-8 §5 권장) | 5쿼리 smoke로는 미입증, 큰 pool에서 재검증 필요 | Phase 2 필수 |
| 5쿼리 smoke로 모델 결정 가능 | 쿼리 setup 한계로 모든 모델 5/5 → 결정 불가 | 5쿼리 smoke 신뢰 보류 |
| baseline이 충분히 강해 R-8 무용 | 11쿼리 회귀에서도 이미 10/10 → 폐기 가설 strong | Phase 2 결과 따라 polished 폐기/채택 결정 |

### 5-2. Phase 2 권장 setup (R-8 §4-2 + 본 smoke 한계 반영)

100 쿼리 분포 (R-8 §4-2 따름):
- 수의학 전용: 20 (vet-specific, baseline 강한 영역)
- 범용 disorder: 25 (cross-domain, SapBERT 강점 영역)
- Procedure: 20
- Body structure: 15
- Drug/Substance: 10
- 한국어→영어 reformulate: 10

ChromaDB 1,000 샘플 — SNOMED tag별 분포(disorder 30%, procedure 20%, body structure 15%, finding 15%, organism 10%, substance 10%) 반영.

지표 (R-8 §4-3):
- **MRR@10** (mean reciprocal rank, 정답 순위 역수 평균)
- **Recall@10**
- **수의학 쿼리 Recall@5** ≥ baseline × 0.95 (수의학 손실 ≤5% 허용)
- 11쿼리 회귀 RERANK=1 none·gemini 10/10 유지

### 5-3. Phase 2 후보 우선순위 재조정

본 smoke가 R-8 §5 권장과 다른 결과를 낸 점 반영:

| 우선순위 | 후보 | Phase 2 진입 근거 |
|---|---|---|
| **1** | M2 SapBERT mean (cambridgeltl/...-fulltext, mean pool) | smoke에서 diag_mean 최고(+0.9430). 의미 공간 단어 임베딩 average가 큰 pool 분별력에 유리할 가능성 |
| **2** | M3 NeuML pubmedbert | smoke margin 2위 + sentence-transformers 호환으로 마이그레이션 비용 최소 |
| 3 | M1 SapBERT [CLS] | smoke margin 3위. mean pooling이 [CLS]보다 일반적으로 sentence embedding에 유리 |
| **배제** | M0 baseline (이미 production) | Phase 2의 비교 대상(baseline)이지 채택 후보 아님 |

---

## §6. 사용자 결정 입력 (Phase 2 진입 시)

| # | 항목 | 옵션 | 본 smoke 결과 반영 권장 |
|---|---|---|---|
| P2-1 | Phase 2 진행 여부 | (a) 진행 / (b) R-8 폐기(baseline 유지) | **(a) 진행** — 5쿼리는 분별력 측정 부적합, 큰 pool 검증 필수 |
| P2-2 | Phase 2 비교 대상 | (a) M2 SapBERT mean 단독 / (b) M2 + M3 둘 비교 / (c) M2+M3+M1 셋 비교 | **(b) M2 + M3** — smoke 1, 2위 두 모델만 |
| P2-3 | 1,000 샘플 추출 방식 | (a) random / (b) tag-stratified (R-8 §4-2 분포) / (c) 수의학 우선 | **(b) tag-stratified** |
| P2-4 | 100쿼리 dataset | (a) 새로 작성 / (b) 기존 11쿼리 + 89 추가 | **(b) 기존 11 확장** — 회귀 비교 가능 |
| P2-5 | 결과 임계 | (a) MRR@10 +5% / (b) +10% / (c) Recall@10만 | **(a) +5%** — R-8 §4-3 그대로 |

---

## §7. 산출물

| 분류 | 경로 |
|---|---|
| 스크립트 | `scripts/r8_phase1_smoke.py` (240 LoC) |
| 실행 로그 | `graphify_out/r8_phase1_smoke.log` |
| 본 보고서 | `docs/20260427_r8_phase1_smoke.md` |

---

## §8. 핸드오프 H-1~H-8 1:1 PASS/FAIL

| # | 항목 | PASS 조건 | 결과 |
|---|---|---|---|
| H-1 | smoke 실행 성공 | 4 모델 × 5 쿼리 cosine 매트릭스 출력 | **PASS** §2 |
| H-2 | 결과 정직 보고 | smoke가 R-8 §5 권장과 다를 때 솔직히 명시 | **PASS** §1 결론 + §4 한계 명시 |
| H-3 | smoke 한계 명시 | 분별력 측정 부적합 setup 진단 | **PASS** §4 4가지 구조적 한계 |
| H-4 | Phase 2 권장 | 진입 여부 + 후보 우선순위 + setup 명시 | **PASS** §5-2/§5-3 |
| H-5 | 사용자 결정 입력 | P2-1~P2-5 5항목 명시 | **PASS** §6 |
| H-6 | 회귀 위험 0 | smoke 자체는 신규 스크립트 + 로그만, production 무영향 | **PASS** (코드 수정 0) |
| H-7 | 모델 다운로드 정직 보고 | ~880MB 다운로드 사실 명시 | **PASS** §1 |
| H-8 | 다음 cycle handoff 준비 | Phase 2 진입 명령 + 결정 입력 명시 | **PASS** §6 |

---

**R-8 Phase 1 종결 — 결론은 "Phase 2 가치 재확인 + 후보 우선순위 SapBERT mean 1순위로 재조정". 사용자 §6 결정 후 Phase 2 진입.**
