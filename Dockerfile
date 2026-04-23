# ============================================================
# vet-snomed-rag v2.0 — Dockerfile (멀티스테이지)
# 베이스: python:3.11-slim
#
# [데이터 전략]
#   - SNOMED DB (snomed_ct_vet.db) : 볼륨 마운트 필수 (라이선스 제한)
#   - ChromaDB 인덱스 (chroma_db/) : 볼륨 마운트 필수 (1.1 GB)
#   - 코드·의존성만 이미지에 포함
#
# [환경변수]
#   - GOOGLE_API_KEY   : Gemini SOAP 추출기 (필수)
#   - ANTHROPIC_API_KEY: Claude 백엔드 (선택)
#   → docker-compose.yml의 env_file:.env 으로 주입 (하드코딩 금지)
# ============================================================

# ────────────────────────────────────────────────────────────
# Stage 1: builder — pip 설치 + 휠 캐시
# ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# 빌드 도구 설치 (chromadb, faster-whisper 컴파일 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# pip 업그레이드 후 의존성 설치 (별도 레이어 — 캐시 활용)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ────────────────────────────────────────────────────────────
# Stage 2: runtime — 최소 실행 이미지
# ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# 런타임 시스템 패키지
# - ffmpeg: 오디오 포맷 변환 (stt_wrapper.py가 ffprobe 사용)
# - libgomp1: faster-whisper OpenMP 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# builder에서 설치된 Python 패키지 복사
COPY --from=builder /install /usr/local

# 프로젝트 소스 복사 (.dockerignore에서 제외된 파일은 복사 안 됨)
COPY . .

# 볼륨 마운트 포인트 생성
# - /app/data/snomed_ct_vet.db : SNOMED DB (호스트 마운트)
# - /app/data/chroma_db/       : ChromaDB 벡터 인덱스 (호스트 마운트)
RUN mkdir -p /app/data/chroma_db

# Streamlit 기본 포트
EXPOSE 8501

# 헬스체크: Streamlit healthz 엔드포인트
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Streamlit 실행 (서버모드: headless + CORS 허용)
ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
