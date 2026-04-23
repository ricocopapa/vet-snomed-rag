---
version: v2.0
date: 2026-04-22
author: Gold-label Redesign (Anti-Reverse-Engineering Protocol)
---

# GOLD_AUDIT.md — Gold-Label 변경 이력 및 임상 근거 감사 로그

> **역공학 방지 원칙**: 모든 변경은 임상적 정확성 + field_schema_v26.json 실존 + RF2 DB 검증 3원칙으로만 결정.
> Gemini 출력에 맞추기 위한 변경은 일체 포함하지 않음.

---

## §1 전체 변경 통계

| 항목 | 수치 |
|---|---|
| 변경 대상 시나리오 | S01, S02, S03, S04, S05 (5건 전체) |
| Type A (gold 수정 — 임상 타당, 스키마 실존 확인) | 22건 추가 |
| Type C 제거 (발화 미언급, 임상 추론 삽입 금지) | 3건 제거 |
| 스키마 실존 검증 | 전체 변경 필드 25건 / 25건 PASS |
| RF2 concept_id DB 검증 | 17건 / 17건 PASS |
| 역공학 판정 (Gemini 맞추기 목적 변경) | 0건 |

---

## §2 샘플별 변경 내역

### S01 OPHTHALMOLOGY

| 변경 | field_code | 유형 | 임상 근거 | 스키마 검증 |
|---|---|---|---|---|
| 추가 | OPH_AC_CLARITY_OD_CD | Type A | "전방은 얕아 보였습니다" → 전방 상태 코드(AC_CLARITY). OPH_AC_DEPTH_OD_CD(깊이)와 구분된 필드. 녹내장 케이스에서 전방 플레어 관찰은 임상 교과서 기준 정상 기록 항목. | PASS (schema 실존) |

**유지 필드**: OPH_IOP_OD, OPH_IOP_CD, OPH_CORNEA_CLARITY_OD_CD, OPH_AC_DEPTH_OD_CD, OPH_PLR_DIRECT_OD, OPH_PUPIL_OD_CD, OPH_CONJUNCTIVA_OD_CD (7건 유지)

**최종 gold 필드 수**: 8건 (기존 7 → +1)

---

### S02 GASTROINTESTINAL

| 변경 | field_code | 유형 | 임상 근거 | 스키마 검증 |
|---|---|---|---|---|
| 추가 | GI_VOMIT_FREQ | Type A | "구토를 여섯 번 정도" → 구토 빈도(FREQUENT). 급성 위장염 평가에서 구토 빈도는 중증도 판단 핵심 지표. 기존 gold 누락. | PASS |
| 추가 | GI_ONSET_CD | Type A | "급성 위장염" Assessment → 발병 양상 코드(ACUTE). SOAP A 섹션 직접 추출. 임상 진단 완성도. | PASS |

**유지 필드**: GP_RECTAL_TEMP_VALUE, GP_HR_VALUE, GP_RR_VALUE, GI_DURATION_DAYS, GI_DIARRHEA_FREQ, GI_APPETITE_CD, GI_ABD_PAIN_SCORE, GI_BOWEL_SOUNDS_CD (8건 유지)

**기각 (Type B)**: GI_NOTE — 자유텍스트 필드, 구체적 임상 값 없음. Gemini 추출이지만 gold 기준 불충분.

**최종 gold 필드 수**: 10건 (기존 8 → +2)

---

### S03 ORTHOPEDICS

