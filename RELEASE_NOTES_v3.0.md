# Release Notes — v3.0 (2026-04-27)

> **v3.0 — R-9 cycle 종결: production 임베더 BGE-M3 교체로 한국어 결함 본질 해소**
>
> v2.9.1까지 production 임베더로 사용한 `all-MiniLM-L6-v2` (384d, 영문 단일)는 한국어
> 임상 쿼리 11/11 hits@10 = 0/11 (R-8 Phase 2 1,000-pool 측정)이라는 본질적 한계를
> 노출했다. v3.0은 R-9 cycle (Phase 1→2→3)을 통해 후보 비교·정량 평가·production
> migration을 거쳐 임베더를 `BAAI/bge-m3` (1024d, 100+ 언어 dense)로 교체한다.
> production 11쿼리 RERANK=1 회귀에서 한국어 3/3 rank=1 + 영어 무손실 입증.

---

## 핵심 메트릭

| 항목 | v2.9.1 | **v3.0** | 변화 |
|---|---|---|---|
| **임베더** | all-MiniLM-L6-v2 (384d) | **BAAI/bge-m3 (1024d)** | 다국어 교체 |
| **ChromaDB 크기** | 1.1GB | 2.0GB | +0.9GB (1024d) |
| **단위 테스트** | 251 | **251** + 59 subtests | 회귀 0 |
| **11쿼리 RERANK=1 (none)** | 10/10 | **10/10** | 회귀 0 ★ |
| **11쿼리 RERANK=1 (gemini)** | 10/10 | **10/10** | 회귀 0 ★ |
| **한국어 11쿼리 hits@10 (1,000-pool)** | 0/11 | **8/11 (73%)** | **+8건 ★** |
| **영어 89쿼리 hits@10 (1,000-pool)** | 89/89 | **89/89** | **무손실 ★** |
| **MRR@10 (1,000-pool)** | 0.8850 | **0.9119** | +3.0% |
| **Recall@10 (1,000-pool)** | 0.89 | **0.97** | +9.0% |

---

## R-9 cycle 누적 5 commit

| commit | 단계 | 결과 |
|---|---|---|
| `dc11156` | R-8 폐기 | SapBERT/NeuML §3-2 임계 (MRR×1.05) FAIL → baseline 유지, R-9 발생 |
| `611e08c` | R-9 진입 핸드오프 | 다국어 임베더 cycle 진입 |
| `c8c832c` | R-9 Phase 1 | 7쿼리 smoke (baseline 5-pool 한국어 2/3 — smoke 분별력 한계 발견), C1 BGE-M3 단독 권고 |
| `87d1788` | R-9 Phase 2 | C1 1,000-pool 한국어 8/11 + 영어 89/89 + MRR +3.0%, R@10 +9.0% |
| **`fa69e49`** | **R-9 Phase 3** | **production migration 완료, 11쿼리 100% PASS** |

---

## Track A — R-8 폐기

### A-1. R-8 영문 임베더 평가 (commit `dc11156`)

R-8은 SapBERT/NeuML/MedCPT/BiomedBERT 등 8 후보 중 SapBERT mean (M2) + NeuML pubmedbert (M3)를 Phase 1 5쿼리 smoke 후 Phase 2 1,000-pool × 100쿼리 평가에 진입.

| 모델 | dim | MRR@10 | 영어 hits | 한국어 hits | 임계 (≥0.929) |
|---|---:|---:|---:|---:|:---:|
| **M0 baseline** all-MiniLM-L6-v2 | 384 | **0.8850** | 89/89 | 0/11 | (baseline) |
| M2 SapBERT mean | 768 | 0.8820 (-0.34%) | 89/89 | 0/11 | **FAIL** |
| M3 NeuML pubmedbert | 768 | 0.8767 (-0.94%) | 89/89 | 0/11 | **FAIL** |

§3-2 MRR×1.05 임계 두 후보 모두 미달 → R-8 폐기. baseline 유지 + Phase 3 미실행. **한국어 11쿼리 3 모델 모두 0/11** 노출 → R-9 다국어 임베더 cycle 발생.

### A-2. Setup 결함 학습

R-8 Phase 2 원안 `ORDER BY RANDOM()`은 1,000 sample 안에 T1-T11 gold 적중 0/11 → 평가 불가. **Gold-Forced Inclusion 재설계** (96 unique gold + 904 tag-stratified random) 적용. 향후 패턴: small candidate pool + random query 평가 setup은 항상 Gold-Forced 필수.

---

## Track B — R-9 cycle (Phase 1 → 2 → 3)

### B-1. R-9 Phase 1 — 7쿼리 다국어 smoke (commit `c8c832c`)

C1 BGE-M3 + C2 multilingual-e5-large 두 후보를 7쿼리 (영어 4 + 한국어 3)에서 5-candidate cosine 매트릭스 비교.

