---
tags: [vet-snomed-rag, v3.0, R-9, Phase-3, production, migration, BGE-M3]
date: 2026-04-27
status: R-9 Phase 3 진입 (Phase 2 §2-2 모두 PASS + 사용자 옵션 A 채택)
prev_state: Phase 2 종결 (commit 87d1788). C1 BGE-M3 한국어 8/11 + 영어 89/89 + MRR +3.0% / R@10 +9.0%. R-9 §2-2 임계 모두 PASS.
next_target: production 임베더 BGE-M3 교체 + ChromaDB 366,570×1024d 재빌드 + 단위·회귀 가드 + R-9 cycle 최종 종결
session_anchor: 2026-04-27 (Phase 2 87d1788 직후)
related:
  - docs/20260427_r9_phase2_evaluation.md
  - docs/20260427_r9_phase1_smoke.md
  - docs/20260427_r9_multilingual_handoff.md
  - src/retrieval/hybrid_search.py
  - src/indexing/vectorize_snomed.py
  - data/chroma_db/
---

# R-9 Phase 3 — Production migration (BGE-M3 교체)

## §0. 결론 요약 (3줄)

R-9 Phase 2 §2-2 모두 PASS + 사용자 옵션 A 채택. Production 임베더 `all-MiniLM-L6-v2` (384d) → `BAAI/bge-m3` (1024d) 교체. **변경 2 파일** (`src/retrieval/hybrid_search.py:31` + `src/indexing/vectorize_snomed.py:33`) + ChromaDB 366,570×1024d 재빌드 (~2-4h). baseline `data/chroma_db_baseline_minilm/`로 rollback 안전망 확보.

---

## §1. 변경 영향 분석 (Phase 2 탐색 결과)

### 1-1. 변경 대상 파일 (2건)

| # | 파일:라인 | 변경 |
|---|---|---|
| 1 | `src/retrieval/hybrid_search.py:31` | `EMBEDDING_MODEL = "all-MiniLM-L6-v2"` → `"BAAI/bge-m3"` |
| 2 | `src/indexing/vectorize_snomed.py:33` | `EMBEDDING_MODEL = "all-MiniLM-L6-v2"` → `"BAAI/bge-m3"` |

→ **수정 2 라인.** 구조·로직 무변경, 모델명 단일 상수만 교체.

### 1-2. 변경 보존 (임베더 미접촉)

- `src/retrieval/agentic/`: synthesis/reformulator/judge — 임베더 무관 (Gemini API 사용)
- `src/retrieval/reranker.py`: BGE-reranker-v2-m3 (별도 모델, 변경 X)
- `src/retrieval/query_reformulator.py`: 한국어→영어 변환, 임베더 무관
- `src/retrieval/graph_rag.py`: 임베더 무관 SQL FTS
- `src/tools/`: UMLS/PubMed/Tavily 외부 도구
- `src/retrieval_v2_2_snapshot/`: v2.2 스냅샷 (참고용 보존)

### 1-3. 변경 미포함 — scripts/

scripts/r8_*, scripts/r9_phase1_smoke.py, scripts/r9_phase2_*: baseline 비교 분석 스크립트. R-8/R-9 cycle 산출물로 보존. `"all-MiniLM-L6-v2"` 참조 그대로 유지 (역사 기록).

### 1-4. 데이터 변경

| 자산 | 변경 | 백업 전략 |
|---|---|---|
| `data/chroma_db/` (384d, 1.1GB) | **이름 변경 → `data/chroma_db_baseline_minilm/`** | atomic mv, 디스크 0 추가, rollback 안전망 |
| `data/chroma_db/` (1024d, ~3GB 추정) | **신규 빌드** | `python -m src.indexing.vectorize_snomed` |
| `data/snomed_ct_vet.db` (414,860 SQLite) | 무변경 | — |
| `data/index_stats.json` | 갱신 (BGE-M3 + 1024d 정보) | — |

---

## §2. §3 Task Definition

### §2-1. 입력
- 변경 대상 2 파일 (§1-1)
- baseline ChromaDB `data/chroma_db/` (1.1GB, 384d)
- SNOMED DB `data/snomed_ct_vet.db` (414,860 entries)
- 인덱싱 대상: PRIORITY_TAGS (disorder/finding/procedure/body structure/substance/observable entity/morphologic abnormality/clinical drug/medicinal product/qualifier value/assessment scale/tumor staging/organism) ≈ 366,570 entries (R-8 측정값)

### §2-2. 판단 기준 (P3-S1~P3-S6)

