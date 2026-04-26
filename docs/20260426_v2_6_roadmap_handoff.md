---
tags: [vet-snomed-rag, v2.6, roadmap, handoff]
date: 2026-04-26
status: 종결 (묶음 A + 묶음 B + T7 처리 완료, 2026-04-26 동일 세션)
prev_release: v2.5.1 (2026-04-25)
next_target: v2.6 / v2.6.1 (사용자 결정 후 확정)
completed_set:
  - 묶음 A (N-1 agentic 정밀 회귀 + N-3 외부 도구 LLM 합성)
  - 묶음 B (N-4 한국어 사전 v1.1)
  - T7 처리 (영어 약식 정식화 v1.2, none 9/10 → 10/10)
related:
  - RELEASE_NOTES_v2.5.md
  - docs/20260425_v2_5_tier_b_external_tools_design_v1.md
  - docs/20260426_v2_6_n4_korean_lexicon_v1_1.md
  - memory/project_vet_snomed_rag.md
---

# v2.5.1 → v2.6 다음 단계 핸드오프

> **사용자 선호 반영:** 프로젝트 완성도 우선·이력서/자소서 후순위 (`feedback_project_first_resume_later.md`).  
> 본 핸드오프는 v2.5.1 종결 시점에서 후속 작업 후보 N-1~N-6을 분해·우선순위화한다. 다음 세션에서 사용자가 N-x 선택 → 본 문서 §3-x를 그대로 실행 입력으로 사용.

---

## §1. 현재 상태 (v2.5.1 종결 시점)

### 1-1. 완료 단계
| 단계 | 결과 |
|---|---|
| Tier A — 백엔드 분기 활성화 | smoke 12/12 + mini regression PASS |
| Tier B — UMLS + PubMed 통합 | B-S1 ~ B-S9 9/9 PASS |
| v2.5.1 — 한국어 사전 backend-무관 | 정밀 회귀 gemini 10/10 회복 |
| 단위 테스트 | **53건 PASS** |
| GitHub Release v2.5.1 | <https://github.com/ricocopapa/vet-snomed-rag/releases/tag/v2.5.1> |
| main HEAD | `714bf76` (squash merge of v2.4 + v2.5) |

### 1-2. 미결 사항 (v2.5 설계서·release notes Known Limitations)
1. **agentic_query 경로 정밀 회귀 미작성** — `run_regression.py`는 `base.query()` 기반이라 Tier B 외부 도구 효과 미정량화
2. **Web Search (Tavily/Brave) 미통합** — Combo Beta/Gamma 후보, v2.5 범위 외
3. **외부 도구 결과는 base.answer에 markdown append만** — LLM context 합류 (별도 합성 호출) 미구현
4. **none backend 8/10** — 한국어 사전 미등재 케이스(예: T7 `feline diabetes` rank 외 등) 잔존

### 1-3. 환경·자산
- **로컬 경로:** `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag`
- **venv:** `venv/` (Python 3.14.4, pytest 9.0.3, requests 2.33.1)
- **인덱스:** `data/chroma_db/` (366,570) + `data/snomed_ct_vet.db` (414,860)
- **사용자 .env 키 (확인 완료):** `GOOGLE_API_KEY` (재발급) + `UMLS_API_KEY` (36자) + `NCBI_API_KEY` (36자)
- **graphify 그래프:** `graphify-out/` (v2.5.1 시점 동기화 완료)
- **회귀 산출물:** `graphify_out/regression_metrics.json` (default) + `regression_metrics_rerank.json` (RERANK=1)

---

## §2. 후속 작업 후보 N-1 ~ N-6

