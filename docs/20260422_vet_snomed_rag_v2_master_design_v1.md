---
tags: [vet-snomed-rag, v2.0, 설계서, 이직포트폴리오, RAG, STT, SOAP, SNOMED]
date: 2026-04-22
status: draft_for_approval
version: 1.0
---

# vet-snomed-rag v2.0 — 마스터 설계서

> **승인 사항 확정 (2026-04-22)**
> - 스코프: **Option A** (Track A/B/C 동시 진행, 7일 목표)
> - 가속 옵션: **옵션 2 적용** (Contextual Retrieval은 v2.1로 분리)
> - Q1: **A** — JSONL 출력까지만 공개, EMR DB/웹 UI는 사내 잔존
> - Q2: **A** — 사용자 직접 수의 시나리오 5건 녹음 (Day 6~7 배치)
> - Q3: **A** — 기존 `vet_stt_pipeline.py` 백엔드 유지 (Claude Haiku + Sonnet)

---

## §0. 작업 메타 (Hard Gate 준수 확인)

| 항목 | 확인 |
|---|---|
| CLAUDE.md 로드 | ✅ (`~/CLAUDE.md`, `~/claude-cowork/CLAUDE.md`, `~/.claude/CLAUDE.md` 모두 이번 세션 컨텍스트 주입 확인) |
| 03_Working_Rules §1-1 Task Definition 5항목 | ✅ (§2에 전 에이전트 기입) |
| 검증 출처 컬럼 | ✅ (§2 각 항목) |
| model 파라미터 명시 | ✅ (§2 각 에이전트) |
| 피드백 메모리 사전 확인 | ✅ (§0.1) |
| Small-Sample 규칙 | ✅ (§4 Day 2 회귀 3쿼리 smoke) |
| 독립 검증 2계층 | ✅ (§6 Reviewer 에이전트) |
| Output Quality Gate | ✅ (§7 O1~O12 해당분) |

### §0.1 적용된 피드백 메모리 (9건)

| ID | 내용 | 본 설계 반영 위치 |
|---|---|---|
| feedback_design_before_execute | 로드맵≠설계 | 본 문서 = 설계서, 디스패치 금지 상태 |
| feedback_orchestrator_responsibility | 5가지 사전 점검 | §2 검증 출처 컬럼 |
| feedback_knowledge_flywheel_agent_design | 도메인 주장 출처 | §2 검증 출처 컬럼 |
| feedback_parallel_dispatch | 독립 에이전트 병렬 | §4 Day 1 2기 동시 디스패치 |
| feedback_small_sample | 10건+ 전 3~5건 테스트 | §4 Day 2 3쿼리 smoke |
| feedback_independent_verify_persona | 체크리스트 자기검증 금지 | §6 Reviewer는 독립 페르소나 |
| feedback_output_quality_gate | DB 적재 시 QG 필수 | §7 JSONL 스키마 QG |
| feedback_snomed_mapping_method | keyword/LIKE 금지, exact+post-coord | §2 Track B3 판단기준 |
| feedback_write_then_verify | Write→Read-back | §4 각 Day 종료 QG |

---

## §1. 목표·경계 (Scope Contract)

### §1.1 포함 (Must Deliver)

| 기능 | 수용 조건 |
|---|---|
| **리랭커 통합** (BAAI/bge-reranker-v2-m3) | `hybrid_search.py`에 rerank 옵션 추가, v1.0 11-쿼리 회귀 PASS 10/10 유지 |
| **Whisper STT 래퍼** | m4a/wav/mp3 입력 → 한국어 텍스트, faster-whisper 또는 openai-whisper 기반 |
| **SOAP 추출 파이프라인** | `scripts/vet_stt_pipeline.py` 4단계 로직 추출 → 공개용 리팩토링, 실DB 의존성 제거 |
| **SNOMED 자동 태깅** | 추출된 S/O/A/P 필드 → v1.0 하이브리드 RAG 호출 → concept_id 자동 부여 |
| **MRCM 검증 + 후조합 SCG** | A축 v8·P축 v3.5 매핑 노하우 적용, LOCAL 0건 유지 |
| **E2E JSONL 출력** | 1 음성(or 텍스트) = 1 JSONL 레코드, 스키마 §7.1 |
| **Streamlit UI 확장** | 기존 app.py에 "음성/텍스트 업로드 → SOAP+SNOMED 결과" 탭 추가 |
| **합성 샘플 5건** | 사용자 직접 녹음, 공개 리포 포함 가능한 일반 임상 시나리오 |
| **E2E 평가 스크립트 + 리포트** | SOAP 필드 precision/recall, SNOMED 태깅 일치율, latency |
| **v2.0 릴리즈 문서** | README 업데이트, CHANGELOG, 새 벤치마크 차트 |

