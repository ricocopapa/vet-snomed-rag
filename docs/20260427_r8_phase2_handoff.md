---
tags: [vet-snomed-rag, v3.0, R-8, phase2, handoff, embedder]
date: 2026-04-27
status: Phase 1 종결 (commit becdd45) — Phase 2 진입 대기
prev_state: R-8 Phase 1 5쿼리 smoke 종결 (baseline 우위, 단 setup 한계 진단). v2.9.1 v3.0 phase 1 종결 (commit 13d36e4, GitHub v2.9.1 publish).
next_target: R-8 Phase 2 (1,000 샘플 임시 ChromaDB + 100쿼리 평가) 또는 R-8 폐기 결정
session_anchor: 2026-04-27 (Phase 1 commit becdd45 직후, push 완료, untagged)
related:
  - docs/20260427_r8_phase1_smoke.md (Phase 1 결과 본문)
  - docs/20260427_r8_embedder_candidates.md (R-8 후보 비교 보고서)
  - scripts/r8_phase1_smoke.py
  - graphify_out/r8_phase1_smoke.log (gitignored, local-only)
  - data/snomed_ct_vet.db (SNOMED 414,860 concept)
  - data/chroma_db/ (현 ChromaDB 366,570, all-MiniLM-L6-v2 384d)
  - graphify_out/regression_metrics.json (11쿼리 baseline)
  - memory/project_vet_snomed_rag.md
---

> **핸드오프 목적:** 다음 세션에서 본 문서 1건만 정독해도 R-8 Phase 2 진입에 필요한 모든 컨텍스트(Phase 1 결과·한계 진단·후보 우선순위·실행 절차·성공 기준·결정 입력)가 회복되도록 작성.

# R-8 Phase 2 진입 핸드오프 — 1,000 샘플 + 100쿼리 평가

---

## §1. 현재 상태 (Phase 1 종결, 2026-04-27)

### 1-1. Phase 1 결과 요약 (5쿼리 smoke)

| 모델 | dim | diag↑ | off-diag↓ | **margin↑** | rank-1 hits |
|---|---|---|---|---|---|
| **M0 baseline all-MiniLM-L6-v2** | 384 | +0.9120 | +0.1305 | **+0.7816 ★** | 5/5 |
| M1 SapBERT [CLS] | 768 | +0.9256 | +0.2314 | +0.6942 | 5/5 |
| **M2 SapBERT mean** | 768 | **+0.9430** ★ | +0.2685 | +0.6745 | 5/5 |
| M3 NeuML pubmedbert | 768 | +0.8261 | +0.0938 | +0.7323 | 5/5 |

→ **baseline이 margin 1위, 그러나 5쿼리 setup 한계로 Phase 2 재검증 필수.**

### 1-2. Phase 1 한계 진단 (재인용)

본 5쿼리 smoke가 baseline 우위로 결론 나온 것은 setup 한계 때문:

1. **쿼리=concept 표면 일치** — "feline panleukopenia" ↔ "Feline panleukopenia". 의미 공간 매칭이 아닌 표면 단어 매칭만으로 도달
2. **Candidate pool 5개뿐** (production 366,570) — 큰 pool 분별력 미측정
3. **Cross-walk / 약어 / 동의어 / 한국어 reformulate 케이스 0** — SapBERT entity-linking 강점 미반영
4. **R-8 §5가 인용한 200K SNOMED concept 벤치마크 setup과 다름**

### 1-3. v3.0 commit + tag 현황

```
HEAD: becdd45 feat(v3.0): R-8 phase 1 — 5쿼리 smoke
      13d36e4 docs(v2.9.1): release notes
      8c24f3b feat(v2.9.1): v3.0 phase 1 — budget_guard 통합 + venv 정리 + R-8 후보
Tags: v2.9.1 (latest tagged, 2026-04-26 publish)
GitHub Releases: v2.9 / v2.9.1 publish (R-8 phase는 untagged 누적)
Push: main 동기화 완료 (becdd45)
```

### 1-4. 환경·자산

