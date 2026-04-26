---
tags: [handoff, vet-snomed-rag, v2.0, 이직포트폴리오, 새세션]
date: 2026-04-23
status: handoff_ready
predecessor_session: 2026-04-22 (v2.0 릴리즈 Day 1~7)
purpose: GitHub Release 작성 이후 후속 4개 작업을 새 세션에서 진행
---

# vet-snomed-rag v2.0 후속 작업 핸드오프

> **새 세션 진입 즉시 본 파일을 Read로 로드**. 이후 §2의 우선순위 순서로 작업 진행.

---

## §1. 현재 상태 스냅샷 (2026-04-22 Day 7 종료 시점)

### §1.1 완료 사항 (100%)
| 영역 | 상태 | 증거 |
|---|---|---|
| v2.0 로컬 commit | ✅ `dda6bca feat: v2.0 End-to-End clinical encoding pipeline` | `git log -1` |
| v2.0 tag (annotated) | ✅ `v2.0` (tagger: ricocopapa) | `git tag -l "v2.0"` |
| GitHub main push | ✅ `de8a821 → dda6bca` | `git log origin/main -1` |
| GitHub tag push | ✅ new tag v2.0 | https://github.com/ricocopapa/vet-snomed-rag/releases/tag/v2.0 |
| pytest | ✅ 85 passed, 1 skipped | `pytest tests/` |
| Reviewer 감사 | ✅ RELEASE_APPROVED_WITH_KNOWN_LIMITATIONS | `benchmark/v2_review.md` §12 |
| 이직 보고서 §6.1 | ✅ v2.0 수치 반영 | `05_Output_Workspace/Career_Transition/20260419_Career_Transition_Report_v1.md` |

### §1.2 v2.0 최종 공식 수치 (이력서·포스트 인용 전용)

| Metric | Target | Text Mode | Audio Mode | Day 6 대비 개선 |
|---|---|---|---|---|
| Precision | ≥0.80 | **0.938** ✅ | **0.826** ✅ | +118% |
| Recall | ≥0.70 | **0.737** ✅ | **0.774** ✅ | +42% |
| SNOMED Match (synonym) | ≥0.70 | 0.584 ⚠️ | 0.250 ⚠️ | +446% |
| Latency p95 | ≤60s | **33.4s** ✅ | 60.5s ⚠️ | −74% |

**서사 요약 (한 문단)**:
> SNOMED CT VET 414K concepts 기반 End-to-End 임상 인코딩 파이프라인 v2.0 공개. Whisper STT → SOAP 4필드 구조화 → SNOMED 자동 태깅 + MRCM 검증 25도메인. Text Mode Precision 0.938 / Recall 0.737 / Latency p95 33.4s 달성. Day 6 초기 대비 Precision +118%, SNOMED 일치율 +446% 향상. 7일 단일 스프린트로 v1.0 검색 엔진 → v2.0 E2E 임상 AI 시스템 확장, 3-Track 병렬 에이전트 오케스트레이션 + Gemini 3.1 Flash Lite Preview 백엔드 + Gold-label 역공학 감사 통과 + Reviewer 블라인드 감사 CRITICAL 6건 전수 해소. MIT 라이선스.

### §1.3 핵심 리소스

| 자산 | 경로/URL |
|---|---|
| GitHub Repo | https://github.com/ricocopapa/vet-snomed-rag |
| Release Tag | https://github.com/ricocopapa/vet-snomed-rag/releases/tag/v2.0 |
| 로컬 프로젝트 | `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag` |
| Release Notes | `RELEASE_NOTES_v2.0.md` (173줄) |
| 이직 보고서 | `05_Output_Workspace/Career_Transition/20260419_Career_Transition_Report_v1.md` §6 |
| 본 핸드오프 | `05_Output_Workspace/Career_Transition/20260423_vet_snomed_rag_v2_handoff.md` |

### §1.4 마지막 미결 항목

**GitHub Release 작성** — 사용자 action 필요:
- URL: https://github.com/ricocopapa/vet-snomed-rag/releases/new
- Tag: `v2.0` 선택
- Title: `vet-snomed-rag v2.0 — End-to-End Clinical Encoding Pipeline`
- Body: `RELEASE_NOTES_v2.0.md` 내용 복사
- ✅ **새 세션 진입 시 이 작업 완료 여부 첫 확인** (아래 §4.0 참조)

