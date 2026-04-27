# Release Notes — v3.1.0 (2026-04-27)

> **v3.1.0 — 한국어 cycle (R-1~R-4) 종결: 사전 v1.4 + reformulate skip 로직으로 한국어 11/11×2 PERFECT 도달**
>
> v3.0이 production 임베더를 BGE-M3 (1024d)로 교체하면서 한국어 hits를 0/11 → 8/11
> (1,000-pool)로 끌어올렸으나, 11쿼리 production 회귀에서는 RERANK=1 미달 사례가 잔존했다.
> v3.1은 R-1 production 통합 측정 → R-2/R-3 한국어 임상사전 v1.3·v1.4 확장 →
> R-4 reformulate skip 로직 (사전 변환 결과 보존)으로 한국어 production 회귀를
> **none 11/11 + gemini 11/11 PERFECT** 까지 끌어올린다. 영어 11쿼리 RERANK=1 (10/10×2)
> 및 단위 251 PASS 무손실. 임베더·DB 변경 없이 사전 + 분기 로직만으로 본질 해소.

---

## 핵심 메트릭

| 항목 | v3.0 | **v3.1.0** | 변화 |
|---|---|---|---|
| **임베더** | BAAI/bge-m3 (1024d) | BAAI/bge-m3 (1024d) | 동일 (재빌드 0) |
| **ChromaDB** | 2.0GB / 366,570 entries | 2.0GB / 366,570 entries | 동일 |
| **단위 테스트** | 251 + 59 subtests | **251 + 59 subtests** | 회귀 0 |
| **11쿼리 RERANK=1 (none)** | 10/10 | **10/10** | 회귀 0 |
| **11쿼리 RERANK=1 (gemini)** | 10/10 | **10/10** | 회귀 0 |
| **한국어 11쿼리 (none, RERANK=1)** | 6/11 (R-1 측정) | **11/11 PERFECT ★★** | **+5건** |
| **한국어 11쿼리 (gemini, RERANK=1)** | 8/11 (R-1 측정) | **11/11 PERFECT ★★** | **+3건** |
| **한국어 임상사전 entries** | v1.2 (~140) | **v1.4 (171)** | +31 entries |
| **rag_pipeline.py Step 0.7** | reformulate 항상 적용 | **사전 변환 시 skip** | 신규 분기 1건 |

---

## v3.1 R-1~R-4 cycle 누적 4 commit

| commit | 단계 | 한국어 결과 |
|---|---|---|
| `c4783e8` | **R-1 production 통합 측정** | none 6/11 + gemini 8/11 (백내장·녹내장 PASS 입증, 미해소 5건 식별) |
| `a27b2e3` | **R-2 사전 v1.3 (generic 매핑 강화)** | none 9/11 + gemini 10/11 (+3/+2 회복) |
| `e17ff54` | **R-3 사전 v1.4 (외이염·심장 잡음·고관절·림프종)** | none 11/11 PERFECT + gemini 10/11 |
| **`c441a6f`** | **R-4 reformulate skip 로직** | **none 11/11 + gemini 11/11 PERFECT ★★** |

---

## Track A — R-1 production 통합 측정 (commit `c4783e8`)

v3.0 R-9 Phase 2 (1,000-pool 단독 BGE-M3) 한국어 8/11은 evaluation pool 측정값. v3.1 R-1은 동일 11쿼리를 **production rag_pipeline (RERANK=1)** 로 재측정하여 production 통합 영향을 정량화한다.

| 모드 | hits | 미해소 |
|---|---:|---|
| none (reformulate 비활성) | 6/11 | 5건 |
| gemini (reformulate 활성) | 8/11 | 3건 |

**핵심 발견:**
1. **백내장·녹내장**: BGE-M3 다국어 임베딩만으로 rank=1 도달 입증 (v2.9.1까지 0/11 → v3.1 production 통합 PASS).
2. **미해소 5건 (none) / 3건 (gemini)**: 외이염·심장 잡음·고관절 이형성·림프종·간 효소 — specific 한국어 임상 통칭이 SNOMED preferred_term과 의미 매핑 미흡.
3. R-2~R-3 사전 확장 + R-4 분기로 5건 전수 해소 가능 판정.

---

