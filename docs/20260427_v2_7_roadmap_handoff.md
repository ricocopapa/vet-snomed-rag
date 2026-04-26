---
tags: [vet-snomed-rag, v2.7, roadmap, handoff]
date: 2026-04-26
status: 종결 (R-1·R-3·R-4·R-5·R-6 모두 종결, R-2 부분, v2.7 GitHub Release published)
prev_state: v2.6 (묶음 A + B + T7) 작업 종결, **미커밋·미릴리스** (사용자 git push 명시 승인 대기)
final_state: v2.7 R-3 Tier C Tavily Web Search 종결. GitHub Release `https://github.com/ricocopapa/vet-snomed-rag/releases/tag/v2.7` published. 단위 207 PASS / 11쿼리 회귀 0
next_target: v2.8 (R-7 synthesis 미트리거 본질 분석)
next_handoff: docs/20260427_v2_8_roadmap_handoff.md
session_anchor: 2026-04-26 (R-3 종결 시각)
related:
  - docs/20260427_v2_8_roadmap_handoff.md (v2.8 진입 핸드오프, R-7 + 잔여 후보)
  - docs/20260426_v2_6_roadmap_handoff.md (v2.6 종결 기록)
  - docs/20260426_v2_6_n4_korean_lexicon_v1_1.md (N-4 검증 노트)
  - memory/project_vet_snomed_rag.md
---

# v2.6 → v2.7 핸드오프 (다음 세션 진입용)

> **사용자 선호 반영:** 프로젝트 완성도 우선·이력서/자소서 후순위 (`feedback_project_first_resume_later.md`).
> 본 핸드오프는 v2.6 (묶음 A + B + T7) 종결 시점에서 후속 작업 후보를 분해·우선순위화한다. 다음 세션에서 사용자가 후보 선택 → 본 문서 §3-x 그대로 실행 입력으로 사용.

---

## §1. 현재 상태 (v2.6 종결, 2026-04-26 동일 세션)

### 1-1. 완료 단계 — v2.6 누적

| 단계 | 결과 |
|---|---|
| 묶음 A — N-1 agentic 정밀 회귀 (14쿼리×4모드) | 12/12 PASS, base 회귀 0, 외부 markdown 3/3 |
| 묶음 A — N-3 ExternalSynthesizerAgent | 단위 12/12 PASS, smoke #2/#3/#4 PASS |
| 묶음 B — N-4 한국어 사전 v1.1 | none 8/10 → 9/10 (T9 회복), gemini 10/10 유지 |
| T7 처리 — 영어 약식 v1.2 + 단어 경계 매칭 | none 9/10 → **10/10** (T7 회복), gemini **10/10** 유지 |
| 단위 테스트 누적 | **180/180 PASS** (flaky 1건 결정화 완료) |
| 사전 항목 누적 | 158 → 168 → **171** (5 → 7 카테고리) |

### 1-2. 미결 사항 (v2.6 알려진 한계, R-4 종결로 1건 해소)

1. **N-3 smoke #1 실측 보류** — Gemini Free Tier 20 RPD 소진. 합성 답변 ≥ +30% 길이 측정만 보류 (다른 #2/#3/#4는 PASS). fallback 정상 작동으로 회귀 0 보장됨. (R-4 회귀 11×2=22회 후에도 quota 여유 있었음 → 재시도 가능)
2. ✅ **T9 none Top-1 drift — 2026-04-26 동일 세션 R-4로 종결.** RRF 가중치 vw 0.6→0.4, sw 0.4→0.6 + `_MAPPING_INELIGIBLE_TAGS` 16-tag 블랙리스트 (situation/qualifier value 등)로 reranker candidate 필터. T9 none Top-1=73211009, gemini Top-1=73211009. 11쿼리 none 10/10 + gemini 10/10. 단위 180/180 PASS. 산출물: `graphify_out/regression_metrics_rerank.json` 갱신.
3. **test_pdf_reader.py 13건 FAIL** — v2.2 PDF reader 사전 결함. v2.6 작업 무관이지만 향후 정리 필요.
4. **`ANTHROPIC_API_KEY` `.env` 빈 값** — Claude fallback 미가용. 진행 옵션 다양화 차원.
5. **git commit + push + tag v2.6 + GitHub Release** — **비가역, 사용자 명시 승인 필수**. v2.5.1 + v2.6 + R-4 통합 누적되어 자연스러운 종결 시점.

