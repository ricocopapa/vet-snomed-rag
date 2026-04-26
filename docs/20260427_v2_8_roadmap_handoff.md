---
tags: [vet-snomed-rag, v2.8, roadmap, handoff]
date: 2026-04-26
status: 묶음 G 단위 fix 완료 / production 검증 보류 (Gemini 한도)
prev_state: v2.7 R-3 Tier C Tavily Web Search 종결, GitHub Release v2.7 published
next_target: v2.8 production smoke + 11쿼리 회귀 (한도 reset 또는 R-10 PAYG 후)
session_anchor: 2026-04-26 (R-7 단위 fix 완료 시각)
related:
  - docs/20260427_r7_synthesis_diagnosis.md (R-7 진단 + fix 노트)
  - docs/20260427_v2_7_roadmap_handoff.md (v2.7 종결 기록)
  - docs/20260426_v2_6_roadmap_handoff.md (v2.6 종결 기록)
  - RELEASE_NOTES_v2.7.md, RELEASE_NOTES_v2.6.md
  - memory/project_vet_snomed_rag.md
---

> **2026-04-26 갱신 (R-7 단위 fix 완료):**
> 핸드오프 §3-1 추정("마지막 iter만 보존")은 코드 분석 가설. 실제 진단 결과 직접 원인은
> **Gemini Free Tier 일일 20 RPD 한도 초과 → 합성기 fallback (used=False)**.
> fix 옵션 (γ) 적용: 누적 보존(잠재 결함 해소) + 429 retry/backoff + synthesis_method/fallback_reason 노출.
> 단위 215 PASS. production smoke + 11쿼리 회귀는 한도 reset 또는 R-10 PAYG 활성화 후 재실행 필수.
> 진단 상세 → `docs/20260427_r7_synthesis_diagnosis.md`

# v2.7 → v2.8 핸드오프 (다음 세션 진입용)

> **사용자 선호:** 프로젝트 완성도 우선·이력서/자소서 후순위 (`feedback_project_first_resume_later.md`).
> 본 핸드오프는 v2.7 (R-3 Tier C Tavily Web Search) 종결 시점에서 **R-7 (synthesis 미트리거 본질 분석)** 을 v2.8 우선 후보로 분해한다.

---

## §1. 현재 상태 (v2.7 종결, 2026-04-26)

### 1-1. 완료 단계 — v2.7 누적

| 단계 | 결과 |
|---|---|
| v2.5 Tier A·B (UMLS + PubMed) | 53 단위 PASS |
| v2.6 묶음 A (agentic 정밀 회귀 + LLM 합성) | 180 단위 + agentic 12/12 |
| v2.6 묶음 B (한국어 사전 v1.1) | T9 회복 |
| v2.6 T7 (영어 약식 v1.2) | T7 none 10/10 |
| v2.6 R-4 (T9 vector drift 정밀화) | none·gemini 둘 다 10/10 Top-1 |
| v2.6 R-5 (PDF reader 13건 진단) | 환경 의존만, v2.2 결함 0건 |
| v2.6 R-6 + R-1 (release notes + git push v2.6) | GitHub Release v2.6 published |
| **v2.7 R-3 (Tier C Tavily Web Search)** | **단위 207 PASS, smoke §3-3-5 4/4, 회귀 0, GitHub Release v2.7 published** |

### 1-2. 미결 사항 (R-7 + R-2 보강 + 운영)

1. **R-7 synthesis 미트리거 본질 분석** ← v2.8 우선 후보
   - **현상:** v2.6 R-2 N-3 smoke에서 T13 (`rare feline endocrine literature`, pubmed) / T14 (`고양이 당뇨 ICD-10 매핑`, umls)이 외부 도구는 호출되었음에도 `synthesis_used=False`
   - **추정 원인:** `agentic_pipeline.py` multi-iter loop에서 `last_external = iter_external` (line 236)으로 **마지막 iter만 보존**. 마지막 iter에서 외부 호출이 없으면 `synthesis_used=False`. 이전 iter에 누적된 외부 결과는 합성에 반영 안 됨
   - **위치:** `src/retrieval/agentic_pipeline.py:120-265` (loop) + `synthesizer.synthesize()` 진입 조건 (line 196)

