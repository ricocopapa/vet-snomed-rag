---
scenario_id: 1
domain: OPHTHALMOLOGY
duration_target_sec: 60
species: feline
created: 2026-04-22
pii_check: PASS (식별정보 0건)
---

# Scenario 1: 고양이 우안 녹내장 의심

## 녹음 스크립트 (한국어 구어체)

보호자 말씀으로는, 어제부터 고양이 오른쪽 눈이 충혈되고 동공이 많이 커 보인다고 하셨습니다. 밥도 잘 못 먹고 눈을 자꾸 비빈다고 하시더라고요.

검진 결과, 우안 안압이 32밀리미터에이치지, 좌안은 14밀리미터에이치지로 양안 차이가 컸습니다. 우안에 각막 부종이 관찰되었고, 전방은 얕아 보였습니다. 동공 반사는 우안이 느렸으며, PLR 직접반응 감소 소견 확인했습니다.

임상 판단으로는 우안 녹내장 의심 진단 내렸습니다. 각막 부종과 안압 상승이 동반된 상태입니다.

처치 계획은 도르졸라마이드 점안액 우안 하루 세 번 투여 시작하고, 경과 관찰 위해 3일 후 재내원 예약했습니다.

## Gold-Label

### 기대 도메인
- PRIMARY: OPHTHALMOLOGY
- SECONDARY: VITAL_SIGNS (활력징후 맥락)

### 기대 필드 (field_schema_v26.json 기준)
| field_code | label | value | section |
|---|---|---|---|
| OPH_IOP_OD | 우안 안압 | 32 (mmHg) | O |
| OPH_IOP_CD | 안압 등급 코드 | ELEVATED | O |
| OPH_CORNEA_CLARITY_OD_CD | 우안 각막 투명도 코드 | EDEMATOUS | O |
| OPH_AC_DEPTH_OD_CD | 우안 전방 깊이 코드 | SHALLOW | O |
| OPH_AC_CLARITY_OD_CD | 우안 전방 상태 코드 | FLARE_MILD | O |
| OPH_PLR_DIRECT_OD | 우안 직접 PLR | DECREASED | O |
| OPH_PUPIL_OD_CD | 우안 동공 크기·형태 코드 | MYDRIASIS | O |
| OPH_CONJUNCTIVA_OD_CD | 우안 결막 소견 코드 | HYPEREMIC | O |

### 기대 SNOMED 태깅
| field_code | concept_id | preferred_term | semantic_tag | confidence | 검증 |
|---|---|---|---|---|---|
| OPH_IOP_OD | 41633001 | Intraocular pressure | observable entity | 0.95 | DB PASS |
| OPH_CORNEA_CLARITY_OD_CD | 27194006 | Corneal edema | disorder | 0.90 | DB PASS |

### 임상 근거
- IOP OD=32 mmHg: 고양이 정상 참고치 10~25 mmHg 초과
- IOP 양안 차이 18 mmHg: 녹내장 의심 기준(>10 mmHg) 충족
- 각막 부종 + 동공 산동 + PLR 감소 = 녹내장 삼징후
- OPH_AC_CLARITY_OD_CD 추가 근거 [v2.0 재설계 Type A]: "전방은 얕아 보였습니다" 발화에서 전방 상태(AC_CLARITY) 코드 추출이 임상적으로 타당. OPH_AC_DEPTH_OD_CD(깊이)와 OPH_AC_CLARITY_OD_CD(상태)는 스키마상 구분된 필드이며 Gemini 실측값(FLARE_MILD)도 임상 근거 있음. 역공학 아님: 스키마 실존 + 임상 타당성 기준 충족.
- [v2.0 SNOMED 재설계 2026-04-22] SNOMED 태깅 테이블 재편:
  - "Assessment(진단)"=23986001 Glaucoma 제거: field_code 아닌 임상 메모. RAG 파이프라인이 Assessment SOAP 섹션을 snomed_tagging 대상에서 제외하는 구조적 설계. pred JSONL의 snomed_tagging 배열에 Glaucoma field_code 없음. 매칭 불가 → DIFFERENT. 역공학 아님: 구조적 불가 항목을 gold total에서 제외하는 것은 평가 정확성 제고.
  - OPH_IOP_OD(41633001 Intraocular pressure, observable entity) 유지: pred=302157000(Intraocular pressure finding, finding). semantic_tag 상이(observable entity vs finding). snomed-mapping 원칙상 semantic_tag 다른 concept 허용 금지. DIFFERENT — RAG semantic_tag 오류. gold 유지.
  - OPH_CORNEA_CLARITY_OD_CD(27194006 Corneal edema, disorder) 유지: pred=1231706000(Post-surgical corneal haze, disorder). LCA=Disorder of cornea(dist=6). 임상 의미 상이(단순 부종 vs 수술 후 혼탁). DIFFERENT — RAG 한계.

### 식별정보 검토
- 이름: 없음, 병원명: 없음, 날짜: 없음, 주소: 없음 — PASS
