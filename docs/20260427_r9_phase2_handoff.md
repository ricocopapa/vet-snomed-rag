---
tags: [vet-snomed-rag, v3.0, R-9, Phase-2, multilingual, embedder, handoff]
date: 2026-04-27
status: R-9 Phase 2 진입 (Phase 1 옵션 A 채택)
prev_state: R-9 Phase 1 종결 (commit c8c832c, 2026-04-27). en rank-1 4/4 (3 모델) / ko rank-1 baseline 2·C1 2·C2 1. baseline 5-pool 한국어 2/3 적중 — smoke 분별력 한계. C1 한국어 cosine 절대값 baseline 대비 3.5-16.5배 → 1,000-pool 분별 신호 가능성. 옵션 A 채택 (사용자 결정).
next_target: C1 BGE-M3 단독 1,000-pool × 100쿼리 평가 → production 교체 결정 권고
session_anchor: 2026-04-27 (Phase 1 c8c832c 직후, push 미완료)
related:
  - docs/20260427_r9_multilingual_handoff.md
  - docs/20260427_r9_phase1_smoke.md
  - docs/20260427_r8_phase2_evaluation.md
  - data/r8_phase2_sample_concepts.json
  - data/r8_phase2_query_dataset.json
  - data/chroma_phase2_baseline/
  - graphify_out/r8_phase2_metrics.json
  - scripts/r8_phase2_build_indices.py
  - scripts/r8_phase2_evaluation.py
---

# R-9 Phase 2 — C1 BGE-M3 단독 1,000-pool × 100쿼리 평가

---

## §0. 결론 요약 (3줄)

R-9 Phase 1 옵션 A 채택 결과 C1 BGE-M3 단독 Phase 2 진입. R-8 Phase 2 자산(1,000 sample + 100 query + baseline ChromaDB) 그대로 재활용 + C1 ChromaDB 신규 빌드 → 100쿼리 평가. **임계: 한국어 hits@10 ≥ 5/11 AND 영어 hits@10 ≥ 89/89 AND 11쿼리 RERANK=1 회귀 무손상.** PASS 시 production 교체 결정 권고, FAIL 시 R-9 폐기 보고서.

---

## §1. 현재 상태 (Phase 1 직후)

### 1-1. Phase 1 결과 요약

| 모델 | dim | en rank-1 | ko rank-1 | margin |
|---|---:|---:|---:|---:|
| **M0 baseline** all-MiniLM-L6-v2 | 384 | 4/4 | 2/3 | +0.3205 |
| **C1 BGE-M3** | 1024 | 4/4 | 2/3 | +0.2077 |
| C2 ml-e5-large | 1024 | 4/4 | 1/3 | +0.0440 |

→ **C2 제외 정당화:** 분별력 평탄성 (모든 cosine 0.79-0.91, margin +0.044) → 1,000-pool 발현 미기대. 시간 +30-45m 절약.
→ **C1 단독 진입 정당화:** 한국어 cosine 절대값 baseline 대비 3.5-16.5배 → 의미 신호 정량.

### 1-2. R-8 자산 재활용 (Phase 2 입력)

| 자산 | 경로 | 상태 |
|---|---|---|
| 1,000 sample (Gold-Forced 96 unique gold) | `data/r8_phase2_sample_concepts.json` | 재사용 |
| 100쿼리 dataset | `data/r8_phase2_query_dataset.json` | 재사용 |
| baseline ChromaDB (M0) | `data/chroma_phase2_baseline/` (gitignored) | 재사용 (비교 baseline) |
| build 패턴 | `scripts/r8_phase2_build_indices.py` | 패치 (MODELS만 C1으로) |
| evaluation 패턴 | `scripts/r8_phase2_evaluation.py` | 패치 (MODELS + 임계 변경) |
| baseline metrics | `graphify_out/r8_phase2_metrics.json` | 재사용 (M0 결과) |

### 1-3. Phase 1 commit 상태

```
HEAD: c8c832c feat(v3.0): R-9 Phase 1 — 7쿼리 다국어 임베더 smoke
      611e08c docs(v3.0): R-9 다국어 임베더 진입 핸드오프
      dc11156 docs(v3.0): R-8 Phase 2 평가 + 폐기 결정
Push: main 동기화 미완료 (R-8 dc11156부터 누적)
HF cache: BGE-M3 ~2.3GB / ml-e5-large ~2.2GB (Phase 1 다운로드)
```

---

## §2. R-9 Phase 2 §3 Task Definition (5항목)

### §2-1. 입력 데이터