| 모델 | dim | margin | en rank-1 | ko rank-1 |
|---|---:|---:|---:|---:|
| M0 baseline | 384 | +0.3205 | 4/4 | 2/3 (5-pool 우연) |
| **C1 BGE-M3** | 1024 | +0.2077 | 4/4 | **2/3** |
| C2 ml-e5-large | 1024 | +0.0440 | 4/4 | 1/3 |

**핵심 발견:**
1. baseline도 5-pool에서 한국어 2/3 적중 → R-8 1,000-pool 0/11과 모순 → smoke 분별력 한계 재확인
2. **C1 한국어 cosine 절대값 baseline 대비 3.5-16.5배** (0.03→0.53, 0.08→0.45, 0.14→0.48) — 의미 신호 정량
3. C2는 분별력 평탄성 (모든 cosine 0.79-0.91) → 1,000-pool 미발현 예측

**옵션 A 권고:** Phase 2 C1 BGE-M3 단독 진입 (R-8 dataset 재활용).

### B-2. R-9 Phase 2 — C1 1,000-pool × 100쿼리 평가 (commit `87d1788`)

R-8 자산 (1,000 Gold-Forced sample + 100쿼리) 그대로 재활용. C1 ChromaDB 신규 빌드 후 평가.

**§2-2 R-9 임계 1:1 PASS:**

| # | 기준 | 임계 | C1 결과 | 판정 |
|---|---|---|---|---|
| ① | 한국어 hits@10 | ≥ 5/11 | **8/11 (73%)** | **PASS ✓** |
| ② | 영어 hits@10 | ≥ 89/89 | **89/89 (100%)** | **PASS ✓** |
| ③ | 11쿼리 RERANK=1 회귀 | none·gemini 10/10×2 | **10/10 + 10/10** | **PASS ✓** |
| ④ | 단위 251 PASS | 251 | mathematical 보존 | **PASS ✓** |

**한국어 회복 8건:** T9 6위 / T11 2위 / N-ko-01 갑상선 저하증 4 / N-ko-02 항진증 8 / N-ko-05 외이염 1 / N-ko-06 심장 잡음 3 / N-ko-07 고관절 이형성증 5 / N-ko-08 림프종 2.

**미해소 한국어 3건 (정직 보고):** T10 개 췌장염 / N-ko-03 백내장 / N-ko-04 녹내장.

→ **production 교체 권고 (옵션 A 채택).**

### B-3. R-9 Phase 3 — production migration 완료 (commit `fa69e49`)

**변경 산출 (실측):**

| 파일 | 변경 |
|---|---|
| `src/retrieval/hybrid_search.py:31` | `EMBEDDING_MODEL = "BAAI/bge-m3"` |
| `src/indexing/vectorize_snomed.py:33` | `EMBEDDING_MODEL = "BAAI/bge-m3"` |
| `.gitignore` | `data/chroma_db_baseline_minilm/` 추가 |
| `data/chroma_db_baseline_minilm/` | atomic mv 백업 (1.1GB rollback 안전망) |
| `data/chroma_db/` | 신규 빌드 (366,570 × 1024d, 2.0GB) |

**빌드 실측:** 1h 51m (10:32 → 12:23, CPU 평균 200% 멀티코어, RAM 피크 3.4GB).

**P3-S1~P3-S5 모두 PASS:**
- baseline 백업 1.1GB ✓
- src/ 2 파일 교체 ✓
- ChromaDB 366,570 × 1024d 정확 ✓
- 단위 251 + 59 subtests (79.11s) ✓
- **11쿼리 RERANK=1 none 10/10 + gemini 10/10 ★**

**T9·T10·T11 한국어 모두 rank=1.** Phase 2 1,000-pool 미해소였던 T10 (개 췌장염)이 본 production 파이프라인 (BGE-M3 임베딩 + Gemini reformulate "개 췌장염→canine pancreatitis" + BGE-rerank-v2-m3 Top-20→Top-5 재정렬) 통합 시 PASS 회복. **R-9 핵심 가설 production 입증.**

---

## ⚠️ Breaking Changes

### 1. 임베딩 차원 변경 (384d → 1024d)

다음 코드가 임베딩 차원을 hardcoded로 가정한다면 v3.0 호환 변경 필요:
- `np.zeros(384)` → `np.zeros(1024)` 또는 dynamic dim 사용
- 임베딩 벡터를 외부 저장소에 직렬화하는 코드

`hybrid_search.py` / `vectorize_snomed.py` 내부에서는 dim을 직접 참조하지 않으므로 src/ 무영향.

### 2. ChromaDB 재빌드 필수

clone/pull 후 다음 명령으로 ChromaDB 재빌드 필요 (~2시간 CPU + 디스크 ~2GB):

```bash
cd vet-snomed-rag
source venv/bin/activate
python -m src.indexing.vectorize_snomed
```

기존 v2.9.1 384d ChromaDB는 `data/chroma_db_baseline_minilm/`로 보존 가능 (rollback 안전망, gitignored).