2. **R-2 #1 (+30% 길이) 기준 재정의** — v2.6 부분 종결의 잔여
   - 현 기준 "+30% 길이"는 LLM 합성의 본질(통합·압축)과 맞지 않음 (T12에서 base 7922→3020자, 0.38x)
   - 후보 metric: `synthesis_used=True` 비율 / 인용 정확도 ≥80% (이미 v2.6에서 PASS) / 합성 답변 quality 별도 평가
   - R-7과 함께 묶거나 별도 작업

3. **Tavily 비용 모니터링** — v2.7 운영 중 Tavily Free 1,000 credits/월 한도 초과 여부
   - 현재 사용량: smoke ~2 credits / 한도 0.2%
   - 운영 회귀 + agentic 11쿼리 실행 시 web 키워드 케이스 0 → 추가 사용 0
   - 한도 초과 시 Pay As You Go 전환 (1 credit = $0.008)

4. **`ANTHROPIC_API_KEY` `.env` 빈 값** — Claude fallback 미가용 (영향 0, 진행 옵션 다양화 차원만)

5. **test_pdf_reader.py 13건** — v2.6 R-5에서 venv 동기화로 해소. 단위 207 PASS에 포함됨. 향후 동일 issue 방지를 위해 README 또는 onboarding 가이드에 `pip install -r requirements.txt` 명시 검토 (선택)

### 1-3. 환경·자산

- **로컬 경로:** `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag`
- **venv:** `venv/` (Python 3.14.4, pytest 9.0.3) + pdfplumber/pdf2image/pytesseract 설치 완료
- **인덱스:** `data/chroma_db/` (366,570) + `data/snomed_ct_vet.db` (414,860)
- **사용자 .env 키:** `GOOGLE_API_KEY` ✓ / `UMLS_API_KEY` ✓ (36자) / `NCBI_API_KEY` ✓ (36자) / `TAVILY_API_KEY` ✓ (58자, v2.7에서 등록) / `ANTHROPIC_API_KEY` placeholder
- **회귀 산출물:** `graphify_out/regression_metrics_rerank.json` (v2.7 갱신, none·gemini 10/10), `agentic_regression_metrics.json`, `v2_7_tier_c_web_smoke.log` (Tavily 실 호출)
- **GitHub:** main 브랜치 origin 동기화 완료, tag v2.6 / v2.7 published

### 1-4. v2.8 진입 시점 working tree

```bash
git status --short  # clean (모든 변경 commit + push 완료)
git log -3 --oneline
# e244d42 docs(v2.7): release notes + CHANGELOG entry [2.7.0]
# d1d1880 feat(v2.7): R-3 Tier C — Tavily Web Search 통합
# ab3a669 docs(v2.6): release notes + CHANGELOG + 핸드오프 + 검증 노트
git tag --sort=-creatordate | head -3
# v2.7  v2.6  v2.5.1
```

---

## §2. 후속 작업 후보 + 우선순위

| 코드 | 작업 | 도메인 가치 | 회귀 위험 | 비용 | 즉시 가능 | 권장도 |
|---|---|---|---|---|---|---|
| **R-7** | synthesis 미트리거 본질 분석 + fix (T13/T14) | ★★★ multi-iter loop 본질 결함 해소 | 중 (loop 구조 변경) | 시간 1-2h | ✅ 즉시 | ★★★ |
| **R-2.1** | +30% 길이 기준 재정의 + smoke metric 재설계 | ★★ 검증 metric 정합성 | 낮음 | 시간 30m-1h | ✅ R-7과 묶음 권장 | ★★ |
| **R-8** (신규) | T9 vector drift 추가 정밀화 — embedder 교체 (BioBERT/PubMedBERT) | ★ 도메인 임베딩 품질 ↑ | **높음** (ChromaDB 재구축, 366,570 재임베딩) | **수시간~하루** | ⚠️ heavy | ★ |
| **R-9** (신규) | onboarding 가이드 갱신 — `pip install -r requirements.txt` + venv setup 명시 | ★ 환경 issue 방지 | 0 (docs only) | 30m | ✅ 즉시 | ★ |
| **R-10** (신규) | Tavily Pay As You Go 전환 시뮬레이션 (Free 한도 초과 검증) | ★ 운영 견고성 | 낮음 | Tavily 추가 credit ~$0.10 | ⚠️ 사용자 카드 등록 결정 | ★ |

