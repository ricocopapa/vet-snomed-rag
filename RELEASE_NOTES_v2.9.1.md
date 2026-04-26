# Release Notes — v2.9.1 (2026-04-27)

> **v2.9.1 — v3.0 phase 1: budget_guard runtime 통합 + venv 정리 + R-8 후보 보고서**
>
> v2.9 R-10에서 PoC로 끝낸 `budget_guard`를 production runtime에 통합하고,
> `setup_env.sh` / `README.md`의 venv 이름 불일치를 정리하며, v3.0 R-8(embedder
> 교체) phase 1로 후보 비교 보고서를 추가한다.

---

## 핵심 메트릭

| 항목 | v2.9 | v2.9.1 (이번) | 변화 |
|---|---|---|---|
| **단위 테스트 누적** | 243 | **251** | +8 (BudgetGuard integration) |
| **11쿼리 정밀 회귀 (none, RERANK=1)** | 10/10 | **10/10** | 회귀 0 |
| **11쿼리 정밀 회귀 (gemini, RERANK=1)** | 10/10 | **10/10** | 회귀 0 |
| **runtime hook 통합** | PoC only | **production 호출점 통합** | synthesizer + web_search_client |

---

## Track A — runtime 통합 + 정비

### A-1. venv 이름 통일 (`.venv` → `venv`)

핸드오프 §1-3 표준은 `venv/`이지만 `setup_env.sh`/`README.md`가 `.venv/`로 작성되어 있어
신규 사용자가 `setup_env.sh` 실행 시 stale `.venv/`를 만들고 운영 `venv/`를 못 찾는 문제 발생.

- `setup_env.sh`: 3곳 수정 (생성·활성화·완료 메시지)
- `README.md`: 2곳 수정 (Docker 빌드 / 빠른 시작)

### A-2. budget_guard runtime 통합

v2.9 R-10에서 PoC standalone로 종결한 `BudgetGuard`를 실제 호출 경로에 통합:

| 위치 | 통합 내용 |
|---|---|
| `src/observability/__init__.py` | 싱글톤 `get_budget_guard()` + 테스트 격리용 `reset_budget_guard()` |
| `src/retrieval/agentic/synthesizer.py:128` 직후 | Gemini `response.usage_metadata`에서 token 추출 → `record_gemini()` |
| `src/tools/web_search_client.py:196` 직후 | 성공한 네트워크 호출만 `record_tavily_search(depth)` (cache hit은 미도달) |

방어:
- `usage_metadata` 없는 응답(legacy/mock) → silent skip
- 통합 코드 예외 발생 시 silent skip (합성 결과·검색 결과에 영향 X)

### 단위 테스트 — 신규 8건

`tests/test_budget_guard_integration.py`:

| 클래스 | 검증 |
|---|---|
| `TestSynthesizerHook` | usage_metadata 있을 때 기록 / 없을 때 silent (2건) |
| `TestWebSearchHook` | basic 1 credit / advanced 2 credits / cache hit 미기록 / failure 미기록 (4건) |
| `TestSingletonAccessor` | get_budget_guard 동일 인스턴스 / reset 후 재초기화 (2건) |

---

## Track B — R-8 v3.0 phase 1 (후보 조사)

`docs/20260427_r8_embedder_candidates.md` (26K, 8 후보 비교):

| # | 후보 | 권장 | 핵심 |
|---|---|---|---|
| 1 | **SapBERT** (cambridgeltl/SapBERT-from-PubMedBERT-fulltext) | ★ 1순위 | UMLS/SNOMED CT entity linking 직접 최적화. 2024-2025 매핑 벤치마크에서 BioBERT/PubMedBERT 상회. Apache 2.0, 월 다운로드 110만 |
| 2 | **NeuML/pubmedbert-base-embeddings** | ★ 2순위 | sentence-transformers 완전 호환 (코드 한 줄 교체). PubMed Pearson 95.62% (현행 +2.16%p) |
| 3 | MedCPT-Query-Encoder (NIH) | 후보 | NIH 공식, 의학 검색 최적화 |
| 4 | BioLinkBERT-base | 후보 | 인용 그래프 학습 |
| 5 | BiomedBERT (Microsoft) | 후보 | PubMed 풀텍스트 학습 |
| 6 | BioBERT (dmis-lab) | 후보 | 의학 NER 표준 |
| 7 | BGE-M3 (BAAI) | 후보 | 다국어, 1024차원 |
| 8 | e5-mistral-7b-instruct | **명시 배제** | 7B + 4096차원, GPU 필수, 의학 entity linking 비특화 |

**핵심 발견:** 수의학 코퍼스 학습 모델은 공개된 것이 **단 하나도 없음**. 모든 후보는 "인간 의학→수의학 전이"(Alpha Transfer) 가설에 의존.

**현행 한계:** `all-MiniLM-L6-v2` (384차원, 범용)는 SNOMED CT 매칭 정확도 ~64.73%로 SapBERT 계열(~70%) 대비 현저히 낮음.

---

## 사용자 결정 (R-8 phase 2 진입 시)

보고서 §6 U-1 ~ U-6 항목:

- **U-1** 모델 최종 선택 (SapBERT vs NeuML pubmedbert vs 다른 후보)
- **U-2** 차원 384 → 768 증가 허용 (저장 2배, ChromaDB 재구축 필수)
- **U-3** 라이선스 검토 (전체 후보 Apache/MIT 안전)
- **U-4** 한국어 처리 (현 사전+reformulate로 영어 임베더만 평가)
- **U-5** 샘플 100쿼리 선행 검증 vs 전수 재구축 직행
- **U-6** 카드 등록 (GPU 클라우드 사용 시. CPU 인덱싱은 1.5~3시간으로 가능)

---

## Commit

- `8c24f3b feat(v2.9.1): v3.0 phase 1 — budget_guard runtime 통합 + venv 정리 + R-8 후보 보고서`
- 7 files changed: 5 modified (`setup_env.sh` / `README.md` / `observability/__init__.py` / `synthesizer.py` / `web_search_client.py`) + 2 new (`tests/test_budget_guard_integration.py` / `docs/20260427_r8_embedder_candidates.md`)
- 단위 243 → 251 PASS (+8 integration), 회귀 0