---

## §2. 후속 작업 4개 — 우선순위 순

### Task 1 — LinkedIn/X 릴리즈 포스트 (P0, 30~60분)

**목적**: 이직 시장·면접관에게 v2.0 릴리즈 노출 → 포트폴리오 가시성 확보.

**입력 데이터**:
- v2.0 수치 (§1.2)
- Release Notes (`RELEASE_NOTES_v2.0.md`)
- 서사 요약 (§1.2 마지막 문단)
- 차트 3장 (`benchmark/charts/v2_field_accuracy.png`, `v2_snomed_match.png`, `v2_e2e_latency.png`)

**판단 기준**:
- 플랫폼별 톤: LinkedIn = 전문적 서사 + 수치 강조 / X = 간결 + 스레드
- 이모지 **절대 최소화** (사용자 CLAUDE.md 정책 + 한국 시니어 엔지니어 타겟)
- SNOMED 0.584 미달 **투명 공개** (한계 인정 → 전문성 어필)
- v2.1 로드맵 명시 (지속 개선 의지)

**실행 방법**:
1. LinkedIn 버전 (800~1200자):
   - 헤드라인: "수의 EMR 기획자 + AI Engineer — vet-snomed-rag v2.0 오픈소스 공개"
   - 3-Track 스프린트 프로세스 간략 소개
   - 공식 수치 테이블 (§1.2)
   - v2.1 로드맵 (실 수의사 녹음 + RAG 개선)
   - GitHub URL + Release Notes 링크
   - 해시태그: `#수의학 #SNOMEDCT #RAG #Gemini #오픈소스 #이직`
2. X 스레드 버전 (5~7 트윗, 각 280자):
   - 트윗 1: 릴리즈 + URL
   - 트윗 2~3: 아키텍처 + 수치
   - 트윗 4: Gold-label 역공학 감사 서사
   - 트윗 5: v2.1 로드맵

**산출물 포맷**:
- `05_Output_Workspace/Career_Transition/20260423_v2_release_linkedin_post.md`
- `05_Output_Workspace/Career_Transition/20260423_v2_release_x_thread.md`
- 사용자 최종 승인 후 직접 플랫폼에 게시

**성공 기준**:
- LinkedIn 초안 완성
- X 스레드 5~7 트윗 완성
- 이모지 10개 이하 (LinkedIn) / 3개 이하 (X)
- 수치 인용은 §1.2 정확히 복제 (반올림·가공 금지)
- SNOMED 0.584 미달을 "한계+로드맵"으로 투명 공개

---

### Task 2 — 이력서 PDF v2.0 수치 반영 확정 (P0, 1~2시간)

**목적**: 이직 지원 시 제출할 이력서 PDF에 v2.0 수치 최종 확정.

**입력 데이터**:
- 기존 이력서 초안: `05_Output_Workspace/Career_Transition/20260420_Resume_Draft_v1.1_LG_CNS.md`
- v2.0 수치 (§1.2)
- 이직 보고서 §6.1 (v2.0 반영 완료 상태)
- JD 분석: `05_Output_Workspace/Career_Transition/20260420_LG_CNS_JD_Gap_Analysis_v2.md`

**판단 기준**:
- 이력서는 **1~2페이지** 분량 준수 (시니어 한국 포맷)
- v2.0 수치 **정확 인용** (§1.2, 반올림·가공 금지)
- GitHub URL 명시 (hyperlink 가능 포맷)
- SNOMED 한계 투명 공개 — "Precision 0.938 달성, SNOMED 일치율 v2.1 개선 로드맵" 형식
- 수의 EMR 기획 10년 경력 + AI 엔지니어링 융합 강조

