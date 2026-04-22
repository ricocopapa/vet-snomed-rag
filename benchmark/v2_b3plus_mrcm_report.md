# vet-snomed-rag v2.0 — B3+ MRCM 규칙 확장 보고서 (Day 4)

> 작성일: 2026-04-22  
> 버전: mrcm_rules_v1.json v2.0.0  
> 작업: Track B3+ — MRCM 규칙 5→25도메인 확장

---

## 1. 25도메인 확장 요약

### 그룹별 추가 도메인

| 그룹 | 도메인 (신규) | 주요 semantic_tag | 핵심 allowed attribute |
|---|---|---|---|
| 그룹 1 — 검사 수치형 | HEMATOLOGY, CHEMISTRY, URINALYSIS, COAGULATION, BLOOD_GAS | `observable entity`, `procedure` | Has interpretation(363713009), Component(246093002), Procedure site-Direct(405813007) |
| 그룹 2 — 임상 소견/진찰 | NEUROLOGY, EAR_NOSE, RESPIRATORY, GASTROINTESTINAL, DENTISTRY | `finding`, `observable entity`, `disorder`, `procedure` | Finding site(363698007), Severity(246112005), Laterality(272741003) |
| 그룹 3 — 처치/수술/마취 | ANESTHESIA, SURGICAL_RECORD, WOUND_TRAUMA, ONCOLOGY | `procedure` | Procedure site-Direct(405813007), Method(260686004) |
| 그룹 4 — 평가/점수 | SCORING, TRIAGE, NURSING | `observable entity`, `procedure` | Has interpretation(363713009), Procedure site-Direct(405813007) |
| 그룹 5 — 내분비/독성 | ENDOCRINE, TOXICOLOGY | `observable entity`, `procedure`, `disorder` | Has interpretation(363713009), Component(246093002), Causative agent(246075003) |
| 그룹 6 — 종괴 | MASS | `finding` | Finding site(363698007), Severity(246112005) |
| (기존 v1.0) | OPH, VITAL_SIGNS, CARDIOLOGY, ORTHOPEDICS, DERMATOLOGY | 다수 | 무변경 |

### MRCM 핵심 금지 패턴 (전체)

| base semantic_tag | forbidden attribute | 이유 |
|---|---|---|
| `observable entity` | Procedure site-Direct(405813007) | observable entity hierarchy에 procedure 전용 attribute 부착 불가 |
| `observable entity` | Causative agent(246075003) | 원인 귀속은 disorder hierarchy만 허용 |
| `procedure` | Has interpretation(363713009) | 해석 판단은 observable entity/finding에만 MRCM 허용 |
| `procedure` | Causative agent(246075003) | procedure에 원인 귀속 불가 (MRCM 비허용) |
| `finding` | Causative agent(246075003) | finding에 Causative agent 부착 시 disorder 계층으로 의미 이동 위험 |
| `finding` | Direct substance(363701004) | finding에 물질 직접 부착 불가 |

---

## 2. concept_id DB 실존 검증

| 항목 | 수치 |
|---|---|
| 총 base_concept_id 제시 수 (64개 필드 패턴) | 64개 |
| DB 검증 통과 | 64개 (100%) |
| DB 검증 실패 | 0개 |
| 샘플 5개 상세 검증 | 전수 PASS |

### 샘플 5개 상세

| concept_id | preferred_term | semantic_tag | 도메인 |
|---|---|---|---|
| 103228002 | Hemoglobin saturation with oxygen | observable entity | HEMATOLOGY |
| 28317006 | Hematocrit determination | procedure | HEMATOLOGY |
| 6942003 | Level of consciousness | observable entity | NEUROLOGY |
| 225390008 | Triage | procedure | TRIAGE |
| 4192000 | Toxicology testing for organophosphate insecticide | procedure | TOXICOLOGY |

---

## 3. 테스트 결과

### test_mrcm_rules.py (신규 — 4건 목표, 7건 실행)

```
tests/test_mrcm_rules.py::TestMRCMRulesLoad::test_01_all_25_domains_present         PASSED
tests/test_mrcm_rules.py::TestMRCMRulesLoad::test_01_each_domain_has_fields          PASSED
tests/test_mrcm_rules.py::TestMRCMRulesLoad::test_01_json_parseable                  PASSED
tests/test_mrcm_rules.py::TestMRCMRulesSemanticTags::test_02_all_expected_semantic_tags_valid PASSED
tests/test_mrcm_rules.py::TestMRCMRulesForbiddenAttributes::test_03_observable_entity_forbids_procedure_site PASSED
tests/test_mrcm_rules.py::TestMRCMRulesConceptIdValidation::test_04_all_mrcm_base_concepts_exist PASSED
tests/test_mrcm_rules.py::TestMRCMRulesConceptIdValidation::test_04_sample_concept_ids_exist_in_db PASSED

7 passed in 0.02s
```

