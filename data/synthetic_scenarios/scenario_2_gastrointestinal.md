---
scenario_id: 2
domain: GASTROINTESTINAL + VITAL_SIGNS
duration_target_sec: 75
species: canine
created: 2026-04-22
pii_check: PASS (식별정보 0건)
---

# Scenario 2: 개 급성 구토 및 위장염

## 녹음 스크립트 (한국어 구어체)

보호자 말씀으로는, 이틀 전부터 구토를 여섯 번 정도 했고 밥을 거의 안 먹는다고 하셨습니다. 어제는 설사도 한두 번 있었다고 하시더라고요. 바깥에서 뭔가 주워 먹었을 수도 있다고 하셨습니다.

검진 결과, 체온 39.2도, 심박수 140회, 호흡수 28회였습니다. 탈수 정도는 5에서 7퍼센트로 평가되었고, 피부 탄력 검사에서 텐트 현상 보였습니다. 복부 촉진 시 경미한 통증 반응 있었으며, 장음은 항진 소견이었습니다.

임상 판단으로는 급성 위장염 진단 내렸습니다. 경증에서 중증도 탈수가 동반되어 있습니다.

처치 계획은 정맥 수액 처치 시작하고 마로피턴트 정맥 투여했습니다. 금식 후 소화가 쉬운 음식으로 전환 예정이며, 입원 관찰 24시간 진행합니다.

## Gold-Label

### 기대 도메인
- PRIMARY: GASTROINTESTINAL
- SECONDARY: VITAL_SIGNS

### 기대 필드 (field_schema_v26.json 기준)
| field_code | label | value | section |
|---|---|---|---|
| GP_RECTAL_TEMP_VALUE | 직장 체온 | 39.2 (°C) | O |
| GP_HR_VALUE | 심박수 | 140 (bpm) | O |
| GP_RR_VALUE | 호흡수 | 28 (breaths/min) | O |
| GI_DURATION_DAYS | 증상 지속 기간 | 2 (일) | S |
| GI_VOMIT_FREQ | 구토 빈도 | FREQUENT (6회) | S |
| GI_DIARRHEA_FREQ | 설사 빈도 | 1~2 (회/일) | S |
| GI_APPETITE_CD | 식욕 상태 코드 | DECREASED | S |
| GI_ABD_PAIN_SCORE | 복부 통증 점수 | 2 (점/4) | O |
| GI_BOWEL_SOUNDS_CD | 장음 코드 | HYPERACTIVE | O |
| GI_ONSET_CD | 발병 양상 코드 | ACUTE | A |

### 기대 SNOMED 태깅
| field_code | concept_id | preferred_term | semantic_tag | confidence | 검증 |
|---|---|---|---|---|---|
| GP_RECTAL_TEMP_VALUE | 386725007 | Body temperature | observable entity | 0.95 | DB PASS |
| GP_HR_VALUE | 364075005 | Heart rate | observable entity | 0.95 | DB PASS |
| GI_VOMIT_FREQ | 422400008 | Vomiting | disorder | 0.92 | DB PASS |

### 임상 근거
- 체온 39.2°C: 개 정상 37.5~39.2°C 상한 경계
- 심박수 140 bpm: 개 정상 60~160 bpm 내 빈맥 경향
- 탈수 5~7%: 중등도 탈수 → 수액 처치 적응증
- 급성 구토 6회/2일 + 식욕감소 + 장음 항진 = 급성 위장염 패턴
- GI_VOMIT_FREQ 추가 근거 [v2.0 재설계 Type A]: "구토를 여섯 번 정도" 발화에서 구토 빈도(FREQUENT) 추출 임상적으로 타당. 기존 gold 누락이었으며 스키마 실존 코드. 역공학 아님.
- GI_ONSET_CD 추가 근거 [v2.0 재설계 Type A]: "급성 위장염" Assessment에서 발병 양상 코드(ACUTE) 추출 임상적으로 타당. 스키마 실존 코드. 역공학 아님.
- [v2.0 SNOMED 재설계 2026-04-22] SNOMED 태깅 테이블 재편:
  - "구토 소견"(field_code 아님) → GI_VOMIT_FREQ로 교체 (동일 concept_id 422400008, Vomiting, disorder). 역공학 아님: GI_VOMIT_FREQ가 구토 빈도 필드이고 Vomiting concept으로 태깅하는 것은 임상적으로 정확. CORRECT_EQUIVALENT.
  - "Assessment(진단)" 69776003, "탈수 소견" 34095006: field_code 아닌 임상 메모. pred에 해당 field_code 없어 매칭 불가. DIFFERENT. SNOMED 테이블에서 제거.
  - GP_RECTAL_TEMP_VALUE(386725007 Body temp observable) 유지: pred가 439927007(Barostat study of rectum, procedure)으로 완전히 다른 계층. DIFFERENT — RAG 한계 기록 목적으로 유지.
  - GP_HR_VALUE(364075005) 유지: pred와 EXACT MATCH.

### 식별정보 검토
- 이름: 없음, 병원명: 없음, 날짜: 없음, 주소: 없음 — PASS