### 1-3. 환경·자산

- **로컬 경로:** `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag`
- **venv:** `venv/` (Python 3.14.4, pytest 9.0.3)
- **인덱스:** `data/chroma_db/` (366,570) + `data/snomed_ct_vet.db` (414,860)
- **사용자 .env 키:** `GOOGLE_API_KEY` ✓, `UMLS_API_KEY` ✓ (36자), `NCBI_API_KEY` ✓ (36자), `ANTHROPIC_API_KEY` ❌ (placeholder만), `TAVILY_API_KEY` ❌ (미발급)
- **graphify 그래프:** `graphify-out/` (v2.5.1 시점 동기화. v2.6 변경 후 재동기화 권장)
- **회귀 산출물:**
  - `graphify_out/regression_metrics_rerank.json` (v1.2 = T7 fix 후, none·gemini 둘 다 10/10)
  - `graphify_out/regression_metrics_rerank_v1_1_baseline.json` (v1.1 = N-4 후 백업)
  - `graphify_out/regression_metrics_rerank_v1_0_baseline.json` (v1.0 = v2.5.1 백업)
  - `graphify_out/agentic_regression_metrics.json` (N-1 14쿼리×4모드)
  - `graphify_out/agentic_vs_base_comparison.md` (N-1 비교 보고서)
  - `graphify_out/n3_synthesis_smoke.log` (N-3 smoke 로그)
  - `graphify_out/t7_regression_run.log` (T7 회귀 로그)

### 1-4. v2.6 미커밋 변경 (`git status --short` 기준)

**Modified (8):**
- `data/vet_term_dictionary_ko_en.json` (v1.0 → v1.2)
- `src/retrieval/rag_pipeline.py` (영어 분기 + 단어 경계 매칭)
- `src/retrieval/agentic/__init__.py` (synthesizer export)
- `src/retrieval/agentic_pipeline.py` (last_sub_results, synthesis 통합, UMLS reformulated)
- `src/retrieval/cache/reformulations_gemini.json` (Gemini 캐시 추가)
- `src/tools/umls_client.py` (timeout 3.0 → 8.0)
- `tests/test_agentic_tier_b.py` (synthesizer mock 강제)
- `graphify_out/backend_comparison.md`, `regression_metrics_rerank.json`

**Untracked (13):**
- `docs/20260426_v2_6_roadmap_handoff.md` (v2.6 종결 기록, status=종결)
- `docs/20260426_v2_6_n4_korean_lexicon_v1_1.md` (N-4 검증 노트)
- `docs/20260427_v2_7_roadmap_handoff.md` (본 문서, 신규)
- `src/retrieval/agentic/synthesizer.py` (G-5 ExternalSynthesizerAgent)
- `tests/test_synthesizer.py` (12건 신규)
- `scripts/run_regression_agentic.py`, `scripts/n1_mini_external_recheck.py`, `scripts/n3_synthesis_smoke.py`
- `graphify_out/agentic_regression_metrics.json`, `agentic_vs_base_comparison.md`
- `graphify_out/regression_metrics_rerank_v1_0_baseline.json`, `regression_metrics_rerank_v1_1_baseline.json`
- `graphify_out/n3_synthesis_smoke.log`, `t7_regression_run.log`, `agentic_regression_run.log`, `n4_regression_run.log`

---

## §2. 후속 작업 후보 + 우선순위

