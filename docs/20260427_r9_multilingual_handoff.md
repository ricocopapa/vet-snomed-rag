---
tags: [vet-snomed-rag, v3.0, R-9, multilingual, embedder, handoff]
date: 2026-04-27
status: R-9 진입 대기 (R-8 폐기 종결 직후)
prev_state: R-8 폐기 (commit dc11156, 2026-04-27). baseline `all-MiniLM-L6-v2` 유지, Phase 3 미실행.
next_target: R-9 Phase 1 (5쿼리 smoke 다국어 후보 비교) 또는 R-9 Phase 2 (1,000+100 R-8 dataset 재활용)
session_anchor: 2026-04-27 (R-8 dc11156 종결 직후, push 미완료)
related:
  - docs/20260427_r8_disposal.md
  - docs/20260427_r8_phase2_evaluation.md
  - docs/20260427_r8_phase2_handoff.md
  - docs/20260427_r8_embedder_candidates.md
  - data/r8_phase2_sample_concepts.json
  - data/r8_phase2_query_dataset.json
  - graphify_out/r8_phase2_metrics.json
  - scripts/r8_phase2_build_indices.py
  - scripts/r8_phase2_evaluation.py
  - memory/project_vet_snomed_rag.md
---

> **핸드오프 목적:** 다음 세션에서 본 문서 1건만 정독해도 R-9 다국어 임베더 검증에 필요한 모든 컨텍스트(R-8 폐기 결과·한국어 결함·후보 우선순위·실행 절차·성공 기준·결정 입력)가 회복되도록 작성.

# R-9 진입 핸드오프 — 다국어 임베더 검증 (한국어 0% 결함 해소)

---

## §0. 결론 요약 (3줄)

R-8 Phase 2에서 **한국어 11쿼리 3 모델 모두 MRR=0** 노출. 영문 임베더 공통 한계로 다국어 임베더 검토 필요. 본 cycle은 BGE-M3 / multilingual-e5 / paraphrase-multilingual-mpnet 3-4 후보를 R-8 동일 setup(1,000-pool Gold-Forced + 100쿼리)에서 비교 → **한국어 11쿼리 hits@10 ≥ 5 + 영어 89쿼리 무손실** 조건 PASS 시 production 교체 후보 채택.

---

## §1. 현재 상태 (R-8 폐기 직후, 2026-04-27)

### 1-1. R-8 Phase 2 결과 요약

| 모델 | dim | MRR@10 | 영어 hits@10 | 한국어 hits@10 |
|---|---:|---:|---:|---:|
| **M0 baseline** all-MiniLM-L6-v2 | 384 | **0.8850** | 89/89 | **0/11** |
| M2 SapBERT mean | 768 | 0.8820 | 89/89 | **0/11** |
| M3 NeuML pubmedbert | 768 | 0.8767 | 89/89 | **0/11** |

→ R-8 폐기 disjunction 충족. **baseline 유지 + Phase 3 미실행.** 한국어 결함은 영문 임베더 공통 한계 → R-9에서 별도 cycle.

상세 본문: `docs/20260427_r8_phase2_evaluation.md`, 폐기 결정: `docs/20260427_r8_disposal.md`.

### 1-2. R-8 → R-9 전환 핵심 인사이트

1. **Setup 결함 패턴 학습:** small candidate pool(1,000) + random query 평가는 항상 Gold-Forced Inclusion 필요. R-8 Phase 2 옵션 A 재설계 후 100/100 gold 적중.
2. **production 우월성 부산물:** baseline + Gemini reformulate + BGE rerank 통합 파이프라인이 11쿼리 RERANK=1 10/10·10/10 PASS. 한국어는 reformulate 단계가 영문 변환으로 baseline 적용을 우회 (T9·T10·T11 production 회귀 PASS). R-9는 reformulate 우회 없이 한국어 직접 매칭이 가능한 임베더 검증.
3. **MRR×1.05 임계 보수성:** baseline 0.885 → 0.929 임계는 rank 평균 1.077 요구로 매우 빡셈. R-9는 한국어 향상이 1차 지표이므로 임계를 다국어 hits 절대값으로 재설계.

### 1-3. v3.0 commit + tag 현황 (R-8 종결 직후)

