# v2.0 B3 Smoke Report — SNOMED 자동 태깅 + MRCM 검증

**날짜:** 2026-04-22  
**Track:** B3 — SNOMEDTagger  
**담당:** Day 3 독립 구현 (B2 통합은 Day 4)

---

## 1. MRCM 규칙 추출 결과

### 도메인별 허용 attribute 요약

| 도메인 | 필드 패턴 수 | 핵심 base concept | 허용 attribute | 금지 attribute |
|--------|------------|-------------------|----------------|----------------|
| OPH | 3 | Intraocular pressure(41633001), Visual acuity(363983007), Ophthalmic exam(36228007) | Has interpretation, Laterality, Method, Finding site | Causative agent, Direct substance (observable에), Has interpretation (procedure에) |
| VITAL_SIGNS | 5 | Heart rate(364075005), Respiratory rate(86290005), Body temperature(386725007), Blood pressure(75367002), Body condition(33761000009102) | Has interpretation, Finding site | Causative agent, Procedure site |
| CARDIOLOGY | 3 | Heart murmur(88610006), Cardiac ejection fraction(70822001), ECG(29303009) | Severity, Finding site, Has interpretation, Method, Procedure site - Direct | Causative agent (finding에), Has interpretation (procedure에) |
| ORTHOPEDICS | 3 | Lameness of quadruped(272981000009107), Knee joint effusion(202381003), Range of joint movement(364564000) | Severity, Laterality, Finding site, Causative agent (disorder에) | Causative agent (finding에) |
| DERMATOLOGY | 3 | Itching(418290006), Erythema(247441003), Skin lesion(95324001) | Severity, Finding site, Causative agent (disorder에) | Direct substance (finding에), Causative agent (finding에) |

**모든 base_concept_id: RF2 DB 실존 검증 완료 (2026-04-22, 15/15 PASS)**

---

## 2. 구현 요약

### `src/pipeline/snomed_tagger.py`

| 메서드 | 역할 |
|--------|------|
| `validate_concept_exists(concept_id)` | RF2 DB SELECT 1 실존 검증 — AI 추론 concept_id 방지 핵심 게이트 |
| `check_mrcm(base_concept_id, attribute_id)` | MRCM 규칙 내 forbidden/allowed 목록 대조 |
| `build_post_coordination(base, attribute, value)` | 3개 concept_id 전부 DB 검증 후 SCG 표현식 생성 |
| `tag_field(field_code, value, domain)` | 단일 필드 → snomed_tagging 엔트리 (MRCM 직접지정 → UNMAPPED 강제) |
| `tag_all(fields)` | B2 출력 fields 배열 → snomed_tagging 배열 |

### 가짜 concept_id 방지 메커니즘

```
[입력 field_code]
      ↓
[MRCM 규칙 패턴 매칭] → base_concept_id 결정
      ↓
[validate_concept_exists()] → DB SELECT 1 검증
      ↓ 실패
  concept_id = "UNMAPPED" (NULL 금지)
      ↓ 성공
[build_post_coordination()] → 3개 concept_id 각각 DB 검증
      ↓ 임의 1개라도 실패
  post_coordination = "" (SCG 불생성)
      ↓ 전부 성공
[check_mrcm(base, attribute)] → MRCM 검증
      ↓ 실패
  post_coordination = "" (MRCM 위반 SCG 폐기)
      ↓ 성공
[반환: 완전 검증된 snomed_tagging 엔트리]
```

---

## 3. 테스트 결과

```
============================= test session starts ==============================
platform darwin -- Python 3.14.4, pytest-9.0.3
collected 7 items

tests/test_snomed_tagger.py::TestSNOMEDTaggerValidation::test_01_iop_field_mapping PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerValidation::test_02_mrcm_violation PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerValidation::test_03_unmapped_field PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerConceptValidation::test_fake_concept_exists PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerConceptValidation::test_known_concept_exists PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerConceptValidation::test_mrcm_rule_concepts_all_exist PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerConceptValidation::test_unmapped_not_valid PASSED

============================== 7 passed in 0.03s ==============================
```

**7 / 7 PASS** — 0 FAIL

---

## 4. 1샘플 Smoke

### 입력 fields (B2 가상 출력 — 안과 IOP 케이스 + VITAL)

| field_code | value | domain |
|------------|-------|--------|
| CA_OPH_IOP_OD_VAL | 28.0 | OPH |
| CA_OPH_IOP_OS_VAL | 14.0 | OPH |
| GP_HR_VAL | 180.0 | VITAL_SIGNS |
| GP_TEMP_VAL | 39.8 | VITAL_SIGNS |
| XX_UNKNOWN_FIELD | test | DEFAULT |

### 출력 snomed_tagging 배열 (JSON)