**실행 방법**:
1. `20260420_Resume_Draft_v1.1_LG_CNS.md` Read
2. §"대표 프로젝트" 섹션 v2.0 정보로 업데이트
3. §"기술 스택" Gemini 3.1 Flash Lite + ChromaDB + faster-whisper 등 추가
4. §"성과 지표" v2.0 수치 추가
5. MD → PDF 변환:
   - 옵션 A: Pandoc (`pandoc resume.md -o resume.pdf`)
   - 옵션 B: 브라우저 Print to PDF
   - 옵션 C: Typora / Obsidian PDF export
6. PDF 폰트·여백·색상 최종 검토 (한국어 폰트 필수)

**산출물 포맷**:
- `05_Output_Workspace/Career_Transition/20260423_Resume_v2_final.md`
- `05_Output_Workspace/Career_Transition/20260423_Resume_v2_final.pdf`

**성공 기준**:
- MD 초안 완성
- PDF 변환 성공 (한국어 폰트 깨짐 없음)
- v2.0 수치 정확 인용 (§1.2)
- GitHub URL 활성 링크
- 1~2페이지 분량 준수
- 사용자 검토 후 이직 지원용 승인

---

### Task 3 — 이직 지원 프로세스 킥오프 (P1, 지속)

**목적**: 실제 이직 지원 시 표준 첨부 자산 세트 확정 + 첫 지원서 제출.

**입력 데이터**:
- Task 2 산출 이력서 PDF
- 이직 보고서 §6 포트폴리오 자산
- GitHub Repo + Release Tag URL
- LG CNS JD 분석 (이미 완료, `20260420_LG_CNS_JD_Gap_Analysis_v2.md`)

**판단 기준**:
- 표준 첨부 세트: 이력서 PDF + 자기소개서 + GitHub URL + Release Notes 링크
- 지원 타겟 우선순위: LG CNS AI PM/PL → 기타 수의 EMR / 의료 AI 스타트업
- 지원서별 맞춤화 (JD별 핵심 키워드 반영)

**실행 방법**:
1. 표준 첨부 세트 정의 문서 작성: `20260423_application_asset_kit.md`
2. LG CNS 지원서 초안 작성 (JD Gap Analysis 활용)
3. 자기소개서 v2.0 수치 반영 버전 작성
4. 지원서 제출 체크리스트 (이력서/자소서/포트폴리오/레퍼런스)

**산출물 포맷**:
- `05_Output_Workspace/Career_Transition/20260423_application_asset_kit.md`
- `05_Output_Workspace/Career_Transition/20260423_LG_CNS_application_draft.md`
- `05_Output_Workspace/Career_Transition/20260423_cover_letter_v2.md`

**성공 기준**:
- 첨부 세트 정의 완료
- LG CNS 지원서 초안 완성
- 자소서 v2.0 반영 완료
- 사용자 검토 후 실제 지원 제출

---

### Task 4 — v2.1 로드맵 GitHub Issue 등록 (P2, 30분)

**목적**: v2.0 한계 4건을 공개 Issue로 등록하여 **지속 개선 엔지니어 이미지** 구축 + 면접 시 "다음 단계 계획" 어필 자산.

**입력 데이터**:
- v2.0 한계 (`README.md` Limitations 섹션)
- `benchmark/v2_review.md` 잔존 이슈
- v2.1 로드맵 (`RELEASE_NOTES_v2.0.md` v2.1 Planned)

**판단 기준**:
- Issue 4건 독립 등록 (서로 depend 표기)
- 각 Issue: 문제 기술 + 재현 방법 + 수락 기준 + 예상 공수
- Label 사용: `v2.1`, `enhancement`, `rag`, `benchmark`, `data` 등
- Milestone: `v2.1`

**실행 방법 (4 Issues)**:
1. **Issue #1 — Real veterinarian recordings for benchmark**
   - Title: "Replace gTTS synthetic audio with real veterinarian recordings"
   - Body: gTTS 한계 + 실녹음 확보 방안 + 수락 기준 (5+ 실녹음, Precision/Recall 유지 확인)
   - Labels: `v2.1`, `benchmark`, `data`
2. **Issue #2 — Improve SNOMED match rate (0.58 → 0.70+)**
   - RAG Top-1 vs gold IS-A 3+ 단계 불일치 근본 원인
   - 개선 방안: BM25 tuning / semantic_tag priority / LCA-weighted ranking
   - Labels: `v2.1`, `rag`, `enhancement`
