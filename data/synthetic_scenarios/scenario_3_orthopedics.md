---
scenario_id: 3
domain: ORTHOPEDICS
duration_target_sec: 65
species: canine
created: 2026-04-22
pii_check: PASS (식별정보 0건)
---

# Scenario 3: 개 좌측 슬개골 내측 탈구

## 녹음 스크립트 (한국어 구어체)

보호자 말씀으로는, 한 달 전부터 왼쪽 뒷다리를 가끔 들고 다닌다고 하셨습니다. 뛸 때 특히 심하고, 잠깐 들었다가 다시 딛는 패턴이 반복된다고 하시더라고요.

검진 결과, 좌측 슬개골 내측 탈구 그레이드 2 확인했습니다. 슬개골을 압박하면 내측으로 탈구되고 자연 정복되는 소견이었습니다. 좌측 뒷다리 파행 등급은 2점이었고, 넙다리근육 위축 경미하게 관찰했습니다. 관절 삼출 점수는 1점이었습니다.

임상 판단으로는 좌측 슬개골 내측 탈구 그레이드 2 진단 내렸습니다. 간헐적 파행과 경미한 근위축이 동반된 상태입니다.

처치 계획은 비스테로이드성 소염제 2주 처방하고, 체중 관리 권장드렸습니다. 그레이드 2는 경과 관찰 후 수술 여부 결정 예정이며, 보호자에게 수술 상담 안내했습니다.

## Gold-Label

### 기대 도메인
- PRIMARY: ORTHOPEDICS

### 기대 필드 (field_schema_v26.json 기준)
| field_code | label | value | section |
|---|---|---|---|
| OR_LAMENESS_ONSET_CD | 파행 발병 양상 코드 | CHRONIC | S |
| OR_GAIT_PATTERN_NM | 보행 양상명 | INTERMITTENT_LAMENESS | S |
| OR_LAMENESS_WORSE_WHEN | 파행 악화 요인 | DURING_EXERCISE | S |
| OR_PATELLAR_LUX_L | 좌측 슬개골 탈구 등급 | 2 (점/4) | O |
| OR_PATELLAR_LUXATION_GRADE | 슬개골 탈구 등급 | 2 | O |
| OR_PATELLAR_LUXATION_L_CD | 좌측 슬개골 탈구 코드 | GRADE_2 | O |
| OR_PATELLAR_LUXATION_DIRECTION | 슬개골 탈구 방향 | MEDIAL | O |
| OR_PATELLAR_LUXATION_CD | 슬개골 탈구 등급 코드 | GRADE_2 | A |
| OR_LAMENESS_FL_L | 좌전지 파행 등급 | 2 (점/5) | O |
| OR_MUSCLE_ATROPHY_FL_L | 좌전지 근위축 점수 | 1 (점/3) | O |
| OR_MUSCLE_ATROPHY_CD | 근위축 등급 코드 | MILD | O |
| OR_MUSCLE_ATROPHY_GROUP_CD | 위축 근육군 코드 | QUADRICEPS | O |
| OR_JOINT_EFFUSION_SCORE | 관절 삼출 점수 | 1 (점/3) | O |

### 기대 SNOMED 태깅
| field_code | concept_id | preferred_term | semantic_tag | confidence | 검증 |
|---|---|---|---|---|---|
| OR_PATELLAR_LUX_L | 311741000009107 | Medial luxation of patella | disorder | 0.95 | DB PASS (VET) |
| OR_LAMENESS_FL_L | 272981000009107 | Lameness of quadruped | finding | 0.90 | DB PASS (VET) |
| OR_PATELLAR_LUXATION_CD | 311741000009107 | Medial luxation of patella | disorder | 0.95 | DB PASS (VET) |

### 임상 근거
- MPL Grade 2: 슬개골이 수동 탈구 가능하나 자연 정복 — 수술 적응증 경계
- 파행 등급 2/5: 간헐적 파행, 체중 부하 유지
- VET Extension 311741000009107: 수의학 전용 개념 (VET source) — 원칙 3 VET 우선 적용
- [v2.0 재설계 Type A] OR_LAMENESS_ONSET_CD/GAIT_PATTERN_NM/LAMENESS_WORSE_WHEN 추가: "한 달 전부터 간헐적 파행, 뛸 때 악화" → 발병 양상·패턴·악화 요인 모두 발화에서 직접 추출 가능, 스키마 실존 코드, 임상 타당.
- [v2.0 재설계 Type A] OR_PATELLAR_LUXATION_L_CD/DIRECTION/CD 추가: "좌측 내측 탈구 Grade 2" → 측방향·방향·등급 분리 추출 임상 교과서 기준 완전한 MPL 기록 방식. 스키마 실존 코드.
- [v2.0 재설계 Type A] OR_MUSCLE_ATROPHY_CD/GROUP_CD 추가: "넙다리근육 위축 경미하게" → 등급(MILD)·근육군(QUADRICEPS) 분리 추출 임상 타당. 스키마 실존 코드.
- [v2.0 SNOMED 재설계 2026-04-22] SNOMED 태깅 테이블 재편:
  - "Assessment(진단)" → OR_PATELLAR_LUXATION_CD로 교체 (동일 concept_id 311741000009107, Medial luxation of patella, disorder). 역공학 아님: 진단 Assessment 코드는 SNOMED 태깅에서 OR_PATELLAR_LUXATION_CD(Assessment 섹션 탈구 등급 코드 필드)와 동일 개념. CORRECT_EQUIVALENT. pred도 311741000009107 확인 완료.
  - OR_LAMENESS_FL_L(272981000009107): pred JSONL에 OR_LAMENESS_FL_L field_code 없음(pred에는 OR_LAMENESS_ONSET_CD/WORSE_WHEN이 동일 concept_id로 태깅됨). OR_LAMENESS_FL_L(파행 등급 수치) ≠ OR_LAMENESS_ONSET_CD(발병 양상 코드) — 임상 의미 상이, field_code 교체 불가. DIFFERENT — RAG 한계. gold 유지.
  - OR_PATELLAR_LUX_L(311741000009107) 유지: pred EXACT MATCH 확인 완료.

### 식별정보 검토
- 이름: 없음, 병원명: 없음, 날짜: 없음, 주소: 없음 — PASS