```
HEAD: dc11156 docs(v3.0): R-8 Phase 2 평가 + 폐기 결정
      53ae57a feat(v3.0): R-8 Phase 2 ChromaDB build + 100쿼리 평가
      4ae55f7 feat(v3.0): R-8 Phase 2 — 1,000 샘플 + 100쿼리 dataset (Gold-Forced)
      cafbc9a docs(v3.0): R-8 Phase 2 진입 핸드오프
      becdd45 feat(v3.0): R-8 phase 1 — 5쿼리 smoke
      13d36e4 docs(v2.9.1): release notes
Tags: v2.9.1 (latest tagged)
GitHub Releases: v2.9 / v2.9.1 publish (R-8 phase는 untagged 누적)
Push: main 동기화 필요 (R-8 dc11156 push 미완료, 사용자 결정 대기)
```

### 1-4. 환경·자산 (R-8 직후 상태 그대로)

- **로컬 경로:** `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag`
- **venv:** `venv/` (Python 3.14.4, sentence-transformers 5.4.1, transformers 5.5.4, torch 2.11.0)
- **CUDA:** False (CPU only)
- **모델 캐시:** `~/.cache/huggingface/hub/` 기존 3종 (SapBERT, NeuML, MiniLM-L6-v2). **R-9 후보 모델은 미다운로드.**
- **인덱스:** `data/chroma_db/` (366,570 baseline 무변경) + `data/snomed_ct_vet.db` (414,860)
- **단위 테스트:** **251 PASS** (R-8 무변경)
- **11쿼리 정밀 회귀 (RERANK=1):** none **10/10** + gemini **10/10** (회귀 0)
- **R-8 Phase 2 산출 (R-9 재활용 가능):**
  - `data/r8_phase2_sample_concepts.json` (1,000 Gold-Forced sample)
  - `data/r8_phase2_query_dataset.json` (100쿼리 96 unique gold)
  - `data/chroma_phase2_{baseline,sapbert_mean,neuml}/` (gitignored, 22.5MB, 정리 시점 사용자 결정)
  - `scripts/r8_phase2_{build_indices,evaluation}.py` (모델 추가만 하면 R-9에 재사용)
- **사용자 .env 키:** R-8과 동일 (`GOOGLE_API_KEY` / `UMLS_API_KEY` / `NCBI_API_KEY` / `TAVILY_API_KEY` / `ANTHROPIC_API_KEY` placeholder)

---

## §2. R-9 후보 + 우선순위

| 코드 | 모델 | dim | 크기 | 강점 | 도메인 가치 | 비용 (CPU) | 권장도 |
|---|---|---:|---|---|---|---|---|
| **C1** | BAAI/bge-m3 | 1024 | ~2.3GB | dense+sparse+colbert hybrid, 100+ langs, FlagEmbedding 표준 | ★★★ 한국어 + 영어 균형 | 중-높음 (다운로드 + 임베딩) | **★★★** |
| **C2** | intfloat/multilingual-e5-large | 1024 | ~2.2GB | 100+ langs, 임베딩 품질 우수, sentence-transformers 호환 | ★★★ 한국어 + 영어 균형 | 중-높음 | **★★★** |
| **C3** | intfloat/multilingual-e5-base | 768 | ~1.1GB | e5-large 축소, 빠름, sentence-transformers 호환 | ★★ 빠른 검증용 | 중 | ★★ |
| **C4** | sentence-transformers/paraphrase-multilingual-mpnet-base-v2 | 768 | ~1GB | 50+ langs, 균형, 가장 작음 | ★★ 한국어 가능, 도메인 약함 | 낮음 | ★★ |

**Phase 1 권장:** C1 (BGE-M3) + C2 (e5-large) 2 후보 smoke. C3·C4는 Phase 1에서 hits ≥ baseline 시 추가.

**비추천 후보:**

- KoSimCSE/Klue 계열 한국어 특화 — 영어 89쿼리 손실 위험, R-8 vet Recall@5 가드 미통과 가능
- E5-large-instruct — query/passage prefix 조작 필요, 임시 평가에 setup 부담

---

## §3. R-9 Phase 1 Task Definition (5항목)

### §3-1. 입력 데이터