### §1.2 제외 (Out of Scope, v2.1 이후)

- Contextual Retrieval (SOAP 청크 적용) — v2.1
- 다화자 분리 / 실시간 스트리밍 / 웹훅 — v2.1+
- EMR DB(`cdw_vetstar.db`, `master.db`, `encounter.db`) 적재 — **사내 private 레벨 유지**
- 실환자 녹음/PDF — **공개 금지**, private 벤치마크만 수치 인용
- vetstt-soap-prototype의 server.py 웹 UI — **사내 유지**

---

## §2. Track별 에이전트 Task Definition (5항목 + 검증 출처)

### Track A — Reranker 통합

#### A1. Reranker 구현 에이전트
| 항목 | 내용 | 검증 출처 |
|---|---|---|
| **Persona / Model** | Specialist (Sonnet) | `Model_Selection_Rules.md §9` |
| **입력 데이터** | `src/retrieval/hybrid_search.py` (현재 575 LOC 확인), `tests/regression_queries.json` (11 쿼리) | 실측 Read 완료 (2026-04-22) |
| **판단 기준** | (1) BAAI/bge-reranker-v2-m3 (MIT, 다국어) 우선 (2) Top-20 → Top-5 재정렬 (3) `include_relationships` 호출 전 rerank 적용 | HuggingFace 공식 모델 카드 확인 필요 (Day 1 착수 시) |
| **실행 방법** | Step 1: `hybrid_search.py`에 `RerankerStage` 클래스 신설 → `HybridSearchEngine.search()` `rerank=True` 파라미터 추가. Step 2: `requirements.txt`에 `sentence-transformers>=2.7` 이미 존재, `FlagEmbedding` 추가. Step 3: 3쿼리 smoke 테스트 (feline panleukopenia / canine parvovirus / 고양이 당뇨). Step 4: 11쿼리 전체 회귀. | 기존 `hybrid_search.py:425` HybridSearchEngine 구조 분석 완료 |
| **산출물 포맷** | (1) `src/retrieval/reranker.py` 신규 (2) `hybrid_search.py` diff (3) `benchmark/v2_reranker_report.md` (before/after 테이블) | — |
| **성공 기준 (State-Based)** | - 11쿼리 PASS 10/10 **유지** (regression 0건) <br> - Top-10 miss NF 건수 **1→0** <br> - p95 latency +30% 이내 <br> - MRR 증가 (정량 수치 무관, Δ≥0) | v1.0 기준 수치: `project_vet_snomed_rag.md` (PASS 10/10, latency 1,064ms) |

### Track B — End-to-End 파이프라인 (4개 서브트랙)

#### B1. Whisper STT 래퍼
| 항목 | 내용 | 검증 출처 |
|---|---|---|
| **Persona / Model** | Specialist (Sonnet) | `Model_Selection_Rules.md §9` |
| **입력 데이터** | `scripts/whisper_retranscribe.py` (향남병원 파이프라인, 재활용 참고) | `project_emr_whisper.md` (34일전 메모, 현존 확인 필요) |
| **판단 기준** | (1) `faster-whisper` 기본 (로컬, 재현성↑) (2) 한국어 `language="ko"` 강제 (3) beam_size=5 (기존 재변환 방식) (4) 오디오 포맷: m4a/wav/mp3/mp4 | Whisper 공식 문서 |
| **실행 방법** | Step 1: `src/pipeline/stt_wrapper.py` 신설, `transcribe(audio_path) → {text, segments}`. Step 2: 1건 샘플로 스모크. Step 3: 에러 처리 (파일 없음, 포맷 미지원, 빈 결과). | — |
| **산출물 포맷** | `src/pipeline/stt_wrapper.py`, `tests/test_stt_wrapper.py` | — |
| **성공 기준** | - 샘플 m4a 1건 → 한국어 텍스트 출력 <br> - 파일 없음/빈 오디오에 `ValueError` 명확 <br> - tests 3건 PASS | — |