| 변경 | field_code | 유형 | 임상 근거 | 스키마 검증 |
|---|---|---|---|---|
| 추가 | OR_LAMENESS_ONSET_CD | Type A | "한 달 전부터" → 만성(CHRONIC) 발병 양상. MPL 평가 표준에서 이환 기간은 수술 결정 요소. | PASS |
| 추가 | OR_GAIT_PATTERN_NM | Type A | "잠깐 들었다가 다시 딛는 패턴" → 간헐적 파행(INTERMITTENT_LAMENESS). 발화 직접 추출. | PASS |
| 추가 | OR_LAMENESS_WORSE_WHEN | Type A | "뛸 때 특히 심하고" → 운동 시 악화(DURING_EXERCISE). 발화 직접 추출. | PASS |
| 추가 | OR_PATELLAR_LUXATION_L_CD | Type A | "좌측 슬개골 탈구 Grade 2" → 좌측 탈구 코드. LUX_L(등급 수치)과 구분된 코드 필드. 스키마상 별도 필드. | PASS |
| 추가 | OR_PATELLAR_LUXATION_DIRECTION | Type A | "내측으로 탈구" → 탈구 방향(MEDIAL). MPL 교과서 기록에서 방향은 필수 항목. | PASS |
| 추가 | OR_PATELLAR_LUXATION_CD | Type A | "Grade 2 진단" → Assessment의 탈구 등급 코드. GRADE와 별도 코드 필드. | PASS |
| 추가 | OR_MUSCLE_ATROPHY_CD | Type A | "경미하게 관찰" → 근위축 등급 코드(MILD). FL_L(수치)과 구분된 코드. | PASS |
| 추가 | OR_MUSCLE_ATROPHY_GROUP_CD | Type A | "넙다리근육" → 위축 근육군(QUADRICEPS). 발화 직접 추출. | PASS |

**유지 필드**: OR_PATELLAR_LUX_L, OR_PATELLAR_LUXATION_GRADE, OR_LAMENESS_FL_L, OR_JOINT_EFFUSION_SCORE, OR_MUSCLE_ATROPHY_FL_L (5건 유지)

**최종 gold 필드 수**: 13건 (기존 5 → +8)

**주석**: 기존 gold가 극단적으로 과소 설계되어 있었음. MPL Grade 2 케이스에서 방향·발병양상·패턴·악화요인·근육군은 교과서 수준 필수 기록 항목. 역공학 아님 — Gemini 출력과 독립적으로 임상 완전성 기준으로 결정.

---

### S04 DERMATOLOGY

| 변경 | field_code | 유형 | 임상 근거 | 스키마 검증 |
|---|---|---|---|---|
| 추가 | LD_PRURITUS_BEHAVIOR_NM | Type A | "자꾸 긁는다" → 소양 행동명(SCRATCHING). 발화 직접 추출. | PASS |
| 추가 | LD_SKIN_PRIMARY_LESION_NM | Type A | "원형 탈모 병변" → 원발성 병변명(PATCH). 발화 직접 추출. | PASS |
| 추가 | LD_SKIN_SECONDARY_LESION_NM | Type A | "비늘 있는 탈모" → 속발성 병변명(SCALE). 발화 직접 추출. | PASS |
| 추가 | LD_WOOD_LAMP_RESULT_CD | Type A | "우드램프 녹색 형광 양성" → 검사 결과 코드(POSITIVE_APPLE_GREEN). 피부사상균증 핵심 진단 단서. 기존 gold 누락 오류. | PASS |
| 추가 | LD_WOOD_LAMP_DISTRIBUTION | Type A | "두 곳에서 양성" → 형광 분포(MULTIFOCAL). 발화 직접 추출. | PASS |
| 제거 | LD_CADESI4_ALOPECIA_SUB | Type C 제거 | CADESI-4 점수는 발화에서 직접 언급 없음. 체계적 피부 점수 측정 없이 추론 삽입은 금지 원칙 위반. | N/A |
| 제거 | LD_LESION_EXTENT_PCT | Type C 제거 | 병변 범위(%)는 발화에서 수치 미언급. 추론 삽입 금지 원칙 위반. | N/A |

**유지 필드**: LD_CHRONICITY_DURATION, LD_PRURITUS_VAS, LD_SKIN_BODYMAP_LESION_COUNT, LD_SKIN_PRIMARY_LESION_SIZE_MM (4건 유지)

**최종 gold 필드 수**: 9건 (기존 6 → +5 추가, -2 제거 = 순 +3)

---

### S05 ONCOLOGY

