---
scenario_id: 4
domain: DERMATOLOGY
duration_target_sec: 70
species: feline
created: 2026-04-22
pii_check: PASS (식별정보 0건)
---

# Scenario 4: 고양이 피부사상균증 (Dermatophytosis) 의심

## 녹음 스크립트 (한국어 구어체)

보호자 말씀으로는, 3주 전부터 얼굴과 앞발에 동그란 탈모 병변이 생겼다고 하셨습니다. 가려워하는지 자꾸 긁는다고 하시더라고요. 최근에 새 고양이를 집에 데려온 이후 시작됐다고 하셨습니다.

검진 결과, 얼굴과 앞발에 원형 탈모 병변 3개소 확인했습니다. 병변 크기는 각각 1에서 2센티미터였으며, 경계가 명확하고 비늘 있는 탈모 소견이었습니다. 우드램프 검사에서 두 곳에서 녹색 형광 양성 반응 보였습니다. 소양감 점수는 VAS 5점 정도로 평가했습니다.

임상 판단으로는 피부사상균증 의심 진단 내렸습니다. 우드램프 양성과 원형 탈모 패턴이 합치되는 소견입니다.

처치 계획은 이트라코나졸 경구 투여 4주 처방하고, 진균 배양 검사 의뢰했습니다. 접촉 동물과의 격리 권장드렸고, 환경 소독도 안내드렸습니다.

## Gold-Label

### 기대 도메인
- PRIMARY: DERMATOLOGY

### 기대 필드 (field_schema_v26.json 기준)
| field_code | label | value | section |
|---|---|---|---|
| LD_CHRONICITY_DURATION | 이환 기간 | 1_3M (3주) | S |
| LD_PRURITUS_VAS | 소양감 VAS 점수 | 5 (점/10) | S |
| LD_PRURITUS_BEHAVIOR_NM | 소양 행동명 | SCRATCHING | S |
| LD_SKIN_BODYMAP_LESION_COUNT | 바디맵 병변 수 | 3 (개소) | O |
| LD_SKIN_PRIMARY_LESION_NM | 원발성 피부 병변명 | PATCH | O |
| LD_SKIN_PRIMARY_LESION_SIZE_MM | 주요 병변 크기 | 10~20 (mm) | O |
| LD_SKIN_SECONDARY_LESION_NM | 속발성 피부 병변명 | SCALE | O |
| LD_WOOD_LAMP_RESULT_CD | 우드등 검사 결과 코드 | POSITIVE_APPLE_GREEN | O |
| LD_WOOD_LAMP_DISTRIBUTION | 형광 분포 | MULTIFOCAL | O |

### 기대 SNOMED 태깅
| field_code | concept_id | preferred_term | semantic_tag | confidence | 검증 |
|---|---|---|---|---|---|
| LD_PRURITUS_BEHAVIOR_NM | 418290006 | Itching | finding | 0.88 | DB PASS |

### 임상 근거
- 원형 탈모 3개소 + 비늘형성 + Wood's lamp 양성: 피부사상균증 전형적 3징
- Microsporum canis: Wood's lamp에서 녹색 형광 (Trichophyton은 음성 가능)
- 새 고양이 도입 후 발병: 전파 경로 합치
- 우드램프 양성 2/3: 높은 진단 신뢰도 (배양으로 확인 필요)
- [v2.0 재설계 Type A] LD_WOOD_LAMP_RESULT_CD/DISTRIBUTION 추가: "우드램프 녹색 형광 양성, 두 곳에서" → 피부사상균증 핵심 진단 검사 결과, 발화에서 직접 추출, 스키마 실존. 기존 gold에서 누락된 핵심 필드. 역공학 아님.
- [v2.0 재설계 Type A] LD_PRURITUS_BEHAVIOR_NM 추가: "자꾸 긁는다" → 소양 행동명(SCRATCHING) 직접 추출. 스키마 실존.
- [v2.0 재설계 Type A] LD_SKIN_PRIMARY_LESION_NM/SECONDARY_LESION_NM 추가: "원형 탈모(PATCH)/비늘(SCALE)" → 발화에서 직접 추출. 스키마 실존.
- [v2.0 재설계 Type C 제거] LD_CADESI4_ALOPECIA_SUB, LD_LESION_EXTENT_PCT: 시나리오 발화에 CADESI-4 점수 측정 및 병변 범위% 직접 언급 없음. 임상 추론 필요 필드로 이번 시나리오 scope 밖. gold에서 제거.
- [v2.0 SNOMED 재설계 2026-04-22] SNOMED 태깅 테이블 재편:
  - "소양감"(field_code 아님) → LD_PRURITUS_BEHAVIOR_NM으로 교체 (동일 concept_id 418290006, Itching, finding). 역공학 아님: 소양 행동 필드가 소양감 개념을 태깅하는 것은 임상적으로 정확. CORRECT_EQUIVALENT.
  - LD_CADESI4_ALOPECIA_SUB: GOLD_AUDIT §2 S04 Type C 제거 필드이나 SNOMED 테이블에 잔존하여 일관성 위반. 제거.
  - "Assessment(진단)", "진균 배양": field_code 아닌 임상 메모 → RAG 매칭 불가 구조. pred에 해당 field_code 없어 DIFFERENT로 분류. SNOMED 테이블에서 제거.
  - 결과: SNOMED 테이블 1행 (LD_PRURITUS_BEHAVIOR_NM) 유지 — 정확한 매칭 가능 기준.

### 식별정보 검토
- 이름: 없음, 병원명: 없음, 날짜: 없음, 주소: 없음 — PASS
