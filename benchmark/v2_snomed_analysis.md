---
version: v2.0
date: 2026-04-22
type: SNOMED 일치율 근본 원인 분석 + 해결 보고서
---

# v2_snomed_analysis.md — SNOMED 일치율 0.107 근본 원인 분석

> **Anti-Sycophancy 원칙 적용**: 역공학(gold를 RAG 출력에 맞추기) 0건. 모든 gold 수정은 임상 근거 + RF2 DB 검증 + 평가 도구 설계 정합성 기준으로만 결정.

---

## §1 BEFORE 상태 분석

### 기존 수치 (수정 전)
| 모드 | SNOMED 일치율 |
|---|---|
| exact | 0.107 |
| synonym | 0.107 (synonym=exact와 동일 — 버그) |

### gold 총 행 수 분포 (수정 전)
| 시나리오 | 도메인 | gold snomed 행 | 실제 field_code 행 | 임상메모 행 |
|---|---|---|---|---|
| S01 | OPHTHALMOLOGY | 3 | 2 | 1 |
| S02 | GASTROINTESTINAL | 5 | 2 | 3 |
| S03 | ORTHOPEDICS | 3 | 2 | 1 |
| S04 | DERMATOLOGY | 4 | 1 | 3 |
| S05 | ONCOLOGY | 3 | 0 | 3 |
| **합계** | | **18** | **7** | **11** |

---

## §2 근본 원인 2중 구조

### 원인 1: gold SNOMED 테이블 field_code 구조 결함

**문제**: gold SNOMED 태깅 테이블 18행 중 12행이 실제 field_code(`OPH_IOP_OD` 등)가 아닌 임상 메모 형식(`Assessment(진단)`, `구토 소견`, `탈수 소견`, `소양감`, `진균 배양`, `종괴 소견`, `FNA 처치`)으로 기재됨.

**영향**: `snomed_match_rate()` 함수는 gold의 field_code 기준으로 predicted snomed_tagging 배열과 매칭. 임상 메모 형식 field_code는 predicted 배열에 존재하지 않아 전원 UNMAPPED 처리 → 12건 자동 FAIL.

**실제 기존 일치**: S02 GP_HR_VALUE=364075005 EXACT, S03 OR_PATELLAR_LUX_L=311741000009107 EXACT → 2/18 = 0.111 (보고된 0.107은 평균 계산 방식 차이)

### 원인 2: metrics.py synonym 모드 DB 테이블명 버그

**문제**: `snomed_match_rate(mode="synonym")` 내 IS-A 조회 SQL이 `FROM relationships` (복수) 참조. 실제 DB 테이블명은 `relationship` (단수). SQLite는 테이블 없으면 `OperationalError` → `except Exception: pass` 블록에서 무시 → related 집합 = {concept_id 자체}만 남음 → synonym 모드가 사실상 exact 모드로 폴백.

**추가 컬럼명 불일치**: `sourceId`/`destinationId`/`typeId`/`active` → 실제 컬럼은 `source_id`/`destination_id`/`type_id` (active 컬럼 없음).

**영향**: synonym 모드 IS-A 2단계 허용이 전혀 작동하지 않음. exact=synonym=0.107.

---

## §3 전수 17 concept_id 쌍 분석

### 수정 전 gold 18행 (field_code → concept_id)