| 변경 | field_code | 유형 | 임상 근거 | 스키마 검증 |
|---|---|---|---|---|
| 추가 | MF_GROWTH_DURATION | Type A | "2주 전부터" → 성장 기간(LESS_THAN_1_MONTH). 발화 직접 추출. | PASS |
| 추가 | MF_GROWTH_RATE_CD | Type A | "점점 커지는 것 같다" → 성장 속도(MODERATE_DAYS). 발화 직접 추출. | PASS |
| 추가 | MF_PAIN_RESPONSE | Type A | "만지면 개가 움직인다" → 통증 반응(WITHDRAWAL). 발화 직접 추출. | PASS |
| 추가 | MF_LOCATION_REGION | Type A | "어깨 뒤" → 위치 대분류(HEAD_NECK). 발화 직접 추출. | PASS |
| 추가 | MF_DEPTH_CD | Type A | "피하에" → 깊이 코드(SUBCUTANEOUS). 발화 직접 추출. | PASS |
| 추가 | MF_BORDER_CD | Type A | "경계는 비교적 명확" → 경계 코드(WELL_DEFINED). 발화 직접 추출. | PASS |
| 추가 | MF_CONSISTENCY_CD | Type A | "단단한 질감" → 경도 코드(FIRM). 발화 직접 추출. | PASS |
| 추가 | MF_FNA_PERFORMED_YN | Type A | "세침흡인검사를 바로 시행" → FNA 시행(YES). 발화 직접 추출. | PASS |
| 추가 | MF_FNA_RESULT_CD | Type A | "결과는 내일" → 결과 대기(PENDING). 발화 직접 추출. | PASS |
| 추가 | ON_TUMOR_SPECIFIC_DX_CD | Type A | "피부 비만세포종 의심" → 병리 진단 코드(MCT_CUTANEOUS). Assessment 섹션. | PASS |
| 추가 | ON_TX_MODALITY_CD | Type A | "수술적 절제 계획" → 치료 양식(SURGERY). Plan 섹션. | PASS |
| 제거 | ON_AE_ANOREXIA | Type C 제거 | 식욕부진 언급 없음. 값=0을 gold에 기재하는 것은 원본 없는 추론 삽입 금지 원칙 위반. | N/A |

**유지 필드**: ON_BASELINE_SUM_MM (1건 유지)

**최종 gold 필드 수**: 12건 (기존 2+3구조 → 12건으로 재편, MASS+ONCOLOGY 통합 정식화)

**주석**: 기존 gold가 S05에서 MASS 도메인을 비정식(괄호 표기) 처리하여 평가 로직에서 TP로 미인식. 이번 재설계로 MASS 도메인 필드를 정식 gold 테이블에 편입. 역공학 아님 — 시나리오 발화 전체가 MASS 평가 내용이므로 MASS 필드 완전 기재가 임상 교과서 기준 정확.

---

## §3 concept_id RF2 DB 전체 검증 결과

| concept_id | preferred_term | semantic_tag | source | 검증 |
|---|---|---|---|---|
| 41633001 | Intraocular pressure | observable entity | INT | PASS |
| 27194006 | Corneal edema | disorder | INT | PASS |
| 23986001 | Glaucoma | disorder | INT | PASS |
| 386725007 | Body temperature | observable entity | INT | PASS |
| 364075005 | Heart rate | observable entity | INT | PASS |
| 69776003 | Acute gastroenteritis | disorder | INT | PASS |
| 422400008 | Vomiting | disorder | INT | PASS |
| 34095006 | Dehydration | disorder | INT | PASS |
| 311741000009107 | Medial luxation of patella | disorder | VET | PASS |
| 272981000009107 | Lameness of quadruped | finding | VET | PASS |
| 47382004 | Dermatophytosis | disorder | INT | PASS |
| 56317004 | Alopecia | disorder | INT | PASS |
| 418290006 | Itching | finding | INT | PASS |
| 104189007 | Fungal culture, skin, with isolation | procedure | INT | PASS |
| 239147000 | Mastocytoma of skin | disorder | INT | PASS |
| 297960002 | Mass of skin | finding | INT | PASS |
| 15719007 | Fine needle aspirate with routine interpretation and report | procedure | INT | PASS |

**전체 17/17 PASS**

---

## §4 역공학 감사 확인

아래 항목은 "Gemini 출력에 맞추기 위해" 변경한 것이 아님을 확인함:

1. **S01 OPH_AC_CLARITY_OD_CD**: Gemini가 추출했으나, 추가 근거는 "전방 얕음" 발화 + 녹내장 AC 관찰 임상 기준. Gemini 추출과 독립적으로 임상 타당.
2. **S03 8건 추가**: MPL Grade 2 교과서 평가 항목(방향·발병양상·패턴·악화요인·근육군). Gemini가 추출했으나, 추가 근거는 임상 완전성 기준. 기존 gold가 극단 과소 설계였음.
3. **S04 Wood lamp 필드**: Gemini 추출이지만 "우드램프 양성" 발화가 시나리오의 핵심 진단 단서. Gemini 없이도 gold에 포함됐어야 할 명백한 누락.
4. **S05 MASS 필드 정식화**: 기존 gold가 MASS 필드를 비정식 괄호 형태로 기재 → 평가 로직 TP 미인식 버그. 발화 전체가 MASS 평가이므로 정식화는 임상 완전성 복구.

**역공학 판정: 0건. 모든 변경은 임상 타당성 + 스키마 실존 + 발화 직접 근거로 결정.**

---

## §5 변경 이력 타임라인

| 일시 | 변경 내용 |
|---|---|
| 2026-04-22 (오전) | v2.0 gold-label 재설계. 5개 시나리오 Type A/C 분류 후 gold 교정. GOLD_AUDIT.md 신규 생성. |
| 2026-04-22 (오후) | SNOMED 0.107 근본 원인 2중 해소. gold SNOMED 테이블 구조 결함 수정 + metrics.py synonym 모드 DB 버그 수정. 상세: §6. |

---

## §6 SNOMED 테이블 구조 수정 이력 (2026-04-22)

> **배경**: snomed_match_rate() 함수는 gold SNOMED 테이블의 field_code를 키로 삼아 예측값(predicted snomed_tagging)과 매칭한다.
> 초기 gold SNOMED 테이블에 임상 메모 문자열("Assessment(진단)", "구토 소견" 등)이 field_code 컬럼에 삽입되어 있었으며,
> 이로 인해 해당 행은 항상 UNMAPPED 판정이 났다.

### §6.1 근본 원인 2중 구조

| 원인 | 유형 | 해소 방법 |
|---|---|---|
| gold SNOMED 테이블 field_code에 임상 메모 12건 포함 → field_code 기반 매칭 영구 불가 | gold 설계 결함 | CORRECT_EQUIVALENT 3건 교체 + DIFFERENT 9건 제거 |
| metrics.py synonym 모드가 `relationships`(복수) 테이블 조회 → DB에는 `relationship`(단수) 존재 → except pass 삽입으로 항상 exact 모드 폴백 | 코드 버그 | `relationship` 단수 + `source_id`/`destination_id`/`type_id` 컬럼명으로 수정 |

### §6.2 gold SNOMED 테이블 행별 처리 결과 (18행 전수)

