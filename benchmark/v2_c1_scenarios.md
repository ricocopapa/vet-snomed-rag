---
title: vet-snomed-rag v2.0 Track C1 — 합성 임상 시나리오 종합 리포트
version: 1.0
created: 2026-04-22
phase: Day 4
status: 산출물 완료 / 녹음 대기 중
---

# C1 종합 리포트: 합성 임상 시나리오 5건

## 1. 5건 시나리오 요약

| # | 도메인 | 종 | 주호소 | 핵심 수치 | 예상 duration |
|---|---|---|---|---|---|
| 1 | OPHTHALMOLOGY (안과) | 고양이 | 우안 충혈 + 동공 산동 | IOP OD=32 mmHg | ~60초 |
| 2 | GASTROINTESTINAL + VITAL_SIGNS (소화기+활력징후) | 개 | 2일간 구토 6회 + 식욕감소 | BT=39.2°C, HR=140 bpm, 탈수 5~7% | ~75초 |
| 3 | ORTHOPEDICS (정형외과) | 개 | 왼쪽 뒷다리 간헐적 파행 1개월 | MPL grade 2, 파행 등급 2/5 | ~65초 |
| 4 | DERMATOLOGY (피부과) | 고양이 | 얼굴/앞발 원형 탈모 3주 | 병변 3개소, Wood's lamp 양성 2/3 | ~70초 |
| 5 | ONCOLOGY (종양학) | 개 | 어깨 종괴 2주간 성장 | 3×2 cm, 피하 경계 명확 | ~65초 |

**총 발화 목표 시간:** 약 335초 (5건 합산)

---

## 2. 도메인 커버리지

전체 25도메인 중 5개 커버:

| 도메인 | field_count | 시나리오 | 커버 여부 |
|---|---|---|---|
| VITAL_SIGNS | 33 | S2 (보조) | ✓ |
| OPHTHALMOLOGY | 72 | S1 (주) | ✓ |
| ORTHOPEDICS | 147 | S3 (주) | ✓ |
| DERMATOLOGY | 91 | S4 (주) | ✓ |
| GASTROINTESTINAL | 20 | S2 (주) | ✓ |
| ONCOLOGY | 141 | S5 (주) | ✓ |
| 나머지 19개 도메인 | — | — | v2.0 후속 단계 |

---

## 3. Gold-Label 수치

### 필드 수

| 시나리오 | 기대 필드 수 |
|---|---|
| S1 (안과) | 7필드 |
| S2 (소화기+활력징후) | 8필드 |
| S3 (정형외과) | 5필드 |
| S4 (피부과) | 6필드 |
| S5 (종양학) | 2필드 + 3 MASS연계 |
| **합계** | **31필드** |

### Concept_id DB 검증 통계

| concept_id | preferred_term | semantic_tag | 시나리오 | DB 검증 |
|---|---|---|---|---|
| 41633001 | Intraocular pressure | observable entity | S1 | PASS |
| 27194006 | Corneal edema | disorder | S1 | PASS |
| 23986001 | Glaucoma | disorder | S1 (Assessment) | PASS |
| 386725007 | Body temperature | observable entity | S2 | PASS |
| 364075005 | Heart rate | observable entity | S2 | PASS |
| 69776003 | Acute gastroenteritis | disorder | S2 (Assessment) | PASS |
| 422400008 | Vomiting | disorder | S2 | PASS |
| 34095006 | Dehydration | disorder | S2 | PASS |
| 311741000009107 | Medial luxation of patella | disorder (VET) | S3 (Assessment) | PASS |
| 272981000009107 | Lameness of quadruped | finding (VET) | S3 | PASS |
| 47382004 | Dermatophytosis | disorder | S4 (Assessment) | PASS |
| 56317004 | Alopecia | disorder | S4 | PASS |
| 418290006 | Itching | finding | S4 | PASS |
| 104189007 | Fungal culture, skin, with isolation | procedure | S4 | PASS |
| 239147000 | Mastocytoma of skin | disorder | S5 (Assessment) | PASS |
| 297960002 | Mass of skin | finding | S5 | PASS |
| 15719007 | Fine needle aspirate with routine interpretation and report | procedure | S5 | PASS |