- **로컬 경로:** `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag`
- **venv:** `venv/` (Python 3.14.4, sentence-transformers 5.4.1, transformers 5.5.4, torch 2.11.0)
- **CUDA:** False (CPU only)
- **모델 캐시 (Phase 1 다운로드 완료, ~/.cache/huggingface 아래):**
  - `cambridgeltl/SapBERT-from-PubMedBERT-fulltext` (~440MB)
  - `NeuML/pubmedbert-base-embeddings` (~440MB)
  - `sentence-transformers/all-MiniLM-L6-v2` (~80MB, 기존)
- **인덱스:** `data/chroma_db/` (366,570 baseline) + `data/snomed_ct_vet.db` (414,860)
- **단위 테스트:** **251 PASS** (243 + 8 budget_guard 통합)
- **11쿼리 정밀 회귀 (RERANK=1):** none **10/10** + gemini **10/10** (회귀 0)
- **사용자 .env 키:** `GOOGLE_API_KEY` ✓ / `UMLS_API_KEY` ✓ / `NCBI_API_KEY` ✓ / `TAVILY_API_KEY` ✓ / `ANTHROPIC_API_KEY` placeholder

---

## §2. 후속 작업 후보 + 우선순위

| 코드 | 작업 | 도메인 가치 | 회귀 위험 | 비용 | 즉시 가능 | 권장도 |
|---|---|---|---|---|---|---|
| **R-8 P2** | Phase 2 — 1,000 샘플 + 100쿼리 평가 | ★★★ R-8 채택/폐기 결정 | 0 (임시 ChromaDB만, production 무영향) | 2-3시간 (CPU) | ✅ | ★★★ |
| **R-8 폐기** | baseline 유지 + R-8 종결 선언 | ★ Phase 1 baseline 우위 보존 | 0 | 30m (docs only) | ✅ | ★ (Phase 2 미실행 시 정보 부족) |
| **budget_guard 영속화** | JSON or SQLite 추가, 세션 간 누적 | ★ 운영 견고성 | 낮음 | 30-60m | ✅ | ★★ |
| **R-8 P3** | 전수 366,570 재구축 (Phase 2 통과 후) | ★★★ 최종 채택 | 높음 (production ChromaDB 교체) | 1.5-3시간 (CPU) | ❌ Phase 2 후 | ★ (Phase 2 통과 시) |

---

## §3. R-8 Phase 2 Task Definition (5항목)

### §3-1. 입력 데이터

| 항목 | 값 | 출처/검증 |
|---|---|---|
| Phase 1 결과 | M2 SapBERT mean +0.9430 diag, M3 NeuML +0.7323 margin | `docs/20260427_r8_phase1_smoke.md` §2 |
| 후보 2개 (Phase 2 비교 대상) | **M2 SapBERT mean + M3 NeuML pubmedbert** | Phase 1 결과 1·2위, Phase 1 보고서 §5-3 |
| baseline (비교 기준) | all-MiniLM-L6-v2 (384d) | `src/indexing/vectorize_snomed.py:33` |
| SNOMED DB | `data/snomed_ct_vet.db` (414,860 concept) | symlink 검증 — `ls -la data/snomed_ct_vet.db` |
| 1,000 샘플 분포 (R-8 후보 보고서 §4-2) | disorder 300 / procedure 200 / body 150 / finding 150 / organism 100 / substance 100 | tag-stratified |
| 100쿼리 분포 | 수의학 전용 20 / 범용 disorder 25 / procedure 20 / body 15 / drug 10 / 한국어 reformulate 10 | R-8 §4-2 |
| 기존 11쿼리 회귀 | T1-T11, gold concept_id 매핑 완료 | `graphify_out/regression_metrics.json` |
| 모델 캐시 | SapBERT + NeuML 이미 다운로드됨 | Phase 1 실행 부수효과 |

### §3-2. 판단 기준

| 지표 | 임계값 | 근거 |
|---|---|---|
| **MRR@10** (100쿼리 평균) | **≥ baseline × 1.05** (+5% 이상) | R-8 후보 보고서 §4-3 |
| **Recall@10** | 동일 또는 향상 | R-8 §4-3 |
| **수의학 전용 쿼리 Recall@5** | ≥ baseline × 0.95 (수의학 손실 ≤5%) | R-8 §4-3 (alpha transfer 위험 가드) |
| **11쿼리 회귀 RERANK=1** | none·gemini 모두 10/10 유지 (회귀 0) | 본체 무손상 보장 |
| **Phase 3 진입 조건** | 위 4 지표 모두 PASS | conjunction 조건 |
| **R-8 폐기 조건** | MRR@10 +5% 미달 또는 수의학 Recall@5 손실 >5% | disjunction 조건 |