3. **Issue #3 — Audio latency optimization (60.5s → <60s)**
   - Gemini 3.1 Flash Lite Preview vs 2.5 Flash Lite GA 비교
   - STT 파이프라인 병렬화 가능성
   - Labels: `v2.1`, `performance`
4. **Issue #4 — Claude backup backend for multi-provider resilience**
   - Gemini 503/rate limit 시 Claude fallback
   - 구현 스켈레톤 (기존 claude 경로 재활용)
   - Labels: `v2.1`, `reliability`

**산출물 포맷**:
- `05_Output_Workspace/Career_Transition/20260423_v2_1_issues_draft.md` (본문 템플릿 4개)
- GitHub Issues 실제 등록 (사용자 수동 or gh CLI)

**성공 기준**:
- Issue 4건 본문 초안 완성
- GitHub에 실제 등록 (v2.1 milestone 연결)
- 각 Issue가 재현 가능한 수락 기준 명시

---

## §3. 새 세션 진입 시 필수 로드 순서

```
1순위 (필수):
  ~/CLAUDE.md                                                        ← Hard Gate
  ~/.claude/CLAUDE.md                                                ← Router
  ~/claude-cowork/00_Core_Context/03_Working_Rules.md §1-1          ← Task Definition
  본 핸드오프 (20260423_vet_snomed_rag_v2_handoff.md)                ← 현황+작업목록

2순위 (작업별):
  Task 1 (LinkedIn/X):
    - RELEASE_NOTES_v2.0.md
    - benchmark/charts/*.png

  Task 2 (이력서):
    - 20260420_Resume_Draft_v1.1_LG_CNS.md
    - 20260420_LG_CNS_JD_Gap_Analysis_v2.md
    - 20260419_Career_Transition_Report_v1.md §6

  Task 3 (지원):
    - Task 2 산출 이력서 PDF
    - 20260420_LG_CNS_AI_PM_PL_JD_v1.md

  Task 4 (v2.1 Issues):
    - 프로젝트 README.md Limitations 섹션
    - benchmark/v2_review.md §11~§12
    - RELEASE_NOTES_v2.0.md v2.1 Planned
```

---

## §4. 새 세션 첫 프롬프트 템플릿

### §4.0 (필수) 세션 시작 직후 확인

```
20260423_vet_snomed_rag_v2_handoff.md 를 읽고 §1.4 미결 항목부터 확인해줘.
GitHub Release (https://github.com/ricocopapa/vet-snomed-rag/releases/tag/v2.0) 작성이
완료되었는지 먼저 확인 후 Task 진행 여부 결정.
```

### §4.1 Task 1 진입 프롬프트

```
vet-snomed-rag v2.0 릴리즈 포스트를 작성하자.
핸드오프: 05_Output_Workspace/Career_Transition/20260423_vet_snomed_rag_v2_handoff.md §2 Task 1
LinkedIn + X 스레드 2개 플랫폼. 이모지 최소화, 수치 §1.2 정확 인용.
```

### §4.2 Task 2 진입 프롬프트

```
vet-snomed-rag v2.0 수치를 반영한 이력서 최종 PDF를 만들자.
핸드오프: 05_Output_Workspace/Career_Transition/20260423_vet_snomed_rag_v2_handoff.md §2 Task 2
기존 20260420_Resume_Draft_v1.1_LG_CNS.md 기반으로 업데이트.
MD → PDF 변환 도구 선택 상담 후 진행.
```

### §4.3 Task 3 진입 프롬프트

```
이직 지원 프로세스 킥오프. LG CNS 지원서부터 작성하자.
핸드오프: 05_Output_Workspace/Career_Transition/20260423_vet_snomed_rag_v2_handoff.md §2 Task 3
Task 2 산출 이력서 PDF + JD Gap Analysis 기반.
```

### §4.4 Task 4 진입 프롬프트

```
vet-snomed-rag v2.1 GitHub Issues 4건을 초안 작성하자.
핸드오프: 05_Output_Workspace/Career_Transition/20260423_vet_snomed_rag_v2_handoff.md §2 Task 4
v2.0 한계 기반 4개 이슈: 실녹음, SNOMED 개선, Audio latency, Claude fallback.
```

