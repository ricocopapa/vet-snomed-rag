---
review_target: T2 (regression_metrics.json)
query_text: "canine parvovirus enteritis"
created: 2026-04-22
reviewer: emr-planner + snomed-mapping skill
---

# T2 Gold-Label 재검토: "canine parvovirus enteritis"

## 현재 상태

```json
{
  "query_id": "T2",
  "query_text": "canine parvovirus enteritis",
  "expected_concept_id": "47457000"
}
```

현재 expected concept_id: `47457000` — **Canine parvovirus (organism)**

---

## 두 Concept 비교 분석

### Concept A: 47457000 (현재 gold-label)

| 항목 | 값 |
|---|---|
| concept_id | 47457000 |
| preferred_term | Canine parvovirus |
| FSN | Canine parvovirus (organism) |
| semantic_tag | **organism** |
| source | INT (SNOMED CT Core) |
| IS-A 계층 | organism → virus → DNA virus → Parvovirus → Canine parvovirus |

**의미:** 바이러스 병원체 자체 (CPV-2 바이러스 입자/종). 임상 질환이 아닌 병원체 분류 개념.

### Concept B: 342481000009106 (대안 후보)

| 항목 | 값 |
|---|---|
| concept_id | 342481000009106 |
| preferred_term | Canine parvovirus infection |
| FSN | Canine parvovirus infection (disorder) |
| semantic_tag | **disorder** |
| source | VET (VetSCT Extension) |
| IS-A 계층 | disorder → Infectious disease → Viral disease → Canine parvovirus infection |
| Causative agent (246075003) | 47457000 (Canine parvovirus) |

**의미:** CPV-2 바이러스가 개에게 일으키는 감염증 질환 개념. 장염(enteritis)은 이 감염증의 주요 임상 표현.

---

## 쿼리 "canine parvovirus enteritis" 분석

쿼리는 다음 두 의미 요소를 포함한다:
1. **병원체 특이성:** "canine parvovirus" → 원인체 명시
2. **임상 표현:** "enteritis" → 장염이라는 질환 소견 명시

**핵심 판단:** "canine parvovirus enteritis"는 "파보바이러스가 유발하는 개의 장염"이라는 **임상 질환 쿼리**다. 병원체 자체를 물어보는 것이 아니라, 그 병원체로 인한 **질환/감염 상태**를 의미한다.

---

## 오매핑 리스크 평가

### Concept A (47457000, organism) 유지 시 리스크

- semantic_tag = organism → snomed-mapping 원칙 1 화이트리스트: A축(진단) 허용 tag는 disorder/finding/situation/event
- **organism tag는 A축 금지 tag** — 오매핑 기준 TypeB 위반
- 쿼리에 "enteritis"라는 질환 단어가 있음에도 병원체 concept으로 매핑 = 임상 의미 불일치
- v1.0에서 현재 PASS인 이유: 현재 벤치마크가 exact match 중심 → 나중에 임상 쿼리 추가 시 FAIL 가능

### Concept B (342481000009106, disorder) 채택 시 장점

- semantic_tag = disorder → A축/진단 쿼리에 적합한 tag
- VET Extension → 원칙 3 VET 우선 적용
- Causative agent = 47457000 (Canine parvovirus) → 병원체 정보도 post-coordination으로 포함
- "canine parvovirus infection"은 장염을 포함하는 상위 임상 개념

---

## 권고안

**권고: 변경 (47457000 → 342481000009106)**

### 근거 요약

1. **의미 적합성:** "canine parvovirus enteritis" 쿼리는 임상 질환 쿼리. `disorder` tag가 `organism` tag보다 의미적으로 정확.
2. **SNOMED 원칙 1 위반 방지:** organism tag는 A축/진단 용도 매핑 금지 tag. gold-label 자체가 규칙 위반 상태.
3. **VET Extension 우선 원칙:** 342481000009106은 VET source — 수의학 전용 개념 우선(원칙 3).
4. **IS-A 계층 적합:** disorder 계층 → 임상 쿼리 응답에 더 적합한 depth.
5. **enteritis 포함성:** Canine parvovirus infection은 임상적으로 소장 장염이 주증상 → 의미 포함.

### 기각 시 조건

`47457000` 유지가 허용되는 경우:
- 쿼리 목적이 "파보바이러스를 SNOMED에서 organism으로 조회"하는 것임이 명시된 경우
- 벤치마크가 병원체 검색 시나리오를 테스트하는 경우

→ 현재 T2 쿼리("canine parvovirus enteritis")는 임상 시나리오이므로 위 조건 해당 없음.

### 변경 시 조치

```json
// regression_metrics.json T2 수정안
{
  "query_id": "T2",
  "query_text": "canine parvovirus enteritis",
  "expected_concept_id": "342481000009106",
  "expected_term": "Canine parvovirus infection",
  "change_reason": "organism→disorder 변경. 임상 질환 쿼리에 disorder tag 적합. VET Extension 우선 원칙 적용."
}
```

### 양쪽 허용 검토

"양쪽 허용"은 현재 채택하지 않는다. 이유:
- regression 세트는 단일 gold-label 기반 PASS/FAIL 이진 판정
- organism과 disorder는 의미적으로 다른 계층 — 양쪽 모두 맞다고 보기 어려움
- v2.0 Track C2 평가에서 혼동 방지를 위해 명확한 단일 ground-truth 필요

---

## 적용 대상

변경 시 수정 파일: `graphify_out/regression_metrics.json` T2 항목 `expected_concept_id`

**중요:** 수정 전 사용자 최종 승인 필요. 이 문서는 권고안이며, 실제 수정은 사용자 승인 후 진행.
