---
tags: [vet-snomed-rag, v3.1, handoff, post-R-4, release-decision]
date: 2026-04-27
status: v3.1 R-4 종결 직후, 다음 세션 진입 대기
prev_state: R-4 종결 (commit c441a6f, push 완료). 한국어 production 회귀 양쪽 backend PERFECT 11/11.
next_target: v3.1.0 release publish 결정 또는 다른 milestone 후보 진입
session_anchor: 2026-04-27 (R-4 c441a6f 직후, 사용자 본 세션 종결)
related:
  - docs/20260427_v3_1_r1_korean_validation.md
  - docs/20260427_v3_1_r2_korean_dictionary_v1_3.md
  - docs/20260427_v3_1_r3_korean_dictionary_v1_4.md
  - docs/20260427_v3_1_r4_reformulate_skip.md
  - docs/20260427_r9_phase3_production_migration.md
---

# v3.1 post-R-4 — 다음 세션 진입 핸드오프

## §0. 결론 요약 (3줄)

v3.1 한국어 cycle (R-1~R-4) 1차 완전 종결, 한국어 production 회귀 PERFECT 11/11×2 도달 (commit c441a6f, push 완료). v3.1.0 release publish 후보 또는 다른 milestone 진입은 본 핸드오프 §3에서 사용자 결정. 다음 세션 진입 시 §6 명령 예시 1줄로 즉시 작업 재개.

---

## §1. 현재 상태 (R-4 종결 직후)

### 1-1. 누적 성과 (R-9 Phase 1 → v3.1 R-4)

| 단계 | commit | 한국어 hits |
|---|---|---|
| R-9 Phase 2 (1,000-pool 단독 BGE-M3) | 87d1788 | 8/11 |
| **v3.0 production migration** | fa69e49 | (영어 회귀 100%) |
| v3.1 R-1 (production 통합) | c4783e8 | none 6/11 + gemini 8/11 |
| v3.1 R-2 (사전 v1.3) | a27b2e3 | none 9/11 + gemini 10/11 |
| v3.1 R-3 (사전 v1.4) | e17ff54 | none 11/11 + gemini 10/11 |
| **v3.1 R-4 (reformulate skip)** | **c441a6f** | **none 11/11 + gemini 11/11 PERFECT ★★** |

### 1-2. 영어 production 회귀 보존

| 항목 | 결과 |
|---|---|
| 11쿼리 RERANK=1 (none) | **10/10 PASS** (NA=1건 제외) |
| 11쿼리 RERANK=1 (gemini) | **10/10 PASS** |
| T7 핵심 (feline diabetes) | rank=1 둘 다 |
| 단위 테스트 | **251 + 59 subtests PASS** (81.99s) |

### 1-3. git 상태

```
HEAD: c441a6f feat(v3.1): R-4 — 사전 변환 시 reformulate skip: 한국어 11/11×2 PERFECT
      e17ff54 feat(v3.1): R-3 — 사전 v1.4: 한국어 none 11/11 PERFECT 도달
      a27b2e3 feat(v3.1): R-2 — 사전 v1.3 한국어 generic 매핑 강화 (+3/+2 회복)
      c4783e8 feat(v3.1): R-1 한국어 11쿼리 production 회귀 — 백내장·녹내장 PASS 입증
      1a01cbb docs(v3.0): release notes — R-9 cycle 종결 + production BGE-M3 교체
Push: 완료 (origin/main 동기화)
Tags: v2.9.1, v3.0 (latest)
```

### 1-4. 환경·자산 보존

| 자산 | 상태 |
|---|---|
| `data/chroma_db/` | production 1024d (BGE-M3, 366,570 entries, 2.0GB) |
| `data/chroma_db_baseline_minilm/` | rollback 안전망 (384d, 1.1GB) |
| `data/vet_term_dictionary_ko_en.json` | v1.4 (171 entries + 외이염·심장 잡음·고관절·림프종 매핑) |
| HF cache | BGE-M3 ~2.3GB + ml-e5-large ~2.2GB |
| `.env` 키 | UMLS · NCBI · Gemini · Tavily 정상 |
| 단위 누적 | 251 PASS |
| 11쿼리 RERANK=1 회귀 | none·gemini 10/10×2 보존 |
| **한국어 11쿼리 회귀** | **none·gemini 11/11×2 ★** |

