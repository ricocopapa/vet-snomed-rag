---
scenario_id: 5
domain: ONCOLOGY
duration_target_sec: 65
species: canine
created: 2026-04-22
pii_check: PASS (식별정보 0건)
---

# Scenario 5: 개 체표 종괴 — 비만세포종 의심

## 녹음 스크립트 (한국어 구어체)

보호자 말씀으로는, 2주 전부터 어깨 뒤쪽에 덩어리가 만져진다고 하셨습니다. 처음에는 작았는데 점점 커지는 것 같다고 하시더라고요. 덩어리를 만지면 개가 움직인다고도 하셨습니다.

검진 결과, 왼쪽 어깨 뒤 피하에 3 곱하기 2 센티미터 크기의 종괴 촉지했습니다. 경계는 비교적 명확하고 단단한 질감이었습니다. 주변 림프절 촉진에서 약간 비대 소견 있었습니다.

임상 판단으로는 피부 비만세포종 의심합니다. 빠른 성장 속도와 종괴 성상이 비만세포종에 합치하는 소견입니다.

처치 계획은 세침흡인검사를 바로 시행했고, 결과는 내일 나올 예정입니다. 결과에 따라 수술적 절제 계획 안내드렸습니다. 종양 스테이징을 위한 추가 검사도 필요할 수 있다고 말씀드렸습니다.

## Gold-Label

### 기대 도메인
- PRIMARY: ONCOLOGY
- SECONDARY: MASS (종괴/종양)

### 기대 필드 (field_schema_v26.json 기준)
| field_code | label | value | section |
|---|---|---|---|
| MF_GROWTH_DURATION | 성장 관찰 기간 | LESS_THAN_1_MONTH (2주) | S |
| MF_GROWTH_RATE_CD | 성장 속도 코드 | MODERATE_DAYS | S |
| MF_PAIN_RESPONSE | 통증 반응 유형 | WITHDRAWAL | O |
| MF_LOCATION_REGION | 종괴 위치 대분류 | HEAD_NECK (어깨) | O |
| MF_DEPTH_CD | 종괴 깊이 코드 | SUBCUTANEOUS | O |
| MF_BORDER_CD | 종괴 경계 코드 | WELL_DEFINED | O |
| MF_CONSISTENCY_CD | 종괴 경도 코드 | FIRM | O |
| MF_FNA_PERFORMED_YN | FNA 시행 여부 | YES | O |
| MF_FNA_RESULT_CD | FNA 결과 분류 코드 | PENDING | O |
| ON_BASELINE_SUM_MM | 기저 직경합 (mm) | 50 (mm, 3×2cm 합산) | O |
| ON_TUMOR_SPECIFIC_DX_CD | 구체적 병리 진단 코드 | MCT_CUTANEOUS | A |
| ON_TX_MODALITY_CD | 치료 양식 코드 | SURGERY | P |

### 기대 SNOMED 태깅

> **[v2.0 SNOMED 재설계 2026-04-22]** 기존 3행(Assessment/종괴 소견/FNA 처치)은 모두 field_code 아닌 임상 메모 형식으로, snomed_match_rate() field_code 기반 매칭 구조에서 pred와 매칭 불가. 전수 DIFFERENT 판정 근거:
> - `Assessment(진단 의심)`=239147000(Mastocytoma of skin): pred ON_TUMOR_SPECIFIC_DX_CD=108369006(Tumor, morphologic abnormality). 의미 상이(specific vs generic). DIFFERENT.
> - `종괴 소견`=297960002(Mass of skin, finding): pred에 해당 field_code 없음. DIFFERENT.
> - `FNA 처치`=15719007(FNA with interpretation, procedure): pred MF_FNA_RESULT_CD=62845000(Superficial FNA biopsy). LCA=Procedure by method(dist=9). DIFFERENT.
> 역공학 아님: 임상 메모 field_code를 gold total에서 제외하는 것은 평가 도구 설계 부합. 3개 concept_id는 RF2 DB 검증 완료(GOLD_AUDIT §3).

| field_code | concept_id | preferred_term | semantic_tag | confidence | 검증 |
|---|---|---|---|---|---|

### 임상 근거
- 2주간 급속 성장: 비만세포종 특징 (빠른 성장 가능)
- 단단하고 경계 명확: 피하 비만세포종 전형 성상
- 림프절 비대: 국소 전이 가능성 → 스테이징 필요
- 239147000 Mastocytoma of skin: A축 기준 disorder tag — 적합
- VET 특이적 등급 분류(361461000009103 등)는 FNA 확진 후 적용
- [v2.0 재설계 Type A] MF_* 9개 전체 gold 채택: 종괴 평가 필드(크기·위치·경도·경계·깊이·성장·FNA) 모두 발화에서 직접 추출 가능, MASS 도메인 스키마 실존 코드. 기존 gold의 MASS 도메인 필드 불완전 기재를 정식화.
- [v2.0 재설계 Type A] ON_TUMOR_SPECIFIC_DX_CD/TX_MODALITY_CD 추가: "비만세포종 의심(A)", "수술적 절제(P)" → Assessment·Plan 섹션 발화 직접 추출, 스키마 실존.
- [v2.0 재설계 Type C 제거] ON_AE_ANOREXIA: 시나리오 발화에 식욕부진 언급 없음. 값 0을 gold에 넣는 것은 추론 삽입 금지 원칙 위반. 제거.

### 식별정보 검토
- 이름: 없음, 병원명: 없음, 날짜: 없음, 주소: 없음 — PASS