| 항목 | 값 | 출처/검증 |
|---|---|---|
| 후보 모델 (Phase 1) | C1 BGE-M3 + C2 multilingual-e5-large | §2 권장 |
| baseline (비교 기준) | M0 all-MiniLM-L6-v2 (production) | R-8 Phase 1 패턴 동일 |
| 5-10쿼리 smoke set | T1-T5 (영어) + T9-T11 (한국어 3건) | R-8 11쿼리 dataset 재활용 |
| SNOMED DB | `data/snomed_ct_vet.db` (414,860) | symlink 검증 |
| gold concept | T1-T11 매핑 (T5 새 부여 709044004) | R-8 dataset 재활용 |

### §3-2. 판단 기준

| 지표 | 임계값 | 근거 |
|---|---|---|
| **smoke margin** (영어 5건 + 한국어 3건) | M0 대비 한국어 적중 ≥ 1 (M0=0) | 한국어 발현 1차 검증 |
| **smoke 영어 무손실** | 영어 5건 rank 1-3 유지 | baseline 영어 회귀 0 |
| **모델 다운로드 + 메모리** | 디스크 5GB+ 여유 / RAM 8GB+ | 자원 사전 확인 |
| **Phase 2 진입 조건** | 한국어 적중 ≥ 1 AND 영어 무손실 | 권장 1+ 후보 통과 시 Phase 2 진입 |
| **R-9 폐기 조건** | 모든 후보 한국어 0/3 적중 | 다국어 임베더로 한국어 미해결 → 다른 전략 (한국어 사전 강화 / Gemini reformulate 강화) |

### §3-3. 실행 방법

#### Step 1 — 후보 모델 다운로드 + 메모리 사전 점검

```bash
df -h | head -3                            # 디스크 5GB+ 여유 확인
venv/bin/python -c "
import resource
print('  rlimit:', resource.getrlimit(resource.RLIMIT_AS))
"
ls ~/.cache/huggingface/hub/ | grep -E "bge-m3|multilingual-e5" | head -5
```

#### Step 2 — `scripts/r9_phase1_smoke.py` 작성

R-8 `scripts/r8_phase1_smoke.py` 패턴 재사용. 8-10쿼리 × 3 모델 (baseline + C1 + C2) cosine 매트릭스 비교. Phase 1 산출물:

```
graphify_out/r9_phase1_smoke.log  (실행 로그, gitignored)
graphify_out/r9_phase1_smoke.json (모델별 margin + per-query rank)
```

#### Step 3 — Phase 1 결과 보고서

`docs/20260427_r9_phase1_smoke.md`:
- §1 8-10쿼리 + 3 모델 cosine 매트릭스
- §2 한국어 3건 적중 비교
- §3 §3-2 판단 기준 1:1 PASS/FAIL
- §4 Phase 2 진입 결정 또는 R-9 폐기

### §3-4. 산출물 포맷

| 분류 | 경로 | 형식 |
|---|---|---|
| 스크립트 | `scripts/r9_phase1_smoke.py` | Python |
| 메트릭 | `graphify_out/r9_phase1_smoke.json` | JSON |
| 로그 | `graphify_out/r9_phase1_smoke.log` | text (gitignored) |
| 보고서 | `docs/20260427_r9_phase1_smoke.md` | Markdown |

### §3-5. 성공 기준 (Phase 1만)

| # | 항목 | PASS 조건 |
|---|---|---|
| P1-S1 | 후보 모델 다운로드 | C1 + C2 hub/ 캐시 확인 |
| P1-S2 | 8-10쿼리 인코딩 | 3 모델 × 8-10 cosine 매트릭스 정상 산출 |
| P1-S3 | 한국어 발현 | C1 또는 C2 한국어 3건 적중 ≥ 1 |
| P1-S4 | 영어 무손실 | C1 또는 C2 영어 5건 rank 1-3 유지 |
| P1-S5 | 판단 기준 1:1 | §3-2 5 지표 PASS/FAIL 표 |
| P1-S6 | Phase 2 결정 | 진입 vs 폐기 명시 권장 |
| P1-S7 | 산출 commit | scripts + docs |

### §3-6. R-9 Phase 2 (Phase 1 PASS 시 별도 진입)

R-8 Phase 2 패턴 그대로:

- 1,000 sample (R-8 산출 그대로 재활용 — Gold-Forced 96 unique gold 동일)
- 100쿼리 dataset (R-8 산출 그대로 재활용)
- 임시 ChromaDB 추가 빌드 (Phase 1 통과 후보만)
- §3-2 판단 임계 재설계: 한국어 hits@10 ≥ 5/11 (~45%) AND 영어 hits@10 ≥ 89/89 (100%) AND 11쿼리 RERANK=1 회귀 무손상

이는 별도 R-9 Phase 2 핸드오프 작성 시점에 확정.

---

## §4. 우선순위 권고

### 4-1. 권장 순서

1. **R-9 Phase 1** — 본 핸드오프 §3 그대로 (~1시간, 5-10쿼리 smoke)
2. **결과 따라 분기:**
   - PASS (한국어 적중 ≥ 1, 영어 무손실) → R-9 Phase 2 별도 핸드오프 작성 후 진행
   - FAIL (모든 후보 한국어 0) → R-9 폐기 보고서 + 한국어 결함은 reformulate/사전 강화로 우회
3. **병렬 가능:** budget_guard 영속화 (별도 cycle, ~30-60m)

### 4-2. 권장 묶음

- **묶음 K (R-9 결정):** Phase 1 → Phase 2 (조건부) → 결과 보고서 → 사용자 production 교체 결정
- **별도 후순위:** budget_guard 영속화

### 4-3. 비추천 패턴

- **Phase 1 skip + Phase 2 직행** — 후보 한국어 발현 미검증 상태에서 1,000-pool 평가는 시간 낭비. R-8 학습 적용.
- **모든 후보 (C1+C2+C3+C4) 동시 Phase 1** — 디스크 6GB+ 사용, 평가 시간 2배. 권장 default 2 후보 (C1+C2)로 시작.
- **한국어 특화 모델만 사용** — 영어 89쿼리 손실 위험. 다국어 임베더의 영어 무손실 보장이 필수.

---

## §5. 재개 가이드 (다음 세션 진입 시)

### 5-1. 첫 명령

```bash
cd ~/claude-cowork/07_Projects/vet-snomed-rag
git status --short                                        # clean 확인
git log -3 --oneline                                      # dc11156 R-8 폐기 commit 확인
venv/bin/python -m pytest tests/ -q | tail -3             # 251 PASS baseline 확인
df -h . | head -3                                         # 디스크 5GB+ 여유
ls ~/.cache/huggingface/hub/ | grep -E "bge-m3|multilingual-e5"  # R-9 후보 캐시 (없을 가능성)
cat docs/20260427_r9_multilingual_handoff.md | head -60   # 본 문서 §1-2
```

### 5-2. 핸드오프 로드 명령 예시

```
이 R-9 핸드오프대로 Phase 1 진행해줘
또는 권장 default로 진행해줘  (= C1 BGE-M3 + C2 multilingual-e5-large 2후보)
또는 C1만 단독 검증해줘  (= 메모리 절약, BGE-M3만)
또는 C1+C2+C4 3후보로 진행  (= mpnet 추가, 빠른 baseline 비교)
또는 R-9 폐기 결정해줘  (= Phase 1 skip, 한국어는 reformulate/사전 강화로 우회)
```

### 5-3. 사용자 의사결정 필요 사항

| # | 항목 | 옵션 | 권장 default |
|---|---|---|---|
| R9-1 | Phase 1 진행 여부 | (a) 진행 / (b) 폐기 / (c) 일부 후보만 | **(a) 진행** |
| R9-2 | 후보 모델 | (a) C1 단독 / (b) C1+C2 / (c) C1+C2+C4 | **(b) C1+C2** |
| R9-3 | smoke 쿼리 셋 | (a) T1-T11 전체 / (b) T1·T3·T5·T8·T9·T10·T11 7건 / (c) 사용자 정의 | **(b) 7건 (영어 4 + 한국어 3)** |
| R9-4 | Phase 2 자동 진입 | (a) Phase 1 PASS 시 자동 / (b) 사용자 결정 | **(b) 사용자 결정** |
| R9-5 | 한국어 임계 | (a) hits ≥ 1 (Phase 1) / hits ≥ 5 (Phase 2) / (b) 더 높게 | **(a)** |
| R9-6 | 임시 ChromaDB 처리 | (a) 보존 / (b) 자동 삭제 / (c) .gitignore + 보존 | **(c) .gitignore + 보존** |