### test_snomed_tagger.py (B3 기존 — regression 7건)

```
tests/test_snomed_tagger.py::TestSNOMEDTaggerValidation::test_01_iop_field_mapping   PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerValidation::test_02_mrcm_violation       PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerValidation::test_03_unmapped_field       PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerConceptValidation::test_fake_concept_rejected PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerConceptValidation::test_known_concept_exists PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerConceptValidation::test_mrcm_rule_concepts_all_exist PASSED
tests/test_snomed_tagger.py::TestSNOMEDTaggerConceptValidation::test_unmapped_not_valid PASSED

7 passed in 0.05s
```

**Regression 0건 — B3 기존 테스트 전수 PASS 유지**

---

## 4. 규칙 파일 통계

| 항목 | 수치 |
|---|---|
| 총 도메인 수 | **25** |
| 기존 도메인 (v1.0 무변경) | 5 |
| 신규 도메인 (Day 4 추가) | 20 |
| 총 필드 패턴 규칙 수 | **64** |
| 총 allowed attribute 정의 수 | 108 |
| 총 forbidden attribute 정의 수 | 90 |
| base_concept_id DB 검증 OK | 64 / 64 (100%) |

### 도메인별 필드 패턴 수

| 도메인 | 필드 패턴 수 | semantic_tag 종류 |
|---|---|---|
| VITAL_SIGNS | 5 | observable entity |
| HEMATOLOGY | 4 | observable entity, procedure |
| OPH | 3 | observable entity, procedure |
| CARDIOLOGY | 3 | finding, observable entity, procedure |
| ORTHOPEDICS | 3 | disorder, finding, observable entity |
| DERMATOLOGY | 3 | disorder, finding |
| CHEMISTRY | 3 | observable entity, procedure |
| URINALYSIS | 3 | finding, observable entity, procedure |
| NEUROLOGY | 3 | finding, observable entity |
| RESPIRATORY | 3 | finding, observable entity |
| TOXICOLOGY | 3 | disorder, procedure |
| EAR_NOSE | 2 | disorder, observable entity |
| GASTROINTESTINAL | 2 | finding |
| DENTISTRY | 2 | procedure |
| ENDOCRINE | 2 | observable entity, procedure |
| COAGULATION | 2 | observable entity |
| BLOOD_GAS | 2 | observable entity |
| MASS | 2 | finding |
| SCORING | 2 | observable entity |
| WOUND_TRAUMA | 2 | procedure |
| NURSING | 2 | procedure |
| ONCOLOGY | 2 | disorder, procedure |
| ANESTHESIA | 2 | procedure |
| SURGICAL_RECORD | 2 | procedure |
| TRIAGE | 2 | observable entity, procedure |

---

## 5. B3 Regression 체크

- `snomed_tagger.py` 파일 변경: **0건** (git diff 확인)
- 기존 7건 테스트 PASS 유지: **확인**
- JSON 외부화 전략 유지: **mrcm_rules_v1.json만 확장**

---

## 6. 리스크/블로커

| 항목 | 상태 | 비고 |
|---|---|---|
| concept_id AI 추론 생성 | 없음 | 전수 RF2 DB 검증 통과 |
| MRCM 규칙 추측 | 없음 | snomed-mapping SKILL.md §2 원칙 기반 |
| 기존 5도메인 규칙 수정 | 없음 | v1.0 구조 보존 확인 |
| snomed_tagger.py 파일 변경 | 없음 | git diff 무변경 |
| HEMATOLOGY: Has specimen attribute | 주의 | feedback_batch_specimen_assignment 준수: 검사별 개별 파싱 원칙. 현재 Component(246093002)로 대체, Has specimen(704325000)은 배치 일괄 부여 금지 원칙으로 JSON에서 제외 |

---

## 7. 적용 피드백 메모리 준수 확인

| 피드백 | 적용 여부 |
|---|---|
| feedback_mrcm_constraint_check | PASS — 모든 도메인 MRCM 허용 attribute 사전 확인 후 정의 |
| feedback_snomed_source_validation | PASS — 64개 base_concept_id 전수 RF2 DB 검증 통과 |
| feedback_null_not_design_intent | PASS — NULL concept 없음, UNMAPPED 강제 유지 |
| feedback_batch_specimen_assignment | PASS — Has specimen 배치 일괄 부여 금지, 검사별 개별 파싱 원칙 준수 |