### §3-3. 실행 방법

#### Step 1 — 1,000 샘플 추출 (tag-stratified)

```sql
-- data/snomed_ct_vet.db
-- semantic_tag별 비례 추출, ORDER BY RANDOM()로 분포 보존
SELECT concept_id, preferred_term, semantic_tag
FROM concept
WHERE semantic_tag = 'disorder' ORDER BY RANDOM() LIMIT 300;
-- procedure 200, body structure 150, finding 150, organism 100, substance 100 동일 패턴
```

산출: `data/r8_phase2_sample_concepts.json` (1,000 entries with concept_id + preferred_term + semantic_tag)

#### Step 2 — 100쿼리 dataset 작성

| 분류 | 수 | 출처 |
|---|---|---|
| 수의학 전용 | 20 | T1, T2, T6, T11 + 16 신규 (vet-specific SNOMED 검색) |
| 범용 disorder | 25 | T3, T4, T5, T8 + 21 신규 |
| Procedure | 20 | 신규 (Tooth extraction, Splenectomy 등) |
| Body structure | 15 | 신규 (Femoral head 등) |
| Drug | 10 | 신규 (Amoxicillin, Prednisolone 등) |
| 한국어 reformulate | 10 | T9, T10 + 8 신규 |

각 쿼리별 gold concept_id 검증 필수 (sqlite로 매칭 확인). 산출: `data/r8_phase2_query_dataset.json`.

#### Step 3 — 임시 ChromaDB 빌드 (M2 + M3)

```python
# scripts/r8_phase2_build_indices.py
# - 1,000 샘플을 M2 SapBERT mean / M3 NeuML 각각으로 임베딩
# - chromadb.PersistentClient(path='data/chroma_phase2_sapbert_mean')
# - chromadb.PersistentClient(path='data/chroma_phase2_neuml')
# - cosine space, batch_size=100
```

소요: 1,000 × 768d × 2 모델 × CPU = ~5-10분 each.

#### Step 4 — 100쿼리 평가

```python
# scripts/r8_phase2_evaluation.py
# - 각 쿼리를 M2/M3로 임베딩 → 임시 ChromaDB top-10 검색
# - rank_of_correct (gold concept이 top-10 안 몇 위) 산출
# - MRR@10 = mean(1/rank), Recall@10 = (rank ≤ 10) 비율
# - baseline 비교: 같은 100쿼리를 현 ChromaDB(366,570)에서 검색 후 1,000 샘플 안 정답만 카운트
```

산출: `graphify_out/r8_phase2_metrics.json` (모델별 MRR/Recall/per-query rank)

#### Step 5 — 11쿼리 회귀 RERANK=1

```bash
# 기존 scripts/run_regression.py 활용 (M2/M3 backend 옵션 추가 필요할 수 있음)
# 또는 별도 r8_phase2_regression.py로 4모델(baseline + M2 + M3 + M1) 비교
```

산출: `graphify_out/r8_phase2_regression.json` (4모델 × 11쿼리 × 2 backend 매트릭스)

#### Step 6 — 결과 보고서

`docs/20260427_r8_phase2_evaluation.md`:
- §1 1,000 샘플 + 100쿼리 분포 검증
- §2 MRR@10 / Recall@10 비교 표 (M2 vs M3 vs baseline)
- §3 수의학 쿼리 손실 측정
- §4 11쿼리 RERANK=1 회귀 결과
- §5 §3-2 판단 기준 1:1 PASS/FAIL
- §6 Phase 3 진입 결정 (또는 R-8 폐기)

### §3-4. 산출물 포맷

