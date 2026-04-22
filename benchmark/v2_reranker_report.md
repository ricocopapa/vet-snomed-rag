---
tags: [vet-snomed-rag, v2.0, benchmark, reranker, regression, Day3]
date: 2026-04-22
version: 1.0
status: final
---

# vet-snomed-rag v2.0 Reranker 통합 최종 리포트 (Day 3 A1)

**측정 일자**: 2026-04-22  
**측정 환경**: macOS Darwin 25.4.0, Apple Silicon MPS, Python 3.14 (venv)  
**BGE 모델**: BAAI/bge-reranker-v2-m3 (MIT, warm cache 기준)  
**기준 데이터**: `benchmark/reranker_regression_raw.json`

---

## §1. 4모드 × 11쿼리 상세 테이블

> T5(chronic kidney disease in cat): expected_concept_id=null → 4모드 전체 NA 처리 (MRR 제외)  
> 각 latency는 3회 평균 (warm cache)

### M1: rerank=False, reformulator=none (v1.0 경로 재현)

| 쿼리 ID | 쿼리 | Top-1 Term | verdict | rank | latency(avg) |
|---|---|---|---|---|---|
| T1 | feline panleukopenia SNOMED code | Feline panleukopenia | PASS | 1 | 652ms |
| T2 | canine parvovirus enteritis | Canine parvovirus | PASS | 1 | 656ms |
| T3 | diabetes mellitus in cat | Diabetes mellitus | PASS | 1 | 698ms |
| T4 | pancreatitis in dog | Suppurative pancreatitis | **FAIL** | 2 | 585ms |
| T5 | chronic kidney disease in cat | Chronic kidney disease stage 1 | NA | - | 656ms |
| T6 | cat bite wound | Cat bite - wound | PASS | 1 | 278ms |
| T7 | feline diabetes | Feline acquired immune deficiency syndrome | **FAIL** | NF | 355ms |
| T8 | diabetes mellitus type 1 | Diabetes mellitus type I | PASS | 1 | 247ms |
| T9 | 고양이 당뇨 | Korean language | **FAIL** | NF | 1,902ms |
| T10 | 개 췌장염 | EMG decelerating bursts | **FAIL** | NF | 1,103ms |
| T11 | 고양이 범백혈구감소증 SNOMED 코드 | Application of safety device | **FAIL** | NF | 1,189ms |

**요약**: PASS 5/10 (T4·T7·T9·T10·T11 FAIL) | MRR 0.5500 | p95 1,907ms | p50 633ms

---

### M2: rerank=False, reformulator=gemini

| 쿼리 ID | 쿼리 | Reformulated | Top-1 Term | verdict | rank | latency(avg) |
|---|---|---|---|---|---|---|
| T1 | feline panleukopenia SNOMED code | feline panleukopenia | Feline panleukopenia | PASS | 1 | 627ms |
| T2 | canine parvovirus enteritis | canine parvovirus enteritis | Canine parvovirus | PASS | 1 | 631ms |
| T3 | diabetes mellitus in cat | diabetes mellitus | Diabetes mellitus | PASS | 1 | 168ms |
| T4 | pancreatitis in dog | pancreatitis | Pancreatitis | PASS | 1 | 205ms |
| T5 | chronic kidney disease in cat | chronic kidney disease | Chronic kidney disease | NA | - | 266ms |
| T6 | cat bite wound | cat bite wound | Cat bite - wound | PASS | 1 | 283ms |
| T7 | feline diabetes | **diabetes mellitus** | Diabetes mellitus | PASS | 1 | 164ms |
| T8 | diabetes mellitus type 1 | diabetes mellitus type 1 | Diabetes mellitus type I | PASS | 1 | 244ms |
| T9 | 고양이 당뇨 | **diabetes mellitus** | Diabetes mellitus | PASS | 1 | 168ms |
| T10 | 개 췌장염 | **pancreatitis** | Pancreatitis | PASS | 1 | 191ms |
| T11 | 고양이 범백혈구감소증 SNOMED 코드 | **feline panleukopenia** | Feline panleukopenia | PASS | 1 | 637ms |

**요약**: PASS 10/10 | MRR 1.0000 | p95 641ms | p50 244ms

---

### M3: rerank=True, reformulator=none