| # | 기준 | 임계 | 검증 방법 |
|---|---|---|---|
| P3-S1 | baseline 백업 | `data/chroma_db_baseline_minilm/` 존재 | ls + count 검증 |
| P3-S2 | src/ 임베더 교체 | 2 파일 모두 `"BAAI/bge-m3"` | grep 검증 |
| P3-S3 | ChromaDB 재빌드 | 366,570 ± 1,000 entries × 1024d | `index_stats.json` + collection.count() |
| P3-S4 | 단위 테스트 251 PASS | 단위 251 + integration 미손실 | `pytest tests/ -q` |
| P3-S5 | **11쿼리 RERANK=1** | none **10/10** + gemini **10/10** (회귀 0) | `RERANK=1 python scripts/run_regression.py` |
| P3-S6 | 정밀 회귀 agentic_rerank | 11/11 PASS (회귀 0) | `python scripts/run_regression_agentic.py` (선택) |

**PASS 조건:** P3-S1 ~ P3-S5 모두 충족 (P3-S6 선택). 미달 시 rollback.

**Rollback 절차:**
```bash
mv data/chroma_db data/chroma_db_failed_bge_m3
mv data/chroma_db_baseline_minilm data/chroma_db
git checkout src/retrieval/hybrid_search.py src/indexing/vectorize_snomed.py
```

### §2-3. 실행 방법 (5 step)

#### Step 1 — baseline 백업

```bash
mv data/chroma_db data/chroma_db_baseline_minilm
ls data/chroma_db_baseline_minilm/  # 검증
```

소요: ~1초 (atomic rename)

#### Step 2 — src/ 임베더 교체

```bash
# Edit 도구로 2 파일 라인 31/33 변경
# "all-MiniLM-L6-v2" → "BAAI/bge-m3"
```

소요: ~10초

#### Step 3 — ChromaDB 재빌드 (백그라운드)

```bash
nohup venv/bin/python -m src.indexing.vectorize_snomed > graphify_out/r9_phase3_build.log 2>&1 &
```

소요: ~2-4시간 (CPU bound, 추정 — 인코딩 ~46m + chromadb add ~82m + HNSW 인덱싱 + I/O)

진행률 모니터: `tail -f graphify_out/r9_phase3_build.log`

#### Step 4 — 병렬 작업 (빌드 중 실행 가능)

- 단위 테스트는 ChromaDB 의존하지 않는 모듈 다수 → 일부 PASS 보장
- 단위 테스트 전체 251 PASS는 ChromaDB 일부 통합 테스트 포함 가능 → 빌드 완료 후 재실행 안전

선택: `pytest tests/ -q --ignore=tests/test_pdf_reader.py` (빠른 단위 230건 추정)

#### Step 5 — 빌드 완료 후 회귀 가드

```bash
# 빌드 완료 검증
cat data/index_stats.json | head -10

# 단위 테스트 251 PASS
venv/bin/python -m pytest tests/ -q

# 11쿼리 회귀 RERANK=1
RERANK=1 venv/bin/python scripts/run_regression.py

# (선택) 정밀 회귀 agentic_rerank
venv/bin/python scripts/run_regression_agentic.py
```

소요: ~10-20분 + Gemini API ~22 call (free tier 안)

#### Step 6 — 보고서 + commit

`docs/20260427_r9_phase3_production_migration.md`:
- §1 변경 영향 + 산출
- §2 P3-S1~S6 1:1 PASS/FAIL
- §3 production 메트릭 비교 (R-8/R-9 Phase 2 vs Phase 3 production)
- §4 회귀 결과
- §5 R-9 cycle 최종 종결 + v3.0 release 권고

```bash
git add src/retrieval/hybrid_search.py src/indexing/vectorize_snomed.py \
        data/index_stats.json docs/20260427_r9_phase3_*.md \
        graphify_out/r9_phase3_*.{json,log,md} graphify_out/regression_metrics_rerank.json \
        graphify_out/backend_comparison.md
git commit -m "feat(v3.0): R-9 Phase 3 — production BGE-M3 교체"
```

### §2-4. 산출물

| 분류 | 경로 | 형식 |
|---|---|---|
| src/ 변경 | `src/retrieval/hybrid_search.py` (line 31) + `src/indexing/vectorize_snomed.py` (line 33) | Python 1-line edit |
| baseline 백업 | `data/chroma_db_baseline_minilm/` | atomic rename, 1.1GB |
| 신규 ChromaDB | `data/chroma_db/` | 1024d, ~3GB 추정 |
| index stats | `data/index_stats.json` | JSON 갱신 |
| build log | `graphify_out/r9_phase3_build.log` | text (gitignored) |
| 보고서 | `docs/20260427_r9_phase3_production_migration.md` | Markdown |

### §2-5. 회귀 결과 비교 (Phase 2 → Phase 3)