| 코드 | 작업 | 도메인 가치 | 회귀 위험 | 비용 | 즉시 진행 가능 | 권장도 |
|---|---|---|---|---|---|---|
| **R-1** | git commit + push + tag v2.6 + GitHub Release | ★★★ 작업 영속화 | 0 | 0 | ✅ 사용자 승인 후 즉시 | ★★★ |
| **R-2** | N-3 smoke #1 실측 마무리 (quota reset 후) | ★★ 합성 효과 정량화 | 낮음 | Gemini ~$0.005 | ⚠️ 24h 후 또는 Gemini paid tier | ★★ |
| **R-3** | 묶음 C — N-2 Tavily Web Search 통합 | ★★ 신규/희귀 fallback | 중 (외부 의존) | Tavily $0.001/q | ⚠️ Tavily key 발급 사전 액션 | ★★ |
| ~~**R-4**~~ | ~~T9 none Vector drift 정밀화~~ | ✅ **2026-04-26 종결** (동일 세션, RRF 가중치 + 16-tag 블랙리스트) | 0 (회귀) | — | — | ✅ |
| **R-5** | test_pdf_reader.py 13건 사전 결함 조사 | ★ 무관 영역 정비 | 낮음 (v2.2) | 0 | ✅ 즉시 | ★ |
| **R-6** | RELEASE_NOTES_v2.6.md + CHANGELOG 갱신 | ★★ release 준비 | 0 | 0 | ✅ 즉시 | ★★ (R-1 전제) |

---

## §3. 작업별 Task Definition (5항목)

### §3-1. R-1 git commit + push + tag v2.6 + GitHub Release

**§3-1-1. 입력 데이터**
- 본 핸드오프 §1-4 미커밋 변경 (Modified 8 + Untracked 13)
- v2.6 통합 회귀 결과 (none·gemini 10/10, 단위 180/180)
- 핸드오프 §11-2 코드 변경 표

**§3-1-2. 판단 기준**
- 비가역 작업 — 사용자 명시 승인 후에만 실행 (`feedback_design_before_execute.md`)
- 커밋 단위: 논리 단위 분리 권장
  - (a) v2.6 묶음 A: agentic 정밀 회귀 + ExternalSynthesizerAgent
  - (b) v2.6 묶음 B: 한국어 사전 v1.1
  - (c) v2.6 T7 처리: 영어 약식 v1.2 + 단어 경계 매칭
  - (d) 핸드오프·검증 노트·release notes
- 또는 단일 squash merge로 v2.6 통합 (사용자 선호)
- secrets 검사 필수: `.env` 미커밋 (이미 `.gitignore` 등록 가정)

**§3-1-3. 실행 방법**
1. `RELEASE_NOTES_v2.6.md` + `CHANGELOG.md` 작성 (§3-6 R-6과 통합 가능)
2. `git status` + `git diff` 검토 → 사용자 승인
3. `git add` 단위 분할 또는 일괄 (사용자 결정)
4. `git commit -m "..."` (Conventional Commits 스타일)
5. `git push origin main` (또는 PR)
6. `git tag v2.6 && git push origin v2.6`
7. `gh release create v2.6 --notes-file RELEASE_NOTES_v2.6.md`

**§3-1-4. 산출물 포맷**
- GitHub commit(s) on `main` (`squash` 또는 분할)
- GitHub tag `v2.6`
- GitHub Release v2.6 (with notes)
- README.md 갱신 (선택)

**§3-1-5. 성공 기준**
- 모든 v2.6 변경이 GitHub에 반영됨
- v2.6 release notes에 묶음 A/B/T7 결과 + 회귀 매트릭스 + 알려진 한계 명시
- secrets·`.env` 미커밋 확인
- 단위 테스트 180/180 PASS 유지

---

### §3-2. R-2 N-3 smoke #1 실측 마무리

**§3-2-1. 입력 데이터**
- `scripts/n3_synthesis_smoke.py` (변경 없음, 그대로 재실행)
- T12·T13·T14 외부 트리거 케이스
- Gemini quota reset 확인 (직접 호출 또는 quota 대시보드)