#### B2. SOAP 추출기 (vet_stt_pipeline 포팅)
| 항목 | 내용 | 검증 출처 |
|---|---|---|
| **Persona / Model** | emr-planner skill + Specialist (Sonnet) — vet-stt skill 로드 필수 | `.claude/skills/vet-stt/SKILL.md` 실측 확인 (2026-04-22) |
| **입력 데이터** | `scripts/vet_stt_pipeline.py` Step 0~2 로직 | 실측 Read 완료 (2026-04-22), 25개 도메인 확인 |
| **판단 기준** | (1) Step 0 Haiku 전처리 → Step 1 Haiku 도메인 탐지 (최대 3개) → Step 2 Sonnet 필드 추출 (2) **실 DB 의존성 제거** (`DB_PATH` 하드코딩 삭제, 필드 스키마 JSON 파일로 외부화) (3) `ANTHROPIC_API_KEY` 없으면 graceful fail | vet-stt SKILL.md §Step 0~3 |
| **실행 방법** | Step 1: `src/pipeline/soap_extractor.py` 신설, `vet_stt_pipeline.py`의 Step 0/1/2 함수 포팅. Step 2: 필드 스키마를 `data/field_schema_v26.json`으로 외부화 (25도메인 메타 포함). Step 3: 3 텍스트 샘플로 smoke (안과·내과·정형외과). | — |
| **산출물 포맷** | `src/pipeline/soap_extractor.py`, `data/field_schema_v26.json`, `tests/test_soap_extractor.py` | — |
| **성공 기준** | - 3 smoke 샘플 모두 도메인 탐지 + 필드 추출 성공 <br> - `CA_OPH_IOP_OD_VAL`(안과 IOP) 같은 정확한 필드 코드 추출 <br> - 없는 필드 `null` 처리 (feedback_source_only_data) | vet-stt SKILL.md Test Case 1 기준 |

#### B3. SNOMED 자동 태깅 + MRCM 검증
| 항목 | 내용 | 검증 출처 |
|---|---|---|
| **Persona / Model** | snomed-mapping skill + Specialist (Sonnet) | `.claude/skills/snomed-mapping/` 실측 확인 (SKILL.md + workflow-a/p/o/s-axis.md + audit-queries.md) |
| **입력 데이터** | B2 출력(필드 딕셔너리), v1.0 `rag_pipeline.py`, SNOMED CT VET DB 414,860 concepts | `project_vet_snomed_rag.md` + 실측 Read |
| **판단 기준** | (1) **exact match + semantic_tag 강제만 안전** (keyword LIKE 매핑 금지) (2) post-coordination 기본 (base concept + attribute) (3) MRCM 제약 확인 후 부착 (4) NULL을 설계 의도로 분류 금지 — 미매핑은 `UNMAPPED` 명시 (5) Has specimen 일괄 배치 금지 (검사별 개별 파싱) | feedback_keyword_mapping_danger, feedback_snomed_mapping_method, feedback_mrcm_constraint_check, feedback_null_not_design_intent, feedback_batch_specimen_assignment |
| **실행 방법** | Step 1: `src/pipeline/snomed_tagger.py` 신설. Step 2: B2 각 필드 → v1.0 `SNOMEDRagPipeline.query()` 호출 → Top-1 concept_id. Step 3: MRCM 검증 (procedure attribute 허용 여부). Step 4: 후조합 SCG 표현 생성. Step 5: 매핑 불가 시 `UNMAPPED` 플래그. | snomed-mapping workflow-a-axis.md (후조합 기본), P축 v3.5 노하우 |
| **산출물 포맷** | `src/pipeline/snomed_tagger.py`, tagging 결과 스키마 (§7.1) | — |
| **성공 기준** | - 3 smoke 샘플 필드 100%에 concept_id or `UNMAPPED` 부여 (NULL 금지) <br> - 후조합 필요 케이스 SCG 표현 생성 <br> - 가짜 concept_id 0건 (hallucinate 0) | feedback_snomed_source_validation |

#### B4. E2E 파이프라인 통합 + Streamlit UI
| 항목 | 내용 | 검증 출처 |
|---|---|---|
| **Persona / Model** | Specialist (Sonnet) | — |
| **입력 데이터** | B1/B2/B3 완성 모듈, 기존 `app.py` | — |
| **판단 기준** | (1) `src/pipeline/e2e.py` = STT → SOAP → SNOMED 오케스트레이션 (2) 각 단계 실패 graceful handling (3) JSONL 한 줄 = 하나의 encounter | — |
| **실행 방법** | Step 1: `src/pipeline/e2e.py` 작성. Step 2: `app.py`에 "Clinical Encounter" 탭 추가 (파일 업로드 + 텍스트 입력 + JSONL 다운로드). Step 3: jsdom 대신 Streamlit headless smoke (`streamlit run app.py --server.headless true` 로그 에러 0건). | feedback_write_then_verify (UI 변경 DoD) |
| **산출물 포맷** | `src/pipeline/e2e.py`, `app.py` diff, UI 스크린샷 3장 | — |
| **성공 기준** | - 3 합성 샘플 E2E 성공 (오디오 30초 → JSONL ≤60초) <br> - Streamlit 탭 정상 동작 (콘솔 에러 0) <br> - 파일 업로드 → 다운로드 flow 무결 | — |

