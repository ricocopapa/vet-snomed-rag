# v2.0 C2 Day 6 실행 가이드 (Runbook)

> **작성일**: 2026-04-22  
> **목적**: 사용자 녹음 5건 완료 후 즉시 실행 가능한 E2E 평가 절차

---

## 사전 체크리스트

- [ ] 시나리오 5건 녹음 완료 (`scenario_{1..5}.m4a` 또는 `.wav`)
- [ ] 녹음 파일을 `data/synthetic_scenarios/` 디렉토리에 배치
- [ ] `ANTHROPIC_API_KEY` 환경변수 설정 확인
- [ ] Python venv 활성화 확인

---

## Step 1: 녹음 파일 배치 확인

```bash
ls data/synthetic_scenarios/scenario_*.m4a
# 기대 출력:
# scenario_1_ophthalmology.m4a
# scenario_2_gastrointestinal.m4a
# scenario_3_orthopedics.m4a
# scenario_4_dermatology.m4a
# scenario_5_oncology.m4a
```

파일명 패턴: `scenario_{N}*.m4a` (N=1~5, 이후 임의 suffix 허용)

---

## Step 2: 환경 설정

```bash
cd /Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag
source venv/bin/activate

# API 키 확인
echo $ANTHROPIC_API_KEY | head -c 10   # 앞 10자만 표시 (키 노출 방지)
```

---

## Step 3: E2E 평가 실행 (오디오 모드)

```bash
python scripts/evaluate_e2e.py \
  --input-mode audio \
  --input-dir data/synthetic_scenarios/ \
  --output benchmark/v2_e2e_report.md \
  --jsonl-out benchmark/v2_e2e_raw.jsonl \
  --snomed-mode exact
```

### 옵션 설명

| 옵션 | 값 | 설명 |
|---|---|---|
| `--input-mode` | `audio` | Day 6: 오디오 모드 (Day 5 dry_run은 `text`) |
| `--input-dir` | `data/synthetic_scenarios/` | m4a 파일 위치 |
| `--output` | `benchmark/v2_e2e_report.md` | 리포트 출력 경로 |
| `--snomed-mode` | `exact` | SNOMED 일치 모드 (exact / synonym) |

---

## Step 4: 예상 소요 시간

| 단계 | 예상 시간 (시나리오당) | 비고 |
|---|---|---|
| STT (Whisper) | 10~30s | 오디오 30~90초 기준 |
| SOAP 추출 | 10~30s | Claude Haiku + Sonnet API |
| SNOMED 태깅 | 5~15s | RAG + DB 조회 |
| **총합 (5건)** | **약 3~6분** | 병렬 처리 없음, 순차 실행 |

---

## Step 5: 출력 파일 확인

```bash
# JSONL 5건 확인
wc -l benchmark/v2_e2e_raw.jsonl       # 5 이어야 함

# 리포트 확인
head -30 benchmark/v2_e2e_report.md

# 차트 3장 확인
ls benchmark/charts/v2_*.png
# 기대:
# v2_field_accuracy.png
# v2_snomed_match.png
# v2_e2e_latency.png
```

---

## Step 6: 목표 수치 (§5.2)

| 메트릭 | 목표 | 비고 |
|---|---|---|
| SOAP 필드 Precision | >= 0.800 | - |
| SOAP 필드 Recall | >= 0.700 | - |
| SNOMED 태깅 일치율 (exact) | >= 0.700 | concept_id 완전 일치 |
| E2E Latency p95 | <= 60,000 ms | 30초 오디오 기준 |

목표 미달 시: `benchmark/v2_e2e_report.md` §1 Executive Summary의 FAIL 항목 확인

---

## Step 7: synonym 모드 추가 실행 (선택)

exact 모드 실행 후 IS-A 상위/하위 2단계 허용 모드로 재측정:

```bash
python scripts/evaluate_e2e.py \
  --input-mode audio \
  --input-dir data/synthetic_scenarios/ \
  --output benchmark/v2_e2e_report_synonym.md \
  --jsonl-out benchmark/v2_e2e_raw.jsonl \
  --snomed-mode synonym \
  --no-chart
```

---

## 블로커 및 대응

| 블로커 | 원인 | 대응 |
|---|---|---|
| `ANTHROPIC_API_KEY` 미설정 | 환경변수 없음 | `export ANTHROPIC_API_KEY=sk-ant-...` |
| 오디오 파일 없음 | 녹음 파일 미배치 | Step 1 재확인 |
| STT 실패 (FileNotFoundError) | faster-whisper 미설치 | `pip install faster-whisper` |
| SNOMED rate=0 | RAG DB 미초기화 | `python scripts/setup.py` 또는 chromadb 재확인 |
| API 비용 초과 우려 | 5건 전체 실행 | `--dry-run` 플래그로 텍스트 모드 재확인 후 실행 |

---

## Day 5 dry_run vs Day 6 공식 수치 비교 방법

```bash
# Day 5 dry_run 결과 (임시 보존)
cp benchmark/v2_e2e_report.md benchmark/v2_e2e_report_dryrun_day5.md

# Day 6 실행 후 diff
diff benchmark/v2_e2e_report_dryrun_day5.md benchmark/v2_e2e_report.md
```

---

> 본 runbook은 정량 수치 측정 절차만 포함합니다. 임상적 판단은 포함하지 않습니다.  
> (data-analyzer 원칙 준수)