---

## §2. 다음 작업 후보 — 우선순위

### 2-1. v3.1.0 release publish (R-1~R-4 cycle 마침표)

| 옵션 | 내용 | 시간 |
|---|---|---|
| **A (자연스러운 후속)** | GitHub Release v3.1.0 publish — R-1~R-4 누적 narrative + RELEASE_NOTES_v3.1.0.md 작성 | ~30-45m |
| B | v3.1.0-rc tag → 외부 검증 1주일 → 정식 publish | 보수적 |
| C | v3.1.0 보류, 다른 milestone 후 묶어 publish | — |

### 2-2. 다른 v3.1 milestone 후보

| 후보 | 작업 | 시간 |
|---|---|---|
| **R-5 budget_guard 영속화** | v2.9 R-10 미완 작업. in-memory only → JSON·SQLite 영속화 | ~30-60m |
| **R-6 SNOMED VET 2026-09-30 release 갱신** | 다음 reference DB 업데이트 (Sept 30 2026 SNOMED VET 릴리스 시점) | dataset 의존 |
| **R-7 hybrid retrieval 정량화** | BGE-M3 + reformulate + rerank 통합 우월성 정량 분석. 이력서·기술 블로그 자료 (사용자 메모리 "프로젝트 완성도 우선·이력서 후순위" 따라 후순위) | ~1-2시간 |

---

## §3. 다음 세션 결정 사항

| # | 항목 | 옵션 | 권장 default |
|---|---|---|---|
| Q1 | v3.1.0 release publish 시점 | (A) 즉시 publish / (B) v3.1.0-rc 후 정식 / (C) 보류 | **(A)** R-1~R-4 cycle 마침표 |
| Q2 | release publish 후 다음 cycle | R-5 budget_guard / R-6 SNOMED VET / R-7 hybrid 정량화 | **R-5** (R-10 미완 작업 우선) |
| Q3 | 외이염 dataset 추가 정밀 분석 | (a) 별도 cycle / (b) 보류 | **(b)** 본 cycle PERFECT 도달로 보류 충분 |

---

## §4. 다음 세션 §3 Task Definition (가장 자연스러운 흐름 — 옵션 A + R-5)

### §4-1. v3.1.0 release publish 작업

| 항목 | 내용 |
|---|---|
| 입력 | R-1~R-4 commit 4건 + R-9 Phase 3 fa69e49 이후 누적 |
| 산출 | RELEASE_NOTES_v3.1.0.md + git tag v3.1.0 + GitHub Release publish |
| 임계 | tag annotated + RELEASE_NOTES Breaking changes/Migration 명시 + Release URL 제공 |
| 시간 | ~30-45m |

### §4-2. R-5 budget_guard 영속화 후속 cycle

| 항목 | 내용 |
|---|---|
| 입력 | `src/observability/budget_guard.py` 218 LoC (v2.9 R-10) + tests/test_budget_guard.py 24건 |
| 미완 | in-memory state → JSON 또는 SQLite 영속화. 프로세스 재시작 시 budget 누적 보존 |
| 임계 | (1) JSON·SQLite write/read 동작 / (2) 단위 테스트 추가 (~10건) / (3) v2.9 24건 PASS 회귀 0 / (4) 11쿼리 회귀 0 |
| 시간 | ~30-60m |

---

## §5. 위험·블로커

| 위험 | 회피 |
|---|---|
| v3.1.0 release publish는 비가역 (외부 게시) | 사용자 명시 승인 후만 진행 |
| SNOMED VET 2026-09-30 release 시점 의존 | dataset 가용 시점 확인 (현재 04-27, 9월 30일은 5개월 후) |
| budget_guard 영속화 schema 결정 (JSON vs SQLite) | 단순한 작업이면 JSON, 복잡한 query 필요시 SQLite |
| Gemini Free Tier 20 RPD 한도 (작업 회귀 시) | RPD 500 (gemini-3.1-flash-lite-preview) 사용 중, 안전 |
| 외이염 dataset gold 추가 분석 (Q3) | 본 cycle PERFECT라 보류 권장. 향후 cycle에서만 |

---

## §6. 다음 세션 진입 명령 예시