### Track C — 평가·릴리즈

#### C1. 합성 샘플 시나리오 설계
| 항목 | 내용 | 검증 출처 |
|---|---|---|
| **Persona / Model** | emr-planner skill (Sonnet) | `.claude/skills/emr-planner/SKILL.md` |
| **입력 데이터** | 25개 도메인 (vet_stt_pipeline.py DOMAINS) | 실측 확인 |
| **판단 기준** | (1) 5건은 서로 다른 도메인 조합 (안과·내과·정형·피부·종양) (2) 각 30~90초 분량 한국어 스크립트 (3) 실환자 정보 0 (100% 합성) (4) 공개 가능 수준 일반 임상 발화 | feedback_source_only_data (합성 명시) |
| **실행 방법** | Step 1: 5개 시나리오 스크립트 작성 (S+O+A+P 4필드 모두 포함). Step 2: 각 시나리오의 기대 SNOMED 태깅 gold-label 작성. Step 3: 사용자에게 녹음 스크립트 전달. | — |
| **산출물 포맷** | `data/synthetic_scenarios/scenario_{1..5}.md` (스크립트 + gold-label) | — |
| **성공 기준** | - 5개 스크립트 완성 <br> - 각 gold-label에 기대 concept_id 명시 <br> - 사용자 리뷰 PASS | — |

#### C2. E2E 평가 스크립트
| 항목 | 내용 | 검증 출처 |
|---|---|---|
| **Persona / Model** | data-analyzer skill (Sonnet) | `.claude/skills/data-analyzer/` |
| **입력 데이터** | C1 gold-label, B4 E2E 출력 JSONL | — |
| **판단 기준** | (1) 필드별 precision/recall (2) SNOMED 태깅 일치율 (exact concept_id 또는 동의어 허용) (3) E2E latency p50/p95 (4) 통계만, 투자·임상 판단 금지 | data-analyzer SKILL 규칙 (수치만) |
| **실행 방법** | Step 1: `scripts/evaluate_e2e.py` 작성. Step 2: 5 샘플 실행 → 메트릭 계산. Step 3: `benchmark/v2_e2e_report.md` 생성. | — |
| **산출물 포맷** | `scripts/evaluate_e2e.py`, `benchmark/v2_e2e_report.md`, 차트 3장 (필드 정확도 / 태깅 일치 / latency) | — |
| **성공 기준** | - SOAP 필드 정확도 ≥80% <br> - SNOMED 태깅 일치율 ≥70% <br> - E2E latency p95 ≤ 60s (30s 오디오 기준) | — |

#### C3. v2.0 릴리즈 문서화
| 항목 | 내용 | 검증 출처 |
|---|---|---|
| **Persona / Model** | Utility (Haiku) — 문서 작업 | `Model_Selection_Rules.md §9` |
| **입력 데이터** | A·B·C 전 결과, 기존 README.md, CHANGELOG.md | 실측 Read 완료 |
| **판단 기준** | (1) README에 v2.0 파이프라인 다이어그램 (2) Before/After 벤치마크 (3) SNOMED 라이선스 안내 유지 (4) 환자 데이터 절대 미포함 | feedback_pdf_source_primary (실데이터 금지) |
| **실행 방법** | Step 1: README 업데이트 (파이프라인 섹션 + v2.0 수치). Step 2: CHANGELOG에 v2.0 항목. Step 3: `git tag v2.0` + 릴리즈 노트. | — |
| **산출물 포맷** | README diff, CHANGELOG diff, v2.0 릴리즈 노트 | — |
| **성공 기준** | - `.env` / 실데이터 유출 0 <br> - GitHub 릴리즈 v2.0 공개 <br> - 이직 보고서 §6.1 갱신 가능한 수치 확보 | project_vet_snomed_rag.md |

---

## §3. 산출물 맵 (파일 단위)

