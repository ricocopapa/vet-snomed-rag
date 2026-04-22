# v2.0 Reranker Smoke 리포트 (Day 2 체크포인트)

**날짜**: 2026-04-22  
**작성자**: A1 Reranker 구현 에이전트 (Specialist/Sonnet)  
**모델**: BAAI/bge-reranker-v2-m3 (MIT, HuggingFace)  
**측정 환경**: macOS Darwin 25.4.0, Apple Silicon MPS, Python 3.14 (venv)

---

## §1. 실측 결과

### §1.1 회귀 세트 위치
- `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag/graphify_out/regression_metrics.json`
- 11쿼리 (T1~T11), v1.0 `none` 모드 기준 PASS 7/10 (T5 NA 제외)

### §1.2 v1.0 Baseline Smoke (1쿼리 확인)
| 쿼리 | concept_id | Term | Latency | PASS |
|---|---|---|---|---|
| feline panleukopenia SNOMED code | 339181000009108 | Feline panleukopenia | 899ms | ✅ |

> **측정 방법**: `SNOMEDRagPipeline(llm_backend='none', reformulator_backend='none')` → `pipeline.query(q, rerank=False)`. `preprocess_query()`가 "SNOMED code" 메타 불용어를 제거하여 실제 검색 쿼리 = "feline panleukopenia"

---

## §2. 구현 요약

### §2.1 신규 파일: `src/retrieval/reranker.py`
| 클래스/함수 | 역할 |
|---|---|
| `BGEReranker` | `sentence_transformers.CrossEncoder` 래퍼. BAAI/bge-reranker-v2-m3 로드 |
| `BGEReranker.rerank(query, candidates, top_n=5)` | Top-N 후보 → CrossEncoder 점수 계산 → top_n 반환 |
| `RerankedResult` | SearchResult + rerank_score 필드를 가진 dataclass |
| `get_reranker(device=None)` | 싱글턴 팩토리 (최초 호출 시 모델 로드, 이후 재사용) |

**의존성**: `sentence-transformers>=2.7.0` (기존 requirements.txt 재활용, 추가 패키지 0개)

### §2.2 수정 파일: `src/retrieval/hybrid_search.py` (feature flag 구조)
```python
# 초기화: enable_rerank=False 기본값
HybridSearchEngine(enable_rerank=False)

# 검색: rerank=False 기본값 → v1.0 코드 경로 100% 동일
engine.search(query, top_k=10, rerank=False)   # v1.0 경로

# rerank=True → Top-20 검색 → BGEReranker → Top-5 반환
engine.search(query, top_k=10, rerank=True)    # v2.0 경로
```

**feature flag 격리 구조**:
- `rerank=False`이면 `if rerank and self._enable_rerank:` 분기 진입 안 함 → v1.0 코드 경로 완전 동일
- `enable_rerank=False`이면 초기화 시 모델 로드 없음 (지연 로딩)

### §2.3 수정 파일: `src/retrieval/rag_pipeline.py`
- `SNOMEDRagPipeline.__init__(enable_rerank=False)` 파라미터 추가
- `SNOMEDRagPipeline.query(question, rerank=False)` 파라미터 추가
- 반환 딕셔너리에 `"reranked": bool` 필드 추가

---

## §3. 3쿼리 Smoke 결과

### §3.1 rerank=False (v1.0 경로 검증)

| 쿼리 | Top-1 concept_id | Top-1 Term | Latency p50 | v1.0 baseline 일치 |
|---|---|---|---|---|
| feline panleukopenia virus infection | 407400009 | Feline panleucopenia virus | 931ms | N/A (새 쿼리) |
| canine parvovirus | 47457000 | Canine parvovirus | 348ms | ✅ (T2 기록과 일치) |
| 고양이 당뇨 | 297461008 | Korean language | 1,958ms | ✅ (T9 none=FAIL 기록과 일치) |

> **참고**: "feline panleukopenia virus infection"은 regression_metrics.json에 없는 새 쿼리. T1("feline panleukopenia SNOMED code")과 다른 쿼리임 — T1 smoke는 §1.2에서 별도 확인 완료(PASS).

### §3.2 rerank=True (BGE 리랭커 적용)