| 항목 | 값 | 출처 |
|---|---|---|
| 후보 모델 | C1 BAAI/bge-m3 (1024d) 단독 | Phase 1 옵션 A |
| baseline | M0 all-MiniLM-L6-v2 (production, 384d) | R-8 ChromaDB 재사용 |
| 1,000 sample | `data/r8_phase2_sample_concepts.json` | R-8 Gold-Forced (96 unique gold) |
| 100쿼리 | `data/r8_phase2_query_dataset.json` (en 89 + ko 11) | R-8 dataset |
| baseline metrics | `graphify_out/r8_phase2_metrics.json` (M0 비교 기준) | R-8 결과 |

### §2-2. 판단 기준 (R-9 한국어 발현 1차 + 영어 무손실 2차)

| # | 지표 | 임계 | 근거 |
|---|---|---|---|
| 1 | **한국어 hits@10** | ≥ 5/11 (45% +) | R-8 핸드오프 §3-6 R-9 Phase 2 임계 |
| 2 | **영어 hits@10** | ≥ 89/89 (100%, R-8 baseline 동일) | 영어 무손실 가드 |
| 3 | **11쿼리 RERANK=1 회귀** | none·gemini 10/10×2 | 본 production 무손상 |
| 4 | **단위 테스트** | 251 PASS | 본체 src/ 무변경 보증 |
| 5 | (참고) MRR@10 | C1 vs baseline 0.8850 절대 비교 | 동일/우월 시 production 교체 정당성 강화 |
| 6 | (참고) Recall@10 | C1 vs baseline 0.8900 절대 비교 | 영어 손실 정량 |

**PASS 조건:** 1+2+3+4 모두 충족 → production 교체 결정 권고.
**FAIL 조건:** 1 미달 → R-9 폐기 보고서 (한국어 우회 전략 R-9.1~R-9.3 후속).

### §2-3. 실행 방법 (4 step)

#### Step 1 — `scripts/r9_phase2_build_indices_c1.py` 작성 + 실행

R-8 `r8_phase2_build_indices.py` 패턴 재사용. MODELS만 C1 1개로 축소. dim 1024 검증. 산출:
- `data/chroma_phase2_c1_bge_m3/` (gitignored, ~10MB)
- `graphify_out/r9_phase2_build_summary.json`

소요: ~3-5분 (1,000 docs × 1024d 인코딩 + ChromaDB add)

#### Step 2 — `scripts/r9_phase2_evaluation.py` 작성 + 실행

R-8 `r8_phase2_evaluation.py` 패턴. MODELS C1 + baseline (R-8 ChromaDB 재사용). 임계 §2-2 적용. 산출:
- `graphify_out/r9_phase2_metrics.json`
- console: per-model MRR@10 / Recall@10 / 한국어 hits / 영어 hits + §2-2 PASS/FAIL

소요: ~2-3분

#### Step 3 — 회귀 가드

```bash
venv/bin/python -m pytest tests/ -q | tail -3
venv/bin/python scripts/run_regression.py --rerank 1  # 11쿼리 none·gemini 10/10
```

소요: ~3-5분

#### Step 4 — 보고서 작성 + commit

`docs/20260427_r9_phase2_evaluation.md`:
- §1 100쿼리 결과 (per-model + per-language + per-category)
- §2 §2-2 1:1 PASS/FAIL
- §3 회귀 가드 결과
- §4 production 교체 결정 권고 또는 R-9 폐기

### §2-4. 산출물

| 분류 | 경로 | 형식 |
|---|---|---|
| build 스크립트 | `scripts/r9_phase2_build_indices_c1.py` | Python |
| eval 스크립트 | `scripts/r9_phase2_evaluation.py` | Python |
| 임시 ChromaDB | `data/chroma_phase2_c1_bge_m3/` | Persistent (gitignored) |
| build 메트릭 | `graphify_out/r9_phase2_build_summary.json` | JSON |
| 평가 메트릭 | `graphify_out/r9_phase2_metrics.json` | JSON |
| 보고서 | `docs/20260427_r9_phase2_evaluation.md` | Markdown |

### §2-5. 성공 기준 (P2-S1 ~ P2-S7)

| # | 항목 | PASS 조건 |
|---|---|---|
| P2-S1 | C1 ChromaDB 빌드 | 1,000 entries × 1024d, count=1000 |
| P2-S2 | 100쿼리 평가 | C1 metrics 산출 (MRR@10 / Recall@10 / per-lang) |
| P2-S3 | 한국어 hits@10 ≥ 5/11 | C1 한국어 11쿼리 hits@10 절대값 |
| P2-S4 | 영어 hits@10 ≥ 89/89 | C1 영어 89쿼리 hits@10 절대값 |
| P2-S5 | 11쿼리 RERANK=1 회귀 | none·gemini 10/10×2 |
| P2-S6 | 단위 251 PASS | src/ 무변경 보증 |
| P2-S7 | 보고서 + commit | scripts + chroma 미포함 + docs commit |

---

## §3. 위험·블로커