---

## §3. 작업별 Task Definition (5항목)

### §3-1. R-7 synthesis 미트리거 본질 분석 + fix

**§3-1-1. 입력 데이터**
- 현상 케이스:
  - T13 `rare feline endocrine literature` → `external_results['pubmed']` 존재, `synthesis_used=False`
  - T14 `고양이 당뇨 ICD-10 매핑` → `external_results['umls']` 존재, `synthesis_used=False`
- 코드 위치:
  - `src/retrieval/agentic_pipeline.py:116-265` (multi-iter loop)
  - 합성 트리거: `:196` `if iter_external and any(iter_external.values()):`
  - 마지막 iter 보존: `:236` `last_external = iter_external`
- 진단 도구: `scripts/n3_synthesis_smoke.py` (loop_trace 노출)

**§3-1-2. 판단 기준**
- T13/T14 케이스에서 `synthesis_used=True` 회복
- 회귀 0 — 기존 12 단위(`test_synthesizer.py`) + 7 단위(`test_agentic_tier_b.py`) PASS 유지
- 11쿼리 회귀 (none + gemini) 10/10 유지

**§3-1-3. 실행 방법** (옵션 분석 → 사용자 선택)

진단 단계 (필수, ~15분):
1. T13/T14 실행하면서 `loop_trace`의 각 iter `external_counts` print
2. 마지막 iter에서 외부 도구 호출 여부 + sub_results 내 external 확인
3. 원인 식별: (a) 마지막 iter rewrite 경로에서 외부 도구 미호출 / (b) 마지막 iter sub_results['external'] 누락 / (c) iter_external dict가 비어있음

수정 옵션 (3안):
- **(a) 누적 보존:** `iter_external` 누적해서 모든 iter의 외부 결과를 보존 → 합성 입력으로 사용
- **(b) Final 단계 합성:** loop 종료 후 누적된 모든 iter의 external을 통합해 합성 한 번 더
- **(c) 트리거 조건 강화:** `synthesizer.synthesize()` 진입 조건을 마지막 iter에 한정 → 누적된 외부 결과 모두 입력

**§3-1-4. 산출물 포맷**
- 변경 코드: `agentic_pipeline.py` (loop 구조 또는 last_external 누적)
- 진단 노트: `docs/20260427_r7_synthesis_diagnosis.md`
- smoke 재실행: `graphify_out/n3_synthesis_smoke.log` 갱신
- 신규 단위 테스트 ≥3건 (multi-iter 누적 / 마지막 iter 외부 미호출 / 합성 정상)

**§3-1-5. 성공 기준**
- T13/T14 `synthesis_used=True` 회복 (3/3 case 합성 적용)
- 단위 테스트 누적 ≥210 PASS (현재 207 + R-7 추가 ≥3)
- 11쿼리 회귀 (RERANK=1) none 10/10 + gemini 10/10 유지
- N-3 smoke #2 (인용 80%) 유지: 3/3 PASS

---

### §3-2. R-2.1 +30% 길이 기준 재정의

**§3-2-1. 입력 데이터**
- v2.6 R-2 결과: T12 ratio=0.38x (base 7922→synth 3020) — 합성이 base를 압축한 정상 동작이지만 +30% 기준에 어긋남
- 합성 효과의 실질 표지표: 인용 ≥80% (이미 PASS), source 통합 여부, answer quality

**§3-2-2. 판단 기준**
- 새 metric은 LLM 합성의 본질(통합·압축)과 일치
- 회귀 0 — 기존 #2/#3/#4 PASS 유지
- 기존 N-3 smoke 케이스에서 PASS 가능