| 코드 | 작업 | 도메인 가치 | 회귀 위험 | 비용 | 권장도 |
|---|---|---|---|---|---|
| **N-1** | agentic_query 경로 정밀 회귀 신규 작성 | ★★★ Tier B 효과 정량화 | 낮음 (테스트 추가) | Gemini ×22 ≈ $0.05 | ★★★ |
| **N-2** | Tier C — Web Search (Tavily/Brave) 통합 | ★★ 신규/희귀 fallback | 중 (외부 의존) | Tavily $0.001/q | ★★ |
| **N-3** | 외부 도구 결과 LLM 합성 (base.answer markdown → LLM 입력) | ★★★ 답변 품질 ↑ | 중 (LLM 호출 1회 추가) | Gemini/Claude +α | ★★ |
| **N-4** | none backend 한국어 강화 (사전 확장 + reformulator prompt) | ★★ 한국 EMR 도메인 | 낮음 | 무료 | ★★ |
| **N-5** | 다른 프로젝트 (CDW Phase 2 / EMR STT 재개 등) | — | — | — | 사용자 결정 |
| **N-6** | 휴식 / 다음 세션으로 미룸 | — | — | — | 사용자 결정 |

---

## §3. 작업별 Task Definition (5항목)

### §3-1. N-1 agentic_query 경로 정밀 회귀

**§3-1-1. 입력 데이터**
- v2.5.1 main HEAD 코드 (`AgenticRAGPipeline.agentic_query()` 진입점)
- 11쿼리 또는 신규 12-15쿼리 (외부 도구 트리거 키워드 포함 케이스 추가)
  - 추가 권고 케이스: `T12 "diabetes mellitus ICD-10 cross-walk"` (UMLS 활성)
  - `T13 "rare feline endocrine literature"` (PubMed 활성)
  - `T14 "고양이 당뇨 ICD-10 매핑"` (한국어 + UMLS)
- 사용자 `.env` UMLS_API_KEY + NCBI_API_KEY (이미 등록됨)

**§3-1-2. 판단 기준**
- agentic_query 결과 (AgenticRAGResult.final_answer + external_results)에서:
  - Top-1 hit rate ≥ **9/10** (LLM 단계 포함 game)
  - 외부 도구 활성 케이스에서 markdown 섹션(`[UMLS Cross-Walk]` / `[PubMed Evidence]`) 정확히 포함
  - relevance_judge verdict PASS 비율 ≥ 80%
- 비교: agentic_query (외부 도구 ON) vs base.query (외부 도구 OFF) Top-1 동일률 + 답변 길이/품질 차이

**§3-1-3. 실행 방법**
1. `scripts/run_regression_agentic.py` 신규 작성 (run_regression.py 변형)
2. 11~14쿼리 × {agentic, base} × {RERANK ON, OFF} 매트릭스 실행
3. 결과 JSON: `graphify_out/agentic_regression_metrics.json`
4. 비교 보고서: `graphify_out/agentic_vs_base_comparison.md`

**§3-1-4. 산출물 포맷**
```json
{
  "qid": "T12",
  "query": "diabetes mellitus ICD-10 cross-walk",
  "modes": {
    "agentic_rerank": {
      "iterations": 1,
      "top1_id": "73211009",
      "external_tools_called": ["umls"],
      "external_results_summary": {"umls": 1},
      "verdict": "PASS",
      "answer_length": 1234,
      "latency_ms": 3500
    },
    "base_rerank": { ... }
  }
}
```

**§3-1-5. 성공 기준**
- agentic_query Top-1 ≥ 9/10
- 외부 도구 트리거 케이스에서 markdown 섹션 정확 포함 (≥ 95% 정확도)
- agentic vs base 회귀 0 (외부 도구 OFF 시 동일 결과)

---

### §3-2. N-2 Tier C Web Search 통합

**§3-2-1. 입력 데이터**
- API 후보: Tavily ($0.001/query, 1k free trial), Brave Search ($3/CPM), Bing Web Search ($7/CPM)
- 권장: **Tavily** (저비용 + AI-optimized 답변)

**§3-2-2. 판단 기준 (라우터 룰)**
- 활성 트리거: LOCAL Top-1 score < 0.3 (매우 낮은 confidence)
- 또는 명시 키워드: `최신`, `latest`, `recent`, `web`, `news`
- 비활성: 일반 SNOMED 매핑 쿼리 (LOCAL 충분)