| 쿼리 | Top-1 concept_id | Top-1 Term | Latency | reranked | 비고 |
|---|---|---|---|---|---|
| feline panleukopenia virus infection | 334421000009101 | Feline leukemia virus infection | 9,469ms* | ✅ | 정답 Top-3 위치 (#3: 339181000009108) |
| canine parvovirus | 47457000 | Canine parvovirus | 1,099ms | ✅ | Top-1 유지 PASS |
| 고양이 당뇨 | 297668006 | Nkole language | 2,914ms | ✅ | 한국어 쿼리 번역 미적용 — 관찰 기록 |

*최초 모델 로드 포함 (BGE 모델 다운로드 ~155초, 이후 캐시)

### §3.3 Top-5 상세 (rerank=True)

**Q1: "feline panleukopenia virus infection"**
| 순위 | concept_id | Term |
|---|---|---|
| 1 | 334421000009101 | Feline leukemia virus infection |
| 2 | 407400009 | Feline panleucopenia virus |
| **3** | **339181000009108** | **Feline panleukopenia** ← 정답 |
| 4 | 340931000009100 | Vaccine product containing Feline panleukopenia virus antigen |
| 5 | 354701000009102 | Parenteral vaccine product containing ... panleukopenia virus antigens |

**Q2: "canine parvovirus"**
| 순위 | concept_id | Term |
|---|---|---|
| **1** | **47457000** | **Canine parvovirus** ← 정답 |
| 2 | 342481000009106 | Canine parvovirus infection |
| 3 | 345501000009106 | Canine parvovirus antigen test kit |
| 4 | 708216003 | Deoxyribonucleic acid of Canine parvovirus |
| 5 | 709323009 | Canine parvovirus antigen |

**Q3: "고양이 당뇨" (한국어 번역 미적용)**
| 순위 | concept_id | Term |
|---|---|---|
| 1 | 297668006 | Nkole language |
| 2 | 704612000 | Singapore sign language |
| 3 | 704606005 | Penang sign language |
| 4 | 297423005 | Karamojong language |
| 5 | 704618001 | Chiangmai sign language |

---

## §4. v1.0 Regression 검증

| 검증 항목 | 결과 |
|---|---|
| `rerank=False` 경로 v1.0과 동일 | **PASS** (T2 concept_id 동일, T9 FAIL 패턴 동일) |
| T1 baseline smoke (`feline panleukopenia SNOMED code`, rerank=False) | **PASS** (339181000009108 Top-1) |
| `enable_rerank=False` 시 모델 로드 없음 | **PASS** (지연 로딩 확인) |
| v1.0 코드 경로 변경 없음 | **PASS** (feature flag 뒤에만 신규 로직) |

---

## §5. Latency 델타 (warm cache, 3회 평균)

| 쿼리 | rerank=False p50 | rerank=True p50 | 델타(ms) | 델타(%) |
|---|---|---|---|---|
| feline panleukopenia virus infection | 931ms | 1,485ms | +554ms | +59% |
| canine parvovirus | 348ms | 684ms | +336ms | +97% |
| 고양이 당뇨 | 1,958ms | 2,081ms | +123ms | +6% |

> **참고**: v1.0 baseline p50 = ~1,064ms (11쿼리 평균). 리랭커 오버헤드는 쿼리당 약 300~600ms. p95는 첫 모델 로드 시만 높음(~7,000ms), 이후 안정화.
>
> **설계 목표(§5.1)**: +30% 이내. 실측에서 canine parvovirus 쿼리가 +97%로 초과.  
> **원인 분석**: Top-20 후보에 대한 CrossEncoder 배치 추론이 CPU/MPS에서 200~400ms 소요.  
> **완화 방안**: Day 3 11쿼리 전체 회귀 시 평균 latency로 재측정 예정.

---

## §6. 리스크 / 블로커

| 리스크 | 상태 | 조치 |
|---|---|---|
| **한국어 쿼리 리랭킹 실패** | 🟡 관찰 | 리랭커에 `final_search_query`(전처리된 영어) 전달. 단, `고양이 당뇨`는 `preprocess_query`가 한국어 유지 → Ollama/Gemini 번역 없이는 영어 변환 불가. **Day 3에서 `reformulator_backend=gemini` 조합 테스트 권장** |
| **rerank=True Top-1 정확도 하락** | 🟡 관찰 | Q1에서 rerank=False Top-1(407400009)이 rerank=True Top-1(334421000009101)보다 정답에 더 가까움. CrossEncoder가 "virus infection" 표현 때문에 leukemia를 선호한 것으로 추정. Top-3 안에 정답 존재 → MRR 관점에서는 개선 여지 있음 |
| **latency +30% 초과** | 🟡 관찰 | 단일 쿼리 기준 +59~97%. Day 3 11쿼리 평균값으로 재평가 예정 |
| **BGE 모델 최초 다운로드 155초** | ✅ 해결 | 이후 HuggingFace 캐시(`~/.cache/huggingface/`)에서 즉시 로드 (~2초) |

---

## §7. Day 3 넘김 이슈

- **11쿼리 전체 회귀 실행** (Day 3): T1~T11 대상, rerank=False / rerank=True 양쪽 측정
- **한국어 쿼리 + reformulator 조합 테스트**: `enable_rerank=True` + `reformulator_backend=gemini` → T9/T10/T11 개선 여부 확인
- **MRR/NDCG 계산**: rerank 전후 순위 품질 정량화
- **`benchmark/v2_reranker_report.md`** 최종 작성 (Day 4)