```
vet-snomed-rag/
├─ src/
│  ├─ pipeline/                  # 신규
│  │  ├─ stt_wrapper.py          # B1
│  │  ├─ soap_extractor.py       # B2
│  │  ├─ snomed_tagger.py        # B3
│  │  └─ e2e.py                  # B4
│  └─ retrieval/
│     ├─ hybrid_search.py        # A1 수정 (rerank 추가)
│     └─ reranker.py             # A1 신규
├─ data/
│  ├─ field_schema_v26.json      # B2 외부화
│  └─ synthetic_scenarios/       # C1 5건
├─ tests/
│  ├─ test_stt_wrapper.py
│  ├─ test_soap_extractor.py
│  └─ test_e2e.py
├─ scripts/
│  └─ evaluate_e2e.py            # C2
├─ benchmark/
│  ├─ v2_reranker_report.md      # A1
│  └─ v2_e2e_report.md           # C2
├─ app.py                         # B4 수정
├─ README.md                      # C3 수정
└─ CHANGELOG.md                   # C3 수정
```

---

## §4. 일정 (7일, 병렬 3-Track)

```
Day 1 ─ [A1 착수] [B1 착수]                      ← 2기 병렬 디스패치
Day 2 ─ [A1 smoke 3쿼리] [B1 완료] [B2 착수]     ← B2 vet-stt skill 로드
Day 3 ─ [A1 11쿼리 회귀] [B2 완료] [B3 착수]     ← B3 snomed-mapping skill 로드
Day 4 ─ [A1 완료] [B3 완료] [B4 착수] [C1 착수]
Day 5 ─ [B4 완료] [C1 완료→사용자 녹음 스크립트 전달]
Day 6 ─ [사용자 녹음 5건] [C2 평가 스크립트 작성]
Day 7 ─ [C2 실행+리포트] [C3 릴리즈]             ← v2.0 태그 push
```

### §4.1 Checkpoint (사용자 승인 필요 지점)

| Day | 체크포인트 | 승인 필요 |
|---|---|---|
| Day 2 | A1 3쿼리 smoke 결과 | 리랭커 도입 확정 or 롤백 |
| Day 3 | B2 3샘플 smoke 결과 | 필드 추출 품질 승인 |
| Day 5 | B4 E2E 1샘플 데모 | 릴리즈 진행 확정 |
| Day 7 | v2.0 릴리즈 직전 | 최종 승인 후 `git push origin v2.0` |

---

## §5. Quality Gate (종합)

### §5.1 Regression Guard
- v1.0 11-쿼리 회귀 **PASS 10/10 유지** (단 1건 실패 시 v1.0 롤백)
- v1.0 평균 latency **1,064ms 이하 유지** (리랭커 추가로 ±30% 이내)

### §5.2 v2.0 신규 목표
| 메트릭 | 목표 | 측정 |
|---|---|---|
| SOAP 필드 precision | ≥80% | C2 gold-label 대조 |
| SOAP 필드 recall | ≥70% | C2 |
| SNOMED 태깅 일치율 | ≥70% (exact concept_id) | C2 |
| E2E latency p95 (30s 오디오) | ≤60s | C2 |
| Streamlit 에러 | 0건 | B4 headless run |

### §5.3 Security Gate (security-audit skill 1% rule 적용)
- `.env` 실키 push 0 (`git log -p | grep -E "AIza|sk-ant-"` = 0 매치)
- 환자 데이터 push 0 (`cdw_vetstar.db` / `master.db` / `encounter.db` .gitignore 확인)
- 향남병원 녹음 push 0 (`data/synthetic_scenarios/`만 포함)

---

## §6. 독립 검증 (2계층)

### §6.1 Layer A — 작업분 검증 (실행자 재작업)
- 각 Track 담당 에이전트가 자체 smoke 테스트 실행
- 실패 시 해당 에이전트가 재작업

### §6.2 Layer B — 기존 결함 검증 (Reviewer 재설계)
- **Reviewer 에이전트 (Sonnet)** 을 Day 5·Day 7에 독립 디스패치
- 검증 대상: v1.0 regression 발생 여부 + v2.0 산출물 논리 정합성
- 체크리스트 자기검증 금지, 페르소나 기반 독립 탐색 (feedback_independent_verify_persona)

### §6.3 Reviewer Task Definition
| 항목 | 내용 |
|---|---|
| Model | Sonnet |
| 입력 | 본 설계서 + 실제 산출물 diff + 11쿼리 회귀 결과 + 5샘플 E2E 로그 |
| 판단 기준 | (1) 설계서 §1.1 10항목 모두 delivery 여부 (2) §5.1 regression 0 여부 (3) §5.2 수치 달성 여부 (4) §5.3 보안 gate 통과 |
| 실행 방법 | 블라인드 검증 (설계 의도 모르고 산출물만 수령) |
| 산출물 | `benchmark/v2_review.md` (PASS/FAIL + 실패 근거) |
| 성공 기준 | 모든 gate PASS + Reviewer 독립 승인 |

