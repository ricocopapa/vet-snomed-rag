# v2.0 E2E 평가 리포트

> **생성 시각**: 2026-04-22 08:55 UTC  
> **실행 모드**: text 모드  
> **SNOMED 일치 모드**: synonym  
> **주의**: 공식 측정 수치

---

## §1 Executive Summary

| 메트릭 | 목표 (§5.2) | 결과 | 상태 |
|---|---|---|---|
| SOAP 필드 Precision | >=0.800 | 0.938 | PASS (0.938 >= 0.8) |
| SOAP 필드 Recall | >=0.700 | 0.737 | PASS (0.737 >= 0.7) |
| SNOMED 태깅 일치율 (exact) | >=0.700 | 0.584 | FAIL (0.584 >= 0.7) |
| E2E Latency p95 | <=60,000 ms | 33368 ms | PASS (33368.100 <= 60000) |

---

## §2 시나리오별 상세 결과

| Scenario | Domain | Precision | Recall | F1 | TP | FP | FN | SNOMED Rate | Total Latency |
|---|---|---|---|---|---|---|---|---|---|
| S01 | OPHTHALMOLOGY | 1.000 | 0.625 | 0.769 | 5 | 0 | 3 | 0.000 | 32154 ms |
| S02 | GASTROINTESTINAL | 1.000 | 1.000 | 1.000 | 10 | 0 | 0 | 0.667 | 28712 ms |
| S03 | ORTHOPEDICS | 0.889 | 0.615 | 0.727 | 8 | 1 | 5 | 0.667 | 25831 ms |
| S04 | DERMATOLOGY | 1.000 | 0.778 | 0.875 | 7 | 0 | 2 | 1.000 | 37961 ms |
| S05 | ONCOLOGY | 0.800 | 0.667 | 0.727 | 8 | 2 | 4 | N/A | 33368 ms |

---

## §3 메트릭 요약 (Target vs Actual)

### 필드 추출

| 항목 | 수치 |
|---|---|
| Precision (mean) | 0.938 |
| Recall (mean) | 0.737 |
| F1 (mean) | 0.820 |
| 총 TP | 38 |
| 총 FP | 3 |
| 총 FN | 14 |

### SNOMED 태깅 (synonym 모드)

| 항목 | 수치 |
|---|---|
| 일치율 (mean) | 0.584 |

### Latency

| 시나리오 | STT p50 | SOAP p50 | SNOMED p50 | Total p50 | Total p95 |
|---|---|---|---|---|---|
| S01 | 0 ms | 30393 ms | 1761 ms | 32154 ms | 32154 ms |
| S02 | 0 ms | 25380 ms | 3332 ms | 28712 ms | 28712 ms |
| S03 | 0 ms | 24046 ms | 1785 ms | 25831 ms | 25831 ms |
| S04 | 0 ms | 35767 ms | 2194 ms | 37961 ms | 37961 ms |
| S05 | 0 ms | 29538 ms | 3831 ms | 33368 ms | 33368 ms |

---

## §4 차트

### Chart 1: 도메인별 필드 Precision/Recall

![Field Accuracy](/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag/benchmark/charts/v2_field_accuracy.png)

### Chart 2: SNOMED 태깅 일치율

![SNOMED Match](/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag/benchmark/charts/v2_snomed_match.png)

### Chart 3: E2E Latency (단계별)

![E2E Latency](/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag/benchmark/charts/v2_e2e_latency.png)

---

## §5 Raw JSONL 출력 경로

```
benchmark/v2_e2e_raw.jsonl
```

---

> 본 리포트는 정량 수치만 포함합니다. 임상적 판단은 포함하지 않습니다.
> (data-analyzer 원칙 준수)