| 분류 | 경로 | 형식 |
|---|---|---|
| 스크립트 1 | `scripts/r8_phase2_build_indices.py` | Python |
| 스크립트 2 | `scripts/r8_phase2_evaluation.py` | Python |
| 스크립트 3 | `scripts/r8_phase2_regression.py` (옵션) | Python |
| 데이터 1 | `data/r8_phase2_sample_concepts.json` | JSON 1,000 entries |
| 데이터 2 | `data/r8_phase2_query_dataset.json` | JSON 100 entries |
| 임시 인덱스 1 | `data/chroma_phase2_sapbert_mean/` | ChromaDB |
| 임시 인덱스 2 | `data/chroma_phase2_neuml/` | ChromaDB |
| 산출 메트릭 | `graphify_out/r8_phase2_metrics.json` | JSON |
| 회귀 산출 | `graphify_out/r8_phase2_regression.json` | JSON |
| 본 보고서 | `docs/20260427_r8_phase2_evaluation.md` | Markdown |

`data/chroma_phase2_*/` 디렉토리는 임시 — Phase 3 진입 시 폐기, R-8 폐기 시 즉시 폐기 가능. `.gitignore` 추가 권장.

### §3-5. 성공 기준

| # | 항목 | PASS 조건 |
|---|---|---|
| P2-S1 | 1,000 샘플 추출 | tag별 분포 표 + sanity check (vet-specific concept 비율 ≥ baseline ChromaDB 비율) |
| P2-S2 | 100쿼리 dataset | 각 쿼리 gold concept 1차 검증 (SQL 매칭 PASS) |
| P2-S3 | 임시 ChromaDB 빌드 | M2 + M3 둘 다 1,000 entries × 768d, cosine space |
| P2-S4 | MRR@10 측정 | 100쿼리 × 3 setup(baseline / M2 / M3) MRR 산출 |
| P2-S5 | 판단 기준 §3-2 | 4 지표 1:1 PASS/FAIL 표 |
| P2-S6 | 11쿼리 회귀 | none·gemini 10/10 유지 (본체 무손상) |
| P2-S7 | Phase 3 결정 | 진입 vs 폐기 명시적 권장 |
| P2-S8 | 산출물 commit | scripts + docs (data/JSON, graphify_out/JSON 사용자 결정) |

---

## §4. 우선순위 권고

### 4-1. 권장 순서

1. **R-8 Phase 2** — 본 핸드오프 §3 그대로 (~2-3시간)
2. **결과 따라 분기:**
   - PASS → Phase 3 (전수 재구축, 별도 핸드오프)
   - FAIL → R-8 폐기 보고서 + v3.0 종결 선언
3. **병렬 가능:** budget_guard 영속화 (별도 cycle, ~30-60m)

### 4-2. 권장 묶음

- **묶음 J (R-8 결정):** Phase 2 → 결과 보고서 → 사용자 P3 결정
- **별도 후순위:** budget_guard 영속화 (Phase 2와 무관)

### 4-3. 비추천 패턴

- **Phase 2 skip + Phase 3 직행** — 1,000 샘플 검증 없이 366,570 전수 재구축은 회귀 위험 + 시간 낭비
- **5쿼리 smoke 결과만 근거로 R-8 폐기** — Phase 1 §4 setup 한계 명시. baseline 우위는 setup 한계의 결과
- **M2 + M3 + M1 셋 동시 비교** — Phase 2 시간 50% 증가, M1 [CLS]은 mean에 일반적으로 열세 (Phase 1 +0.6942 vs +0.6745, 거의 차이 없음)

---

## §5. 재개 가이드 (다음 세션 진입 시)

### 5-1. 첫 명령

```bash
cd ~/claude-cowork/07_Projects/vet-snomed-rag
git status --short                                    # clean 확인
git log -3 --oneline                                  # becdd45 phase 1 commit 확인
venv/bin/python -m pytest tests/ -q | tail -3         # 251 PASS baseline 확인
ls ~/.cache/huggingface/hub/ | grep -E "SapBERT|pubmedbert|MiniLM" | head -5  # 모델 캐시 확인
cat docs/20260427_r8_phase2_handoff.md | head -80     # 본 문서 §1-3
```

### 5-2. 핸드오프 로드 명령 예시