---

## §7. Output Quality Gate

### §7.1 JSONL 레코드 스키마

```json
{
  "encounter_id": "string",
  "timestamp": "ISO8601",
  "audio": {
    "path": "string | null",
    "duration_sec": "number",
    "language": "ko"
  },
  "stt": {
    "raw_text": "string",
    "normalized_text": "string (Step 0)"
  },
  "soap": {
    "subjective": "string",
    "objective": "string",
    "assessment": "string",
    "plan": "string"
  },
  "domains": ["string"],
  "fields": [
    {
      "field_code": "string (CA_OPH_IOP_OD_VAL)",
      "value": "number | string | null",
      "domain": "string",
      "validation": "PASS | WARN | CRITICAL | INVALID"
    }
  ],
  "snomed_tagging": [
    {
      "field_code": "string",
      "concept_id": "string | UNMAPPED",
      "preferred_term": "string",
      "semantic_tag": "string",
      "source": "INT | VET | LOCAL",
      "post_coordination": "string (SCG) | null",
      "mrcm_validated": "boolean",
      "confidence": 0.0
    }
  ],
  "latency_ms": {
    "stt": "number",
    "soap": "number",
    "snomed": "number",
    "total": "number"
  }
}
```

### §7.2 JSONL QG (O1~O12 해당분)
- O1 필드 누락 0건 (모든 레코드에 required 키)
- O3 값 타입 일치
- O6 concept_id는 RF2 원본 DB 실존 검증 (snomed-mapping audit-queries 참조)
- O11 DB Authoritative (매핑은 v1.0 DB 호출로만 획득, 에이전트 추론 금지)
- O12 NA 보호 (필드값 `null` vs `"NA"` 명확 구분)

---

## §8. 리스크 & 완화

| 리스크 | 확률 | 영향 | 완화책 |
|---|---|---|---|
| 리랭커 latency 과다 (>30%) | 중 | 중 | Day 2 smoke에서 조기 발견 시 BAAI → Jina API로 변경 |
| SOAP 추출 프롬프트 품질 미달 | 중 | 상 | Day 3 3샘플 smoke에서 조기 발견, vet_stt_pipeline 기존 프롬프트 그대로 보존 |
| ANTHROPIC_API_KEY 비용 초과 | 저 | 중 | 5샘플만 평가, 캐싱 적용, dry-run 모드 유지 |
| 사용자 녹음 지연 | 중 | 중 | Day 5에 시나리오 전달, Day 6 녹음 실패 시 AI 합성(gTTS)으로 fallback |
| v1.0 regression | 저 | 치명 | 모든 변경은 feature flag(`rerank=True/False`) 뒤에 격리, 기본값 off |
| 실데이터 유출 | 저 | 치명 | §5.3 security gate 3중 체크, Day 7 push 전 `git log -p` grep |

---

## §9. Day 1 착수 디스패치 플랜 (승인 요청)

승인 시 즉시 아래 2기 에이전트를 **단일 메시지 내 병렬 디스패치**합니다.

### §9.1 디스패치 1: Track A1 (Reranker 구현)
- subagent_type: `general-purpose`
- model: `sonnet`
- description: "vet-snomed-rag v2.0 Reranker 통합"
- prompt: 본 설계서 §2 A1 Task Definition 전문 + CLAUDE.md 준수 지시

### §9.2 디스패치 2: Track B1 (Whisper STT 래퍼)
- subagent_type: `general-purpose`
- model: `sonnet`
- description: "vet-snomed-rag v2.0 Whisper STT 래퍼"
- prompt: 본 설계서 §2 B1 Task Definition 전문 + CLAUDE.md 준수 지시

---

## §10. 승인 체크리스트 (사용자 확인)

- [ ] §1 스코프 (포함·제외) 동의
- [ ] §2 Task Definition 5항목 전 에이전트 확인
- [ ] §4 7일 일정 및 Checkpoint 동의
- [ ] §5 Quality Gate 목표 수치 동의
- [ ] §7 JSONL 스키마 동의
- [ ] §9 Day 1 디스패치 플랜 승인

**전 항목 OK 주시면 Day 1 에이전트 병렬 디스패치 실행합니다.**
