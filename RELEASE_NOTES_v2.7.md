# Release Notes — v2.7 (2026-04-26)

> **v2.7 — Tier C: Tavily Web Search 통합**
>
> v2.5 Tier B(UMLS+PubMed) + v2.6 묶음 A/B/T7/R-4에 이어, **v2.7은 Tier C로 Tavily Web Search를 추가**해 일반 웹/뉴스/가이드라인/규제 정보를 SNOMED 매핑에 보강한다. NLM 공식 무료 도구만 쓰던 외부 도구 layer가 일반 웹까지 확장되어, "최신 권고/리콜/가이드라인" 같은 도메인 외 신호를 수집할 수 있게 됐다.

---

## 핵심 메트릭

| 항목 | v2.6 | v2.7 (이번) | 변화 |
|---|---|---|---|
| **단위 테스트 누적** | 190 | **207** | +17 (web_search 12 + source_router web 5) |
| **11-쿼리 정밀 회귀 (none, RERANK=1)** | 10/10 | **10/10** | 회귀 0 |
| **11-쿼리 정밀 회귀 (gemini, RERANK=1)** | 10/10 | **10/10** | 회귀 0 |
| **외부 도구 종류** | 2 (UMLS, PubMed) | **3 (UMLS, PubMed, Web)** | Tier C 신규 |
| **Tavily 실 호출 smoke** | — | **§3-3-5 4/4 PASS** | 신규 |
| **외부 호출 credit 사용** | UMLS·PubMed 무료 | + Tavily Free 1,000/월 | 무료 한도 내 |

---

## v2.7 R-3 — Tier C: Tavily Web Search

### 채택 근거 (Combo Beta 채택)
도메인 분석 결과 **"가이드라인·리콜·뉴스" 정보는 LOCAL DB(SNOMED VET)와 학술 DB(UMLS/PubMed)로 커버 안 됨**. AAHA 가이드라인, FDA 리콜, 신규 규제 등은 일반 웹에 분산되어 Tavily Web Search가 가장 적합:

| 도구 | 가치 | 인증 | 비용 |
|---|---|---|---|
| **C-1 Tavily Search** | 일반 웹 + 뉴스 + 가이드라인/규제 | API Key (이메일 가입, 카드 불필요) | Free 1,000 credits/월 |

### 신규 모듈
- `src/tools/web_search_client.py` (~210줄) — `pubmed_client.py` 패턴 미러
  - POST `https://api.tavily.com/search` + `Authorization: Bearer tvly-...`
  - 정규화 응답 `{title, url, content, score, source: "tavily"}`
  - Search depth: `basic`(default, 1 credit), `fast`, `advanced`(2 credits)
  - Rate: 토큰 버킷 5 rps (보수적, Tavily 명시 제한 없음)

### 핵심 안전장치 (UMLS/PubMed 패턴 동일)
- **env 미설정 자동 비활성** — `TAVILY_API_KEY` 미설정 시 `enabled=False` → 호출 0건 (회귀 0 보장)
- **5종 graceful fallback** — 401(인증 실패, 영구 차단) / 429(backoff [1·2·4s]) / timeout / 네트워크 오류 / non-2xx → 빈 결과
- **LRU+TTL cache 24h** — 동일 쿼리 재호출 시 외부 호출 0
- **Tier A·B 회귀 0 보장** — `external_tools=[]` default 유지

### 라우팅 룰 (`source_router.py` 확장)
- **Web 활성 키워드:**
  - 영어: `news`, `breaking`, `web search`, `google`, `guideline`, `regulation`, `FDA`, `EMA`, `recall`
  - 한국어: `뉴스`, `웹 검색`, `구글`, `가이드라인`, `규제`, `허가`, `리콜`
- **PubMed와 분리** — PubMed는 학술 문헌(`literature`/`evidence`/`논문`/`문헌`/`최신`/`희귀`), Web은 일반/뉴스/규제로 도메인 분리

### 통합 (`agentic_pipeline.py` 확장)
- `TavilyWebSearchClient` import + `__init__`에 `web_client` 파라미터 추가 (DI)
- Step C에 `"web" in route.external_tools` 분기 — UMLS/PubMed와 동일 패턴
- `_format_web_md()` 신규 — `[Web Search]` markdown 섹션, title + URL + content snippet(200자 cut) + score

