---
tags: [vet-snomed-rag, v2.9, roadmap, handoff]
date: 2026-04-26
status: 묶음 H 종결 (commit 40c6d2a, GitHub v2.8/v2.8.1 publish) — 다음 cycle 후보 R-10/R-8
prev_state: v2.8.1 묶음 H 종결 (R-7.1 + R-9), N-3 smoke 4/4 PASS, GitHub Release v2.8/v2.8.1 published
next_target: v2.9+ (R-10 PAYG 또는 R-8 embedder 또는 신규 phase)
session_anchor: 2026-04-26 (v2.8.1 commit + Release publish 직후)
related:
  - docs/20260427_v2_8_roadmap_handoff.md (v2.8 종결 기록)
  - docs/20260427_r7_synthesis_diagnosis.md (R-7 진단 노트)
  - RELEASE_NOTES_v2.8.md (v2.8 릴리즈 노트)
  - RELEASE_NOTES_v2.8.1.md (v2.8.1 릴리즈 노트)
  - memory/project_vet_snomed_rag.md
---

> **2026-04-26 묶음 H 종결 갱신:**
> R-7.1 + R-9 완료. _SYNTH_PROMPT 강화("단 하나도 누락 없이") + _format_external_summary 한도 확장
> ([:3]/[:5] → [:10]/[:10]/[:5] web 신규). 단위 **219 PASS** (+4). **N-3 smoke 4/4 PASS** (인용률 100%×3 회복).
> 11쿼리 회귀 none·gemini 10/10. .env.example TAVILY 추가 + README setup 보강.
> GitHub Release v2.8 (9e5f8f6) + v2.8.1 (40c6d2a) publish.
> R-7 본질 fix 사이클 종결. v2.9+ 후보: R-10 PAYG / R-8 embedder.

# v2.8 → v2.9 핸드오프

> **사용자 선호:** 프로젝트 완성도 우선·이력서/자소서 후순위 (`feedback_project_first_resume_later.md`).

---

## §1. 현재 상태 (v2.8 종결, 2026-04-26)

### 1-1. v2.8 누적 결과

| 항목 | 결과 |
|---|---|
| 단위 테스트 | **215 PASS** (+8 신규) |
| 11쿼리 회귀 RERANK=1 | none **10/10** + gemini **10/10** (회귀 0) |
| N-3 smoke #1 합성 적용률 | **3/3 PASS** ← R-7 핵심 |
| N-3 smoke #3 회귀 0 | **2/2 PASS** |
| N-3 smoke #4 비용 | **3/3 PASS** |
| N-3 smoke #2 인용률 | **2/3 PARTIAL** (T12만 60%) ← v2.9 R-7.1 |
| agentic 파이프라인 RPD | 20 → **500** (3.1-flash-lite-preview) |
| commit | `9e5f8f6` |
| GitHub Release | 미생성 (사용자 push + tag 결정 대기) |

### 1-2. 미결 사항 (우선순위)

