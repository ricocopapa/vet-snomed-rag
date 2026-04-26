---
tags: [vet-snomed-rag, v2.5, tier-b, external-tools, design]
date: 2026-04-25
version: 1.0
status: 사용자 승인 대기
related:
  - docs/20260424_v2_4_agentic_rag_design_v1.md
  - 01_Knowledge_Base/EMR/SNOMED_CT_VET_Fundamentals.md
---

# v2.5 Tier B 설계서 — 외부 도구 통합 (UMLS + PubMed)

## §1. 배경 및 목표

v2.4 Agentic RAG 11단계 다이어그램 ⑥ Sources의 "Tools & APIs" 분기 호출이 v2.4까지 미완성. v2.5 Tier A(완료)에서 Vector/SQL/Graph 가중치·플래그 분기까지 활성화. **Tier B는 외부 도구 분기(`use_external_tool`) 실제 호출을 활성화**한다.

**채택 조합 (Combo Alpha):** B-3 NLM UMLS REST + B-5 PubMed E-utilities

**채택 사유:**
1. 사용자 도메인(한국 수의 EMR + 향남병원 STT) 직접 적합 — UMLS의 ICD-10/11 cross-walk + 수의 임상 문헌 evidence
2. 둘 다 **NLM 공식, 무료** (한국 SNOMED 회원국 → UMLS Affiliate License 무료)
3. 회귀 위험 분리 — UMLS는 검색 단계 보강(concept cross-walk), PubMed는 LLM context 보강(evidence) → 충돌 없음

---

## §2. 외부 API 공식 사양 (조사 결과)

### B-3 UMLS REST API