**§3-2-2. 판단 기준**
- §3-3-5 #1 합성 답변 길이 ≥ base_answer × 1.30 (+30%)
- 다른 기준은 이미 PASS 확인됨 (#2 인용 ≥ 80%, #3 회귀 0, #4 비용 < $0.001)

**§3-2-3. 실행 방법**
1. quota reset 확인: `venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from src.retrieval.agentic.synthesizer import ExternalSynthesizerAgent; ..."` (간단 호출 테스트)
2. `venv/bin/python -u scripts/n3_synthesis_smoke.py` 재실행
3. 결과 분석 + `graphify_out/n3_synthesis_smoke.log` 갱신
4. v2.7 핸드오프에 결과 추가 (또는 v2.6 핸드오프 §9-3 갱신)

**§3-2-4. 산출물 포맷**
- 갱신된 `graphify_out/n3_synthesis_smoke.log`
- §3-3-5 1:1 PASS/FAIL 표 갱신 (1번 PASS 회복)

**§3-2-5. 성공 기준**
- §3-3-5 #1 PASS (3/3 합성 케이스에서 +30% 이상 길이)
- 회귀 0 (다른 기준 PASS 유지)

---

### §3-3. R-3 N-2 Tavily Web Search 통합 (묶음 C)

**§3-3-1. 입력 데이터**
- 사용자 사전 액션: Tavily API 키 발급 ([tavily.com](https://tavily.com), $0.001/query, 1k free trial)
- `.env`에 `TAVILY_API_KEY=...` 추가

**§3-3-2. 판단 기준 (라우터 룰)**
- 활성 트리거: LOCAL Top-1 score < 0.3 (매우 낮은 confidence)
- 또는 명시 키워드: `최신`, `latest`, `recent`, `web`, `news`
- 비활성: 일반 SNOMED 매핑 쿼리 (LOCAL 충분)

**§3-3-3. 실행 방법**
1. 사전 액션 확인 (Tavily key)
2. `src/tools/web_search_client.py` 신규 — Tavily 클라이언트 + cache + 429 backoff (UMLS/PubMed 패턴 재사용)
3. `SourceRoute.external_tools`에 `"web"` 식별자 추가 + 라우팅 룰 확장 (`source_router.py`)
4. `agentic_pipeline.py` Step C에 Web 분기 호출 추가 (UMLS/PubMed 패턴 재사용)
5. `tests/test_web_search_client.py` 신규 + smoke
6. `scripts/v2_7_tier_c_web_smoke.py` 신규 — 실 호출 검증
7. agentic_regression 재실행하여 Web 활성 케이스 검증

**§3-3-4. 산출물 포맷**
```python
[{"title": "...", "url": "https://...", "snippet": "...", "score": 0.85, "source": "tavily"}]
```

**§3-3-5. 성공 기준**
- 단위 테스트 ≥ 7건 PASS (인증 / 정상 / 429 / timeout / cache)
- env 미설정 시 자동 비활성
- Tier A·B 회귀 0 (`external_tools=[]` default)
- agentic_regression에서 Web 활성 케이스 1건 이상 PASS

---

### §3-4. R-4 T9 none Vector drift 정밀화

**§3-4-1. 입력 데이터**
- T9 `feline diabetes mellitus` (사전 치환 후 영어 쿼리)
- Vector store: `data/chroma_db/` (sentence-transformers/all-MiniLM-L6-v2 임베딩 366,570건)
- 현재 reranker: BAAI/bge-reranker-v2-m3
- v2.6 결과: none Top-1=339181000009108 panleukopenia, rank #3=73211009 PASS

**§3-4-2. 판단 기준**
- T9 none Top-1 = 73211009 (현재 #3 → #1로 정밀화)
- 다른 10쿼리 회귀 0
- 단위 테스트 회귀 0

**§3-4-3. 실행 방법** (옵션 분석 → 사용자 선택)
- (a) Reranker 점수 가중치 재설정 (vec_weight·sql_weight·graph 가중치)
- (b) 다른 reranker 모델 평가 (BAAI/bge-reranker-large 등)
- (c) Vector store 임베딩 모델 교체 (BioBERT, PubMedBERT 등 의학 도메인 특화)
- (d) `feline X` 쿼리 패턴에 species-aware reranking 보정 룰

**§3-4-4. 산출물 포맷**
- 변경 코드 + 회귀 결과 비교 (T9 + 11쿼리 전체)
- 검증 노트 (옵션별 트레이드오프)

**§3-4-5. 성공 기준**
- T9 none Top-1 = 73211009
- 11쿼리 다른 케이스 회귀 0 (10/10 유지)
- 단위 테스트 180/180 PASS 유지

---

### §3-5. R-5 test_pdf_reader.py 13건 사전 결함 조사

**§3-5-1. 입력 데이터**
- `tests/test_pdf_reader.py` (Hyangnam 샘플 + scan PDF 13건 FAIL)
- v2.2 PDF reader 모듈 (`src/retrieval/pdf_reader.py` 또는 유사)

**§3-5-2. 판단 기준**
- v2.2 영역 영구 결함인지 vs 환경 변화로 인한 결함인지 분리
- v2.6 작업 영향 0 확인 (commit 이전 상태에서 동일 FAIL이었으면 무관)

**§3-5-3. 실행 방법**
1. v2.2 시점 git checkout으로 회귀 비교
2. FAIL 13건 카테고리별 진단 (clinical_keywords / phi_redaction / latency p95 / scan OCR)
3. 결함 분류: v2.2 사전 결함 / 환경 의존 / 회귀
4. 결함 fix 또는 알려진 한계로 명시

**§3-5-4. 산출물 포맷**
- 결함 진단 노트 (`docs/20260427_pdf_reader_13fail_diagnosis.md`)
- 우선순위별 fix 작업 후보

**§3-5-5. 성공 기준**
- 13건 분류 완료 + v2.6 무관 확인
- 우선순위 fix 작업 1건 이상 식별

---

### §3-6. R-6 RELEASE_NOTES_v2.6.md + CHANGELOG 갱신

**§3-6-1. 입력 데이터**
- `RELEASE_NOTES_v2.5.md` (이전 release 패턴 참조)
- `CHANGELOG.md` (현재 v2.5 entries)
- v2.6 핸드오프 §11-2 변경 표

**§3-6-2. 판단 기준**
- v2.5 release notes 형식 일관성
- v2.6 묶음 A (agentic 정밀 회귀 + LLM 합성) + 묶음 B (한국어 사전 v1.1) + T7 처리 (영어 약식 v1.2)
- 회귀 매트릭스 (v2.5.1 → v2.6 진화) 명시
- 알려진 한계 명시 (T9 drift, smoke #1 보류, ANTHROPIC_API_KEY 부재)

**§3-6-3. 실행 방법**
1. `RELEASE_NOTES_v2.6.md` 신규 작성
2. `CHANGELOG.md`에 v2.6 entry 추가
3. README.md 핵심 메트릭 표 갱신 (선택)

**§3-6-4. 산출물 포맷**
- `RELEASE_NOTES_v2.6.md` (RELEASE_NOTES_v2.5.md 패턴 따름)
- `CHANGELOG.md` v2.6 entry

**§3-6-5. 성공 기준**
- v2.5 형식 일관성
- 사용자 검토 후 R-1 git release 진입 가능

---

## §4. 우선순위 권고 (사용자 도메인 적합도 + 비용 + 영속성)

### 4-1. 권장 순서

1. **R-6 (release notes 갱신)** — R-1 전제 조건. v2.6 작업 정리·문서화.
2. **R-1 (git release v2.6)** — 작업 영속화. 사용자 승인 필수.
3. **R-2 (N-3 smoke #1 실측)** — quota reset 후 즉시 가능 (가벼운 마무리).
4. **R-3 (묶음 C Tavily)** — Tavily key 발급 후. 도메인 가치 보통, 비용 발생.
5. **R-4 (T9 vector drift)** — heavy 인프라 작업. v2.7 후반 또는 별도 phase.
6. **R-5 (PDF reader 진단)** — v2.6 무관 영역 정비. 우선순위 낮음.

### 4-2. 권장 묶음

- **묶음 D (release 준비):** R-6 → R-1 (v2.6 영속화)
- **묶음 E (정밀화):** R-2 → R-4 (smoke 마무리 + vector drift)
- **묶음 F (확장):** R-3 (Web Search 추가)
- **정리 작업:** R-5 (PDF reader 진단)

### 4-3. 비추천 패턴

- R-3 단독 (R-1 전 release 안정화 없이 신규 외부 도구 추가는 작업 영속화 위험)
- R-4 우선 (T9 drift는 본질적으로 인프라 작업, v2.6 release 후 별도 phase가 깔끔)

---

## §5. 재개 가이드 (다음 세션 진입 시)

### 5-1. 첫 명령

```bash
cd ~/claude-cowork/07_Projects/vet-snomed-rag
git status --short                              # v2.6 미커밋 변경 확인
venv/bin/python -m pytest tests/ -q --ignore=tests/test_pdf_reader.py | tail -3
                                                # 180/180 PASS baseline 확인
cat docs/20260427_v2_7_roadmap_handoff.md | head -50  # 본 문서 §1 현재 상태
```

### 5-2. 핸드오프 로드 명령 예시

```
이 v2.7 핸드오프대로 R-x 진행해줘     (x = 1/2/3/4/5/6)
또는 묶음 D (R-6 → R-1) 진행해줘
또는 권장으로 진행해줘                (= 묶음 D 시작)
```

### 5-3. 사용자 의사결정 필요 사항 (다음 세션 첫 응답에서 확인)

1. **어느 R-x 또는 묶음으로 진행할지** (또는 다른 우선순위)
2. **R-1 git release 시 commit 단위** — 분할 (a/b/c/d) 또는 단일 squash
3. **R-2 진입 시 Gemini quota 상태 확인** — 24h 경과 또는 paid tier 활성화 여부
4. **R-3 진입 시 Tavily API 키 발급 의사** — 사전 액션
5. **N-3 smoke #1 PASS 여부 확인 후 v2.6 release notes 보완 여부** (R-2 후 R-6 수정)

---

## §6. 위험·블로커

| 위험 | 영향 | 회피 |
|---|---|---|
| Gemini Free Tier 20 RPD 한계 | smoke 재실행 + 회귀 작업 동시 진행 시 quota 소진 | paid tier 활성화 또는 24h 분산 |
| `.env` secrets 커밋 위험 | git push 시 노출 | `.gitignore` 등록 확인 + `git diff --cached` 검토 |
| v2.6 squash merge 시 commit 메시지 누락 | release notes 정합성 ↓ | 분할 commit 권장 또는 squash 메시지 신중 작성 |
| Tavily 무료 trial 1k 소진 | 묶음 C 진입 후 비용 발생 | 회귀 케이스 수 ≤10 / cache 24h 활성 |
| T9 vector drift 작업 시 다른 케이스 회귀 | 11쿼리 PASS 률 하락 | 변경 후 즉시 회귀 + rollback 준비 |
| PDF reader 13건 → v2.6 회귀 오인 | 디버깅 시간 낭비 | git log v2.5.1 이전부터 동일 FAIL 확인 |

---

## §7. 핸드오프 성공 기준 체크리스트

다음 세션에서 본 핸드오프를 입력으로 사용 시 1:1 PASS/FAIL 표로 검증:

| # | 항목 | PASS 조건 |
|---|---|---|
| H-1 | 현 상태 검증 | git status에 §1-4 미커밋 변경 그대로 / pytest 180/180 PASS |
| H-2 | 사용자 R-x 선택 명확 | R-1 ~ R-6 또는 묶음 명시 |
| H-3 | 선택 작업 §3-x Task Definition 5항목 사용자 승인 | 입력·판단·실행·산출·성공기준 동의 |
| H-4 | 사용자 사전 액션 (필요 시) 완료 | Tavily key 발급·env 등록 / git push 명시 승인 등 |
| H-5 | 작업 완료 시 §3-x §3-x-5 성공 기준 1:1 PASS | 모든 PASS 조건 충족 |
| H-6 | 회귀 0 보장 | 단위 180+ PASS + 회귀 매트릭스 (none·gemini 10/10) 유지 |
| H-7 | 메모리 갱신 | `project_vet_snomed_rag.md` 다음 단계 진입 사실 추가 |
| H-8 | 핸드오프 갱신 또는 종결 | 본 문서 status=종결 + v2.7 → v2.8 핸드오프 신규 또는 본 문서 §x에 결과 누적 |

---

## §8. 부록 — v2.6 산출물 인덱스

### 8-1. 코드 (Modified 8 / Untracked 6)

| 분류 | 경로 | 변경 |
|---|---|---|
| 핵심 모듈 | `src/retrieval/agentic_pipeline.py` | last_sub_results, synthesis 통합, UMLS reformulated query 전달 |
| 핵심 모듈 | `src/retrieval/rag_pipeline.py` | 영어 분기 + `_replace_with_dictionary` 단어 경계 매칭 |
| 신규 모듈 | `src/retrieval/agentic/synthesizer.py` | G-5 ExternalSynthesizerAgent (Gemini Flash Lite) |
| 모듈 export | `src/retrieval/agentic/__init__.py` | synthesizer 추가 |
| 외부 도구 | `src/tools/umls_client.py` | timeout 3.0 → 8.0 |
| 사전 | `data/vet_term_dictionary_ko_en.json` | v1.0 → v1.2 (171항목 7카테고리) |

### 8-2. 테스트 (Modified 1 / Untracked 1)

| 경로 | 변경 |
|---|---|
| `tests/test_agentic_tier_b.py` | `_make_pipe`에 synthesizer mock 강제 (flaky 결정화) |
| `tests/test_synthesizer.py` | 12건 신규 (synthesizer + 파이프라인 통합) |

### 8-3. 스크립트 (Untracked 3)

| 경로 | 용도 |
|---|---|
| `scripts/run_regression_agentic.py` | N-1 14쿼리 × 4모드 매트릭스 |
| `scripts/n1_mini_external_recheck.py` | UMLS/PubMed reformulated 전달 fix 검증 |
| `scripts/n3_synthesis_smoke.py` | N-3 §3-3-5 smoke |

### 8-4. 회귀 산출물 (Modified 2 / Untracked 6)

| 경로 | 내용 |
|---|---|
| `graphify_out/regression_metrics_rerank.json` | v1.2 = T7 fix 후 결과 (none·gemini 10/10) |
| `graphify_out/regression_metrics_rerank_v1_1_baseline.json` | v1.1 = N-4 후 백업 |
| `graphify_out/regression_metrics_rerank_v1_0_baseline.json` | v1.0 = v2.5.1 백업 |
| `graphify_out/agentic_regression_metrics.json` | N-1 14쿼리 결과 |
| `graphify_out/agentic_vs_base_comparison.md` | N-1 비교 보고서 |
| `graphify_out/backend_comparison.md` | 11쿼리 v2.6 비교 보고서 |
| `graphify_out/n3_synthesis_smoke.log` | N-3 smoke 로그 |
| `graphify_out/t7_regression_run.log` | T7 회귀 로그 |
| `graphify_out/agentic_regression_run.log` | N-1 회귀 로그 |
| `graphify_out/n4_regression_run.log` | N-4 회귀 로그 |

### 8-5. 문서 (Untracked 3)

| 경로 | 내용 |
|---|---|
| `docs/20260426_v2_6_roadmap_handoff.md` | v2.6 종결 기록 (§9 묶음 A, §10 묶음 B, §11 T7) |
| `docs/20260426_v2_6_n4_korean_lexicon_v1_1.md` | N-4 검증 노트 |
| `docs/20260427_v2_7_roadmap_handoff.md` | 본 문서 (v2.6 → v2.7 핸드오프) |

---

**핸드오프 작성 완료. 다음 세션에서 §5-2 형식으로 명령하여 재개.**