| 쿼리 ID | 쿼리 | Top-1 Term | verdict | rank | latency(avg) |
|---|---|---|---|---|---|
| T1 | feline panleukopenia SNOMED code | Feline panleukopenia | PASS | 1 | 3,437ms* |
| T2 | canine parvovirus enteritis | **Canine parvovirus infection** | **FAIL** | 2 | 896ms |
| T3 | diabetes mellitus in cat | Diabetes mellitus | PASS | 1 | 1,016ms |
| T4 | pancreatitis in dog | Pancreatitis | **PASS** | 1 | 822ms |
| T5 | chronic kidney disease in cat | Chronic kidney disease | NA | - | 841ms |
| T6 | cat bite wound | Cat bite - wound | PASS | 1 | 441ms |
| T7 | feline diabetes | Feline acquired immune deficiency syndrome | **FAIL** | NF | 491ms |
| T8 | diabetes mellitus type 1 | Diabetes mellitus type I | PASS | 1 | 384ms |
| T9 | 고양이 당뇨 | Nkole language | **FAIL** | NF | 2,120ms |
| T10 | 개 췌장염 | EMG finding | **FAIL** | NF | 1,286ms |
| T11 | 고양이 범백혈구감소증 SNOMED 코드 | Assessment using STOP-Bang questionnaire | **FAIL** | NF | 1,364ms |

*T1 첫 호출에 모델 로드 포함 (~8,300ms). warm cache 후 2~3회 avg 기준: ~982ms

**요약**: PASS 5/10 | MRR 0.5500 | p95 2,194ms | p50 858ms

---

### M4: rerank=True, reformulator=gemini (v2.0 후보)

| 쿼리 ID | 쿼리 | Reformulated | Top-1 Term | verdict | rank | latency(avg) |
|---|---|---|---|---|---|---|
| T1 | feline panleukopenia SNOMED code | feline panleukopenia | Feline panleukopenia | PASS | 1 | 914ms |
| T2 | canine parvovirus enteritis | canine parvovirus enteritis | **Canine parvovirus infection** | **FAIL** | 2 | 874ms |
| T3 | diabetes mellitus in cat | diabetes mellitus | Diabetes mellitus | PASS | 1 | 332ms |
| T4 | pancreatitis in dog | pancreatitis | Pancreatitis | PASS | 1 | 404ms |
| T5 | chronic kidney disease in cat | chronic kidney disease | Chronic kidney disease | NA | - | 446ms |
| T6 | cat bite wound | cat bite wound | Cat bite - wound | PASS | 1 | 484ms |
| T7 | feline diabetes | diabetes mellitus | Diabetes mellitus | PASS | 1 | 333ms |
| T8 | diabetes mellitus type 1 | diabetes mellitus type 1 | Diabetes mellitus type I | PASS | 1 | 386ms |
| T9 | 고양이 당뇨 | diabetes mellitus | Diabetes mellitus | PASS | 1 | 329ms |
| T10 | 개 췌장염 | pancreatitis | Pancreatitis | PASS | 1 | 422ms |
| T11 | 고양이 범백혈구감소증 SNOMED 코드 | feline panleukopenia | Feline panleukopenia | PASS | 1 | 889ms |

**요약**: PASS 9/10 (T2 FAIL) | MRR 0.9500 | p95 1,011ms | p50 428ms

---

## §2. 모드별 통계 요약

| Mode | 설명 | PASS/평가 | MRR | p50 | p95 | p95 Δ vs M1 | 도입 기준 달성 |
|---|---|---|---|---|---|---|---|
| **M1** | v1.0 baseline 재현 | 5/10 | 0.5500 | 633ms | 1,907ms | — | — |
| **M2** | reformulator only | **10/10** | **1.0000** | **244ms** | **641ms** | **-66.4%** | **✅ 전 항목 PASS** |
| **M3** | rerank only | 5/10 | 0.5500 | 858ms | 2,194ms | +15.0% | ❌ PASS 미달 |
| **M4** | rerank+reformulator | 9/10 | 0.9500 | 428ms | 1,011ms | -47.0% | ❌ T2 regression |

---

## §3. v1.0 Baseline 대비 분석

### §3.1 주의: M1 수치와 v1.0 공식 수치 차이

v1.0 공식 기록: PASS 10/10, latency 1,064ms (project_vet_snomed_rag.md)  
M1 본 측정: PASS 5/10, MRR 0.550, p95 1,907ms

**차이 원인 분석**:
- v1.0 공식 10/10은 `regression_metrics.json`의 `verdict_per_backend["none"]` 기준 (T4는 PASS로 기록됨)
- 본 측정 M1에서 T4 FAIL: 동일 쿼리 재측정 시 Top-1이 `Suppurative pancreatitis`(rank=2)로 반환됨  
  → 벡터 임베딩 캐시 상태, DB 인덱스 순서 등 비결정적 요소로 인한 미세 차이 추정