```json
[
  {
    "field_code": "CA_OPH_IOP_OD_VAL",
    "concept_id": "41633001",
    "preferred_term": "Intraocular pressure",
    "semantic_tag": "observable entity",
    "source": "INT",
    "post_coordination": "41633001 |Intraocular pressure|: 363713009 |Has interpretation| = 75540009 |High|",
    "mrcm_validated": true,
    "confidence": 0.95,
    "latency_ms": 1
  },
  {
    "field_code": "CA_OPH_IOP_OS_VAL",
    "concept_id": "41633001",
    "preferred_term": "Intraocular pressure",
    "semantic_tag": "observable entity",
    "source": "INT",
    "post_coordination": "41633001 |Intraocular pressure|: 363713009 |Has interpretation| = 17621005 |Normal|",
    "mrcm_validated": true,
    "confidence": 0.95,
    "latency_ms": 0
  },
  {
    "field_code": "GP_HR_VAL",
    "concept_id": "364075005",
    "preferred_term": "Heart rate",
    "semantic_tag": "observable entity",
    "source": "INT",
    "post_coordination": "",
    "mrcm_validated": true,
    "confidence": 0.95,
    "latency_ms": 0
  },
  {
    "field_code": "GP_TEMP_VAL",
    "concept_id": "386725007",
    "preferred_term": "Body temperature",
    "semantic_tag": "observable entity",
    "source": "INT",
    "post_coordination": "",
    "mrcm_validated": true,
    "confidence": 0.95,
    "latency_ms": 0
  },
  {
    "field_code": "XX_UNKNOWN_FIELD",
    "concept_id": "UNMAPPED",
    "preferred_term": "",
    "semantic_tag": "",
    "source": "UNMAPPED",
    "post_coordination": "",
    "mrcm_validated": false,
    "confidence": 0.0,
    "latency_ms": 0
  }
]
```

### concept_id DB 실존 검증 결과

| concept_id | 용어 | DB 실존 |
|------------|------|---------|
| 41633001 | Intraocular pressure | PASS |
| 363713009 (SCG attr) | Has interpretation | PASS |
| 75540009 (SCG value) | High | PASS |
| 17621005 (SCG value) | Normal | PASS |
| 364075005 | Heart rate | PASS |
| 386725007 | Body temperature | PASS |
| UNMAPPED | — | N/A |

**가짜 concept_id: 0건 / SCG 내 가짜 concept_id: 0건**

### Post-coordination SCG 해석

- `CA_OPH_IOP_OD_VAL=28.0` → IOP 우안 28mmHg (정상 상한 25 초과)  
  SCG: `41633001 |Intraocular pressure|: 363713009 |Has interpretation| = 75540009 |High|`  
  → "안압 측정 = 높음" 임상 의미 완전 표현

- `CA_OPH_IOP_OS_VAL=14.0` → IOP 좌안 14mmHg (정상 범위 내)  
  SCG: `41633001 |Intraocular pressure|: 363713009 |Has interpretation| = 17621005 |Normal|`

---

## 5. 가짜 concept_id 감사

| 항목 | 결과 |
|------|------|
| 생성된 concept_id 총 수 | 4건 (4 필드 × 1) |
| DB 실존 검증 통과 | 4 / 4 |
| SCG 내 concept_id | 6건 (SCG 2개 × 3 components) |
| SCG DB 검증 통과 | 6 / 6 |
| **가짜 concept_id 총 0건** | **PASS** |
| UNMAPPED 정확 플래그 | 1건 (XX_UNKNOWN_FIELD) |

---

## 6. v1.0 무결성

`src/retrieval/` 변경 내역은 Day 1/2 reranker 기능 추가(Track B1)이며, B3 Day 3 작업에서는 `src/retrieval/` 파일을 **전혀 수정하지 않았음**.

B3 신규 생성 파일:
```
src/pipeline/snomed_tagger.py     (신규)
data/mrcm_rules_v1.json           (신규)
tests/test_snomed_tagger.py       (신규)
benchmark/v2_b3_smoke.md          (본 파일)
```

---

## 7. B2 통합 준비

### B2 출력 fields 배열 수신 인터페이스

```python
from src.pipeline.snomed_tagger import SNOMEDTagger
from src.retrieval.rag_pipeline import SNOMEDRagPipeline

# Day 4 B4 E2E 통합 시 사용 패턴
rag = SNOMEDRagPipeline(llm_backend="none")
tagger = SNOMEDTagger(rag_pipeline=rag)

# B2 출력: {"fields": [...]} 구조 가정
b2_output = {
    "fields": [
        {"field_code": "CA_OPH_IOP_OD_VAL", "value": 28, "domain": "OPH"},
        # ... B2가 확정한 25개 도메인 필드 목록
    ]
}
snomed_tagging = tagger.tag_all(b2_output["fields"])
```

### Day 4 B4 통합 시 필요 사항

1. **B2 출력 스키마 확정**: `field_schema_v26.json`의 `domain_id` 필드가 tag_field() `domain` 파라미터에 그대로 전달되어야 함
2. **MRCM 규칙 확장**: 현재 5개 도메인 → 25개 전체 도메인으로 확장 필요 (Day 4 B3 확장 작업)
3. **RAG 연동 활성화**: `rag_pipeline=None` → 실제 `SNOMEDRagPipeline` 인스턴스 주입
4. **JSON Schema 검증**: §7.1 snomed_tagging 배열 스키마 대조 게이트 추가

---

## 8. 리스크/블로커

| 항목 | 수준 | 내용 |
|------|------|------|
| MRCM 규칙 미커버 필드 | 중 | 현재 5개 도메인만 정의. MRCM 규칙 없는 필드는 RAG Top-1 fallback (RAG=None 시 UNMAPPED) |
| HR/TEMP 후조합 없음 | 저 | 수치형 임계값 미정의로 Has interpretation 후조합 미생성. 임계값 테이블 추가 시 해소 가능 |
| RAG 연동 미테스트 | 중 | Day 3는 RAG=None으로 MRCM 직접지정만 검증. Day 4 B4에서 RAG Top-1 경로 통합 테스트 필요 |
| field_schema_v26.json B2 확정 대기 | 저 | B2와 병렬 진행 중. Day 4 통합 전 domain_id 매핑 표 조율 필요 |