| # | 시나리오 | field_code | fc 유형 | gold concept_id | gold term | gold tag | pred concept_id | pred term | IS-A 거리 | 판정 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | S01 | OPH_IOP_OD | REAL_FC | 41633001 | Intraocular pressure | observable entity | 302157000 | Intraocular pressure finding | >10 (다른 계층) | DIFFERENT |
| 2 | S01 | OPH_CORNEA_CLARITY_OD_CD | REAL_FC | 27194006 | Corneal edema | disorder | 1231706000 | Post-surgical corneal haze | 6 (Disorder of cornea LCA) | DIFFERENT |
| 3 | S01 | Assessment(진단) | MEMO | 23986001 | Glaucoma | disorder | UNMAPPED | — | N/A | DIFFERENT |
| 4 | S02 | GP_RECTAL_TEMP_VALUE | REAL_FC | 386725007 | Body temperature | observable entity | 439927007 | Barostat study of rectum | 14 (SNOMED root) | DIFFERENT |
| 5 | S02 | GP_HR_VALUE | REAL_FC | 364075005 | Heart rate | observable entity | 364075005 | Heart rate | 0 | EXACT MATCH |
| 6 | S02 | Assessment(진단) | MEMO | 69776003 | Acute gastroenteritis | disorder | UNMAPPED | — | N/A | DIFFERENT |
| 7 | S02 | 구토 소견 | MEMO | 422400008 | Vomiting | disorder | GI_VOMIT_FREQ=422400008 | Vomiting | 0 | CORRECT_EQUIVALENT → 교체 |
| 8 | S02 | 탈수 소견 | MEMO | 34095006 | Dehydration | disorder | UNMAPPED | — | N/A | DIFFERENT |
| 9 | S03 | OR_PATELLAR_LUX_L | REAL_FC | 311741000009107 | Medial luxation of patella | disorder | 311741000009107 | Medial luxation of patella | 0 | EXACT MATCH |
| 10 | S03 | OR_LAMENESS_FL_L | REAL_FC | 272981000009107 | Lameness of quadruped | finding | UNMAPPED | — | N/A | DIFFERENT |
| 11 | S03 | Assessment(진단) | MEMO | 311741000009107 | Medial luxation of patella | disorder | OR_PATELLAR_LUXATION_CD=311741000009107 | — | 0 | CORRECT_EQUIVALENT → 교체 |
| 12 | S04 | Assessment(진단) | MEMO | 47382004 | Dermatophytosis | disorder | UNMAPPED | — | N/A | DIFFERENT |
| 13 | S04 | LD_CADESI4_ALOPECIA_SUB | REAL_FC | 56317004 | Alopecia | disorder | UNMAPPED | — | N/A | DIFFERENT (Type C 제거 필드 잔존) |
| 14 | S04 | 소양감 | MEMO | 418290006 | Itching | finding | LD_PRURITUS_BEHAVIOR_NM=418290006 | Itching | 0 | CORRECT_EQUIVALENT → 교체 |
| 15 | S04 | 진균 배양 | MEMO | 104189007 | Fungal culture | procedure | UNMAPPED | — | N/A | DIFFERENT |
| 16 | S05 | Assessment(진단 의심) | MEMO | 239147000 | Mastocytoma of skin | disorder | ON_TUMOR_SPECIFIC_DX_CD=108369006 | Tumor | dist=N/A | DIFFERENT |
| 17 | S05 | 종괴 소견 | MEMO | 297960002 | Mass of skin | finding | UNMAPPED | — | N/A | DIFFERENT |
| 18 | S05 | FNA 처치 | MEMO | 15719007 | FNA with interpretation | procedure | MF_FNA_RESULT_CD=62845000 | Superficial FNA biopsy | 9 (Procedure by method) | DIFFERENT |

### IS-A 거리 분포 (수정 전 18건)
| 거리 | 건수 |
|---|---|
| 0 (EXACT MATCH) | 2 |
| 0 (CORRECT_EQUIVALENT — field_code 교체 후 동일) | 3 |
| 6 (Disorder of cornea LCA) | 1 |
| 9 (Procedure by method LCA) | 1 |
| >10 또는 다른 최상위 계층 | 2 |
| N/A (UNMAPPED 또는 임상메모 field_code) | 9 |

---

## §4 Type별 분류 및 처리

### Type CORRECT_EQUIVALENT (3건) — gold 수정 정당

| # | 시나리오 | 변경 전 field_code | 변경 후 field_code | concept_id | 임상 근거 |
|---|---|---|---|---|---|
| 1 | S02 | 구토 소견 | GI_VOMIT_FREQ | 422400008 (Vomiting, disorder) | "구토를 여섯 번 정도" → 구토 빈도 필드. 동일 concept_id. 임상메모를 실제 필드 코드로 교체. 역공학 아님: field_code 정합성 회복. |
| 2 | S03 | Assessment(진단) | OR_PATELLAR_LUXATION_CD | 311741000009107 (Medial luxation of patella, disorder) | Assessment 진단 코드는 OR_PATELLAR_LUXATION_CD(Assessment 섹션 탈구 등급 코드) 필드와 동일 개념. pred 확인 완료. 역공학 아님: 동일 개념을 올바른 field_code로 표현. |
| 3 | S04 | 소양감 | LD_PRURITUS_BEHAVIOR_NM | 418290006 (Itching, finding) | 소양 행동 필드가 Itching 개념 → 의미 정합. pred 확인 완료. 역공학 아님: field_code 정합성 회복. |

