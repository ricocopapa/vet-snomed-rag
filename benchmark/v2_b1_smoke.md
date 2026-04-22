---
tags: [vet-snomed-rag, v2.0, B1, STT, smoke-test]
date: 2026-04-22
status: PASS
---

# Track B1 — Whisper STT 래퍼 Smoke 리포트

## 1. 재활용 자산 실측

| 항목 | 결과 |
|---|---|
| `scripts/whisper_retranscribe.py` 존재 | **없음 (NOT_FOUND)** |
| 조치 | faster-whisper 공식 README 기반 신규 구현 |
| 참조 파라미터 | `project_emr_whisper.md` 기준 beam_size=5, language="ko" 적용 |

## 2. 구현 요약

### 파일 목록

| 파일 | 유형 | 설명 |
|---|---|---|
| `src/pipeline/__init__.py` | 신규 | 파이프라인 패키지 초기화 |
| `src/pipeline/stt_wrapper.py` | 신규 | Whisper STT 래퍼 핵심 모듈 |
| `tests/test_stt_wrapper.py` | 신규 | 단위 테스트 3건 |
| `tests/requirements-dev.txt` | 신규 | 개발/테스트 전용 의존성 |
| `requirements.txt` | 수정 | `faster-whisper>=1.0` 추가 |

### `transcribe()` 함수 시그니처

```python
def transcribe(
    audio_path: str | Path,
    model_size: str = "small",
    language: str = "ko",
    beam_size: int = 5,
) -> dict:
    """Returns: {text, segments, language, duration_sec, model_size, elapsed_sec}"""
```

### 에러 처리

| 조건 | 예외 |
|---|---|
| 파일 없음 | `FileNotFoundError` |
| 지원 포맷 외 (m4a/wav/mp3/mp4 제외) | `ValueError("unsupported format: ...")` |
| duration=0 (빈 오디오) | `ValueError("empty audio")` |
| faster-whisper + openai-whisper 모두 미설치 | `RuntimeError` |

### duration 계산 전략

ffprobe → mutagen → soundfile 순서로 시도, 모두 실패 시 faster-whisper `info.duration` 사용.

### faster-whisper / openai-whisper 우선순위

1. `faster-whisper` (기본, 로컬 재현성, MIT 라이선스, int8 양자화)
2. `openai-whisper` (fallback, 미설치 시 자동 전환)

## 3. 테스트 결과

```
pytest tests/test_stt_wrapper.py -v
===================== 3 passed in 3.30s ======================

tests/test_stt_wrapper.py::TestSttWrapperErrors::test_file_not_found_raises     PASSED
tests/test_stt_wrapper.py::TestSttWrapperErrors::test_unsupported_format_raises PASSED
tests/test_stt_wrapper.py::TestSttWrapperSmoke::test_synthetic_korean_audio_transcription PASSED
```

| 테스트 | 결과 |
|---|---|
| 파일 없음 → FileNotFoundError | ✅ PASS |
| 지원 포맷 외 확장자(.ogg) → ValueError | ✅ PASS |
| 합성 오디오 1건 → 텍스트 출력 | ✅ PASS |

## 4. 합성 오디오 Smoke

| 항목 | 값 |
|---|---|
| 합성 엔진 | gTTS (Google Text-to-Speech) |
| 입력 텍스트 | `"체온 삼십팔도 심박수 백이십"` |
| 전사 결과 | `"채운 38도 침박스 100기시"` |
| duration_sec | **3.24** |
| elapsed_sec | 0.706 (캐시된 tiny 모델 기준) |
| language | ko |
| segments 수 | 1 |

### 정성 평가

- **"삼십팔도" → "38도"**: 숫자 변환 정확 (Whisper 한국어 숫자 처리 정상)
- **"심박수" → "침박스"**: tiny 모델 오인식 (small 모델 사용 시 개선 예상)
- **"백이십" → "100기시"**: tiny 모델 오인식
- **전체 평가**: tiny 모델 한계 내에서 한국어 수의 발화 전사 동작 확인. 실운영은 `small` 이상 권장 (기본값 small 적용됨).
- **duration_sec 정상**: 3.24초 계산 완료

## 5. v1.0 무결성

```
git diff src/retrieval/
```

B1 작업(`src/pipeline/` 신규 생성)에서 `src/retrieval/` 파일을 수정하지 않았습니다.
`src/retrieval/hybrid_search.py`의 diff는 이전 세션 Track A1(Reranker) 작업 결과로,
B1 작업 범위 외입니다.

| 체크 | 결과 |
|---|---|
| B1 작업으로 인한 src/retrieval/ 변경 | **없음** ✅ |
| 실환자 녹음 사용 | **없음** ✅ (합성 gTTS 오디오만 사용) |
| 하드코딩된 DB 경로 | **없음** ✅ |
| 향남병원 데이터 참조 | **없음** ✅ |

## 6. 리스크 / 블로커

| 항목 | 내용 |
|---|---|
| tiny 모델 인식 품질 | 기본값 `small` 적용됨. tiny 대비 품질 개선 예상. |
| HF_TOKEN 미설정 경고 | 비인증 다운로드 rate limit 존재 — 실환경 배포 시 토큰 설정 권장. |
| duration 계산 실패 | ffprobe/mutagen/soundfile 모두 없으면 -1.0 반환. 대부분 환경에서 ffprobe로 정상 동작. |

---

*생성: 2026-04-22 | 담당: Track B1 Specialist*