| 비교 | Phase 2 (1,000-pool 평가) | Phase 3 (366,570-pool production) |
|---|---|---|
| dataset | R-8 100쿼리 | 11쿼리 + 정밀 12쿼리 |
| baseline | M0 384d ChromaDB (R-8) | (변경 후) BGE-M3 1024d ChromaDB |
| 측정 | per-language MRR / hits | T1-T11 rank-1 + Top-5 PASS |
| 임계 | 한국어 ≥5 + 영어 89/89 | 11쿼리 RERANK=1 10/10×2 |

production 11쿼리 회귀는 본 production 파이프라인 (reformulate + BGE rerank) 통합 효과 측정. Phase 2 미해소 한국어 3건 (T10·백내장·녹내장 — Phase 2 dataset N-ko-03·N-ko-04는 본 11쿼리에 없음) 중 T10이 본 production reformulate 통합 시 PASS 기대.

---

## §3. 위험·블로커

| 위험 | 영향 | 회피 |
|---|---|---|
| ChromaDB 빌드 중 OOM | 빌드 실패 | BATCH_SIZE 500 default. RAM 16GB+ 시 안전. monitor + 빌드 실패 시 batch 축소 |
| 빌드 시간 초과 (>4h) | session 시간 부담 | 백그라운드 + 진행률 모니터, 사용자 다른 작업 가능 |
| 1024d ChromaDB 디스크 부족 | 빌드 중단 | df 사전 확인 (92Gi 여유 충분) |
| BGE-M3 ChromaDB SentenceTransformerEmbeddingFunction 호환성 | 빌드 실패 | 사전 검증: Phase 1·2에서 SentenceTransformer('BAAI/bge-m3') 정상. ChromaDB는 동일 라이브러리 내부 사용 |
| 11쿼리 회귀 PASS율 저하 (10/10 미달) | rollback 필요 | 단계별 검증 + 안전망 절차 |
| 본 production 시간 응답 늘어남 | 사용자 체감 |  BGE-M3 inference 속도 측정 필요 (Phase 1: 1 query 0.06s, baseline 0.04s — +0.02s 미세) |
| HF cache rate limit | 빌드 시작 지연 | 모델 이미 로컬 캐시됨 (Phase 1·2 다운로드) |

---

## §4. 시간·자원 추정

| 단계 | 시간 | 자원 |
|---|---|---|
| Step 1 백업 (mv) | 1s | 0 |
| Step 2 src/ 교체 (Edit ×2) | 10s | 0 |
| Step 3 ChromaDB 빌드 (background) | **~2-4h** | CPU 100% + RAM ~3-4GB + 디스크 +3GB |
| Step 4 병렬 단위 일부 (선택) | ~2-3m | 0 |
| Step 5 회귀 가드 (단위 + 11쿼리) | ~5-10m | Gemini API ~22 call |
| Step 6 보고서 + commit | ~10-15m | 0 |
| **총계** | **~2-4.5h** | 디스크 +3GB (baseline 보존 시 +4GB 총) |

---

## §5. 핸드오프 성공 기준 (H-1 ~ H-7)

| # | 항목 | PASS 조건 |
|---|---|---|
| H-1 | Phase 2 commit 87d1788 검증 | git log + status clean |
| H-2 | BGE-M3 모델 캐시 검증 | `~/.cache/huggingface/hub/models--BAAI--bge-m3` 존재 |
| H-3 | baseline ChromaDB 백업 | `data/chroma_db_baseline_minilm/` count=baseline 동일 |
| H-4 | 변경 2 파일 검증 | grep "BAAI/bge-m3" src/retrieval/hybrid_search.py src/indexing/vectorize_snomed.py |
| H-5 | 새 ChromaDB 검증 | count ≈ 366,570 + dim=1024 |
| H-6 | P3-S1~S5 모두 PASS | 본 핸드오프 §2-2 |
| H-7 | R-9 cycle 종결 | 메모리 갱신 + (선택) v3.0 release tag publish |

---

## §6. R-9 cycle 최종 종결 시나리오

### 6-1. PASS — production 정착

- 보고서 §5: R-9 cycle 종결 + production 메트릭 보존
- (선택) GitHub release tag `v3.0` publish
- 메모리 갱신: project_vet_snomed_rag.md frontmatter R-9 종결 + v3.0 release
- 다음 milestone 후보:
  - v3.1 한국어 dataset 확장 (Phase 2 미해소 백내장/녹내장 등 후속)
  - v3.1 budget_guard 영속화
  - v3.1 SNOMED VET 2026-09-30 release 갱신

### 6-2. FAIL — rollback

- §2-2 P3-S5 회귀 미달 시 rollback 절차 즉시 실행
- 보고서 §5: rollback 사유 + 회귀 결함 분석 + 후속 R-9.x cycle (BGE-M3 부분 채택 vs hybrid retrieval R-9.3)

---

**핸드오프 작성 완료 (2026-04-27).**
**사용자 옵션 A 명시 채택 직후 즉시 실행 진입.**
