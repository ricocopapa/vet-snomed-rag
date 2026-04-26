# Backend Comparison — Gemini 2.5 Flash vs Claude Sonnet 4.6

생성 시각: 2026-04-26 17:57:21

## 요약 테이블

| 메트릭 | none (기준선) | Gemini 2.5 Flash | Claude Sonnet 4.6 (미실행) |
| --- | --- | --- | --- |
| 11쿼리 PASS율 | 10/10 | 10/10 | API 키 미설정으로 실측 생략 |
| T7 (feline diabetes→73211009) | ✓ (rank #1) | ✓ (rank #1) | 미실행 |
| 총 비용 | $0.00000 | $0.00297 | 미실행 |
| 평균 레이턴시 | 1774ms | 25820ms | 미실행 |

## 쿼리별 상세 (T1~T11)

| 쿼리ID | 쿼리 | 기대 concept_id | none rank | none verdict | gemini rank | gemini verdict | claude 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | feline panleukopenia SNOMED code | 339181000009108 | #1 | PASS | #1 | PASS | API 키 미설정으로 실측 생략 |
| T2 | canine parvovirus enteritis | 47457000 | #1 | PASS | #1 | PASS | API 키 미설정으로 실측 생략 |
| T3 | diabetes mellitus in cat | 73211009 | #1 | PASS | #1 | PASS | API 키 미설정으로 실측 생략 |
| T4 | pancreatitis in dog | 75694006 | #1 | PASS | #1 | PASS | API 키 미설정으로 실측 생략 |
| T5 | chronic kidney disease in cat | 복수 | 없음 | NA | 없음 | NA | API 키 미설정으로 실측 생략 |
| T6 | cat bite wound | 283782004 | #1 | PASS | #1 | PASS | API 키 미설정으로 실측 생략 |
| T7 | feline diabetes | 73211009 | #1 | PASS | #1 | PASS | API 키 미설정으로 실측 생략 |
| T8 | diabetes mellitus type 1 | 46635009 | #1 | PASS | #1 | PASS | API 키 미설정으로 실측 생략 |
| T9 | 고양이 당뇨 | 73211009 | #1 | PASS | #1 | PASS | API 키 미설정으로 실측 생략 |
| T10 | 개 췌장염 | 75694006 | #1 | PASS | #1 | PASS | API 키 미설정으로 실측 생략 |
| T11 | 고양이 범백혈구감소증 SNOMED 코드 | 339181000009108 | #1 | PASS | #1 | PASS | API 키 미설정으로 실측 생략 |

## T7 해결 상세 (핵심)

- 원본 쿼리: `feline diabetes`
- Gemini 리포매팅 결과: `diabetes mellitus`
- Gemini confidence: `1.0`
- Gemini post_coord_hint: `Occurs in = Feline species`
- 최종 Top-1: `73211009 Diabetes mellitus`
- 판정: **PASS**

**Claude Sonnet 4.6 섹션**: API 키 미설정으로 실측 생략.

## 결론 (권장 기본 backend)

Gemini 2.5 Flash가 10/10 PASS 달성 — 단일 백엔드로 프로덕션 투입 가능.

Claude Sonnet 4.6: API 키 미설정으로 비교 불가. 키 설정 후 동일 스크립트 재실행 시 자동 포함.

---
*생성: scripts/run_regression.py (Agent A)*