**§3-2-3. 실행 방법**
1. metric 후보 비교:
   - (a) `synthesis_used=True` 비율 ≥ 100% (외부 결과 있을 때)
   - (b) 외부 식별자 인용률 ≥ 80% (현행)
   - (c) 합성 답변 vs base 의미적 차이 (LLM judge)
   - (d) base와 다른 단어 비율 ≥ 30% (token-level diff)
2. 후보 (a)+(b) 결합 권장 — 단순 + 검증 가능
3. `scripts/n3_synthesis_smoke.py` §3-3-5 #1 갱신
4. RELEASE_NOTES_v2.7 또는 v2.8에 metric 변경 기록

**§3-2-4. 산출물**
- `scripts/n3_synthesis_smoke.py` 갱신
- v2.8 release notes에 metric 변경 명시

**§3-2-5. 성공 기준**
- 새 metric으로 §3-3-5 4/4 PASS
- 회귀 0

---

### §3-3. R-8 embedder 교체 (heavy)

**§3-3-1. 입력 데이터**
- 현 embedder: `sentence-transformers/all-MiniLM-L6-v2` (일반 도메인, 366,570 임베딩)
- 후보: `dmis-lab/biobert-v1.1`, `pritamdeka/S-PubMedBert-MS-MARCO`, `cambridgeltl/SapBERT-from-PubMedBERT-fulltext`

**§3-3-2. 판단 기준**
- T9 none Top-1 정확도 = 100% (현 R-4 fix 후 100%, R-8은 부수 도메인 강화)
- 11쿼리 회귀 0 (영어/한국어 모두)
- 단위 테스트 207 PASS 유지

**§3-3-3. 실행 방법**
1. embedder 후보 3개 비교 (mini regression 3쿼리 ~15분)
2. 선택된 모델로 ChromaDB 재구축 (수시간~하루, 366,570 임베딩 재생성)
3. 11쿼리 회귀 + 단위 테스트 + smoke 재실행
4. 성능 메트릭 비교 (Top-1 정확도, latency)

**§3-3-4. 산출물**
- 변경 `vectorize_snomed.py` + `hybrid_search.py` (EMBEDDING_MODEL 상수)
- 새 ChromaDB 인덱스 (data/chroma_db_biobert/ 등 별도 디렉토리)
- 비교 노트 `docs/20260428_r8_embedder_comparison.md`

**§3-3-5. 성공 기준**
- 11쿼리 Top-1 정확도 유지 (10/10)
- T9/T7 같은 도메인 케이스 임베딩 거리 개선 정량 측정
- 회귀 0

**주의:** ChromaDB 재구축은 비가역. 사용자 명시 승인 + 기존 인덱스 백업 필수.

---

### §3-4. R-9 onboarding 가이드 갱신

**§3-4-1. 입력 데이터**
- v2.6 R-5 venv 동기화 누락 사고 (test_pdf_reader 13건 ImportError)
- requirements.txt에는 명시되어 있지만 venv 미설치 상태였음
- 현재 README.md (확인 필요)

**§3-4-2. 판단 기준**
- 신규 사용자가 `git clone` → `setup` 단계 명확히 따라할 수 있어야 함
- 의존성 모두 한 번에 설치되어야 함

**§3-4-3. 실행 방법**
1. README.md `## Setup` 섹션 추가 또는 갱신
2. `python -m venv venv && venv/bin/pip install -r requirements.txt` 명시
3. 시스템 의존성(brew install poppler tesseract) 명시
4. .env.example 모든 키 (GOOGLE/UMLS/NCBI/TAVILY/ANTHROPIC) 템플릿 + 발급 가이드 링크

**§3-4-4. 산출물**
- README.md 갱신
- (선택) `.env.example` 갱신 — TAVILY_API_KEY 템플릿 추가

**§3-4-5. 성공 기준**
- 신규 clone → setup 명령 실행 → 단위 테스트 207/207 PASS 가능

---