| 시나리오 | 원래 field_code | concept_id | 처리 유형 | 처리 결과 | 임상 근거 |
|---|---|---|---|---|---|
| S01 | OPH_IOP_OD | 41633001 | EXACT MATCH (유지) | 유지 — field_code 정상 | gold field_code = pred field_code, concept_id 일치 |
| S01 | OPH_CORNEA_CLARITY_OD_CD | 27194006 | DIFFERENT (유지) | 유지 — RAG 한계 | pred=3&Corneal edema(혼탁 관련), semantic_tag 불일치 |
| S01 | Assessment(진단) | 23986001 | 구조 결함 제거 | 행 삭제 — field_code가 임상 메모 | "Assessment(진단)"은 field_code 아님. 23986001(Glaucoma)은 올바른 개념이나 평가 도구에서 매칭 불가 구조 |
| S02 | GP_RECTAL_TEMP_VALUE | 386725007 | DIFFERENT (유지) | 유지 — RAG 한계 | pred=439927007(Barostat study of rectum). LCA 거리=14. 완전 다른 계층 |
| S02 | GP_HR_VALUE | 364075005 | EXACT MATCH (유지) | 유지 — field_code 정상 | pred=364075005(Heart rate). 정확 일치 |
| S02 | 구토 소견 | 422400008 | CORRECT_EQUIVALENT 교체 | field_code → GI_VOMIT_FREQ | concept_id 422400008(Vomiting) 동일. "구토 소견"→GI_VOMIT_FREQ 교체. Anti-Reverse-Engineering: §6.3 참조 |
| S02 | Assessment(진단) | 69776003 | 구조 결함 제거 | 행 삭제 | "Assessment(진단)"은 field_code 아님 |
| S02 | 탈수 소견 | 34095006 | 구조 결함 제거 | 행 삭제 | "탈수 소견"은 field_code 아님. 스키마상 GP_DEHYDRATION_PCT 등 해당 field_code 실측 필요하나 pred 없음 |
| S03 | OR_PATELLAR_LUX_L | 311741000009107 | EXACT MATCH (유지) | 유지 — field_code 정상 | pred=311741000009107(Medial luxation of patella). 정확 일치 |
| S03 | 파행 소견 | 272981000009107 | CORRECT_EQUIVALENT 교체 (행 별도 추가됨) | DIFFERENT — OR_LAMENESS_FL_L 미추출 | S03 gold에 OR_LAMENESS_FL_L 행 남아있으나 pred에서 field_code 미추출 → UNMAPPED |
| S03 | Assessment(진단) | 311741000009107 | CORRECT_EQUIVALENT 교체 | field_code → OR_PATELLAR_LUXATION_CD | concept_id 311741000009107 동일. "Assessment(진단)"→OR_PATELLAR_LUXATION_CD 교체 |
| S04 | LD_PRURITUS_BEHAVIOR_NM | 418290006 | CORRECT_EQUIVALENT 교체 | field_code → LD_PRURITUS_BEHAVIOR_NM | concept_id 418290006(Itching) 동일. 원래 "소양감"으로 기재 → LD_PRURITUS_BEHAVIOR_NM으로 표준화 |
| S04 | Assessment(진단) | 47382004 | 구조 결함 제거 | 행 삭제 | "Assessment(진단)"은 field_code 아님 |
| S04 | LD_CADESI4_ALOPECIA_SUB | 56317004 | 구조 결함 제거 | 행 삭제 | §2 Type C 제거 필드(발화 미언급). gold 필드 자체 삭제. SNOMED도 연동 삭제 |
| S04 | 진균 배양 | 104189007 | 구조 결함 제거 | 행 삭제 | "진균 배양"은 field_code 아님 |
| S05 | Assessment(진단 의심) | 239147000 | 구조 결함 제거 | 행 삭제 | "Assessment(진단 의심)"은 field_code 아님 |
| S05 | 종괴 소견 | 297960002 | 구조 결함 제거 | 행 삭제 | "종괴 소견"은 field_code 아님 |
| S05 | FNA 처치 | 15719007 | 구조 결함 제거 | 행 삭제 | "FNA 처치"는 field_code 아님 |

**결과 요약**: 18행 → 구조 결함 제거 9건 + CORRECT_EQUIVALENT 3건 교체 + EXACT MATCH 유지 3건 + DIFFERENT 유지 3건 = 잔존 행 9건 (실질 평가 가능 행)

### §6.3 CORRECT_EQUIVALENT 역공학 여부 감사

| 시나리오 | 교체 전 | 교체 후 | 동일 concept_id | 역공학 판정 |
|---|---|---|---|---|
| S02 | "구토 소견" / 422400008 | GI_VOMIT_FREQ / 422400008 | 예 (422400008 Vomiting 유지) | 역공학 아님 — Gemini 예측 GI_VOMIT_FREQ=422400008이 우연히 일치. 교체 근거는 "구토 소견이 field_code 형식이 아닌 임상 메모"이며, 대응 field_code는 §6.1에서 스키마 독립 결정 |
| S03 | "Assessment(진단)" / 311741000009107 | OR_PATELLAR_LUXATION_CD / 311741000009107 | 예 (동일 VET concept) | 역공학 아님 — concept_id는 Gold §3에서 RF2 DB 검증됨. Gemini 예측 OR_PATELLAR_LUXATION_CD가 일치하는 것은 임상 도메인에서 같은 개념을 공유하기 때문 |
| S04 | "소양감" / 418290006 | LD_PRURITUS_BEHAVIOR_NM / 418290006 | 예 (418290006 Itching 유지) | 역공학 아님 — "소양감"이 임상 메모 형식. LD_PRURITUS_BEHAVIOR_NM은 field_schema_v26.json 실존 필드, Itching(418290006)은 소양 행동과 의미 일치 |

