# vet-snomed-rag v2.0 Release Notes

**릴리즈 일자**: 2026-04-22  
**태그**: v2.0  
**GitHub**: https://github.com/ricocopapa/vet-snomed-rag

---

## 개요

v1.0의 SNOMED CT 하이브리드 RAG 검색 시스템 위에, 임상 발화(음성/텍스트)를 받아 SOAP 구조화 및 SNOMED 자동 태깅까지 수행하는 End-to-End 파이프라인을 추가한 메이저 릴리즈.

---

## 핵심 추가 기능

### 1. End-to-End 임상 인코딩 파이프라인

```
[음성 파일 or 텍스트]
        |
  (1) Whisper STT  (faster-whisper, 한국어)        ← 음성 입력 시
        |
  (2) SOAP 추출   (Gemini 3.1 Flash Lite Preview)
        도메인 탐지 → 필드 추출 → 검증
        |
  (3) SNOMED 자동 태깅  (RAG + MRCM 25도메인)
        하이브리드 검색 → 후조합 SCG → MRCM 검증
        |
[JSONL 출력: SOAP 필드 + SNOMED 코드 태깅 레코드]
```

- `src/pipeline/stt_wrapper.py` — faster-whisper / openai-whisper fallback, mp3/m4a/wav/ogg 지원
- `src/pipeline/soap_extractor.py` — Gemini 3.1 Flash Lite Preview / Claude Haiku+Sonnet 멀티 백엔드
- `src/pipeline/snomed_tagger.py` — MRCM 25도메인 64패턴 검증 + 후조합 SCG 빌더
- `src/pipeline/e2e.py` — `ClinicalEncoder` 오케스트레이터, JSONL 출력

### 2. Streamlit UI — Clinical Encoding 탭

`streamlit run app.py` 실행 후 "Clinical Encoding" 탭에서:
- 음성 파일(mp3/m4a/wav) 또는 임상 텍스트 업로드
- SOAP 구조화 결과 실시간 확인
- SNOMED 태깅 JSONL 다운로드

### 3. 3모델 비교 및 백엔드 선택

| 모델 | Latency | 상태 | 선택 |
|---|---|---|---|
| Gemini 2.5 Flash | — | GA, 할당량 초과 (23/20 RPM) | 미선택 |
| Gemini 2.5 Flash Lite | 3~5s | GA, 10× 빠름 | 대안 |
| **Gemini 3.1 Flash Lite Preview** | 18~47s | Preview, RPD 500 | **채택** |

채택 근거: RPD 500 (25× 높은 일일 할당량)으로 배치 평가 안정성 확보. 프로덕션 환경(일 100건 이하)에서 속도 우선 시 2.5 Flash Lite GA 권장.

### 4. 평가 프레임워크

- 5건 합성 임상 시나리오 (안과·위장관·정형·피부·종양)
- Gold-label 역공학 감사 완료 (30건 변경, 0건 역공학)
- `scripts/evaluate_e2e.py` — strict / superset / synonym 3모드

---

## v2.0 벤치마크 결과

### End-to-End 품질 메트릭

| 메트릭 | 목표 | 텍스트 모드 | 오디오 모드 | 판정 |
|---|---|---|---|---|
| 필드 Precision | >=0.800 | **0.938** | **0.826** | 양쪽 PASS |
| 필드 Recall | >=0.700 | **0.737** | **0.774** | 양쪽 PASS |
| SNOMED 일치율 | >=0.700 | 0.584 | 0.250 | 미달 |
| Latency p95 | <=60,000ms | **33,368ms** | 60,461ms | 텍스트 PASS / 오디오 461ms 초과 |

**4개 메트릭 중 텍스트 모드 3개 PASS, 오디오 모드 2개 PASS.**

### v1.0 → v2.0 개선폭 (텍스트 모드)

| 메트릭 | v2.0 초기 (Day 1) | v2.0 Final | 개선 |
|---|---|---|---|
| Precision | 0.43 | **0.938** | +118% |
| Recall | 0.52 | **0.737** | +42% |
| SNOMED 일치율 | 0.107 | **0.584** | +446% |
| Latency p95 | 127,000ms | **33,368ms** | −74% |

SNOMED 0.107 → 0.584 개선 배경:
1. gold-label field_code 구조 결함 수정 — 임상 메모 12건을 표준 field_code로 교체/제거
2. metrics.py synonym 모드 DB 테이블명 버그 수정 (`relationships` → `relationship`)

### 한계 및 미달 항목

- **SNOMED 일치율 미달**: 잔존 4건은 RAG 본질적 한계 (semantic_tag 불일치, 다른 계층 오매핑, 파이프라인 미추출). v2.1 RAG 개선 필요.
- **오디오 Latency 초과 (+461ms)**: Gemini 3.1 Flash Lite Preview 특성. v2.1에서 2.5 Flash Lite GA 전환 검토.
- **합성 음성 평가**: gTTS 합성 음성 기준. 실 수의사 녹음 검증은 v2.1 예정.

---

## 회귀 테스트

- v1.0 11-쿼리 회귀: 기존 회귀 테스트 포함 유지
- v2.0 pytest: **85 passed, 1 skipped** (B1~B4 + Remediation 3건)

---

## 보안

- API 키 git 이력 검증: 0건 매치
- 실환자 데이터: 0건
- 합성 시나리오 역공학 감사: PASS

---

## 설치 및 사용

### 요구사항

```bash
pip install -r requirements.txt
# GOOGLE_API_KEY 또는 ANTHROPIC_API_KEY 필요 (.env.example 참조)
```

### 텍스트 모드 E2E 평가

```bash
python scripts/evaluate_e2e.py \
  --input-mode text \
  --input-dir data/synthetic_scenarios/ \
  --snomed-mode synonym
```

### 오디오 모드 E2E 평가

```bash
python scripts/evaluate_e2e.py \
  --input-mode audio \
  --input-dir data/synthetic_scenarios/ \
  --snomed-mode synonym
```

### Streamlit UI

```bash
streamlit run app.py
```

### v1.0 RAG 검색 (기존 기능 유지)

```bash
python src/retrieval/rag_pipeline.py --interactive --llm claude
```

---

## v2.1 계획

- RAG 랭킹 개선 (BM25 튜닝, semantic_tag 우선순위)
- 실 수의사 녹음 검증
- 오디오 Latency 최적화 (2.5 Flash Lite GA 전환)
- Claude Opus/Sonnet 백업 백엔드 완성

---

## 관련 문서

- [README.md](./README.md) — 전체 프로젝트 소개
- [CHANGELOG.md](./CHANGELOG.md) — 버전별 변경 이력
- [benchmark/v2_headline_metrics.md](./benchmark/v2_headline_metrics.md) — 핵심 지표 요약
- [benchmark/v2_review.md](./benchmark/v2_review.md) — 독립 감사 리포트

---

> 본 릴리즈는 합성 임상 시나리오 기반 평가 결과이며, 실 환자 데이터를 포함하지 않습니다.  
> SNOMED CT 데이터는 SNOMED International 라이선스에 따라 본 저장소에 포함되지 않습니다.  
> 사용자는 소속 국가의 Affiliate Licence 취득 후 로컬에서 재생성해야 합니다.