### 실 호출 검증 (`scripts/v2_7_tier_c_web_smoke.py`)
사용자 키로 실측:
```
[feline diabetes management 2026 guideline]
  → AAHA 2026 Diabetes Management Guidelines for Cats (score=0.87)
  → 추가 2건 (수의 임상 가이드라인 사이트)

[veterinary panleukopenia vaccine recall]
  → RECALL ALERT FOX5Vegas (score=0.53)
  → AVMA Feline panleukopenia (score=0.30)
  → FDA adverse event reports (score=0.29)
```

### §3-3-5 성공 기준 1:1 PASS/FAIL

| # | 항목 | 결과 |
|---|---|---|
| 1 | env 미설정 자동 비활성 | ✅ PASS |
| 2 | 정상 검색 ≥ 1건 결과 (실 호출) | ✅ PASS (2 쿼리 모두 ≥3건) |
| 3 | 라우팅 룰 web 분기 정상 (8 케이스) | ✅ PASS (8/8) |
| 4 | 단위 테스트 ≥ 7건 PASS | ✅ PASS (12/12) |

### Tavily 비용 분석
- v2.7 smoke 실행: ~2 credits 사용 (Free 1,000/월 한도의 0.2%)
- v2.7 11쿼리 회귀: web 키워드 미포함 → Tavily 호출 0
- 운영 시 회귀 ≤10 + cache 24h → 월 사용량 수십 건 수준 → **무료 한도 영구 가능**

---

## 마이그레이션 가이드

### 신규 환경변수
```bash
# .env 추가
TAVILY_API_KEY=tvly-발급받은_Tavily_키
```

### API 키 발급
- **Tavily**: [app.tavily.com](https://app.tavily.com) 이메일 가입 → Dashboard에서 API key 복사 (카드 등록 불필요, Free 1,000 credits/월)

### 코드 마이그레이션
- 기존 코드는 **변경 0** (`web_client` 파라미터 default None → 자동 init, env 미설정 시 비활성)

### Breaking Changes
**없음.** 모든 변경은 backward-compatible:
- `AgenticRAGPipeline.__init__`의 `web_client`: default None → 자동 init (env 기반)
- `SourceRoute.external_tools`에 "web" 추가는 키워드 매칭 기반 (기존 쿼리 영향 0 — Web 키워드 없는 쿼리는 라우팅 변화 0)

---

## Known Limitations

1. **R-2 N-3 smoke #1 (+30% 길이 기준)** — v2.6 작업의 한계. T13/T14 multi-iter loop 외부 결과 누적이 합성으로 연결 안 되는 구조. **v2.8 R-7 후보**로 분리.
2. **`ANTHROPIC_API_KEY` `.env` 빈 값** — Claude fallback 미가용 (영향 0).
3. **Tavily Pay As You Go 미테스트** — Free 1,000 credits 한도 내 동작만 검증. 한도 초과 시 동작은 미실측.

---

## 산출물 통계 (v2.7 누적)

| 분류 | 변경 |
|---|---|
| 신규 모듈 | 1 (`src/tools/web_search_client.py`) |
| 확장 모듈 | 2 (`src/retrieval/agentic/source_router.py`, `src/retrieval/agentic_pipeline.py`) |
| 신규 테스트 | 1 (`tests/test_web_search_client.py` 12건) + 5건 (`test_source_router.py`에 web 추가) |
| 신규 스크립트 | 1 (`scripts/v2_7_tier_c_web_smoke.py`) |
| 산출물 | `graphify_out/v2_7_tier_c_web_smoke.log` (smoke 결과) |

---

## Acknowledgements
- **Tavily** — Web Search API + Free 1,000 credits/월 (카드 불필요)
- **NLM UMLS Terminology Services** — UMLS REST + Affiliate License (v2.5)
- **NCBI E-utilities** — PubMed esearch / esummary (v2.5)
- **Google Gemini** — Flash Lite Preview (v2.6 합성)
- **BAAI** — bge-reranker-v2-m3 (v2.0+)
- **VTSL (Virginia Tech)** — SNOMED VET Extension March 2026 Production

---

## Links
- Repository: [github.com/ricocopapa/vet-snomed-rag](https://github.com/ricocopapa/vet-snomed-rag)
- Tavily: [app.tavily.com](https://app.tavily.com) · [docs](https://docs.tavily.com)
- 이전 릴리즈: [v2.6](./RELEASE_NOTES_v2.6.md) · [v2.5](./RELEASE_NOTES_v2.5.md) · [v2.4](./RELEASE_NOTES_v2.4.md) · [v2.0](./RELEASE_NOTES_v2.0.md)
