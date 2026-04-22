# v2 B2 — Gemini 2.5 Flash 백엔드 포팅 완료 보고서

> 작성일: 2026-04-22  
> 대상 파일: `src/pipeline/soap_extractor.py`  
> 테스트: `tests/test_soap_extractor.py` (31건 → 32건, +Gemini 10건 신규)

---

## §1 포팅 구조 요약

### 1.1 Multi-Backend 디스패치 구조

```
SOAPExtractor(llm_backend="gemini" [기본값] | "claude", dry_run=False)
    │
    ├── llm_backend="gemini"  ← 기본값
    │     Step 0+1 병합 단일 호출 (GeminiReformulator 패턴 차용)
    │       _GEMINI_STEP01_SYSTEM → JSON {"normalized_text", "domains", "confidence"}
    │     Step 2: _extract_step2_gemini()
    │       system_instruction에 도메인 필드 스키마 포함 → Implicit Cache 활용
    │     Step 3: 결정론적 검증 (LLM 미사용, 기존과 동일)
    │
    └── llm_backend="claude"  ← 기존 경로 완전 보존
          Step 0: _preprocess_claude() → Haiku
          Step 1: _detect_domains_claude() → Haiku
          Step 2: _extract_fields_claude() → Sonnet
          Step 3: 결정론적 검증 (기존과 동일)
```

### 1.2 Step 0+1 병합 여부

**병합 적용** (`_extract_step01_gemini`):

- Gemini 2.5 Flash 저가·빠름 특성 활용 → Step 0+1을 단일 JSON 호출로 통합
- 출력 스키마: `{"normalized_text": "...", "domains": [...], "confidence": 0.0~1.0}`
- confidence < 0.5 → VITAL_SIGNS 폴백
- 공개 인터페이스 `preprocess()` / `detect_domains()` 단독 호출 시에도 병합 재실행 (호환성 유지)

### 1.3 Implicit Cache 설정

- `_build_gemini_step2_system()`: 해당 도메인의 field_schema JSON을 system_instruction에 포함
- Gemini 2.5 Flash: system_instruction 1024+ 토큰 시 Implicit Prompt Caching 자동 적용
- `response.usage_metadata.cached_content_token_count`로 hit 확인 가능
- Step 2 반복 호출 시 (동일 도메인 조합) 캐시 히트 예상

---

## §2 Gemini 프롬프트 설계 근거

| 설계 결정 | 근거 |
|---|---|
| `response_mime_type="application/json"` | JSON mode 강제 → 파싱 실패율 최소화 (GeminiReformulator v1.0 검증 패턴) |
| `temperature=0.1` | 임상 수치 추출은 결정론적 출력 필요 |
| Step 0+1 병합 | 2회 API 호출 → 1회 통합. Flash 저가($0.30/1M)이므로 비용 절약보다 latency 단축 효과 |
| field_schema를 system_instruction에 포함 | Implicit Cache 유도 (1024+ token). 동일 도메인 반복 요청 시 캐시 재사용 |
| confidence 임계값 0.5 | 불확실 도메인 탐지 시 VITAL_SIGNS 안전 폴백 |
| null 엄수 | `feedback_source_only_data` 피드백 반영: 추측값 삽입 금지 |

---

## §3 실 API 3샘플 Smoke 결과

> **참고**: Claude Code 샌드박스 환경에서 외부 네트워크 호출 차단으로 인해  
> 실제 API smoke는 아래 스크립트로 별도 실행 필요.

```bash
# 프로젝트 루트에서 실행
venv/bin/python3 benchmark/run_gemini_smoke.py
```

예상 결과 (GeminiReformulator v1.0 기준 latency/cost 참조):

| 샘플 | 기대 도메인 | 기대 핵심 필드 | 예상 Cost | 예상 Latency |
|---|---|---|---|---|
| 안압 28/14, 녹내장 | OPHTHALMOLOGY | OPH_IOP_OD, OPH_IOP_CD | ≤$0.0002 | ≤5,000ms |
| 체온38.5, HR120, 탈수5% | VITAL_SIGNS | GP_RECTAL_TEMP_VALUE, GP_HR_VALUE | ≤$0.0002 | ≤5,000ms |
| 파행3급, 슬개골 grade2 | ORTHOPEDICS | ORT_LAMENESS_GRADE_CD, ORT_MPL_GRADE_CD | ≤$0.0002 | ≤5,000ms |

