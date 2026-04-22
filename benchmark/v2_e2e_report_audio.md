# v2.0 E2E 평가 리포트

> **생성 시각**: 2026-04-22 09:00 UTC  
> **실행 모드**: audio 모드  
> **SNOMED 일치 모드**: synonym  
> **주의**: 공식 측정 수치

---

## §1 Executive Summary

| 메트릭 | 목표 (§5.2) | 결과 | 상태 |
|---|---|---|---|
| SOAP 필드 Precision | >=0.800 | 0.826 | PASS (0.826 >= 0.8) |
| SOAP 필드 Recall | >=0.700 | 0.774 | PASS (0.774 >= 0.7) |
| SNOMED 태깅 일치율 (exact) | >=0.700 | 0.250 | FAIL (0.250 >= 0.7) |
| E2E Latency p95 | <=60,000 ms | 60461 ms | FAIL (60460.600 <= 60000) |

---

## §2 시나리오별 상세 결과

| Scenario | Domain | Precision | Recall | F1 | TP | FP | FN | SNOMED Rate | Total Latency |
|---|---|---|---|---|---|---|---|---|---|
| S01 | OPHTHALMOLOGY | 1.000 | 0.750 | 0.857 | 6 | 0 | 2 | 0.000 | 32427 ms |
| S02 | GASTROINTESTINAL | 0.909 | 1.000 | 0.952 | 10 | 1 | 0 | 0.667 | 55231 ms |
| S03 | ORTHOPEDICS | 0.636 | 0.538 | 0.583 | 7 | 4 | 6 | 0.333 | 96930 ms |
| S04 | DERMATOLOGY | 0.667 | 0.667 | 0.667 | 6 | 3 | 3 | 0.000 | 34088 ms |
| S05 | ONCOLOGY | 0.917 | 0.917 | 0.917 | 11 | 1 | 1 | N/A | 60461 ms |

---

## §3 메트릭 요약 (Target vs Actual)

### 필드 추출

| 항목 | 수치 |
|---|---|
| Precision (mean) | 0.826 |
| Recall (mean) | 0.774 |
| F1 (mean) | 0.795 |
| 총 TP | 40 |
| 총 FP | 9 |
| 총 FN | 12 |

### SNOMED 태깅 (synonym 모드)

| 항목 | 수치 |
|---|---|
| 일치율 (mean) | 0.250 |

### Latency

| 시나리오 | STT p50 | SOAP p50 | SNOMED p50 | Total p50 | Total p95 |
|---|---|---|---|---|---|
| S01 | 9476 ms | 20828 ms | 2123 ms | 32427 ms | 32427 ms |
| S02 | 11536 ms | 39874 ms | 3822 ms | 55231 ms | 55231 ms |
| S03 | 13592 ms | 27834 ms | 55504 ms | 96930 ms | 96930 ms |
| S04 | 12389 ms | 18043 ms | 3656 ms | 34088 ms | 34088 ms |
| S05 | 10582 ms | 44918 ms | 4960 ms | 60461 ms | 60461 ms |

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
benchmark/v2_e2e_raw_audio.jsonl
```

---

> 본 리포트는 정량 수치만 포함합니다. 임상적 판단은 포함하지 않습니다.
> (data-analyzer 원칙 준수)