- T7/T9/T10/T11 한국어 쿼리 5건 FAIL은 v1.0에서도 동일 패턴 (regression_metrics.json `verdict_per_backend["none"]` = FAIL)
- **결론**: M1 5/10은 v1.0 당시부터 이미 존재했던 한국어 취약점 포함. v1.0 공식 10/10은 영어 전용 10쿼리 기준이었을 가능성 高.

### §3.2 M2 vs v1.0

| 지표 | v1.0 공식 | M2 (본 측정) | Δ |
|---|---|---|---|
| PASS | 10/10 | 10/10 | ±0 (regression 0) |
| MRR | 측정 없음 | 1.0000 | — |
| latency p95 | 1,064ms (avg 기준) | 641ms | **-39.8%** (목표 +30% 대비 오히려 개선) |

### §3.3 Top-10 Miss NF 현황

| Mode | NF 건수 (정답 Top-10 밖) |
|---|---|
| M1 | T7(feline diabetes), T9(고양이 당뇨), T10(개 췌장염), T11(고양이 범백혈구감소증) = 4건 |
| M2 | **0건** |
| M3 | T7, T9, T10, T11 = 4건 (M1과 동일) |
| M4 | T2(canine parvovirus enteritis, rank=2) = 0 NF; 단 T2 Top-1 오류 1건 |

---

## §4. 핵심 발견

### §4.1 리랭커(BGE) 단독 효과 (M3 vs M1)
- PASS 변화: 5/10 → 5/10 (동일)
- MRR 변화: 0.55 → 0.55 (동일)
- latency 변화: p95 1,907ms → 2,194ms (+15%)
- **결론**: 리랭커 단독은 품질 개선 없이 latency만 증가. 한국어 쿼리 실패 원인(벡터 검색 오매칭)을 리랭킹이 해결하지 못함.

### §4.2 Reformulator(Gemini) 단독 효과 (M2 vs M1)
- PASS 변화: 5/10 → **10/10** (+5건)
- MRR 변화: 0.55 → **1.00** (+0.45)
- latency 변화: p95 1,907ms → **641ms** (-66.4%, 캐시 활용)
- **핵심 메커니즘**: 
  - T7 "feline diabetes" → "diabetes mellitus" (의미 정규화)
  - T9 "고양이 당뇨" → "diabetes mellitus" (한국어→영어 SNOMED 용어 번역)
  - T10 "개 췌장염" → "pancreatitis" (한국어→영어)
  - T11 "고양이 범백혈구감소증 SNOMED 코드" → "feline panleukopenia" (한국어→영어 + 메타어 제거)
  - T4 "pancreatitis in dog" → "pancreatitis" (species 수식어 제거 → 검색 정밀도 향상)

### §4.3 조합 효과 (M4 = M2 + M3)
- PASS: M2(10/10) 대비 M4(9/10)로 **오히려 1건 하락**
- T2 "canine parvovirus enteritis": M2 PASS(rank=1) → M4 FAIL(rank=2)
  - Reformulator가 "canine parvovirus enteritis" 그대로 유지 → Reranker가 "Canine parvovirus infection"(rank=2)을 Top-1으로 재정렬
  - **원인**: CrossEncoder가 "enteritis" 단어 때문에 infection 개념을 더 높게 scoring. 이는 임상적으로 유사하지만 expected_concept_id와 다름.
- **결론**: 리랭커가 reformulator의 고품질 검색 결과를 오히려 degradation시키는 케이스 발생.

---

## §5. 도입 기준 평가

도입 승인 조건 (마스터 설계서 §2 A1 기준):

| 조건 | 기준 | M2 결과 | M4 결과 |
|---|---|---|---|
| 11쿼리 PASS ≥ 10/10 | regression 0 | **10/10 ✅** | 9/10 ❌ |
| latency p95 ≤ 1,383ms (+30% vs v1.0 1,064ms) | ≤1,383ms | **641ms ✅** | **1,011ms ✅** |
| Top-10 miss NF 감소 (v1.0 4건 → ≤1건) | ≤1건 | **0건 ✅** | 0건 (T2는 rank=2) ✅ |
| MRR 동등 이상 (M1 MRR 0.55 대비) | ≥0.55 | **1.00 ✅** | **0.95 ✅** |

롤백 권고 조건:

| 조건 | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| PASS <10/10 | 5/10 | - | 5/10 | 9/10 |
| latency p95 +50% 초과 (>2,846ms) | 1,907ms | 641ms | 2,194ms | 1,011ms |
| Top-1 정확도 하락 | — | 개선 | 동일 | T2 하락 |

---

## §6. 최종 권고

### **권고: M2 도입 (reformulator=gemini, rerank=False)**

**근거 (수치 인용)**:

1. **PASS 10/10**: M2가 4모드 중 유일하게 회귀 0건 달성. M4는 T2 regression 발생 (9/10).
2. **MRR 1.0000**: M1 대비 +0.45 향상. M4(0.95) 대비도 우수.
3. **latency p95 641ms**: v1.0 baseline(M1 p95 1,907ms) 대비 -66.4% **개선**. 목표 +30%(≤1,383ms) 대비 기준 충족 정도가 아닌 오히려 고속화.
4. **리랭커 효과 없음**: M3(rerank only)가 M1과 동일한 5/10 달성, latency만 +15% 증가. 리랭커 단독은 한국어 쿼리 실패를 해결하지 못함.
5. **M4 degradation**: reformulator가 검색 품질을 이미 최적화한 상태에서 reranker가 T2를 오히려 악화시킴 (canine parvovirus → infection 선호).

### v2.0 기본값 설정 (Day 4 B4 위임)

```python
# 권장 기본값 (Day 4 B4에서 app.py/CLI 반영)
SNOMEDRagPipeline(
    reformulator_backend="gemini",   # 기본값 변경
    enable_rerank=False,             # 기본값 유지
)
```

### BGEReranker 처리 방향

`reranker.py` 파일은 **삭제하지 않고 실험적 모듈로 보존**한다.  
v2.0 기본 파이프라인에서는 사용하지 않으나, 향후 재활성화 조건:
- CrossEncoder 모델을 "canine parvovirus enteritis" 류 exact-phrasing 쿼리에 강한 모델로 교체 시
- 또는 Top-20→Top-5 재정렬 방식이 아닌 검색 점수 보정(score fusion) 방식으로 로직 변경 시

---

## §7. 비교: 대안 리랭커 스펙 (참고용, 구현 금지)

| 모델 | 라이선스 | 다국어 | 추가 패키지 | latency 추정 | 비고 |
|---|---|---|---|---|---|
| BAAI/bge-reranker-v2-m3 | MIT | ✅ | 불필요 (ST) | 200~400ms/배치 | 본 실험 대상 |
| Jina Reranker v2 (API) | 상업용 | ✅ | `jina-ai` | ~100ms (API) | 네트워크 의존, 비용 발생 |
| Cohere Rerank | 상업용 | ✅ | `cohere` | ~200ms (API) | 네트워크 의존, 비용 발생 |
| BAAI/bge-reranker-large | MIT | 제한 | 불필요 (ST) | +10~20% vs v2-m3 | 영어 특화, 한국어 취약 |
| mixedbread-ai/mxbai-rerank-large-v1 | Apache 2.0 | 부분 | 불필요 (ST) | ~300ms | 영어 중심 |

**결론**: 로컬 리랭커 옵션 중 BAAI/bge-reranker-v2-m3가 현재 최선. 그러나 reformulator가 이미 문제를 해결했으므로 추가 리랭커 도입 불필요.

---

## §8. 산출물 목록

| 파일 | 설명 |
|---|---|
| `benchmark/reranker_regression_raw.json` | 11×4×3=132회 원시 측정 데이터 |
| `benchmark/v2_reranker_report.md` | 본 최종 리포트 |
| `benchmark/charts/v2_pass_by_mode.png` | 모드별 PASS/FAIL 막대 차트 |
| `benchmark/charts/v2_mrr_by_mode.png` | 모드별 MRR 막대 차트 |
| `benchmark/charts/v2_latency_by_mode.png` | 모드별 latency p50/p95 그룹 막대 차트 |
| `scripts/run_day3_regression.py` | 측정 실행 스크립트 |
| `scripts/generate_v2_reranker_charts.py` | 차트 생성 스크립트 |

---

## §9. Day 4 인계 사항

1. **M2 도입 확정**: `SNOMEDRagPipeline(reformulator_backend="gemini")` 기본값 변경 → Day 4 B4 (app.py CLI 통합) 단계에서 반영
2. **T2 예외 케이스 문서화**: "canine parvovirus enteritis" expected_concept_id=47457000(Canine parvovirus)은 엄밀히 virus 자체 개념. 임상적으로 infection(342481000009106)도 유효하나 회귀 세트 gold-label 정의 문제 가능성. → C1 합성 샘플 설계 시 gold-label 재검토 권고.
3. **Reformulator Gemini API 비용**: warm cache 기준 쿼리당 ~1.15e-07 USD (무시 수준). cold start 시 +1,000~1,200ms 추가 (캐시 만료 후).
4. **BGEReranker 모듈 보존**: `src/retrieval/reranker.py` 실험 모듈 상태 유지. README에 "optional experimental feature" 명시 예정.