### 5-4. R-9 Phase 1 PASS 시 다음 cycle (Phase 2 진입 조건)

- §3-5 P1-S3·P1-S4 PASS (한국어 ≥ 1 + 영어 무손실)
- 별도 Phase 2 핸드오프 작성 (R-8 Phase 2 패턴 적용)
- Phase 2 산출: 100쿼리 × 통과 후보 임시 ChromaDB + R-8 baseline 비교

### 5-5. R-9 Phase 1 FAIL 시 다음 cycle (R-9 폐기)

- 모든 후보 한국어 0/3 → R-9 폐기 보고서 (`docs/20260427_r9_disposal.md`)
- 한국어 해결책 후속 검토:
  - **R-9.1 한국어 사전 v1.3 확장** (현 158항목 + 한국어 reformulate 케이스 보강)
  - **R-9.2 Gemini reformulate 강화** (한국어 → 영어 변환 정확도 측정)
  - **R-9.3 hybrid retrieval** (영문 임베더 + 한국어 사전 + Gemini reformulate 조합 우월성 보존)

---

## §6. 위험·블로커

| 위험 | 영향 | 회피 |
|---|---|---|
| C1·C2 모델 다운로드 시간 (~2.2-2.3GB each) | Phase 1 실행 +10-20m | df -h 사전 확인 + huggingface_hub TOKEN 권장 (rate limit) |
| RAM 부족 (BGE-M3 + 1,000 entries 인코딩 시) | OOM 위험 | batch_size 16-32로 조절 (R-8 default 32) |
| ChromaDB 1024d 디스크 ~10MB × N | 디스크 부족 가능성 | df -h 사전 확인 + 폐기 시점 사용자 결정 |
| C1 BGE-M3 sentence-transformers 비호환 (FlagEmbedding 표준) | 인코딩 패턴 다름 | FlagEmbedding 라이브러리 또는 transformers AutoModel + manual pooling |
| 한국어 도메인 부족 (수의학 한국어 SNOMED 매핑 부재) | 한국어 평가 11건만으로 임계 도달 어려움 | Phase 2에서 한국어 신규 쿼리 추가 검토 (10→20건) |
| Phase 1 PASS이지만 Phase 2 FAIL | 시간 낭비 | Phase 1 임계 보수적 설정 (≥1 적중) + Phase 2 별도 핸드오프 |
| baseline 자체가 reformulate로 한국어 우회 중 (T9-T11 production 회귀 PASS) | R-9 production 채택 정당성 약화 | 정직한 비교 — "reformulate 없이" R-9 후보 vs "reformulate 포함 production"의 시너지 측정 |
| FlagEmbedding 라이브러리 추가 의존성 | venv 손상 위험 | 별도 venv 또는 sentence-transformers AutoModel 우회 (manual pooling) |

---

## §7. 핸드오프 성공 기준 체크리스트 (다음 세션이 본 핸드오프 입력 시 1:1 검증)

| # | 항목 | PASS 조건 |
|---|---|---|
| H-1 | 현 상태 검증 | git clean / 단위 251 PASS / dc11156 commit / 11쿼리 none·gemini 10/10 / 디스크 5GB+ 여유 |
| H-2 | 사용자 R9-1~R9-6 선택 명확 | 6항목 모두 사용자 답변 또는 권장 default 채택 명시 |
| H-3 | §3 Task Definition 5항목 사용자 승인 | 입력·판단·실행·산출·성공기준 동의 |
| H-4 | 사용자 사전 액션 (필요 시) 완료 | 디스크 5GB 여유 / huggingface_hub TOKEN 등록 (선택) |
| H-5 | 작업 완료 시 §3-5 P1-S1~P1-S7 1:1 PASS | 모든 PASS 조건 충족 |
| H-6 | 회귀 0 보장 | 11쿼리 RERANK=1 none·gemini 10/10 유지 + 251 PASS 유지 |
| H-7 | 메모리 갱신 | `project_vet_snomed_rag.md`에 R-9 Phase 1 결과 + 결정 추가 |
| H-8 | 다음 핸드오프 작성 또는 종결 | Phase 2 진입 시 별도 핸드오프 / R-9 폐기 시 disposal 보고서 |