| 위험 | 영향 | 회피 |
|---|---|---|
| C1 BGE-M3 인코딩 시간 (1,000 docs CPU) | Step 1 +3-5m | batch_size 32, 사전 점검 |
| ChromaDB 1024d 디스크 ~10MB | 디스크 무시 가능 | df 사전 확인 (98Gi 여유 확인됨) |
| 한국어 hits@10 < 5 | R-9 폐기 분기 | smoke 정량 신호로 ~2-5/11 가능성 추정. <5 시 정직 폐기 |
| 영어 hits@10 < 89 | 영어 손실 → 채택 불가 | C1 영어 7쿼리 4/4 rank-1 PASS → 89/89 가능성 높음 |
| 11쿼리 RERANK=1 회귀 0 미달 | src/ 무변경이지만 검증 필수 | 명시적 재실행 (Step 3) |

---

## §4. PASS/FAIL 분기

### 4-1. PASS (P2-S1~S7 모두) → production 교체 결정 권고

- 보고서 §4에 production 교체 절차 권고 작성:
  1. `src/retrieval/snomed_vectorize.py` 또는 동등 위치 임베더 BGE-M3 교체
  2. `data/chroma_db/` 전체 재빌드 (366,570 entries × 1024d, ~3-6시간 추정)
  3. `tests/` 기존 임계 재조정 (MRR/Recall 향상 반영)
  4. 11쿼리 회귀 + 단위 + 정밀 회귀 (Tier B/C 외부 도구 통합 회귀 0)
- 별도 핸드오프: `docs/20260427_r9_phase3_production_handoff.md` (heavy migration cycle)
- 사용자 결정 게이트: production 교체 즉시 vs v3.0 종결 후 v3.1 milestone

### 4-2. FAIL (P2-S3 한국어 < 5/11) → R-9 폐기

- 폐기 보고서: `docs/20260427_r9_disposal.md` (R-8 disposal 패턴)
- 후속 R-9.x 검토:
  - R-9.1 한국어 사전 v1.3 확장 (현 158항목 + 11쿼리 보강)
  - R-9.2 Gemini reformulate 강화 (한국어 → 영어 변환 정확도 측정)
  - R-9.3 hybrid retrieval (영문 임베더 + 한국어 사전 + Gemini reformulate 통합 우월성 입증)

### 4-3. PARTIAL (P2-S3 PASS, P2-S4 < 89/89)

- 영어 손실 발생 → 영어 회귀 분석 보고
- production 교체 보류, hybrid retrieval (R-9.3) 우선 검토

---

## §5. 시간·자원 추정

| 단계 | 시간 | 자원 |
|---|---|---|
| Step 1 build (C1 ChromaDB) | ~3-5m | 디스크 +10MB, RAM ~2GB |
| Step 2 evaluation (100쿼리) | ~2-3m | 디스크 0, RAM ~2GB |
| Step 3 회귀 가드 (단위 251 + 11쿼리) | ~3-5m | 단위 + Gemini API ~22 호출 (free tier 안) |
| Step 4 보고서 + commit | ~5-10m | 0 |
| **총계** | **~15-25m** | 디스크 +10MB |

---

## §6. 즉시 실행 명령 시퀀스

```bash
# Step 1
venv/bin/python scripts/r9_phase2_build_indices_c1.py 2>&1 | tee graphify_out/r9_phase2_build.log

# Step 2
venv/bin/python scripts/r9_phase2_evaluation.py 2>&1 | tee graphify_out/r9_phase2_eval.log

# Step 3
venv/bin/python -m pytest tests/ -q
venv/bin/python scripts/run_regression.py --rerank 1

# Step 4
git add scripts/r9_phase2_*.py docs/20260427_r9_phase2_*.md graphify_out/r9_phase2_*.json
git commit -m "feat(v3.0): R-9 Phase 2 — C1 BGE-M3 1,000-pool × 100쿼리"
```

---

## §7. 핸드오프 성공 기준 체크리스트

| # | 항목 | PASS 조건 |
|---|---|---|
| H-1 | Phase 1 commit c8c832c 검증 | git log + status clean |
| H-2 | C1 다운로드 캐시 검증 | `~/.cache/huggingface/hub/models--BAAI--bge-m3` 존재 |
| H-3 | R-8 자산 검증 | sample/query/baseline ChromaDB 4건 존재 + count=1000 |
| H-4 | §2-2 임계 5건 1:1 PASS/FAIL | 평가 console + JSON |
| H-5 | 회귀 0 보장 | 단위 251 + 11쿼리 10/10×2 |
| H-6 | 메모리 갱신 | `project_vet_snomed_rag.md` Phase 2 결과 + 결정 |
| H-7 | 다음 cycle | PASS → Phase 3 production 핸드오프 / FAIL → R-9 폐기 |

---

**핸드오프 작성 완료 (2026-04-27).**
**옵션 A 사용자 채택 직후 즉시 실행 진입.**