1. **R-7.1 (신규) — synthesizer 인용률 강화** ← v2.9 우선 후보
   - **현상:** T12 (multi-iter, umls 5건 누적) → 합성 답변 본문에 3건만 인용 → 60% (#2 80% 미달)
   - **추정 원인:** R-7 누적 보존의 부수 효과로 LLM 합성 입력이 5건으로 늘었지만, 합성 프롬프트가 "모든 식별자 인용"을 강제하지 않음
   - **위치:** `src/retrieval/agentic/synthesizer.py:31-51` (`_SYNTH_PROMPT`)

2. **R-9 (신규) — onboarding 가이드 갱신** (가벼운 정비)
   - v2.6 R-5 venv 동기화 누락 사고 방지
   - README setup 섹션 + `.env.example` (TAVILY_API_KEY 포함 5종)
   - 시스템 의존성 (`brew install poppler tesseract`) 명시

3. **R-10 (신규) — Tavily/Gemini PAYG 전환 시뮬** (사용자 카드 등록 결정 필요)
   - Gemini RPD 500 (3.1-flash-lite-preview) 한도는 Production 운영 충분 — 현 시점 PAYG 비필수
   - Tavily Free 1,000 credits/월 한도도 0.2% 사용 — 운영 모니터링만으로 가능
   - PAYG 전환은 **운영 견고성 보강 차원** — 후순위

4. **R-8 (heavy) — embedder 교체** (BioBERT/PubMedBERT)
   - ChromaDB 366,570 재임베딩 (수시간~하루)
   - 별도 phase 권고 (v2.9+ 또는 v3.0)

5. **GitHub Release v2.8 publish** (R-1 패턴)
   - `git push origin main` + `git tag v2.8` + `gh release create v2.8`
   - 사용자 명시 승인 후

### 1-3. 환경·자산

- **로컬 경로:** `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag`
- **venv:** `venv/` (Python 3.14.4, pytest 9.0.3)
- **인덱스:** `data/chroma_db/` (366,570) + `data/snomed_ct_vet.db` (414,860)
- **사용자 .env 키:** `GOOGLE_API_KEY` ✓ / `UMLS_API_KEY` ✓ / `NCBI_API_KEY` ✓ / `TAVILY_API_KEY` ✓ / `ANTHROPIC_API_KEY` placeholder
- **회귀 산출물:** `graphify_out/regression_metrics.json` (v2.8 갱신, 10/10), `graphify_out/r7_after_fix_smoke.log`, `graphify_out/v2_8_regression.log`
- **GitHub:** main 동기화 완료, tag v2.6/v2.7 published. **v2.8 미push, 미tag**

### 1-4. v2.9 진입 시점 working tree

```bash
git status --short  # clean
git log -3 --oneline
# 9e5f8f6 feat(v2.8): 묶음 G — R-7 누적 보존 + 429 retry + R-2.1 metric + agentic 모델 RPD 500 교체
# 5daf9e9 docs(v2.8): v2.7 status 종결 갱신 + v2.8 진입 핸드오프 신규
# e244d42 docs(v2.7): release notes + CHANGELOG entry [2.7.0]
git tag --sort=-creatordate | head -3
# v2.7  v2.6  v2.5.1
```

---

## §2. 후속 작업 후보 + 우선순위

| 코드 | 작업 | 도메인 가치 | 회귀 위험 | 비용 | 즉시 가능 | 권장도 |
|---|---|---|---|---|---|---|
| **R-7.1** | synthesizer 프롬프트 강화 — 누적 외부 결과 모두 인용 강제 | ★★★ N-3 smoke #2 4/4 회복 | 낮음 (프롬프트만) | 시간 30m-1h | ✅ 즉시 | ★★★ |
| **R-9** | onboarding 가이드 (README + .env.example) | ★★ 환경 issue 방지 | 0 (docs only) | 30m | ✅ 즉시 | ★★ |
| **GitHub Release v2.8** | push + tag + release notes | ★★ 포트폴리오/이력서 자산 | 0 | 15m | ✅ 사용자 승인 시 | ★★ |
| **R-10** | Tavily/Gemini PAYG 시뮬 | ★ 운영 견고성 | 낮음 | ~$0.10 | ⚠️ 카드 등록 | ★ |
| **R-8** | embedder 교체 (BioBERT/PubMedBERT) | ★ 도메인 임베딩 ↑ | **높음** (ChromaDB 재구축) | 수시간~하루 | ⚠️ heavy | ★ |

---

## §3. 작업별 Task Definition (5항목)

### §3-1. R-7.1 — synthesizer 인용률 강화

**§3-1-1. 입력 데이터**
- 현 합성 프롬프트: `src/retrieval/agentic/synthesizer.py:31-51` `_SYNTH_PROMPT`
- 현 요구사항 #2: "외부 도구 markdown 섹션의 식별자(CUI / PMID / ICD10CM·MSH 코드)를 본문에서 명시 인용·해설하라" (부드러운 권고, "모든" 강제 없음)
- T12 실측 (commit 9e5f8f6 직후 smoke):
  - external `umls`: 5건 누적 (multi-iter 4회 reformulate)
  - 합성 답변 본문: 5건 중 **3건 인용** (60%, 임계값 80% 미달)
- 산출물 노트: `docs/20260427_r7_synthesis_diagnosis.md` §6-1

**§3-1-2. 판단 기준**
- N-3 smoke #2 인용률: 3/3 또는 4/4 PASS (현 2/3 → 모두 PASS 회복)
- 회귀 0 — 단위 215 PASS 유지 + 11쿼리 회귀 none·gemini 10/10 유지
- 합성 답변 quality 유지 (LLM이 인용 강제로 어색해지지 않도록)

**§3-1-3. 실행 방법** (3안 — 사용자 선택)

| 옵션 | 내용 | 장점 | 단점 |
|---|---|---|---|
| **(a) 프롬프트 강화** | "모든 식별자 인용" 명시 + "n/N개 인용" 형식 강제 | 변경 최소, 비용 0 | LLM이 어색하게 모든 코드 나열 가능 |
| **(b) 누적 상한** | source별 최대 3건/이상은 입력에서 제외 | 합성 본질 유지 | 정보 손실 가능 |
| **(c) 임계 완화** | 인용률 ≥ 80% **또는** 핵심 ≥ 3건 | metric 합리화 | 본질 회피 |

권장: **(a) 프롬프트 강화 + 단위 테스트 1건 추가** (인용 강제 동작 검증)

**§3-1-4. 산출물**
- `synthesizer.py` `_SYNTH_PROMPT` 수정
- 신규 단위 테스트 1건 (모든 식별자 인용 강제 검증, mock LLM)
- smoke 재실행 → `graphify_out/r7_1_after_fix_smoke.log`
- `RELEASE_NOTES_v2.9.md` (R-7.1 + R-9 묶음)

**§3-1-5. 성공 기준**
- N-3 smoke #2 인용률 **3/3 PASS** (T12 5/5 또는 ≥80%)
- 단위 ≥ 216 PASS
- 11쿼리 회귀 none·gemini 10/10 유지

---

### §3-2. R-9 — onboarding 가이드 갱신

**§3-2-1. 입력 데이터**
- v2.6 R-5 사고: pdfplumber/pdf2image/pytesseract venv 미설치 → test_pdf_reader 13건 ImportError
- 현재 README.md (확인 필요)

**§3-2-2. 판단 기준**
- 신규 사용자가 `git clone` → setup 단일 명령으로 단위 207+ PASS 가능
- .env 키 5종 (GOOGLE/UMLS/NCBI/TAVILY/ANTHROPIC) 발급 가이드 명확

**§3-2-3. 실행 방법**
1. README.md `## Setup` 섹션 추가 또는 갱신:
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   brew install poppler tesseract  # macOS
   cp .env.example .env  # 키 5종 발급 후 채움
   pytest tests/ -q
   ```
2. `.env.example` 갱신 — 5종 키 placeholder + 발급 URL 주석
3. (선택) Quick Start 섹션 — 한 명령 demo

**§3-2-4. 산출물**
- README.md 갱신
- `.env.example` 갱신

**§3-2-5. 성공 기준**
- 새 venv 생성 → setup → 단위 215+ PASS 재현 가능

---

### §3-3. GitHub Release v2.8 publish

**§3-3-1. 실행 방법**
```bash
cd ~/claude-cowork/07_Projects/vet-snomed-rag
git push origin main
git tag v2.8 9e5f8f6
git push origin v2.8
gh release create v2.8 --title "v2.8 — R-7 누적 보존 + 429 retry + R-2.1 metric + RPD 500 모델 교체" \
  --notes-file RELEASE_NOTES_v2.8.md
```

**§3-3-2. 성공 기준**
- `gh release list` 에 v2.8 표시
- 태그 v2.8이 commit 9e5f8f6 가리킴

---

## §4. 우선순위 권고

### 4-1. 권장 순서

1. **R-7.1** (인용률 강화) — N-3 smoke #2 회복, v2.8 잔여 PARTIAL 해소
2. **R-9** (onboarding) — R-7.1 작업 중간 끼워넣기 가능 (docs only)
3. **GitHub Release v2.8** — 사용자 승인 시 즉시 (R-7.1 결과 v2.9에 묶을지 별도 v2.8.1로 패치 release할지 결정)
4. **R-10** (PAYG) — 후순위, 운영 견고성
5. **R-8** (embedder) — heavy, v3.0 phase

### 4-2. 권장 묶음

- **묶음 H (잔여 정리):** R-7.1 → R-9 → Release v2.8(현 기준) 또는 v2.8.1(R-7.1 포함 패치)
- **별도 후순위:** R-10 (사용자 결정 시)
- **별도 Phase:** R-8 v3.0+

### 4-3. 비추천 패턴

- R-8 단독 (heavy 인프라 — v2.8 release 직후 ChromaDB 재구축 시 운영 안정성 위험)
- R-7.1 없이 R-9만 진행 (인용률 PARTIAL 미해결 상태로 release 부담)

---

## §5. 재개 가이드 (다음 세션 진입 시)

### 5-1. 첫 명령

```bash
cd ~/claude-cowork/07_Projects/vet-snomed-rag
git status --short                              # clean 확인
git log -3 --oneline                            # 9e5f8f6 v2.8 commit 확인
venv/bin/python -m pytest tests/ -q | tail -3   # 215 PASS baseline 확인
cat docs/20260427_v2_9_roadmap_handoff.md | head -80  # 본 문서 §1-2
```

### 5-2. 핸드오프 로드 명령 예시

```
이 v2.9 핸드오프대로 R-7.1 진행해줘
또는 묶음 H (R-7.1 → R-9) 진행해줘
또는 GitHub Release v2.8 먼저 publish해줘
또는 권장으로 진행해줘  (= 묶음 H 시작)
```

### 5-3. 사용자 의사결정 필요 사항

1. **R-7.1 어느 옵션** — (a) 프롬프트 강화 / (b) 누적 상한 / (c) 임계 완화
2. **GitHub Release v2.8 시점** — 즉시(현재 기준) vs R-7.1 후 v2.8.1 패치
3. **R-10 PAYG 활성화 의사** — 카드 등록 + Gemini 카드/Tavily 카드 동시 결정

---

## §6. 위험·블로커

| 위험 | 영향 | 회피 |
|---|---|---|
| R-7.1 프롬프트 강화가 합성 quality 저하 | 답변 자연스러움 ↓ | 단위 테스트 + smoke 답변 육안 검토 |
| R-9 README 갱신 시 기존 사용자 혼란 | 기존 docs와 충돌 | 변경 사항만 추가, 기존 명령은 유지 |
| GitHub Release v2.8이 R-7.1 잔여로 부담 | 인용률 PARTIAL 노출 | release notes에 "R-7.1 후속" 명시 (이미 됨) 또는 v2.8.1 패치로 분리 |
| Gemini 3.1 preview 모델 deprecation | 향후 GA 출시 시 모델 ID 변경 필요 | release notes에 모델 ID 명시 (이미 됨) |

---

## §7. 핸드오프 성공 기준 체크리스트

다음 세션에서 본 핸드오프를 입력으로 사용 시 1:1 PASS/FAIL 표로 검증:

| # | 항목 | PASS 조건 |
|---|---|---|
| H-1 | 현 상태 검증 | git clean / 단위 215 PASS / 11쿼리 none·gemini 10/10 / 9e5f8f6 commit 확인 |
| H-2 | 사용자 R-x 또는 묶음 선택 명확 | R-7.1 / R-9 / Release / R-10 / R-8 또는 묶음 명시 |
| H-3 | 선택 작업 §3-x Task Definition 5항목 사용자 승인 | 입력·판단·실행·산출·성공기준 동의 |
| H-4 | 사용자 사전 액션 (필요 시) 완료 | 예: R-7.1 옵션 선택 / Release 시점 결정 |
| H-5 | 작업 완료 시 §3-x §3-x-5 성공 기준 1:1 PASS | 모든 PASS 조건 충족 |
| H-6 | 회귀 0 보장 | 단위 ≥215 PASS + 11쿼리 회귀 none·gemini 10/10 유지 |
| H-7 | 메모리 갱신 | `project_vet_snomed_rag.md` v2.9 진입 사실 추가 |
| H-8 | 핸드오프 갱신 또는 종결 | 본 문서 status=종결 + v2.9→v3.0 핸드오프 신규 또는 본 문서에 결과 누적 |

---

## §8. 부록 — v2.8 산출물 인덱스

### 8-1. v2.8 commit 이력

| commit | 내용 |
|---|---|
| `9e5f8f6` | feat(v2.8): 묶음 G — R-7 누적 보존 + 429 retry + R-2.1 metric + agentic 모델 RPD 500 교체 |
| `5daf9e9` | docs(v2.8): v2.7 status 종결 갱신 + v2.8 진입 핸드오프 신규 |

### 8-2. v2.8 신규/변경 파일 (commit 9e5f8f6)

| 분류 | 경로 |
|---|---|
| 코어 (R-7) | `src/retrieval/agentic_pipeline.py` (누적/dedup/관찰성) |
| 코어 (R-7) | `src/retrieval/agentic/synthesizer.py` (429 retry/_parse_retry_delay) |
| 모델 교체 | `src/retrieval/agentic/loop_controller.py`, `relevance_judge.py`, `query_complexity.py` |
| 테스트 신규 | `tests/test_synthesizer.py` (+8) |
| 테스트 갱신 | `tests/test_query_complexity.py` (모델 ID) |
| 스크립트 (R-2.1) | `scripts/n3_synthesis_smoke.py` (metric 교체) |
| 산출물 | `graphify_out/regression_metrics.json`, `backend_comparison.md` |
| 캐시 | `src/retrieval/cache/reformulations_gemini.json` |
| 문서 신규 | `docs/20260427_r7_synthesis_diagnosis.md` |
| 문서 신규 | `RELEASE_NOTES_v2.8.md` |
| 문서 갱신 | `docs/20260427_v2_8_roadmap_handoff.md` (status 종결) |

### 8-3. v2.8 누적 메트릭

- 단위 테스트: **215 PASS** (web 12 + router 5 + R-7 8 + 기존 190)
- 11쿼리 정밀 회귀: none **10/10**, gemini **10/10** (회귀 0)
- N-3 smoke: #1 합성 적용률 3/3, #2 인용 2/3 (T12 60% 잔여), #3 회귀 0 2/2, #4 비용 3/3
- 외부 도구: 3종 (UMLS + PubMed + Tavily Web)
- agentic 파이프라인 모델: **gemini-3.1-flash-lite-preview** (RPD 500)
- GitHub Release: v2.6, v2.7 published / v2.8 미발행

---

**핸드오프 작성 완료. 다음 세션에서 §5-2 형식으로 명령하여 v2.9 진입.**