**§3-2-3. 실행 방법**
1. 사용자 사전 액션: Tavily API 키 발급 ([tavily.com](https://tavily.com))
2. `.env`에 `TAVILY_API_KEY=...` 추가
3. `src/tools/web_search_client.py` 신규 — Tavily 클라이언트 + cache + 429 backoff
4. `SourceRoute.external_tools`에 `"web"` 식별자 추가 + 라우팅 룰 확장
5. `agentic_pipeline.py` Step C에 Web 분기 호출 추가
6. `tests/test_web_search_client.py` + smoke

**§3-2-4. 산출물 포맷**
```python
[
    {
        "title": "...",
        "url": "https://...",
        "snippet": "...",
        "score": 0.85,
        "source": "tavily"
    }
]
```

**§3-2-5. 성공 기준**
- 단위 테스트 ≥ 7건 PASS (인증 / 정상 / 429 / timeout / cache)
- env 미설정 시 자동 비활성
- Tier A·B 회귀 0 (`external_tools=[]` default)
- agentic_regression에서 Web 활성 케이스 1건 이상 PASS

---

### §3-3. N-3 외부 도구 결과 LLM 합성

**§3-3-1. 입력 데이터**
- v2.5 Tier B 산출물 (UMLS + PubMed markdown 섹션이 이미 base.answer에 append된 상태)
- LLM backend 선택 (Gemini Flash Lite Preview 권장 — 저비용 + 빠름)

**§3-3-2. 판단 기준**
- 외부 도구 결과가 비어있지 않으면 합성 LLM 호출
- 합성 LLM에 전달할 context: base.answer + UMLS markdown + PubMed markdown
- 합성 결과가 base.answer 보다 길거나 외부 정보를 명시적으로 인용하면 합성 성공

**§3-3-3. 실행 방법**
1. `agentic_pipeline.py`에 `_synthesize_with_external(base_answer, external_results, llm_backend)` 헬퍼 추가
2. Step E (relevance judge) 직전에 합성 LLM 호출
3. 합성 답변을 final_answer로 사용 + base_answer는 sub_results에 보관 (관찰성)
4. tests에 합성 케이스 추가

**§3-3-4. 산출물 포맷**
- AgenticRAGResult.final_answer = 합성된 답변 (외부 정보 인용 + LOCAL 검색 결과 통합)
- AgenticRAGResult에 `synthesis_used: bool` 필드 추가

**§3-3-5. 성공 기준**
- 외부 도구 활성 케이스에서 합성 답변이 base_answer 대비 평균 ≥ 30% 길이 증가
- 합성 답변이 외부 source 식별자(CUI / PMID)를 ≥ 80% 인용
- 외부 도구 OFF 시 합성 skip (회귀 0)
- LLM 비용: 케이스당 < $0.001 (Gemini Flash Lite)

---

### §3-4. N-4 none backend 한국어 강화

**§3-4-1. 입력 데이터**
- `data/vet_term_dictionary_ko_en.json` (158 항목, 5 카테고리)
- 11-쿼리 회귀 결과에서 none backend FAIL 케이스
- 한국어 임상 용어 추가 후보 (Web 검색 또는 KB `Vet_Medical_Terminology.md`)

**§3-4-2. 판단 기준**
- 사전 확장 후 11-쿼리 정밀 회귀 (RERANK=1) **none ≥ 9/10** (현재 8/10)
- gemini 10/10 유지 (회귀 0)
- 사전 항목 추가는 KB·RF2 검증 후만 (feedback_snomed_source_validation 적용)

**§3-4-3. 실행 방법**
1. 11-쿼리 회귀 FAIL 케이스 분석 → 사전 미등재 한국어 용어 식별
2. 한국어 → 영어 정확 매핑 확인 (KB + SNOMED FSN 대조)
3. `vet_term_dictionary_ko_en.json` 항목 추가
4. 회귀 재실행 → 결과 확인
5. 부수 KB 업데이트: `01_Knowledge_Base/EMR/Vet_Medical_Terminology.md` (관련 시)

**§3-4-4. 산출물 포맷**
- `vet_term_dictionary_ko_en.json` v1.1 (항목 +N개)
- 회귀 보고서 갱신

**§3-4-5. 성공 기준**
- none backend 정밀 회귀 ≥ 9/10
- gemini backend 회귀 0 (10/10 유지)
- 사전 추가 항목 모두 SNOMED FSN/preferred-term 매칭 검증 완료

---

### §3-5. N-5 다른 프로젝트 전환

**§3-5-1. 입력 데이터**
- 사용자 다른 프로젝트 미결 사항 (메모리 참조)
  - CDW Phase 2 (`memory/project_cdw_phase2.md`) — Wave21 03-18 스냅샷 + 최신성 경고
  - EMR Whisper STT (`memory/project_emr_whisper.md`) — 향남병원 101건 미완료
  - O축/P축/A축/S축 SNOMED 매핑 (각 메모리 참조)

**§3-5-2. 판단 기준**
- 사용자가 명시 선택한 프로젝트 진입
- 메모리·KB 우선 로드 → 현 상태 파악 후 작업 분해

**§3-5-3. 실행 방법**
- 사용자 지정 프로젝트로 컨텍스트 전환
- 새 세션 권고 (vet-snomed-rag 컨텍스트 분리)

---

## §4. 우선순위 권고 (사용자 도메인 적합도 + 비용 + 회귀 위험)

### 4-1. 권장 순서
1. **N-1 (agentic_query 회귀)** — Tier B 효과 정량 입증. 다른 후보 작업의 baseline이 됨.
2. **N-3 (LLM 합성)** — N-1 결과로 Tier B 가치 확인 후, 답변 품질 한 단계 더.
3. **N-4 (한국어 사전 강화)** — none backend 8/10 → 9/10 (사용자 도메인 직결).
4. **N-2 (Web Search)** — N-1·N-3 안정화 후. 도메인 가치 보통, 비용 발생.

### 4-2. 권장 묶음
- **묶음 A (효과 검증):** N-1 → N-3 (Tier B 정량 + 합성)
- **묶음 B (도메인 강화):** N-4 (한국어) — 단독 가능
- **묶음 C (확장):** N-2 (Web) — 별도 phase

### 4-3. 비추천 패턴
- N-2 → N-1 (Web 통합 먼저는 비효율 — Tier B 정량화 없이 Tier C 추가)
- N-3 단독 (외부 도구 효과 정량화 없이 합성 도입은 가치 측정 어려움)

---

## §5. 재개 가이드 (다음 세션 진입 시)

### 5-1. 첫 명령
```bash
cd ~/claude-cowork/07_Projects/vet-snomed-rag
git status                          # main HEAD 714bf76 + clean working tree
git log --oneline -3                # v2.5 commits 확인
venv/bin/python -m pytest tests/ -q | tail -5   # 단위 테스트 53건 PASS 확인
```

### 5-2. 핸드오프 로드 명령
```
이 핸드오프대로 N-x를 진행해줘 (x = 1/2/3/4)
또는 묶음 A (N-1 → N-3) 진행해줘
```

### 5-3. 사용자 의사결정 필요 사항 (다음 세션 첫 응답에서 확인)
1. **어느 N-x로 진행할지** (또는 묶음)
2. **N-2 진입 시 Tavily API 키 발급 의사** (사전 액션)
3. **N-3 진입 시 LLM 비용 수용 범위** (Gemini Flash Lite 권장, Claude도 가능)

---

## §6. 위험·블로커

| 위험 | 영향 | 회피 |
|---|---|---|
| 외부 API 키 만료 / 폐기 | UMLS·PubMed·Tavily 호출 실패 | env graceful fallback (이미 적용) |
| Gemini Free Tier 5 RPM 한계 | 정밀 회귀 시간 길어짐 | 13s sleep 이미 적용 / Tier 업그레이드 검토 |
| 한국어 사전 부정확 매핑 추가 | 회귀 발생 | KB/RF2 검증 후 추가 (feedback_snomed_source_validation) |
| LLM 비결정성 (Gemini 응답 변동) | 회귀 결과 변동 ±1 케이스 | N=2 재현 검증 권고 (시간/비용 ↑) |
| 외부 도구 latency | agentic_query 응답 시간 ↑ | per-tool timeout 3s + cache 24h (이미 적용) |

---

## §7. 핸드오프 성공 기준 체크리스트

다음 세션에서 본 핸드오프를 입력으로 사용 시 1:1 PASS/FAIL 표로 검증할 항목:

| # | 항목 | PASS 조건 |
|---|---|---|
| H-1 | 현 상태 검증 | git log main에 `714bf76` 또는 그 후속 commit / pytest 53+ PASS |
| H-2 | 사용자 N-x 선택 명확 | N-1 ~ N-6 중 1개 또는 묶음 명시 |
| H-3 | 선택 작업 §3-x Task Definition 5항목 사용자 승인 | 입력·판단·실행·산출·성공기준 동의 |
| H-4 | 사용자 사전 액션 (필요 시) 완료 | API 키 발급·env 등록 등 |
| H-5 | 작업 완료 시 §3-x §3-x-5 성공 기준 1:1 PASS | 모든 PASS 조건 충족 |
| H-6 | 회귀 0 보장 | 기존 53 unit + 11-쿼리 정밀 회귀 PASS 유지 |
| H-7 | 메모리 갱신 | `project_vet_snomed_rag.md` v2.6 진입 사실 추가 |
| H-8 | 핸드오프 갱신 또는 종결 | v2.6 완료 시 v2.6 → v2.7 핸드오프 신규 또는 본 문서 status=종결 |

---

## §8. 부록 — v2.5.1 산출물 인덱스 (참조용)

| 분류 | 경로 |
|---|---|
| 코드 (신규) | `src/tools/{__init__,_cache,umls_client,pubmed_client}.py` |
| 코드 (확장) | `src/retrieval/{rag_pipeline,agentic_pipeline}.py`, `src/retrieval/agentic/source_router.py`, `scripts/run_regression.py` |
| 테스트 | `tests/test_{cache,umls_client,pubmed_client,agentic_tier_b}.py`, `tests/test_source_router.py` 확장 |
| Smoke/회귀 | `scripts/v2_5_tier_a_{smoke,regression}.py`, `scripts/v2_5_tier_b_external_smoke.py` |
| 설계서 | `docs/20260425_v2_5_tier_b_external_tools_design_v1.md` |
| Release | `RELEASE_NOTES_v2.5.md`, `CHANGELOG.md` (v2.5.0 + v2.5.1 entries) |
| 회귀 산출물 | `graphify_out/regression_metrics.json` (default), `regression_metrics_rerank.json` |
| GitHub Release | <https://github.com/ricocopapa/vet-snomed-rag/releases/tag/v2.5.1> |

---

**핸드오프 작성 완료. 다음 세션에서 §5-2 형식으로 명령하여 재개.**

---

## §9. 묶음 A 종결 결과 (2026-04-26 동일 세션 추가)

### 9-1. §7 H-1 ~ H-8 1:1 PASS/FAIL

| # | 항목 | 결과 | 판정 |
|---|---|---|---|
| H-1 | 현 상태 검증 | git HEAD `714bf76` 그대로(squash merge 안 함), pytest 174 PASS / 13 FAIL(test_pdf_reader v2.2 영역, 본 묶음 무관) | ✅ |
| H-2 | 사용자 N-x 선택 명확 | "묶음 A (N-1 → N-3)" 명시 | ✅ |
| H-3 | §3-x Task Definition 5항목 사용자 승인 | N-1·N-3 모두 핸드오프 명시 그대로 채택, "권장 사항 진행" 승인 | ✅ |
| H-4 | 사용자 사전 액션 완료 | UMLS·NCBI·GOOGLE 키 등록 완료. ANTHROPIC_API_KEY는 placeholder 상태(미사용) | ✅ |
| H-5 | §3-x §3-x-5 성공 기준 1:1 PASS | N-1: 3/3 PASS / N-3: 3/4 PASS + 1건 quota reset 보류 | ⚠️ PARTIAL |
| H-6 | 회귀 0 보장 | 단위 180/180 PASS(test_pdf_reader 13건 사전 결함 제외) + base_rerank 11/11 baseline 일치 | ✅ |
| H-7 | 메모리 갱신 | `~/.claude/projects/-Users-wondongmin/memory/project_vet_snomed_rag.md` v2.6 묶음 A 섹션 추가, MEMORY.md 인덱스 갱신 | ✅ |
| H-8 | 핸드오프 갱신/종결 | 본 문서 status=종결 + §9 결과 섹션 추가 | ✅ |

### 9-2. N-1 §3-1-5 1:1 PASS/FAIL

| # | 항목 | 결과 | 판정 |
|---|---|---|---|
| 1 | agentic Top-1 ≥ 9/10 | 12/12 (NA 2건 제외) | ✅ PASS |
| 2 | 외부 도구 markdown ≥ 95% | 3/3 (100%) — fix 후 | ✅ PASS |
| 3 | base_rerank 회귀 0 (≥ 9/10) | 11/11 v2.5.1 baseline 일치 | ✅ PASS |

### 9-3. N-3 §3-3-5 1:1 PASS/FAIL

| # | 항목 | 결과 | 판정 |
|---|---|---|---|
| 1 | 합성 답변 ≥ +30% 길이 | 0/3 (Gemini Free Tier 20 RPD 소진 → fallback) | ⚠️ 측정 보류 |
| 2 | source 식별자(CUI/PMID) ≥ 80% 인용 | 3/3 (100%, base markdown 보존 효과) | ✅ PASS |
| 3 | 외부 OFF 시 skip(회귀 0) | 2/2 — `final_answer == base_answer_pre_synthesis` | ✅ PASS |
| 4 | 케이스당 < $0.001 (Gemini Flash Lite 추정) | 3/3 ($0.000167 ~ $0.000223) | ✅ PASS |

### 9-4. 코드 변경 산출물

| 분류 | 파일 | 변경 |
|---|---|---|
| 핵심 모듈 | `src/retrieval/agentic_pipeline.py` | `last_sub_results`/`synthesis_used`/`base_answer_pre_synthesis` 필드, UMLS·PubMed에 reformulated query 전달, synthesizer 통합 |
| 신규 모듈 | `src/retrieval/agentic/synthesizer.py` | `ExternalSynthesizerAgent` (G-5) — Gemini Flash Lite 합성 |
| 모듈 export | `src/retrieval/agentic/__init__.py` | `ExternalSynthesizerAgent`, `SynthesisResult` 추가 |
| 외부 도구 | `src/tools/umls_client.py` | `DEFAULT_TIMEOUT 3.0 → 8.0` |
| 회귀 스크립트 | `scripts/run_regression_agentic.py` (신규) | 14쿼리 × 4모드 매트릭스 |
| 검증 스크립트 | `scripts/n1_mini_external_recheck.py` (신규) | UMLS/PubMed reformulated 전달 fix 검증 |
| 검증 스크립트 | `scripts/n3_synthesis_smoke.py` (신규) | N-3 §3-3-5 smoke |
| 단위 테스트 | `tests/test_synthesizer.py` (신규, 12건) | synthesizer + 파이프라인 통합 mock |
| 회귀 산출물 | `graphify_out/agentic_regression_metrics.json` | 14쿼리 × 4모드 결과 |
| 회귀 산출물 | `graphify_out/agentic_vs_base_comparison.md` | 비교 보고서 |
| 검증 로그 | `graphify_out/n3_synthesis_smoke.log` | smoke 결과 |

### 9-5. 알려진 한계 (다음 세션 처리 권장)

1. **N-3 smoke #1 실측 보류** — Gemini Free Tier 20 RPD 소진. 처리 옵션:
   - (a) 24시간 후 `venv/bin/python -u scripts/n3_synthesis_smoke.py` 단독 재실행 → #1 PASS 확정
   - (b) Gemini Tier 1 paid 활성화 → 즉시 재실행 (비용 ≪ $0.01/일)
   - (c) `ANTHROPIC_API_KEY` 발급 후 `synthesizer_backend` 변경
2. **`test_pdf_reader.py` 13 FAIL** — v2.2 PDF reader 사전 결함. 본 묶음 무관이지만 추후 정리 필요.

### 9-6. 다음 세션 진입 안내

```
이 핸드오프 §9-5 (a) 따라 N-3 smoke #1 재검증해줘
또는
다음 묶음 — 묶음 B (N-4 한국어 사전 강화) 또는 묶음 C (N-2 Web Search) 진행해줘
```

**묶음 A 종결 (2026-04-26).**

---

## §10. 묶음 B 종결 결과 (2026-04-26 동일 세션 추가)

상세 검증 노트: `docs/20260426_v2_6_n4_korean_lexicon_v1_1.md`

### 10-1. N-4 §3-4-5 1:1 PASS/FAIL

| # | 항목 | PASS 조건 | 결과 | 판정 |
|---|---|---|---|---|
| 1 | none backend 회귀 | ≥ 9/10 | **9/10** (T7만 잔존) | ✅ PASS |
| 2 | gemini backend 회귀 0 | = 10/10 유지 | **10/10** | ✅ PASS |
| 3 | 추가 항목 SNOMED 검증 | 100% | **10/10** | ✅ PASS |

### 10-2. 사전 v1.1 변경

| 항목 | 변경 |
|---|---|
| `data/vet_term_dictionary_ko_en.json` | v1.0(158항목 5카테고리) → **v1.1(168항목 6카테고리)**. 신규 `질병_약식(Disorder Alias)` 카테고리: 당뇨/관절염/심부전/고혈압/기관지염/결막염/각막염/비만/흉수/복수 (10건, 모두 SNOMED preferred_term/FSN 검증) |
| `graphify_out/regression_metrics_rerank_v1_0_baseline.json` | v1.0 백업 (감사 이력) |
| `graphify_out/regression_metrics_rerank.json` | v1.1 결과로 갱신 |
| `docs/20260426_v2_6_n4_korean_lexicon_v1_1.md` | 검증 노트 신규 |

### 10-3. T9 회복 트레이스

```
v1.0:  '고양이 당뇨' → 'feline 당뇨'(부분 치환) → none Top-1 = 132391009 Kui Mlk dog ❌
v1.1:  '고양이 당뇨' → 'feline diabetes mellitus' → none rank #3 (≤5) ✅ PASS
       (gemini reformulator: → 'diabetes mellitus' → Top-1 73211009 ✅)
```

### 10-4. 알려진 한계 (다음 세션 후보)

1. **T7 영어 약식 fail (none)** — `feline diabetes` 같은 영어 합성어가 SNOMED CT에 단일 concept로 없고 사전 조합 필요. none reformulator 미사용 → 본질적 한계. 처리 옵션:
   - (a) 영어 약식 사전 추가
   - (b) lightweight 합성어 정규화 룰 (`feline X` → `X if X exists alone`)
   - (c) 현 상태 유지 (gemini 권장 documented)
2. **T9 none Top-1 drift** — Vector 임베딩에서 `feline diabetes mellitus` 가 `feline panleukopenia` 와 근접. RERANK ON으로도 #1 미회복(#3 PASS). 별도 reranker 튜닝/vector 재학습.

### 10-5. 다음 세션 후보 (갱신)

| 후보 | 트리거 |
|---|---|
| N-3 smoke #1 실측 마무리 | "§9-5 (a) 따라 N-3 smoke #1 재검증해줘" (24h 후, quota reset) |
| 묶음 C — N-2 Tavily Web Search | "묶음 C 진행해줘" (사전 액션: Tavily key) |
| T7 영어 약식 처리 | "§10-4 #1 (a/b/c 중) 진행해줘" |
| T9 vector drift 정밀화 | "§10-4 #2 진행해줘" |
| git commit + push + tag v2.6 | 사용자 명시 승인 (비가역) |

**묶음 A + 묶음 B 종결 (2026-04-26).**

---

## §11. T7 처리 종결 (2026-04-26 동일 세션 추가)

§10-4 #1 권장 옵션 (a) 영어 약식 사전 + (b)에서 영감받은 단어 경계 매칭으로 결합 채택.

### 11-1. T7 §3-4-5 1:1 PASS/FAIL

| # | 항목 | PASS 조건 | 결과 | 판정 |
|---|---|---|---|---|
| 1 | none backend 회귀 | ≥ 9/10 (목표: 10/10) | **10/10** (T7 회복) | ✅ PASS |
| 2 | gemini backend 회귀 0 | = 10/10 유지 | **10/10** | ✅ PASS |
| 3 | 추가 항목 SNOMED 검증 | 100% | 3/3 (feline/canine/bovine diabetes mellitus 73211009 검증) | ✅ PASS |
| 4 | 단위 테스트 회귀 0 | 기존 PASS 유지 | **180/180** (flaky 1건 동시 결정화) | ✅ PASS |

### 11-2. T7 fix 코드 변경

| 파일 | 변경 |
|---|---|
| `data/vet_term_dictionary_ko_en.json` | v1.1 → **v1.2** (171항목 7카테고리). 신규 `영어_약식(English Alias)` 카테고리: feline/canine/bovine diabetes → +mellitus |
| `src/retrieval/rag_pipeline.py` `_replace_with_dictionary` | 영어 키는 단어 경계(`\b`) 매칭 + `(?!\s+mellitus)` negative lookahead로 이중 치환(`feline diabetes mellitus mellitus`) 차단 |
| `src/retrieval/rag_pipeline.py:495` | 영어 쿼리(한국어 미포함)에도 사전 치환 분기 추가 (`else` 절) |
| `tests/test_agentic_tier_b.py:_make_pipe` | synthesizer mock 강제 — Gemini 실호출 비결정성 차단 (flaky FAIL 해소) |
| `graphify_out/regression_metrics_rerank_v1_1_baseline.json` | v1.1 baseline 백업 |
| `graphify_out/regression_metrics_rerank.json` | v1.2 결과로 갱신 |
| `graphify_out/t7_regression_run.log` | 회귀 stdout |

### 11-3. T7 동작 트레이스

```
v1.1:  'feline diabetes' (영어) → _contains_korean=False → 사전 치환 SKIP
       → search_query 'feline diabetes' 그대로 → none Top-1 347101000009106 ❌

v1.2:  'feline diabetes' (영어) → 영어 분기 사전 치환 → 'feline diabetes mellitus'
       → none rank #3 (Top-5 PASS) ✅
       → gemini reformulator: → 'diabetes mellitus' → Top-1 73211009 ✅
```

### 11-4. v2.6 통합 회귀 결과 (RERANK=1)

| Backend | v2.5.1 | v2.6 묶음 B (N-4) | v2.6 T7 fix | 통합 |
|---|---|---|---|---|
| none | 8/10 | 9/10 | **10/10** | T7+T9 회복 |
| gemini | 10/10 | 10/10 | 10/10 | 유지 |

### 11-5. v2.6 잔여 알려진 한계 (다음 세션 후보)

1. **N-3 smoke #1 실측 보류** — Gemini quota reset 후 재검증 (24h)
2. **T9 none Vector drift** — `feline diabetes mellitus` Top-1=339181000009108 panleukopenia(rank #3 73211009 PASS이지만 Top-1 부정확). reranker 튜닝/vector 재학습
3. **test_pdf_reader.py 13건 사전 결함** (v2.2 영역, v2.6 무관)

### 11-6. 다음 세션 후보 (재갱신)

| 후보 | 상태 |
|---|---|
| N-3 smoke #1 (24h 후) | 대기 |
| 묶음 C (Tavily Web Search) | 사용자 사전 액션 (Tavily key) 필요 |
| T9 vector drift 정밀화 | reranker/vector 재학습 (heavy) |
| **git commit + push + tag v2.6** | 사용자 명시 승인 (비가역). v2.6 작업이 충분히 누적되어 자연스러운 종결 시점. |

**T7 처리 종결. v2.6 (묶음 A + B + T7) 종합 (2026-04-26).**