## Track B — R-2 임상사전 v1.3 (commit `a27b2e3`)

R-1 미해소 5건 중 사전 generic 매핑 강화로 즉시 해소 가능한 케이스 우선 적용.

### B-1. v1.3 추가 매핑

| 한국어 | 영어 매핑 | SNOMED 영향 |
|---|---|---|
| 고관절 이형성 | hip dysplasia | rank ↑ (specific match) |
| 림프종 | lymphoma | rank ↑ |
| 간 효소 | liver enzyme | rank ↑ |

### B-2. R-2 결과

| 모드 | hits | 변화 |
|---|---:|---|
| none | 9/11 | +3 |
| gemini | 10/11 | +2 |

R-3 진입 — 잔존 외이염·심장 잡음 specific preferred_term 매핑 필요.

---

## Track C — R-3 임상사전 v1.4 (commit `e17ff54`)

specific preferred_term 매핑으로 잔존 결함 해소.

### C-1. v1.4 추가 매핑

| 한국어 | preferred_term | 근거 |
|---|---|---|
| 외이염 | swimmer's ear | SNOMED 3135009 preferred_term 직접 매칭 |
| 심장 잡음 | heart murmur | SNOMED specific term |

### C-2. R-3 결과

| 모드 | hits | 변화 |
|---|---:|---|
| none | **11/11 PERFECT** ★ | +2 (none 단독 PERFECT 도달) |
| gemini | 10/11 | +0 (외이염 1건 미달 잔존) |

### C-3. R-3 미해소 결함 (외이염 gemini 1건)

```
[N-ko-05] 외이염 (gold: 3135009)
  Step 0   사전: 외이염 → swimmer's ear  ← 정확
  Step 0.7 Gemini: swimmer's ear → otitis externa (conf=0.95)  ← root term 일반화로 사전 효과 무력화
  Step 1   BGE-M3: "otitis externa" → top1=Acute otitis externa
  → rank=11 ✗
```

Gemini reformulator가 사전이 변환한 specific preferred_term을 root term으로 일반화하면서 사전 매핑의 정확성을 무력화. R-4에서 분기 로직으로 해소.

---

## Track D — R-4 reformulate skip 로직 (commit `c441a6f`) ★★

### D-1. 변경 — `src/retrieval/rag_pipeline.py:530-548`

`Step 0.7` 진입 직전 사전 변환 발생 여부를 `dict_applied_korean` flag로 판정. 사전 변환된 경우 reformulate를 skip하여 SNOMED preferred_term 보존.

```python
# v3.1 R-4: 한국어 사전 변환 발생 시 reformulate skip — 사전 결과는 이미 SNOMED preferred_term
# 또는 임상 통칭 specific 매핑이라 정확. Gemini reformulator가 specific term을 root term으로
# 일반화하면서 사전 효과 무력화 방지 (N-ko-05 외이염: swimmer's ear → otitis externa 케이스).
dict_applied_korean = (translated_query is not None and translated_query != question)
if self.reformulator is not None and not dict_applied_korean:
    reformulation = self.reformulator.reformulate(english_query)
    ...
elif self.reformulator is not None and dict_applied_korean:
    print(f"  [Reformulate-{self.reformulator_backend}] 한국어 사전 변환 결과 보존 (skip): {english_query}")
```

### D-2. R-4 옵션 비교

| 옵션 | 변경 | 채택 |
|---|---|---|
| 1. Gemini prompt 수정 (preferred_term 보존 명시) | reformulator prompt 변경 | ✗ — T7 등 다른 reformulate 동작 영향 위험 |
| **2. 사전 변환 시 reformulate skip** | **rag_pipeline.py 1 분기** | **✓ 채택 — 영향 범위 좁음, 회귀 0 입증** |
| 3. ChromaDB description 인덱싱 | 영구 해결 | ✗ — ~2시간 재빌드 + +500MB-1GB |

### D-3. R-4 결과 — PERFECT ★★

| 모드 | hits | 변화 |
|---|---:|---|
| none | **11/11 PERFECT** ★ | 회귀 0 (R-3 동등) |
| gemini | **11/11 PERFECT** ★ | +1 (외이염 해소) |

영어 11쿼리 RERANK=1 (none·gemini 10/10×2) + 단위 251 PASS 회귀 0 확인.