---

## §8. 부록 — R-8 → R-9 전환 자산

### 8-1. R-8 commit 이력 (R-9 시작점)

| commit | 내용 |
|---|---|
| `dc11156` | docs(v3.0): R-8 Phase 2 평가 + 폐기 결정 (R-9 시작점) |
| `53ae57a` | feat(v3.0): R-8 Phase 2 ChromaDB build + 100쿼리 평가 |
| `4ae55f7` | feat(v3.0): R-8 Phase 2 — 1,000 샘플 + 100쿼리 dataset (Gold-Forced) |
| `cafbc9a` | docs(v3.0): R-8 Phase 2 진입 핸드오프 |
| `becdd45` | feat(v3.0): R-8 phase 1 — 5쿼리 smoke |

### 8-2. R-9에서 재사용할 R-8 자산

| R-8 자산 | R-9 활용 |
|---|---|
| `data/r8_phase2_sample_concepts.json` | Phase 2 진입 시 동일 1,000 sample 사용 (Gold-Forced 96 unique gold) |
| `data/r8_phase2_query_dataset.json` | Phase 2 진입 시 동일 100쿼리 사용 (96 unique gold) |
| `data/chroma_phase2_baseline/` | Phase 2 baseline 비교 직접 재사용 (M0 1,000-pool) |
| `scripts/r8_phase2_build_indices.py` | Phase 2 진입 시 모델 추가만 하면 됨 |
| `scripts/r8_phase2_evaluation.py` | Phase 2 진입 시 모델 추가만 하면 됨 |
| `scripts/r8_phase1_smoke.py` | Phase 1 smoke 패턴 재사용 |

### 8-3. R-9 신규 산출 예상 (Phase 1만)

| 분류 | 경로 | 형식 |
|---|---|---|
| 스크립트 | `scripts/r9_phase1_smoke.py` | Python |
| 메트릭 | `graphify_out/r9_phase1_smoke.json` | JSON |
| 로그 | `graphify_out/r9_phase1_smoke.log` | text (gitignored) |
| 보고서 | `docs/20260427_r9_phase1_smoke.md` | Markdown |

Phase 2 진입 시 추가:
- `scripts/r9_phase2_build_indices.py` (R-8 패턴)
- `scripts/r9_phase2_evaluation.py` (R-8 패턴)
- `data/chroma_phase2_{c1_bge_m3,c2_e5_large}/` (gitignored)
- `graphify_out/r9_phase2_metrics.json`
- `docs/20260427_r9_phase2_evaluation.md`

### 8-4. baseline + R-9 후보 비교 setup (Phase 1)

| Setup | dim | 한국어 | 영어 |
|---|---:|---|---|
| **M0 baseline** all-MiniLM-L6-v2 | 384 | 0% (R-8 측정) | 100% (R-8 측정) |
| C1 BGE-M3 | 1024 | 미측정 (Phase 1 핵심) | 미측정 (R-8 회귀 가드) |
| C2 multilingual-e5-large | 1024 | 미측정 | 미측정 |

Phase 1 8-10쿼리 smoke 권장 split: T1·T3·T5·T8 영어 4건 + T9·T10·T11 한국어 3건 = 7쿼리 (또는 R9-3 사용자 결정).

### 8-5. R-8 Phase 2 일관성 보존 사항 (R-9 적용 권장)

| R-8 학습 | R-9 적용 |
|---|---|
| Gold-Forced Inclusion | Phase 2 동일 100 gold 강제 포함 |
| random.seed(20260427) | 동일 seed로 재현성 보존 |
| document text "preferred_term \| fsn \| Category: tag" | 동일 패턴 |
| ChromaDB cosine space | 동일 |
| per-language MRR 분리 보고 | en/ko 분리 보고 강화 |
| §3-2 1:1 PASS/FAIL 표 | 동일 양식 |

---

**핸드오프 작성 완료 (2026-04-27).**
**다음 세션에서 §5-2 형식으로 명령하여 R-9 Phase 1 진입.**
**예: "이 R-9 핸드오프대로 Phase 1 권장 default로 진행해줘"**