### §3-5. R-10 Tavily Pay As You Go 시뮬레이션

**§3-5-1. 입력 데이터**
- v2.7 운영 시 Tavily Free 1,000 credits/월 초과 가능성 평가
- 사용자 카드 등록 의사

**§3-5-2. 판단 기준**
- 한도 초과 시 동작 검증 (429? 빈 결과?)
- Pay As You Go 비용 추정

**§3-5-3. 실행 방법**
1. 사용자 Tavily Dashboard에서 Pay As You Go 활성화 (선택)
2. 인위적으로 1,000+ 호출 시뮬 (테스트 환경에서 cache off + bulk query)
3. 한도 초과 응답 코드/body 확인
4. `web_search_client.py`에 추가 graceful fallback 필요 시 보강

**§3-5-4. 산출물**
- 비용 추정 노트
- (선택) `web_search_client.py` 한도 초과 처리 보강

**§3-5-5. 성공 기준**
- 한도 초과 시에도 회귀 0 (graceful fallback)
- 비용 추정 정확성 확인

---

## §4. 우선순위 권고

### 4-1. 권장 순서

1. **R-7** (synthesis 미트리거 본질 분석) — v2.8 핵심. multi-iter loop 본질 결함 해소
2. **R-2.1** (metric 재정의) — R-7과 묶음 권장. 동일 도메인
3. **R-9** (onboarding 가이드) — 가벼운 정비, R-7 작업 중간에 끼워넣기 가능
4. **R-10** (Tavily PAYG) — 사용자 결정 필요, 후순위
5. **R-8** (embedder 교체) — heavy, v2.9+ 별도 phase 권장

### 4-2. 권장 묶음

- **묶음 G (synthesis 본질):** R-7 → R-2.1 (multi-iter 누적 fix + metric 재정의)
- **묶음 H (운영 정비):** R-9 (onboarding) + R-10 (PAYG 검증) — 사용자 결정 시
- **별도 Phase (embedder):** R-8 v2.9+

### 4-3. 비추천 패턴

- R-8 단독 (heavy 인프라 작업 — v2.7 release 직후 ChromaDB 재구축 시 운영 안정성 위험)
- R-7 없이 R-2.1만 (metric 재정의는 본질 fix 후 정합성 확보)

---

## §5. 재개 가이드 (다음 세션 진입 시)

### 5-1. 첫 명령

```bash
cd ~/claude-cowork/07_Projects/vet-snomed-rag
git status --short                              # clean 확인
git log -3 --oneline                            # v2.7 release 확인
venv/bin/python -m pytest tests/ -q | tail -3   # 207 PASS baseline 확인
cat docs/20260427_v2_8_roadmap_handoff.md | head -80  # 본 문서 §1-2 잔여
```

### 5-2. 핸드오프 로드 명령 예시

```
이 v2.8 핸드오프대로 R-7 진행해줘
또는 묶음 G (R-7 → R-2.1) 진행해줘
또는 R-9 onboarding 가이드부터 진행해줘
또는 권장으로 진행해줘  (= 묶음 G 시작)
```

### 5-3. 사용자 의사결정 필요 사항 (다음 세션 첫 응답에서 확인)

1. **R-7 어느 옵션으로 진행할지** — (a) 누적 보존 / (b) Final 합성 / (c) 트리거 조건 강화
2. **R-2.1 새 metric 후보 결정** — `synthesis_used=True` 비율 / 인용률 / token diff / LLM judge
3. **R-8 embedder 교체 여부** — heavy 작업, 별도 phase 분리 권장
4. **R-10 Tavily PAYG 활성화 의사** — 카드 등록 + 비용 ~$0.10 시뮬

---

## §6. 위험·블로커