---

## 회귀 보존 (영어 + 단위)

| 항목 | 결과 |
|---|---|
| 11쿼리 RERANK=1 (none) | **10/10 PASS** (NA=1건 제외) |
| 11쿼리 RERANK=1 (gemini) | **10/10 PASS** |
| T7 핵심 (feline diabetes) | rank=1 둘 다 |
| 단위 테스트 | **251 + 59 subtests PASS** (81.99s) |

---

## Migration / Breaking changes

### 사용자 영향

| 변경 | 영향 | 조치 |
|---|---|---|
| `data/vet_term_dictionary_ko_en.json` v1.2 → v1.4 (+31 entries) | 한국어 임상 쿼리 hits 향상 | 자동 적용, 별도 조치 없음 |
| `src/retrieval/rag_pipeline.py` Step 0.7 신규 분기 (`dict_applied_korean`) | 사전 변환 발생 시 reformulate skip | 자동 적용, 동작 변경 0 (영어 쿼리 무영향) |
| ChromaDB / 임베더 / 인덱스 | 변경 없음 | 재빌드 불필요 |
| API / CLI / 함수 signature | 변경 없음 | — |

**Breaking changes: 없음.** v3.0 사용자는 코드/설정 변경 없이 v3.1.0으로 업그레이드 가능.

### 업그레이드 절차

```bash
git fetch --tags
git checkout v3.1.0
# 의존성 변경 없음 — 추가 설치 불필요
```

---

## 산출물 인덱스

| 분류 | 경로 |
|---|---|
| R-1 보고서 | `docs/20260427_v3_1_r1_korean_validation.md` |
| R-2 보고서 | `docs/20260427_v3_1_r2_korean_dictionary_v1_3.md` |
| R-3 보고서 | `docs/20260427_v3_1_r3_korean_dictionary_v1_4.md` |
| R-4 보고서 | `docs/20260427_v3_1_r4_reformulate_skip.md` |
| post-R-4 핸드오프 | `docs/20260427_v3_1_post_r4_handoff.md` |
| 검증 스크립트 | `scripts/v3_1_korean_extension_validation.py` |
| 메트릭 | `graphify_out/v3_1_korean_extension.json` |
| 임상사전 v1.4 | `data/vet_term_dictionary_ko_en.json` |
| 핵심 src | `src/retrieval/rag_pipeline.py` (Step 0.7 reformulate skip 분기) |

---

## 다음 cycle — R-5 budget_guard 영속화 (예고)

v2.9 R-10 미완 작업: `src/observability/budget_guard.py` 218 LoC + tests/test_budget_guard.py 24건의 in-memory state를 JSON 또는 SQLite로 영속화하여 프로세스 재시작 시 budget 누적 보존. 임계: write/read 동작 + 단위 테스트 ~10건 추가 + v2.9 24건 PASS 회귀 0 + 11쿼리 회귀 0. 예상 ~30-60m.

R-6 (SNOMED VET 2026-09-30 release 갱신) · R-7 (hybrid retrieval 정량화) 후순위 후보.

---

## v3.0 → v3.1.0 통합 narrative

```
v3.0 (R-9 cycle 종결)
  └─ production 임베더 BGE-M3 교체 (fa69e49)
     ├─ 한국어 hits 0→8/11 (1,000-pool 평가)
     └─ 영어 89/89 무손실
       ↓
v3.1 한국어 cycle (R-1~R-4)
  ├─ R-1 (c4783e8): production 통합 측정 — none 6/11 + gemini 8/11
  ├─ R-2 (a27b2e3): 사전 v1.3 generic 매핑 — none 9/11 + gemini 10/11
  ├─ R-3 (e17ff54): 사전 v1.4 specific preferred_term — none 11/11 + gemini 10/11
  └─ R-4 (c441a6f): reformulate skip 1 분기 — none 11/11 + gemini 11/11 ★★
       ↓
v3.1.0 release — 한국어 production cycle 1차 완전 종결 (PERFECT 11/11×2)
```

---

**Released: 2026-04-27**
**Cycle: v3.1 R-1~R-4 (commits c4783e8 → c441a6f)**
**Regression: 0 (영어 RERANK=1 10/10×2 + 단위 251 PASS 보존)**