| 항목 | 값 | 출처 |
|---|---|---|
| Base URL | `https://uts-ws.nlm.nih.gov/rest/` | UTS 공식 문서 |
| 인증 | `?apiKey={KEY}` 쿼리 파라미터 | [documentation.uts.nlm.nih.gov/rest/authentication](https://documentation.uts.nlm.nih.gov/rest/authentication.html) |
| 키 발급 | UTS My Profile → Generate API Key | NLM 공식 |
| 라이선스 | UMLS Affiliate (한국 회원국 무료) | NLM Affiliate Licence |
| 주요 엔드포인트 | `/content/current/CUI/{cui}` (concept) / `/search/current?string=...` (검색) / `/content/current/CUI/{cui}/atoms` (cross-walk) | UTS 공식 |
| Rate limit | 명시 없음 (합리적 사용) | UTS 공식 |

### B-5 PubMed E-utilities

| 항목 | 값 | 출처 |
|---|---|---|
| Base URL | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` | NCBI 공식 |
| 인증 | `&api_key={KEY}` (선택) | [ncbiinsights — New API Keys](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) |
| Rate limit | API 키 없을 때 3 rps / 있을 때 10 rps | NCBI 공식 |
| 429 발생 시 | exponential backoff 권장 | NCBI 공식 |
| 주요 엔드포인트 | `/esearch.fcgi?db=pubmed&term=...` (검색) / `/efetch.fcgi?db=pubmed&id=...&rettype=abstract` (본문) | E-utils 공식 |

---

## §3. Task Definition 5항목

### 3-1. 입력 데이터
- v2.5 Tier A PASS 코드 베이스 (smoke 12/12 + mini regression PASS)
- 외부 API 사양 (§2)
- 환경변수: `UMLS_API_KEY`, `NCBI_API_KEY` (사용자 사전 발급)

### 3-2. 판단 기준 (외부 도구 활성 트리거)

**UMLS 활성 조건 (라우터 룰):**
- 쿼리에 cross-walk 키워드 감지 (`"ICD-10"`, `"ICD-11"`, `"MeSH"`, `"RxNorm"`)
- 또는 LOCAL Top-1 score < `umls_fallback_threshold` (default 0.5)
- 또는 라우터가 명시적 cross-walk 의도 감지

**PubMed 활성 조건 (라우터 룰):**
- 쿼리에 신규/희귀 신호 (`"emerging"`, `"rare"`, `"novel"`, `"최신"`, `"신규"`)
- 또는 LOCAL Top-1 score < `pubmed_fallback_threshold` (default 0.4)
- 또는 라우터가 evidence 보강 필요 판단

**주의:** 외부 도구는 **항상 fallback 위치** — LOCAL DB가 충분하면 호출 안 함 (latency·rate limit 보호).

### 3-3. 실행 방법

**신규 모듈:**
| 파일 | 역할 |
|---|---|
| `src/tools/umls_client.py` | UMLS REST 클라이언트 (search, getCUI, getCrossWalk) + LRU+TTL cache |
| `src/tools/pubmed_client.py` | E-utils 클라이언트 (esearch+efetch) + rate limit (10 rps + 429 backoff) |
| `src/tools/_cache.py` | 공통 LRU+TTL cache (TTL 24h, max 1000 entries) |

**확장 모듈:**
| 파일 | 변경 |
|---|---|
| `src/retrieval/agentic/source_router.py` | `SourceRoute.external_tools: list[str]` 필드 추가 + cross-walk/evidence 라우팅 룰 |
| `src/retrieval/agentic_pipeline.py` | Step C 확장 — `route.external_tools` 분기 시 UMLS/PubMed 호출 → 결과를 LLM context로 합류 |
| `src/retrieval/rag_pipeline.py` | (변경 없음) — 외부 도구는 agentic_pipeline 레이어에서만 처리 |

**구조적 결정 — 왜 rag_pipeline이 아니라 agentic_pipeline에 통합?**
- v2.2 base.query() API 호환성 보존 (외부 도구 미사용 시 v2.4와 동일)
- agentic 루프(11단계)가 외부 도구 결과 처리에 더 적합 (relevance judge가 외부 결과 품질도 평가)
- rag_pipeline은 검색·생성 단순 책임 유지

### 3-4. 산출물 포맷

```python
# umls_client.search() 반환
{
    "cui": "C0011849",
    "preferred_name": "Diabetes Mellitus, Type 2",
    "semantic_types": ["Disease or Syndrome"],
    "cross_walks": {
        "ICD10CM": ["E11.9"],
        "MSH": ["D003924"],
        "SNOMEDCT_US": ["44054006"],
        "SNOMEDCT_VET": ["..."]  # 있을 때만
    },
    "source": "umls"
}

# pubmed_client.search() 반환
[
    {
        "pmid": "37123456",
        "title": "...",
        "abstract": "...",
        "year": 2025,
        "journal": "Vet J",
        "source": "pubmed"
    }
]
```

**LLM context 합류 형식 (agentic_pipeline):**
```
[Local SNOMED 검색 결과]
...
[UMLS Cross-Walk] (외부)
- CUI C0011849 (Diabetes Mellitus, Type 2)
  ICD-10-CM: E11.9 / MeSH: D003924 / SNOMEDCT_VET: ...

[PubMed Evidence] (외부)
- 2025 Vet J — "..." (PMID 37123456)
```

### 3-5. 성공 기준 (1:1 체크리스트, 완료 보고용)

| # | 항목 | PASS 조건 |
|---|---|---|
| B-S1 | UMLS 클라이언트 단위 smoke | search/getCUI/cross-walk + 401 인증 실패 graceful fallback |
| B-S2 | PubMed 클라이언트 단위 smoke | esearch/efetch + 429 backoff + 빈 결과 처리 |
| B-S3 | 공통 cache (`_cache.py`) | LRU 용량 한계 + TTL 만료 검증 |
| B-S4 | SourceRouter `external_tools` 라우팅 | cross-walk 키워드 → ["umls"], 신규 키워드 → ["pubmed"], 일반 쿼리 → [] |
| B-S5 | agentic_pipeline 외부 도구 통합 | route.external_tools 분기 시 호출 + context 합류 / 비활성 시 호출 0 |
| B-S6 | v2.4/Tier A 회귀 0 보장 | `source_route.external_tools=[]` default → Tier A 동일 (mini regression PASS) |
| B-S7 | 11-쿼리 정밀 회귀 | Top-1 hit rate >= 9/10 유지 |
| B-S8 | 인증/네트워크 실패 시 graceful fallback | API key 미설정 / 401 / 429 / 5xx / timeout 5종 시나리오 PASS |
| B-S9 | graphify 동기화 | exit 0 |

---

## §4. 위험 및 회피

| 위험 | 영향 | 회피 |
|---|---|---|
| UMLS API key 미발급 | 외부 도구 활성화 불가 | env 미설정 감지 시 자동 `use_external_tool=False` + README 안내 |
| PubMed 429 rate limit | retry 폭주 | 토큰 버킷 (10 rps cap) + exponential backoff (1·2·4s) + 3회 후 포기 |
| 네트워크 latency 증가 | agentic_query() 응답 시간 ↑ | per-tool timeout 3s + LRU cache 24h + parallel fetch (UMLS/PubMed 동시) |
| 외부 데이터 노이즈 | LLM context 오염 | UMLS는 정확 매칭 1건만 / PubMed는 max 3건 abstract / relevance judge가 평가 |
| UMLS Affiliate License 위반 | 라이선스 회수 | README에 라이선스 전제 + 사용자 동의 명시 / API key를 코드 commit 금지 (.env) |
| Tier A 회귀 실수 | 백엔드 분기 결과 변경 | external_tools=[] default + smoke #B-S6 자동 검증 |

---

## §5. 단계별 구현 계획 (분할)

| Stage | 작업 | 예상 시간 | 회귀 게이트 |
|---|---|---|---|
| **B-α** | 사용자 사전 액션 (API key 발급 + .env 설정) | 사용자 액션 (~10분) | env 변수 존재 확인 |
| **B-1** | `_cache.py` + `.env.example` + tests | 30분 | 단위 테스트 PASS |
| **B-2** | `umls_client.py` + tests | 1.5시간 | smoke #B-S1 PASS |
| **B-3** | `pubmed_client.py` + tests | 1시간 | smoke #B-S2 PASS |
| **B-4** | `source_router.py` 확장 + tests | 30분 | smoke #B-S4 PASS |
| **B-5** | `agentic_pipeline.py` 통합 + smoke 신규 | 1시간 | smoke #B-S5 PASS |
| **B-6** | mini regression + 정밀 11-쿼리 회귀 + graphify | 1.5시간 | #B-S6, #B-S7, #B-S9 PASS |

**총 예상 시간:** ~6시간 (사용자 액션 제외) — 한 세션 내 완료 가능 또는 2~3 세션 분할

**Stage 간 게이트:** 각 stage smoke PASS 확인 후 다음 stage 진입. 중간 실패 시 다음 stage 진입 금지.

---

## §6. 사용자 사전 액션 필수 (B-α)

| # | 액션 | URL | 비용 | 비고 |
|---|---|---|---|---|
| 1 | UMLS Affiliate License 확인/신청 | [uts.nlm.nih.gov/uts/signup-login](https://uts.nlm.nih.gov/uts/signup-login) | 무료 (한국 회원국) | 기 보유 시 skip |
| 2 | UMLS API key 발급 | UTS My Profile → Generate API Key | 무료 | `apiKey` 쿼리파라미터 인증 |
| 3 | NCBI 계정 + API key | [ncbi.nlm.nih.gov/account](https://www.ncbi.nlm.nih.gov/account/) → Settings → API Key | 무료 | 10 rps 권장 |
| 4 | `.env`에 추가 | (로컬 프로젝트 루트) | — | `UMLS_API_KEY=...` `NCBI_API_KEY=...` |

**대안:** 키 발급 어려우면 `use_external_tool=False` 강제로 v2.4/Tier A 모드 유지 가능 (Tier B는 활성화하지 않음).

---

## §7. 회귀 검증 전략

### 7-1. Tier A 회귀 0 보장
- `source_route.external_tools=[]` default → 외부 호출 0건 → v2.5 Tier A와 동일 동작
- 자동 검증: smoke #B-S6에서 `mock` 후 호출 카운트=0 단언

### 7-2. 외부 도구 활성 mini regression
- 쿼리 3종 × 외부 도구 활성/비활성 × 인증 실패 시나리오
- LLM 호출 없음 (검색 결과만 비교)

### 7-3. 정밀 11-쿼리 회귀
- `scripts/run_regression.py` 기존 런너 + `--external-tools` 옵션 신규
- 비용: Gemini API ~$0.10 / Claude API ~$0.30 (소액)
- Top-1 hit rate 9/10 유지 게이트

### 7-4. 인증/네트워크 실패 5종 시나리오
- API key 미설정 → use_external_tool=False 강제
- 401 (잘못된 키) → graceful skip + warning log
- 429 (rate limit) → backoff + 3회 후 포기
- 5xx (서버 장애) → graceful skip
- Timeout (3s 초과) → graceful skip

---

## §8. 사용자 승인 요청

이 설계서로 Tier B 구현 진입할지 확인 요청.

- **승인 시:** Stage B-α 사용자 액션 → 완료되면 B-1 ~ B-6 순차 구현 (한 세션 또는 분할)
- **변경 시:** 후보 조합 변경 (Combo Beta/Gamma) 또는 일부 stage 제거

API key 발급은 사용자 액션이라 **승인과 동시에 키 발급도 시작**하시면 효율적.