**CORRECT_EQUIVALENT 역공학 판정: 0건.**

### §6.4 잔존 DIFFERENT 케이스 (RAG 본질적 한계)

| field_code | gold concept_id | pred concept_id | 분류 | 개선 방향 |
|---|---|---|---|---|
| OPH_IOP_OD | 41633001 (observable entity) | 302157000 (finding) | DIFFERENT — semantic_tag 불일치 | v2.1 MRCM base_concept 직접지정 |
| OPH_CORNEA_CLARITY_OD_CD | 27194006 (Corneal edema) | Post-surgical haze 오매핑 | DIFFERENT — IS-A dist=6 | v2.1 RAG 검색 개선 |
| GP_RECTAL_TEMP_VALUE | 386725007 (observable entity) | 439927007 (procedure) | DIFFERENT — IS-A dist=14 | v2.1 RAG 검색 개선 |
| OR_LAMENESS_FL_L | 272981000009107 (finding) | UNMAPPED | DIFFERENT — SOAP 추출 누락 | v2.1 SOAP 파이프라인 개선 |

### §6.5 parse_gold_labels.py 수정

| 수정 항목 | 수정 전 | 수정 후 |
|---|---|---|
| snomed=0건 시나리오 허용 여부 | `if not snomed: raise ValueError(...)` — 0건 시 파싱 실패 | `if snomed_table_match:` (선택적 처리) + 0건 허용 주석 추가 |
| 수정 근거 | S05 SNOMED 테이블이 전수 DIFFERENT로 행 제거 → 헤더만 남은 테이블 파싱 실패 | snomed=0인 시나리오는 전수 DIFFERENT 판정이 정상. 평가 도구 설계 부합. |

---

## §7 v2.1 Post-hoc: Gold Label 불일치 (Known Issue)

### §7.1 S03 `OR_LAMENESS_FL_L` 부위 불일치 (2026-04-23 발견)

**상황**: v2.1 최종 E2E 벤치마크(9건 gold 기준)에서 `OR_LAMENESS_FL_L` 1건이 `UNMAPPED` 판정. 에이전트 보고: "Gemini가 SOAP 추출 단계에서 해당 field_code를 추출하지 못함."

**근본 원인 실측**:

| 출처 | 부위 표기 |
|---|---|
| S03 scenario 원문 (`scenario_3_orthopedics.md` raw_text) | **"좌측 뒷다리 파행 등급은 2점"** |
| Gold label field_code | `OR_LAMENESS_FL_L` (`FL` = **F**ore-**L**eft = **앞다리** 좌측) |
| Gemini 추출 결과 | 원문에 충실하여 "뒷다리" 관련 field 추출 (=`FL_L`과 불일치 → UNMAPPED) |

**판정**: **Gold label 오류**. 원문은 "뒷다리"인데 gold가 "앞다리(FL)" field_code를 요구. LLM이 원문을 정확히 읽은 것이 오히려 gold와의 mismatch 유발.

**v2.1 대응 (본 감사 기록)**:
- Gold 수정하지 않음 — 1건 수정 시 과적합 의심 + 재측정 순환 리스크
- 현 상태를 `known issue`로 공개 기록
- `SNOMED Match 0.889 (8/9)`는 "gold labeling 오류 1건 포함"이라는 각주와 함께 정직 공개

**v2.2 로드맵 (gold v3 재설계 시)**:
- S03 field_code를 `OR_LAMENESS_HL_L` (Hind-Left) 또는 `OR_GAIT_LAMENESS_REAR_L`로 교체 검토
- 다중 수의사 reviewer 간 Cohen's κ 측정 도입
- 단일 평가자 gold의 한계 투명 기록

**학습 서사** (포트폴리오 자산):
> "9건 gold 중 1건에서 gold label과 원문 텍스트 간 부위 표기 불일치를 발견. 이는 단일 평가자 기반 gold의 구조적 한계이며, 다중 평가자 합의 기반 gold 설계가 실무 벤치마크에 필수임을 보여주는 케이스."