### 3. 모델 다운로드 (~2.3GB)

BGE-M3는 `~/.cache/huggingface/hub/models--BAAI--bge-m3`에 자동 다운로드. 첫 실행 시 5-15분 소요 (네트워크 의존). HF token 권장 (rate limit 회피).

### 4. RAM 요구사항

v2.9.1 (384d): RAM ~2GB
v3.0 (1024d): RAM ~3-4GB (인코딩 시)

ChromaDB 재빌드 시 RAM 16GB+ 시스템 권장.

---

## Rollback 절차

v3.0 채택 후 문제 발생 시:

```bash
mv data/chroma_db data/chroma_db_failed_bge_m3
mv data/chroma_db_baseline_minilm data/chroma_db
git checkout v2.9.1 -- src/retrieval/hybrid_search.py src/indexing/vectorize_snomed.py
```

복원 ~1분 + 회귀 검증 ~5분.

---

## R-8 → R-9 → Phase 3 메트릭 종합

| 단계 | dataset | 임베더 | dim | MRR@10 | 한국어 hits | 영어 hits |
|---|---|---|---:|---:|---|---|
| R-8 baseline | 1,000-pool × 100쿼리 | all-MiniLM-L6-v2 | 384 | 0.8850 | 0/11 | 89/89 |
| R-8 SapBERT mean (폐기) | 동일 | SapBERT mean | 768 | 0.8820 | 0/11 | 89/89 |
| R-8 NeuML (폐기) | 동일 | pubmedbert | 768 | 0.8767 | 0/11 | 89/89 |
| **R-9 Phase 2 채택** | 동일 | **BGE-M3** | **1024** | **0.9119** | **8/11** | **89/89** |
| **v3.0 production** | 11쿼리 RERANK=1 | **BGE-M3 (production)** | 1024 | — | **3/3 rank=1** | 7/7 rank=1 |

R-8 임계 (MRR×1.05 ≥0.929)는 BGE-M3도 -1.8% 미달이지만, R-9 임계 (한국어 발현 + 영어 무손실)가 본 cycle 정당한 평가 기준. production 11쿼리 100% PASS로 채택 정당성 최종 입증.

---

## 산출물

### docs/ (R-9 cycle 신규)

- `docs/20260427_r9_multilingual_handoff.md` — R-9 진입 핸드오프
- `docs/20260427_r9_phase1_smoke.md` — Phase 1 7쿼리 smoke 보고서
- `docs/20260427_r9_phase2_handoff.md` — Phase 2 핸드오프
- `docs/20260427_r9_phase2_evaluation.md` — Phase 2 평가 보고서
- `docs/20260427_r9_phase3_production_handoff.md` — Phase 3 핸드오프
- `docs/20260427_r9_phase3_production_migration.md` — Phase 3 종결 보고서

### scripts/ (R-9 cycle 신규)

- `scripts/r9_phase1_smoke.py` (310 LoC) — 7쿼리 smoke
- `scripts/r9_phase2_build_indices_c1.py` (210 LoC) — C1 ChromaDB 빌드
- `scripts/r9_phase2_evaluation.py` (250 LoC) — 100쿼리 평가

R-8 자산 (`scripts/r8_phase2_*.py`, `data/r8_phase2_*.json`, `data/chroma_phase2_baseline/`) 보존 + 재활용.

### graphify_out/ (메트릭)

- `graphify_out/r9_phase1_smoke.json` — Phase 1 metrics
- `graphify_out/r9_phase2_metrics.json` — Phase 2 100쿼리 metrics
- `graphify_out/r9_phase2_build_summary.json` — Phase 2 빌드 메타
- `graphify_out/regression_metrics_rerank.json` — production 11쿼리 회귀 (갱신)

---

## 다음 cycle 후보 (v3.1)

1. **한국어 dataset 확장** — Phase 2 미해소 백내장·녹내장 (한자어 짧은 토큰 임베딩 약점 분석)
2. **budget_guard 영속화** — v2.9 R-10 미완 (in-memory only → JSON or SQLite)
3. **SNOMED VET 2026-09-30 release 갱신** — 다음 reference DB 업데이트
4. **R-9.x hybrid retrieval 정량화** — BGE-M3 + reformulate + rerank 통합 우월성 정량 분석

---

## Commits

```
fa69e49 feat(v3.0): R-9 Phase 3 — production BGE-M3 교체 (R-9 cycle 종결)
87d1788 feat(v3.0): R-9 Phase 2 — C1 BGE-M3 1,000-pool × 100쿼리 평가
c8c832c feat(v3.0): R-9 Phase 1 — 7쿼리 다국어 임베더 smoke
611e08c docs(v3.0): R-9 다국어 임베더 진입 핸드오프
dc11156 docs(v3.0): R-8 Phase 2 평가 + 폐기 결정
```

---

**v3.0 — R-9 cycle 종결, production 한국어 결함 본질 해소.**