```
이 R-8 Phase 2 핸드오프대로 진행해줘
또는 권장 default로 진행해줘  (= P2-1=진행, P2-2=M2+M3, P2-3=tag-stratified, P2-4=11+89, P2-5=+5%)
또는 P2-X만 [값]으로 변경해서 진행해줘
또는 R-8 폐기 보고서 작성해줘  (= Phase 2 미실행, baseline 유지 결정)
또는 1,000 샘플 추출만 먼저 보고 결정할게  (= Step 1만 진행 후 일시 정지)
```

### 5-3. 사용자 의사결정 필요 사항

| # | 항목 | 옵션 | 권장 default |
|---|---|---|---|
| P2-1 | Phase 2 진행 여부 | (a) 진행 / (b) R-8 폐기 / (c) 일부 단계만(Step 1만 등) | **(a) 진행** |
| P2-2 | 비교 대상 | (a) M2 단독 / (b) M2 + M3 / (c) M2 + M3 + M1 | **(b) M2 + M3** |
| P2-3 | 1,000 샘플 추출 | (a) random / (b) tag-stratified / (c) 수의학 우선 | **(b) tag-stratified** |
| P2-4 | 100쿼리 dataset | (a) 새로 작성 / (b) 11 + 89 추가 | **(b) 11 + 89** |
| P2-5 | 결과 임계 | (a) MRR@10 +5% / (b) +10% / (c) Recall만 | **(a) +5%** |
| P2-6 | 임시 ChromaDB 처리 | (a) 보존 / (b) Phase 결정 후 자동 삭제 / (c) .gitignore만 | **(c) .gitignore + 보존** |

### 5-4. Phase 2가 PASS일 때 다음 cycle (Phase 3 진입 조건)

- §3-2 4 지표 모두 PASS 시 Phase 3 (전수 366,570 재구축) 진입
- Phase 3은 별도 핸드오프 작성 필요 (~1.5-3시간 CPU)
- Phase 3 산출: `data/chroma_db/` 교체 + `vectorize_snomed.py` `EMBEDDING_MODEL` 변경 + 11쿼리 전수 회귀

### 5-5. Phase 2가 FAIL일 때 다음 cycle (R-8 폐기 조건)

- §3-2 4 지표 중 1개라도 FAIL 시 R-8 폐기 보고서 작성
- 산출: `docs/20260427_r8_disposal.md` (alpha transfer 가설 reject 정당화 + baseline 유지 근거)
- v3.0 종결 선언 + 다음 milestone 후보 brainstorm

---

## §6. 위험·블로커

| 위험 | 영향 | 회피 |
|---|---|---|
| 1,000 샘플 분포 편향 (vet-specific 부족) | Phase 2 결과가 도메인 적합성 미반영 | Step 1 후 sanity check + vet-specific 비율 명시 |
| 100쿼리 89 추가 gold concept 검증 시간 | 데이터 작성 1-2시간 | SNOMED preferred_term 정확 일치 우선, partial match 허용 시 명시 |
| ChromaDB 디스크 ~500MB × 2 임시 사용 | 디스크 부족 가능성 | `df -h` 사전 확인 + Phase 결정 후 정리 |
| M2 SapBERT mean의 sentence-transformers 직접 호환 | 표준 인터페이스 미지원 | `scripts/r8_phase1_smoke.py:encode_huggingface_pooled()` 패턴 재사용 |
| ChromaDB embedding_function이 sentence-transformers 의존 | 커스텀 모델 등록 복잡 | ChromaDB.embed_documents에 사전 계산된 임베딩 직접 주입 (numpy → list) |
| 11쿼리 회귀 시 baseline 외 모델 backend 미구현 | rag_pipeline.py가 baseline ChromaDB만 사용 | 평가용 별도 스크립트(r8_phase2_regression.py)로 4모델 직접 검색, RERANK 분리 |
| Gemini API quota 11쿼리 × 2 backend 추가 | RPD 500 한도 안 (현 사용 ~20/일) | budget_guard 활성화 권장 (`GSD_BUDGET_USD_MONTH=2.0`) |
| Phase 2 결과가 모호 (예: M2만 PASS, M3 FAIL) | 결정 보류 → 추가 Phase 2.5 필요 | §3-2 conjunction 조건으로 단일 모델만 PASS 시도 명시 처리 |

---

## §7. 핸드오프 성공 기준 체크리스트 (다음 세션이 본 핸드오프 입력 시 1:1 검증)