| 위험 | 영향 | 회피 |
|---|---|---|
| R-7 multi-iter loop 구조 변경 회귀 | 단위 테스트 + 11쿼리 회귀 영향 | 단위 테스트 ≥3건 추가 + 회귀 즉시 검증 |
| R-2.1 새 metric이 기존 합성 케이스 일부 FAIL 처리 | smoke #1 새 결함 보고 | 기존 N-3 PASS 케이스 baseline 비교 |
| R-8 ChromaDB 재구축 비가역 | 기존 인덱스 손실 | data/chroma_db/ 백업 + 별도 디렉토리에 신규 인덱스 |
| Tavily 한도 초과 (예상치 못한 사용 폭증) | 외부 호출 실패 (현재 graceful, 영향 0) | LRU+TTL cache 24h 유지 + 운영 모니터링 |
| `.env` secrets 노출 위험 | git push 시 노출 | `.gitignore` 등록 확인 (이미 됨) + `git diff --cached` 검토 |

---

## §7. 핸드오프 성공 기준 체크리스트

다음 세션에서 본 핸드오프를 입력으로 사용 시 1:1 PASS/FAIL 표로 검증:

| # | 항목 | PASS 조건 |
|---|---|---|
| H-1 | 현 상태 검증 | git status clean / 단위 207 PASS / 11쿼리 none·gemini 10/10 |
| H-2 | 사용자 R-x 또는 묶음 선택 명확 | R-7 / R-2.1 / R-9 / R-10 / R-8 또는 묶음 명시 |
| H-3 | 선택 작업 §3-x Task Definition 5항목 사용자 승인 | 입력·판단·실행·산출·성공기준 동의 |
| H-4 | 사용자 사전 액션 (필요 시) 완료 | 예: R-10 카드 등록 / R-7 옵션 선택 |
| H-5 | 작업 완료 시 §3-x §3-x-5 성공 기준 1:1 PASS | 모든 PASS 조건 충족 |
| H-6 | 회귀 0 보장 | 단위 ≥207 PASS + 11쿼리 회귀 (none·gemini 10/10) 유지 |
| H-7 | 메모리 갱신 | `project_vet_snomed_rag.md` 다음 단계 진입 사실 추가 |
| H-8 | 핸드오프 갱신 또는 종결 | 본 문서 status=종결 + v2.8 → v2.9 핸드오프 신규 또는 본 문서에 결과 누적 |

---

## §8. 부록 — v2.7 산출물 인덱스 (참고)

### 8-1. v2.7 commit 이력

| commit | 내용 |
|---|---|
| `e244d42` | docs(v2.7): release notes + CHANGELOG entry [2.7.0] |
| `d1d1880` | feat(v2.7): R-3 Tier C — Tavily Web Search 통합 |
| `ab3a669` | docs(v2.6): release notes + CHANGELOG + 핸드오프 + 검증 노트 |
| `9aabf2b` | feat(v2.6): 사전 v1.2 + T7 + R-4 |
| `06a692d` | feat(v2.6): 묶음 A — Agentic 정밀 회귀 + LLM 합성 |

### 8-2. v2.7 신규 / 변경 파일

| 분류 | 경로 |
|---|---|
| 신규 모듈 | `src/tools/web_search_client.py` |
| 확장 모듈 | `src/retrieval/agentic/source_router.py`, `src/retrieval/agentic_pipeline.py` |
| 신규 테스트 | `tests/test_web_search_client.py` (12) |
| 확장 테스트 | `tests/test_source_router.py` (web 5건 추가) |
| 신규 스크립트 | `scripts/v2_7_tier_c_web_smoke.py` |
| 신규 문서 | `RELEASE_NOTES_v2.7.md`, `docs/20260427_v2_8_roadmap_handoff.md` (본 문서) |
| 산출물 | `graphify_out/v2_7_tier_c_web_smoke.log` |

### 8-3. v2.7 누적 메트릭

- 단위 테스트: **207 PASS** (web 12 + router 5 + 기존 190)
- 11쿼리 정밀 회귀: none **10/10**, gemini **10/10**
- 외부 도구: 3종 (UMLS + PubMed + Tavily Web)
- Tavily credit: smoke ~2 / Free 1,000/월 (0.2%)
- GitHub Release: v2.6, **v2.7** published

---

**핸드오프 작성 완료. 다음 세션에서 §5-2 형식으로 명령하여 v2.8 진입.**