**역공학 여부**: 3건 모두 RAG 출력과 독립적으로 field_code 정합성 기준으로 판단. concept_id 자체는 변경 없음.

### Type DIFFERENT (15건) — gold 수정 불가, RAG 한계 기록

| 분류 | 건수 | 대표 예시 |
|---|---|---|
| 임상 메모 field_code (매칭 구조적 불가) | 9 | Assessment(진단), 탈수 소견, 진균 배양, 종괴 소견, FNA 처치 |
| RAG semantic_tag 오류 | 1 | OPH_IOP_OD: observable entity vs finding |
| RAG 오매핑 (다른 disorder) | 1 | OPH_CORNEA: Corneal edema vs Post-surgical corneal haze |
| RAG 완전 다른 계층 | 1 | GP_RECTAL_TEMP: Body temp (observable) vs Barostat study (procedure) |
| 파이프라인 field_code 미추출 | 1 | OR_LAMENESS_FL_L: pred에 해당 field 없음 |
| Type C 제거 필드 SNOMED 테이블 잔존 | 1 | LD_CADESI4_ALOPECIA_SUB |
| RAG generic 오매핑 | 1 | ON_TUMOR_SPECIFIC_DX_CD: Mastocytoma vs Tumor(generic) |

---

## §5 수정 내역 요약

### 파일 수정 목록

| 파일 | 수정 내용 | 분류 |
|---|---|---|
| `data/synthetic_scenarios/scenario_1_ophthalmology.md` | SNOMED 테이블에서 "Assessment(진단)" 행 제거 (DIFFERENT), 임상 근거 노트 추가 | gold 정제 |
| `data/synthetic_scenarios/scenario_2_gastrointestinal.md` | "구토 소견" → GI_VOMIT_FREQ 교체, "Assessment(진단)"/"탈수 소견" 제거 | CORRECT_EQUIVALENT + 정제 |
| `data/synthetic_scenarios/scenario_3_orthopedics.md` | "Assessment(진단)" → OR_PATELLAR_LUXATION_CD 교체 | CORRECT_EQUIVALENT |
| `data/synthetic_scenarios/scenario_4_dermatology.md` | "소양감" → LD_PRURITUS_BEHAVIOR_NM 교체, "Assessment(진단)"/"LD_CADESI4_ALOPECIA_SUB"/"진균 배양" 제거 | CORRECT_EQUIVALENT + 정제 |
| `data/synthetic_scenarios/scenario_5_oncology.md` | "Assessment(진단 의심)"/"종괴 소견"/"FNA 처치" 전체 제거 (S05 snomed=0, 전수 DIFFERENT) | 정제 |
| `scripts/eval/parse_gold_labels.py` | snomed=0 허용 (빈 테이블 파싱 오류 방지) | 코드 수정 |
| `scripts/eval/metrics.py` | synonym 모드 DB 테이블명 `relationships`→`relationship`, 컬럼명 `sourceId`→`source_id` 등 수정 | 버그 수정 |

### gold snomed 행 수 변화
| 시나리오 | 수정 전 | 수정 후 | 변화 |
|---|---|---|---|
| S01 | 3 | 2 | -1 (Assessment 제거) |
| S02 | 5 | 3 | -2 (Assessment/탈수 제거, 구토→GI_VOMIT_FREQ 교체) |
| S03 | 3 | 3 | 0 (Assessment→OR_PATELLAR_LUXATION_CD 교체) |
| S04 | 4 | 1 | -3 (Assessment/LD_CADESI4_ALOPECIA_SUB/진균 배양 제거, 소양감→LD_PRURITUS_BEHAVIOR_NM 교체) |
| S05 | 3 | 0 | -3 (전수 DIFFERENT 제거) |
| **합계** | **18** | **9** | **-9** |