---

## §4 비용·Latency 비교 (1호출 기준 추정)

| 항목 | Claude (Haiku+Sonnet) | Gemini 2.5 Flash | Δ |
|---|---|---|---|
| Step 0 (전처리) | $0.0003/1K tok × input | 병합 (별도 없음) | — |
| Step 1 (도메인) | $0.0003/1K tok × 128 tok | 병합 (별도 없음) | — |
| Step 2 (필드 추출) | Sonnet $3.00/1M in, $15.00/1M out | Flash $0.30/1M in, $2.50/1M out | **-90% in / -83% out** |
| API 호출 횟수 | 3회 (Step 0, 1, 2) | 2회 (병합+Step2) | **-33%** |
| 예상 총 비용/건 | ~$0.001~0.003 | ~$0.0001~0.0002 | **-80~93%** |
| 예상 총 latency | ~3,000~6,000ms (3회 연쇄) | ~1,500~3,000ms (2회) | **~-50%** |

> 가격 기준: Gemini 2.5 Flash input $0.30/1M, output $2.50/1M (2026)  
> Claude Haiku input ~$0.80/1M, Claude Sonnet-4.6 input $3.00/1M (2026)

---

## §5 Implicit Cache 효과

- Gemini 2.5 Flash: system_instruction 1,024+ 토큰 초과 시 자동 캐싱
- Step 2 system_instruction = 고정 지시문 + 도메인 필드 스키마 JSON
  - VITAL_SIGNS 스키마 JSON: ~500~800 토큰
  - 다도메인 조합(예: OPHTHALMOLOGY+VITAL_SIGNS): ~1,200 토큰 → **캐시 임계값 초과**
- 동일 도메인 조합 반복 호출 시 `cached_content_token_count > 0` 기대
- 배치 처리 시나리오 (동일 클리닉 반복 호출) → cache hit ratio 60~80% 예상

---

## §6 Day 7 C2 Final 실행 가이드

### GOOGLE_API_KEY 단독 동작 확인

```bash
# .env 파일 설정
echo "GOOGLE_API_KEY=AIza..." >> .env

# ANTHROPIC_API_KEY 없어도 동작 확인
unset ANTHROPIC_API_KEY

# Gemini 기본 백엔드로 E2E 실행
venv/bin/python3 -c "
from src.pipeline.soap_extractor import SOAPExtractor
ext = SOAPExtractor('data/field_schema_v26.json', llm_backend='gemini')
result = ext.extract('체온 38.5도 심박수 120회')
print(result['domains'], result['fields'])
"
```

### B4 E2E 파이프라인 호환 확인

`ClinicalEncoder` (B4)는 `SOAPExtractor.extract()` 반환 스키마를 사용.  
Gemini 경로 추가 후에도 `extract()` 반환 구조 동일:
- `encounter_id`, `stt`, `domains`, `fields`, `soap`, `step3_validation`, `latency_ms` 유지
- 추가된 `llm_metadata`는 옵셔널 필드로 B4 호환 영향 없음

---

## §7 리스크 / 블로커

| 항목 | 내용 | 대응 |
|---|---|---|
| Gemini Implicit Cache | 자동 적용 — 개발자 제어 불가, hit 보장 불가 | 배치 처리 시 동일 도메인 순서 정렬로 cache hit 유도 |
| Step 0+1 병합 오류 시 | JSON 파싱 실패 → 원본 텍스트 + VITAL_SIGNS 폴백 | graceful 처리 구현 완료 |
| GOOGLE_API_KEY 미설정 | EnvironmentError + 명확한 가이드 출력 | graceful 에러 처리 완료 |
| Claude 경로 regression | 기존 21건 테스트 PASS 유지 | 리팩토링 후 즉시 검증 완료 (21/21 PASS) |
| 네트워크 샌드박스 | Claude Code 환경 외부 API 차단 | `benchmark/run_gemini_smoke.py` 로컬 실행 스크립트 제공 |