---

## §5. 주의사항 (피드백 메모리 요약)

| ID | 핵심 | Task 적용 위치 |
|---|---|---|
| feedback_verify_before_answer | 메모리만으로 답변 금지, 실제 파일 확인 | 전 Task 공통 |
| feedback_output_mode | 산출물·리포트 = Full-Text, 대화·코드 = 간결 | Task 1·2 (Full-Text) |
| feedback_pdf_source_primary | 원본 절대 기준 | Task 2 (PDF 변환) |
| feedback_design_before_execute | 로드맵 ≠ 설계, 비가역 작업은 설계 후 실행 | Task 3 (지원 제출은 비가역) |
| feedback_write_then_verify | Write 후 Read-back 검증 | 전 Task 공통 |
| feedback_parallel_dispatch | 독립 작업 병렬 | Task 1·2 병렬 가능 (Task 3·4는 Task 2 의존) |

---

## §6. 산출물 위치 인덱스

### 포트폴리오 자산 (공개)
- GitHub: https://github.com/ricocopapa/vet-snomed-rag
- Release: https://github.com/ricocopapa/vet-snomed-rag/releases/tag/v2.0

### 로컬 프로젝트
- 경로: `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag`
- 주요 파일:
  - `README.md` (v2.0 What's New · Architecture · Benchmark · Limitations · v2.1 Roadmap)
  - `CHANGELOG.md` (v2.0.0 entry)
  - `RELEASE_NOTES_v2.0.md` (173줄, GitHub Release 본문)
  - `benchmark/v2_e2e_report_text.md` (텍스트 모드 수치)
  - `benchmark/v2_e2e_report_audio.md` (오디오 모드 수치)
  - `benchmark/v2_headline_metrics.md` (이력서 인용용)
  - `benchmark/v2_review.md` (Reviewer 최종 감사)
  - `benchmark/v2_snomed_analysis.md` (SNOMED IS-A 거리 분석)
  - `benchmark/charts/*.png` (4장)
  - `data/synthetic_scenarios/GOLD_AUDIT.md` (역공학 감사 30건)

### 이직 관련 문서 (05_Output_Workspace/Career_Transition/)
- `20260419_Career_Transition_Report_v1.md` (이직 보고서 — §6.1 v2.0 반영 완료)
- `20260420_Resume_Draft_v1.1_LG_CNS.md` (이력서 v1.1 — Task 2 업데이트 대상)
- `20260420_LG_CNS_AI_PM_PL_JD_v1.md` (LG CNS JD 원문)
- `20260420_LG_CNS_JD_Gap_Analysis_v2.md` (JD 갭 분석)
- `20260422_vet_snomed_rag_v2_master_design_v1.md` (v2.0 마스터 설계서)
- `20260423_vet_snomed_rag_v2_handoff.md` (본 파일)

### 메모리 (auto-memory)
- `project_vet_snomed_rag.md` (v2.0 완료 상태 반영 예정 — 본 핸드오프 작성 후 업데이트)

---

## §7. 완료 상태 체크리스트 (세션 종료 전 확인)

### Day 7 종료 시점 (2026-04-22)
- [x] v2.0 commit + tag 생성
- [x] GitHub main push + v2.0 tag push
- [x] pytest 85 passed, 1 skipped
- [x] Reviewer 감사 RELEASE_APPROVED
- [x] 이직 보고서 §6.1 업데이트
- [x] 핸드오프 문서 작성 (본 파일)
- [ ] GitHub Release 작성 ← **미결 (사용자 action)**

### 후속 세션 완료 목표
- [ ] Task 1: LinkedIn/X 포스트 게시
- [ ] Task 2: 이력서 PDF 확정
- [ ] Task 3: LG CNS 지원서 제출
- [ ] Task 4: v2.1 Issues 4건 등록

---

**세션 종료 시각**: 2026-04-22 18:30 KST
**다음 세션 시작 권장**: GitHub Release 작성 완료 후 즉시 또는 다음 날
**핸드오프 작성자**: Claude Opus 4.7 (1M context)