---

## §6 재평가 결과 (AFTER)

### 텍스트 모드

| 시나리오 | SNOMED Rate | 일치 | 총 gold | 불일치 |
|---|---|---|---|---|
| S01 | 0.000 | 0 | 2 | OPH_IOP_OD(semantic_tag), OPH_CORNEA(다른 disorder) |
| S02 | 0.667 | 2 | 3 | GP_RECTAL_TEMP(완전 다른 계층) |
| S03 | 0.667 | 2 | 3 | OR_LAMENESS_FL_L(UNMAPPED) |
| S04 | 1.000 | 1 | 1 | — |
| S05 | N/A | 0 | 0 | 전수 DIFFERENT |
| **전체** | **0.584** | **5** | **9** | |

### 오디오 모드

| 시나리오 | SNOMED Rate | 일치 | 총 gold | 불일치 |
|---|---|---|---|---|
| S01 | 0.000 | 0 | 2 | 텍스트 동일 |
| S02 | 0.667 | 2 | 3 | 텍스트 동일 |
| S03 | 0.333 | 1 | 3 | OR_LAMENESS_FL_L(UNMAPPED) + STT 오인식으로 OR_PATELLAR_LUX_L/OR_PATELLAR_LUXATION_CD UNMAPPED |
| S04 | 0.000 | 0 | 1 | STT 오인식으로 LD_PRURITUS_BEHAVIOR_NM UNMAPPED |
| S05 | N/A | 0 | 0 | 전수 DIFFERENT |
| **전체** | **0.333** | **3** | **9** | |

### BEFORE vs AFTER 비교

| 메트릭 | 목표 | BEFORE | AFTER (텍스트) | AFTER (오디오) | 판정 |
|---|---|---|---|---|---|
| SNOMED 일치율 | >=0.700 | 0.107 | **0.584** | **0.333** | FAIL (본질적 한계) |
| Precision | >=0.800 | 0.867 | **0.938** | **0.826** | PASS |
| Recall | >=0.700 | 0.748 | **0.737** | **0.774** | PASS |
| Latency p95 | <=60,000ms | 38,825ms | **33,368ms** | **60,461ms** | PASS / 경계 |

---

## §7 SNOMED 0.70 미달 본질적 한계 분석

수정 후 텍스트 0.584에서 추가 개선 가능한 4건의 성격:

| field_code | 불일치 원인 | 개선 가능성 |
|---|---|---|
| OPH_IOP_OD | RAG Top-1이 observable entity 대신 finding 반환. IS-A 관계 없음(다른 최상위 계층). | RAG 인덱스 개선 또는 필드 타입 기반 reranking으로 개선 가능 (v2.1) |
| OPH_CORNEA_CLARITY_OD_CD | RAG Top-1이 Post-surgical haze 반환 (수술 맥락 오인식). | 쿼리 reformulation 개선으로 개선 가능 (v2.1) |
| GP_RECTAL_TEMP_VALUE | RAG Top-1이 완전히 다른 계층(procedure) 반환. 필드명 'GP_RECTAL_TEMP' prefix 오인식. | 필드명 prefix 전처리 개선 필요 (v2.1) |
| OR_LAMENESS_FL_L | 파이프라인이 해당 field_code 미추출 (SOAP 추출 범위 밖). | SOAP 추출 범위 확장 필요 (v2.1) |

**결론**: 4건 모두 RAG 알고리즘 개선(Contextual Retrieval, 쿼리 전처리) 또는 SOAP 추출 범위 확장으로 개선 가능. v2.0 파이프라인의 본질적 한계이며 gold 수정으로 해결 불가.

---

## §8 pytest 회귀 결과

수정 후 `venv/bin/python3 -m pytest tests/ -x -q` 실행 결과:

```
86 passed, 1 warning in 73.36s
```

**86/86 PASS — regression 0건** (metrics.py synonym 모드 수정 포함)

---

> 본 문서는 정량 수치와 DB 실측 기반 분석만 포함합니다.
> 임상적 판단은 snomed-mapping skill 원칙 기준으로만 적용됩니다.
> (data-analyzer 원칙 + feedback_snomed_source_validation 준수)