| # | 항목 | PASS 조건 |
|---|---|---|
| H-1 | 현 상태 검증 | git clean / 단위 251 PASS / becdd45 commit / 11쿼리 none·gemini 10/10 / SapBERT+NeuML 캐시 확인 |
| H-2 | 사용자 P2-1~P2-6 선택 명확 | 6항목 모두 사용자 답변 또는 권장 default 채택 명시 |
| H-3 | §3 Task Definition 5항목 사용자 승인 | 입력·판단·실행·산출·성공기준 동의 |
| H-4 | 사용자 사전 액션 (필요 시) 완료 | 예: 디스크 1GB 여유 확인 / budget_guard env 설정 |
| H-5 | 작업 완료 시 §3-5 P2-S1~P2-S8 1:1 PASS | 모든 PASS 조건 충족 |
| H-6 | 회귀 0 보장 | 11쿼리 RERANK=1 none·gemini 10/10 유지 + 251 PASS 유지 |
| H-7 | 메모리 갱신 | `project_vet_snomed_rag.md`에 Phase 2 결과 + 결정 추가 |
| H-8 | 다음 핸드오프 작성 또는 종결 | Phase 3 진입 시 별도 핸드오프 / R-8 폐기 시 disposal 보고서 |

---

## §8. 부록 — Phase 1 + 사전 작업 산출물 인덱스

### 8-1. v3.0 commit 이력 (Phase 1까지)

| commit | 내용 |
|---|---|
| `becdd45` | feat(v3.0): R-8 phase 1 — 5쿼리 smoke (baseline + SapBERT 2 변형 + NeuML) |
| `13d36e4` | docs(v2.9.1): release notes — v3.0 phase 1 (budget_guard 통합 + R-8 후보) |
| `8c24f3b` | feat(v2.9.1): v3.0 phase 1 — budget_guard runtime 통합 + venv 정리 + R-8 후보 보고서 |

### 8-2. 관련 문서

| 분류 | 경로 | 비고 |
|---|---|---|
| Phase 1 결과 | `docs/20260427_r8_phase1_smoke.md` | 5쿼리 smoke 본문 |
| 후보 비교 보고서 | `docs/20260427_r8_embedder_candidates.md` | 8 후보 + §4 검증 절차 + §6 결정 입력 |
| Phase 1 스크립트 | `scripts/r8_phase1_smoke.py` | 240 LoC, Phase 2에서 패턴 재사용 |
| Phase 1 로그 | `graphify_out/r8_phase1_smoke.log` | gitignored, local-only |
| 이전 핸드오프 | `docs/20260427_v2_9_roadmap_handoff.md` | v2.9 R-10 종결 (status 종결) |
| Release notes | `RELEASE_NOTES_v2.9.md` + `v2.9.1.md` | v3.0 진입 직전 publish 기록 |

### 8-3. Phase 2에서 재사용할 스크립트 패턴

| Phase 2 모듈 | 참고 스크립트 |
|---|---|
| `r8_phase2_build_indices.py` | `src/indexing/vectorize_snomed.py` (ChromaDB 빌드 패턴) + `scripts/r8_phase1_smoke.py:encode_huggingface_pooled()` (mean pooling) |
| `r8_phase2_evaluation.py` | `scripts/r8_phase1_smoke.py:_cosine_matrix()` + ChromaDB query interface |
| `r8_phase2_regression.py` | `scripts/run_regression.py` (11쿼리 회귀 패턴) |

### 8-4. 1,000 샘플 + 100쿼리 분포 (R-8 §4-2 그대로)

| Phase 2 dataset | 분포 |
|---|---|
| 1,000 샘플 ChromaDB | disorder 300 / procedure 200 / body structure 150 / finding 150 / organism 100 / substance 100 |
| 100쿼리 평가 | vet-specific 20 / 범용 disorder 25 / procedure 20 / body 15 / drug 10 / 한국어 reformulate 10 |

---

**핸드오프 작성 완료 (2026-04-27).**
**다음 세션에서 §5-2 형식으로 명령하여 R-8 Phase 2 진입.**
**예: "이 R-8 Phase 2 핸드오프대로 권장 default로 진행해줘"**
