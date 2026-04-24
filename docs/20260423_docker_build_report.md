# vet-snomed-rag v2.0 Docker 빌드 보고서
# 생성일: 2026-04-23

---

## 1. 생성 파일 목록

| 파일 | 경로 | 설명 |
|------|------|------|
| `Dockerfile` | `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag/Dockerfile` | 멀티스테이지 (builder + runtime) |
| `docker-compose.yml` | `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag/docker-compose.yml` | 1-line 실행 구성 |
| `.dockerignore` | `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag/.dockerignore` | 이미지 크기 최소화 규칙 |
| `README.md` | (기존 파일에 `## Quick Start with Docker` 섹션 추가) | 목차 + Docker 섹션 |

> `.env.example`은 프로젝트에 이미 존재하여 신규 생성 없음. 내용 확인: GOOGLE_API_KEY + ANTHROPIC_API_KEY 2개 키, 실값 없음.

---

## 2. Docker 빌드 테스트 결과

### 빌드 명령
```bash
cd /Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag
docker build -t vet-snomed-rag:v2.0-test .
```

### 결과
| 항목 | 값 |
|------|-----|
| 빌드 상태 | **SUCCESS** (exit code 0) |
| 이미지 이름 | `vet-snomed-rag:v2.0-test` |
| 이미지 크기 | **3.22 GB** (disk: 3.46 GB) |
| 빌드 소요 시간 | ~500초 (pip install 최대 의존성 포함) |
| Python 버전 | 3.11-slim |
| 아키텍처 | linux/arm64 (M2 Mac, ARM 네이티브 빌드) |

### 런타임 검증
```bash
docker run --rm --entrypoint python vet-snomed-rag:v2.0-test \
  -c "import streamlit; import chromadb; import anthropic; import sentence_transformers; import faster_whisper; print(...)"
```
결과:
```
OK: streamlit 1.56.0 / chromadb 1.5.8 / anthropic 0.96.0 / faster_whisper 1.2.1
```
**모든 핵심 패키지 임포트 성공.**

---

## 3. 설계 결정 및 근거

### 데이터 볼륨 전략 (빌드 포함 vs 마운트)
| 데이터 | 크기 | 결정 | 근거 |
|--------|------|------|------|
| `snomed_ct_vet.db` | ~1.1 GB (심볼릭 링크) | **볼륨 마운트** | SNOMED CT 라이선스 제한으로 이미지 포함 불가 |
| `chroma_db/` | 1.1 GB | **볼륨 마운트** | 이미지 크기 폭증 방지 + 재인덱싱 시 유연성 |
| 코드·의존성 | ~3.2 GB | **이미지 포함** | 재현 가능한 환경 보장 |

### 멀티스테이지 빌드 구성
- **Stage 1 (builder)**: `build-essential`, `gcc`, `g++` 포함 — chromadb, faster-whisper 컴파일 의존성
- **Stage 2 (runtime)**: `ffmpeg`, `libgomp1`만 포함 — 빌드 도구 제거로 이미지 최소화

### 환경변수 처리
- `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY` → `docker-compose.yml`의 `env_file: .env`로 주입
- Dockerfile, docker-compose.yml 어느 파일에도 실값 하드코딩 없음
- `.env`는 `.gitignore`에 이미 등록되어 있음 (커밋 보호)

### ffmpeg 런타임 포함 근거
- `stt_wrapper.py`가 `ffprobe`를 1순위 오디오 duration 측정 도구로 사용
- `faster-whisper`의 내부 오디오 디코딩에도 ffmpeg 필요
- `libgomp1`: `ctranslate2` (faster-whisper 엔진) OpenMP 병렬화 의존성

---

## 4. 실행 명령 (1줄)

```bash
# 사전: .env 파일 준비 + data/ 볼륨 배치
docker-compose up
# → http://localhost:8501
```

---

## 5. 이미지 크기 분석

| 구성 요소 | 기여도 (추정) |
|-----------|--------------|
| PyTorch (CPU + CUDA libs) | ~2.0 GB |
| chromadb + onnxruntime | ~0.4 GB |
| sentence-transformers + transformers | ~0.3 GB |
| faster-whisper + ctranslate2 | ~0.2 GB |
| streamlit + langchain + anthropic | ~0.2 GB |
| 기타 | ~0.1 GB |

> 이미지 크기 최적화 여지: `torch` CPU-only 빌드(`torch --extra-index-url https://download.pytorch.org/whl/cpu`)로 교체 시 약 1~1.5 GB 절감 가능. 단, faster-whisper의 GPU 추론이 비활성화되므로 STT 성능 트레이드오프 존재.

---

## 6. 성공 기준 체크리스트

- [x] Dockerfile 존재
- [x] docker-compose.yml 존재
- [x] .env.example 존재 (민감 정보 하드코딩 0건)
- [x] .dockerignore 존재
- [x] **실제 docker build 성공** (exit code 0)
- [x] **런타임 패키지 검증 PASS** (streamlit/chromadb/anthropic/faster_whisper 전부 임포트)
- [x] README.md Docker 섹션 존재 (`## Quick Start with Docker`)
- [x] 이미지 크기 기록: **3.22 GB**
- [x] Git 커밋 미수행 (사용자 승인 후 별도 진행)