### 6-1. 가장 자연스러운 흐름 (옵션 A + R-5)

```
이 v3.1 post-R-4 핸드오프대로 v3.1.0 release publish 진행해줘
또는 권장 default로 진행해줘  (= 옵션 A v3.1.0 publish + R-5 budget_guard 영속화 자동 연결)
```

### 6-2. 분리 진행

```
v3.1.0 release publish만 먼저 진행
또는 R-5 budget_guard 영속화부터 진행 (release는 묶기)
또는 R-7 hybrid retrieval 정량화 진행 (이력서 자료)
또는 외이염 dataset 추가 정밀 분석
```

### 6-3. 보류

```
v3.1.0 release 보류, 다른 milestone 후 묶어 진행
또는 본 세션 종결, 다음 세션에서 신규 작업 결정
```

---

## §7. 핸드오프 성공 기준 체크리스트 (다음 세션이 본 핸드오프 입력 시 1:1 검증)

| # | 항목 | PASS 조건 |
|---|---|---|
| H-1 | 현 상태 검증 | git clean / HEAD c441a6f / push 완료 / 단위 251 PASS / 영어·한국어 회귀 PASS |
| H-2 | Q1·Q2·Q3 사용자 선택 명확 | 3 항목 모두 사용자 답변 또는 권장 default 채택 명시 |
| H-3 | §4 Task Definition 사용자 승인 (release publish 비가역) | publish 시점·tag 이름·RELEASE_NOTES 내용 동의 |
| H-4 | 작업 완료 시 1:1 PASS | release URL 제공 + 회귀 0 + 다음 cycle 진입 |
| H-5 | 메모리 갱신 | project_vet_snomed_rag.md frontmatter v3.1.0 release 갱신 |
| H-6 | 다음 핸드오프 | release publish 후 R-5 핸드오프 작성 또는 종결 |

---

## §8. 부록 — R-1~R-4 cycle 통합 narrative

### 8-1. v3.0 → v3.1 cycle 흐름

```
v3.0 (R-9 cycle 종결)
  └─ R-9 Phase 1·2·3: production BGE-M3 교체 (fa69e49)
     ├─ 한국어 hits 0→8/11 (1,000-pool 단독)
     └─ 영어 89/89 (무손실)
       ↓
v3.1 한국어 cycle (R-1~R-4)
  ├─ R-1 (c4783e8): production 통합 측정 — none 6/11 + gemini 8/11
  │   └─ 백내장·녹내장 PASS 입증, 미해소 3건 식별
  ├─ R-2 (a27b2e3): 사전 v1.3 — 고관절·림프종 specific 매핑
  │   └─ none 9/11 + gemini 10/11
  ├─ R-3 (e17ff54): 사전 v1.4 — 외이염 swimmer's ear + 심장 잡음
  │   └─ none 11/11 PERFECT + gemini 10/11
  └─ R-4 (c441a6f): 사전 변환 시 reformulate skip
      └─ none 11/11 + gemini 11/11 PERFECT ★★
       ↓
v3.1.0 release (대기) — 본 핸드오프 §3 사용자 결정
```

### 8-2. v3.1 R-1~R-4 cycle 산출물 인덱스

| 분류 | 경로 |
|---|---|
| 보고서 | `docs/20260427_v3_1_r1_korean_validation.md` (R-1) |
| 보고서 | `docs/20260427_v3_1_r2_korean_dictionary_v1_3.md` (R-2) |
| 보고서 | `docs/20260427_v3_1_r3_korean_dictionary_v1_4.md` (R-3) |
| 보고서 | `docs/20260427_v3_1_r4_reformulate_skip.md` (R-4) |
| 핸드오프 | `docs/20260427_v3_1_post_r4_handoff.md` (본 문서) |
| 스크립트 | `scripts/v3_1_korean_extension_validation.py` |
| 메트릭 | `graphify_out/v3_1_korean_extension.json` |
| 사전 | `data/vet_term_dictionary_ko_en.json` (v1.4) |
| src | `src/retrieval/rag_pipeline.py` (Step 0.7 reformulate skip 분기) |

---

**핸드오프 작성 완료 (2026-04-27).**
**사용자 본 세션 종결, 다음 세션에서 §6 명령 예시 1줄로 즉시 작업 재개.**