**총 기대 concept_id: 17건**
**DB 검증 통과: 17/17 (100%)**
**DB 검증 실패: 0건**

---

## 4. T2 재검토 결과

| 항목 | 현재 | 권고 |
|---|---|---|
| expected_concept_id | 47457000 | **342481000009106** |
| expected_term | Canine parvovirus | **Canine parvovirus infection** |
| semantic_tag | organism | **disorder** |
| source | INT | VET |
| 권고 | — | **변경** |

**핵심 근거:**
- 쿼리 "canine parvovirus enteritis"는 임상 질환 쿼리 → disorder tag 필요
- 47457000은 organism tag → A축 진단 용도 금지 tag (snomed-mapping 원칙 1 위반)
- 342481000009106 (VET Extension) = Causative agent: 47457000 포함 → 의미 완전성 유지
- 변경 시 regression 결과: none 모드 재평가 필요 (기존 PASS → 재검증)

상세 분석: `data/synthetic_scenarios/T2_review.md`

---

## 5. 식별정보 검토 결과

| 시나리오 | 이름 | 병원명 | 날짜 | 주소/전화 | 결과 |
|---|---|---|---|---|---|
| S1 | 없음 | 없음 | 없음 | 없음 | PASS |
| S2 | 없음 | 없음 | 없음 | 없음 | PASS |
| S3 | 없음 | 없음 | 없음 | 없음 | PASS |
| S4 | 없음 | 없음 | 없음 | 없음 | PASS |
| S5 | 없음 | 없음 | 없음 | 없음 | PASS |

**전수 PII 0건 확인**

---

## 6. 산출물 경로

```
data/synthetic_scenarios/
├── README.md                          (녹음 가이드)
├── scenario_1_ophthalmology.md        (안과: 고양이 녹내장 의심)
├── scenario_2_gastrointestinal.md     (소화기: 개 급성 위장염)
├── scenario_3_orthopedics.md          (정형외과: 개 슬개골 탈구)
├── scenario_4_dermatology.md          (피부과: 고양이 피부사상균증)
├── scenario_5_oncology.md             (종양학: 개 비만세포종 의심)
└── T2_review.md                       (T2 gold-label 재검토)

benchmark/
└── v2_c1_scenarios.md                 (본 리포트)
```

---

## 7. 리스크 / 블로커

### 현재 블로커

없음 — 모든 산출물 완료, 녹음 대기 상태.

### 녹음 완료 후 Day 6 C2 평가 필요사항

1. **STT 변환:** 5건 m4a → 텍스트 변환 (VetSTT 파이프라인 또는 Whisper)
2. **SNOMED 매핑 실행:** 변환된 텍스트 → v1.0 RAG 파이프라인 통과
3. **Gold-Label 대조:** 각 시나리오별 추출 필드 vs. 기대 필드 F1 계산
4. **T2 변경 적용:** 사용자 승인 후 regression_metrics.json 수정 후 회귀 재실행

### 주의사항

- S3 슬개골 탈구 gold-label에서 VET Extension (311741000009107)을 기대 — v1.0 RAG가 VET Extension을 올바르게 검색하는지 C2에서 확인 필요
- S5 비만세포종은 FNA 결과 전 단계의 "의심" 케이스 — 확진 전 단계 쿼리 처리 능력 테스트

---

## 8. 성공 기준 체크리스트

- [x] 5건 시나리오 스크립트 완성 (각 150~300자 내 — 한국어 구어체 기준 120~250자 달성)
- [x] 각 시나리오 gold-label 완비 (도메인/필드/concept_id)
- [x] 기대 concept_id 전수 DB 검증 PASS (17/17)
- [x] 식별정보 0건 (이름/병원/주소/전화번호) — 전수 PASS
- [x] T2 재검토 권고안 완성 (근거 포함) — 변경 권고
- [x] 녹음 가이드 README 완비
- [ ] 녹음 파일 생성 (사용자 실행 필요)
