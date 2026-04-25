# vet-snomed-rag

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/demo-streamlit-ff4b4b.svg)](https://streamlit.io/)
[![Release](https://img.shields.io/github/v/release/ricocopapa/vet-snomed-rag)](https://github.com/ricocopapa/vet-snomed-rag/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ricocopapa/vet-snomed-rag)](https://github.com/ricocopapa/vet-snomed-rag/commits/main)

수의학 SNOMED CT 온톨로지 기반 **Agentic RAG** 시스템

> 414,860개 SNOMED CT 개념 · 1,379,816개 온톨로지 관계 · 한국어 자연어 질의 지원  
> **v2.4**: Agentic RAG 11/11 단계 완전 구현 (G-1 Complexity + G-2 Source Router + G-3 Relevance Judge + G-4 Rewrite Loop)  
> **v2.2**: 5-input multimodal pipeline (text / audio / PDF text_layer / PDF OCR / image Vision) — 실 API E2E 도메인 hit **6/6**, SNOMED UNMAPPED **0/25**  
> **v2.1**: SNOMED Match 0.584 → **0.889** (+52.2%) · BGE Reranker + MRCM Direct Mapping · Docker 지원  
> **회귀 테스트**: pytest **135 passed + 1 skipped + 59 subtests** (v2.4) · Precision **0.891** / Recall **0.772** / F1 **0.827**

---

## 목차

- [What's New in v2.4](#whats-new-in-v24-2026-04-25)
- [What's New in v2.2](#whats-new-in-v22-2026-04-23)
- [What's New in v2.1](#whats-new-in-v21-2026-04-23)
- [프로젝트 소개](#프로젝트-소개)
- [아키텍처 v2.0](#아키텍처-v20)
- [v2.0 벤치마크](#v20-벤치마크)
- [아키텍처 v1.0 (RAG 검색)](#아키텍처)
- [포트폴리오 시각 자료 (Portfolio Visuals)](#포트폴리오-시각-자료-portfolio-visuals)
- [데이터 소스](#데이터-소스)
- [Quick Start with Docker](#quick-start-with-docker)
- [빠른 시작](#빠른-시작)
- [데모](#데모)
- [Supported Input Formats](#supported-input-formats)
- [벤치마크 — Gemini Reformulator 회귀 테스트](#벤치마크--gemini-reformulator-회귀-테스트)
- [핵심 기술 상세](#핵심-기술-상세)
- [기술 스택](#기술-스택)
- [프로젝트 구조](#프로젝트-구조)
- [로드맵](#로드맵)
- [v2.2 Roadmap](#v22-roadmap)
- [기여·보안·변경 이력](#기여보안변경-이력)
- [라이선스](#라이선스)

---

## What's New in v2.4 (2026-04-25)

Datasciencedojo "RAG vs Agentic RAG" 인포그래픽 기준 **11단계 Agentic RAG 루프**를 완전 구현했다. v2.2는 6/11 단계만 구현(Rewrite + Hybrid Retrieval + LLM)이었고, v2.4에서 **나머지 4종 Gap을 신규 에이전트로 해소**했다.

**주요 개선 (Wave 1~5 Goal-Backward 분해 적용):**

- **G-1 QueryComplexityAgent (#4)**: rule_based + Gemini hybrid 분해 판정. 복잡 쿼리 → 자동 서브쿼리 분해
- **G-2 SourceRouterAgent (#5·#6)**: Vector / SQL / Graph 동적 라우팅 (concept_id → SQL-heavy / 한국어 → Vector-heavy / 관계어 → Graph 활성)
- **G-3 RelevanceJudgeAgent (#10)**: PASS / PARTIAL / FAIL 3-way 판정 + missing_aspects 추출
- **G-4 RewriteLoopController (#11)**: max_iter=2 + Jaccard cycle detection + Gemini-기반 쿼리 재작성

**호환성 보장:**
- 기존 `SNOMEDRagPipeline.query()` API **변경 0** → v2.2 벤치마크 회귀 0
- 신규 `AgenticRAGPipeline.agentic_query()`는 별도 wrapper 진입점
- 기존 정량 수치(SNOMED 0.889 / F1 0.827 / Latency p95 35.4s)는 **그대로 유지**

**테스트:** 신규 29건 (G-1 6 + G-2 5 + G-3 7 + G-4 5 + Pipeline 6) → 전체 **135 passed + 59 subtests + 1 skipped**.

**상세:** [`RELEASE_NOTES_v2.4.md`](./RELEASE_NOTES_v2.4.md) · [`docs/20260424_v2_4_agentic_rag_design_v1.md`](./docs/20260424_v2_4_agentic_rag_design_v1.md) · [`benchmark/v2_4_agentic_comparison.md`](./benchmark/v2_4_agentic_comparison.md)

---

## What's New in v2.2 (2026-04-23)

v2.1 의 텍스트·오디오 2-input 파이프라인 위에 **PDF(텍스트 레이어·스캔 OCR) + 이미지(Gemini Vision)** 3 input 을 추가하여 **5-input multimodal pipeline** 을 완성했다.

**주요 개선 (Issue [#6](https://github.com/ricocopapa/vet-snomed-rag/issues/6) 전체 해결):**

- **Stage 1 — PDF text_layer**: `src/pipeline/pdf_reader.py` 에 pdfplumber 기반 추출. p95 latency 49 ms (수락 기준 5 s 대비 100배 여유).
- **Stage 2 — PDF OCR fallback**: 동일 모듈에 pdf2image + pytesseract(kor+eng) 자동 fallback. 스캔 PDF 2 건에서 임상 키워드 recall 92.9~100%, OCR latency 2.0~2.3 s/page.
- **Stage 3 — Image Vision**: `src/pipeline/vision_reader.py` 신규. Gemini 2.5 Flash Vision 으로 진료 이미지 → SOAP 텍스트. E2E 도메인 hit 2/2, 필드 추출 4~6 개.
- **5-mode 통합 벤치마크** (`benchmark/v2.2_multimodal_e2e_report.md`): text_layer / OCR / Vision 6 cases 전부 도메인 탐지 성공, SNOMED UNMAPPED **0/25**.
- **테스트**: 17 tests + 59 subtests PASS (pdf_reader 10 + vision_reader 7).
- **Streamlit UI**: Clinical Encoding 탭에 PDF / Image 2 가지 업로드 모드 추가.

**샘플 데이터**: 향남메디동물병원 실제 진료 PDF 101 건 중 도메인 다양성 3 건을 PyMuPDF redact 로 PHI 완전 익명화 후 테스트 fixture 로 커밋. 재생성 가능한 `scripts/anonymize_hyangnam_pdf.py` 포함.

---

## What's New in v2.1 (2026-04-23)

v2.0 End-to-End 파이프라인 위에, SNOMED 매칭 품질을 4단계 전략으로 대폭 개선하고 Docker 원클릭 배포를 추가했다.

**주요 개선:**

- **SNOMED Match 0.584 → 0.889** (+52.2%, 5/9 → 8/9 gold): MRCM 패턴 확장 + BGE Reranker + MRCM 직접 매핑
- BGE Reranker 활성화 (`enable_rerank=True`) + semantic_tag 우선순위
- MRCM 직접 매핑 확대 (OPH_CORNEA_CLARITY, OR_PATELLAR_LUXATION, GI_VOMIT_FREQ)
- Docker 지원: `Dockerfile` + `docker-compose.yml` — `docker-compose up` 원클릭 배포
- Gemini Reformulator: 2.5 Flash → 3.1 Flash Lite Preview (RPD 500, 비용 −40%)
- GOLD_AUDIT.md §7 — S03 gold 불일치 투명 공개 (gold 미수정, 벤치마크 정직성 유지)
- F1 0.827 (MedCAT 0.81–0.94 밴드 진입, FDA Class II SaMD F1 ≥0.80 충족)

v2.0의 주요 추가 기능(End-to-End 파이프라인 · Whisper STT · SOAP 추출 · Clinical Encoding 탭 · pytest 85/86 PASS)은 아래 [아키텍처 v2.0](#아키텍처-v20) 섹션을 참조.

---

## 아키텍처 v2.0

```
[음성 파일 or 텍스트]
        |
  (1) Whisper STT (faster-whisper, 한국어)        ← 음성 입력 시
        |
  (2) SOAP 추출 (Gemini 3.1 Flash Lite Preview)
        도메인 탐지 → 필드 추출 → 검증
        |
  (3) SNOMED 자동 태깅 (RAG + MRCM 25도메인)
        하이브리드 검색 → 후조합 SCG → MRCM 검증
        |
[JSONL 출력: SOAP 필드 + SNOMED 코드 태깅 레코드]
```

v1.0 RAG 파이프라인(한국어 검색 → SNOMED 코드 조회)은 유지되며, v2.0은 그 위에 임상 발화 처리 레이어를 추가한다.

---

## v2.0 벤치마크

### End-to-End 품질 메트릭 (5건 합성 시나리오)

| 메트릭 | 목표 | 텍스트 모드 | 오디오 모드 | 판정 |
|---|---|---|---|---|
| 필드 Precision | >=0.800 | **0.938** | **0.826** | 양쪽 PASS |
| 필드 Recall | >=0.700 | **0.737** | **0.774** | 양쪽 PASS |
| SNOMED 일치율 (synonym) | >=0.700 | 0.584 | 0.250 | 미달 |
| Latency p95 | <=60,000ms | **33,368ms** | 60,461ms | 텍스트 PASS / 오디오 461ms 초과 |

### v1.0 → v2.0 개선폭 (텍스트 모드 기준)

| 메트릭 | v2.0 초기 (Day 1) | v2.0 Final | 개선 |
|---|---|---|---|
| Precision | 0.43 | **0.938** | +118% |
| Recall | 0.52 | **0.737** | +42% |
| SNOMED 일치율 | 0.107 | **0.584** | +446% |
| Latency p95 | 127,000ms | **33,368ms** | −74% |

> SNOMED 일치율 0.107 → 0.584 개선은 두 가지 근본 원인 해소의 결과다: (1) gold-label field_code 구조 결함 수정 (임상 메모 12건 → 표준 field_code 교체/제거), (2) metrics.py synonym 모드 DB 테이블명 버그(`relationships` → `relationship`) 수정.

### 3모델 비교 (SOAP 추출 백엔드)

| 모델 | Latency | 상태 | 선택 이유 |
|---|---|---|---|
| Gemini 2.5 Flash | — | GA, 할당량 초과 (23/20 RPM 차단) | 미선택 |
| Gemini 2.5 Flash Lite | 3~5s | GA, 10× 빠름 | 대안 (GA 환경 권장) |
| **Gemini 3.1 Flash Lite Preview** | 18~47s | Preview, **RPD 500** | **채택** |

> 채택 근거: 3.1 Flash Lite의 RPD 500(25× 높은 할당량)이 배치 평가에서 안정적인 실행을 보장한다. 일 100건 이하 프로덕션 환경에서 할당량 제약 없이 속도를 우선한다면 2.5 Flash Lite GA를 권장한다.

### SNOMED 미달 원인 및 v2.1 로드맵

SNOMED 일치율 미달(텍스트 0.584, 오디오 0.250)의 잔존 원인은 RAG 본질적 한계 4건이다:

| 필드 | 문제 | 유형 |
|---|---|---|
| OPH_IOP_OD | gold=observable entity / pred=finding. IS-A 거리 없음 | semantic_tag 불일치 |
| OPH_CORNEA | Post-surgical haze 오매핑. LCA dist=6 | RAG 랭킹 |
| GP_RECTAL_TEMP | gold=observable entity / pred=procedure. LCA dist=14 | 완전 다른 계층 |
| OR_LAMENESS_FL_L | SOAP 파이프라인 필드 미추출 → UNMAPPED | 추출 실패 |

v2.1 계획: RAG 랭킹 개선 (BM25 튜닝, semantic_tag 우선순위), MRCM base_concept 직접지정 확대, 실 수의사 녹음 검증.

### Usage (v2.0)

**텍스트 모드**

```bash
python scripts/evaluate_e2e.py \
  --input-mode text \
  --input-dir data/synthetic_scenarios/ \
  --snomed-mode synonym
```

**오디오 모드**

```bash
python scripts/evaluate_e2e.py \
  --input-mode audio \
  --input-dir data/synthetic_scenarios/ \
  --snomed-mode synonym
```

**Streamlit UI — Clinical Encoding 탭**

```bash
streamlit run app.py
# "Clinical Encoding" 탭: 음성/텍스트 업로드 → JSONL 다운로드
```

---

## 프로젝트 소개

수의사가 한국어로 질문하면, SNOMED CT(Systematized Nomenclature of Medicine — Clinical Terms) 수의학 확장 데이터베이스에서 정확한 진단 코드, 시술 코드, 해부학적 관계를 검색하고 구조화된 답변을 생성하는 RAG 시스템이다.

**해결하는 문제:** SNOMED CT는 영어 기반 국제 의학 용어 체계로, 한국어 사용자가 직접 검색하기 어렵다. 본 시스템은 한국어→영어 번역 레이어와 하이브리드 검색을 결합하여 이 장벽을 제거한다.

---

## 아키텍처

```mermaid
flowchart TD
    User[사용자 질문<br/>한국어]
    User --> Trans{Step 0<br/>번역 레이어}
    Trans -->|수의학 사전 치환<br/>160+ 용어| Dict[한국어→영어 1차 변환]
    Trans -->|잔여 문법·조사| OllamaTrans[Ollama LLM 번역]
    Dict --> EN[영어 검색 쿼리]
    OllamaTrans --> EN

    EN --> Gemini{Gemini Reformulator<br/>선택적}
    Gemini -->|재정식화 + post-coord hints| Refined[Refined query]
    EN --> Refined

    Refined --> Hybrid[Step 1: Hybrid Search]
    Hybrid --> Vector[Track A<br/>Vector Search<br/>ChromaDB HNSW]
    Hybrid --> SQL[Track B<br/>SQL Retrieval<br/>SQLite]
    Vector --> RRF[RRF Merge<br/>α=0.6 · β=0.4]
    SQL --> RRF

    RRF --> Ctx[Step 2: Context Assembly<br/>Top-7 concepts +<br/>SNOMED relations +<br/>Post-coord patterns]

    Ctx --> LLM{Step 3<br/>LLM Generation}
    LLM --> Claude[Claude Sonnet]
    LLM --> OllamaGen[Ollama gemma2:9b]
    LLM --> NoneBackend[None<br/>검색만]

    Claude --> Out[구조화된 한국어 응답<br/>concept_id · FSN · 관계 인용]
    OllamaGen --> Out
    NoneBackend --> Out

    style User fill:#e1f5ff,stroke:#0366d6,color:#000
    style Out fill:#d4edda,stroke:#28a745,color:#000
    style Gemini fill:#fff3cd,stroke:#856404,color:#000
    style RRF fill:#f8d7da,stroke:#721c24,color:#000
```

<details>
<summary>Text-only 아키텍처 (접혀있음)</summary>

```
사용자 질문 (한국어)
    ↓
Step 0: 번역 레이어
  ① 수의학 용어 사전 치환 (160+ 용어)
  ② Ollama LLM 번역 (잔여 문법 처리)
    ↓ 영어 검색 쿼리
(선택) Gemini Reformulator → post-coord hints
    ↓
Step 1: Hybrid Search Engine
  Track A: Vector Search (ChromaDB, HNSW)
  Track B: SQL Retrieval (SQLite)
  → RRF Merge (α=0.6, β=0.4)
    ↓
Step 2: Context Assembly
  - 검색 결과 Top-7 concepts
  - SNOMED 관계 (is-a, finding_site, associated_morphology)
  - Post-coordination 패턴 (SCG)
    ↓
Step 3: LLM Generation
  Claude API / Ollama / None
    ↓
구조화된 한국어 응답 (concept_id, FSN, 관계 인용)
```

</details>

상세 아키텍처: [docs/architecture.md](docs/architecture.md)

---

## 포트폴리오 시각 자료 (Portfolio Visuals)

프로젝트의 핵심 설계 결정과 성과를 한 장씩 요약한 고해상도(180 DPI) 인포그래픽 8종. 한글·영문 병행, 모든 수치는 `regression_metrics.json` · DB 실측 쿼리로 검증됨. 생성 스크립트: [`scripts/gen_portfolio_visuals.py`](scripts/gen_portfolio_visuals.py) (재현 가능).

### A. Core (핵심 3종)

| # | 제목 | 핵심 내용 |
|---|---|---|
| A1 | [System Architecture](graphify_out/portfolio/A1_system_architecture.png) | 3-Track Hybrid Retrieval + Dual Backend + Verification Layer 통합 |
| A2 | [3-Stage Verification Pipeline](graphify_out/portfolio/A2_verification_pipeline.png) | Agent B→A→C 3단 독립 검증 + 설계-구현 역방향 동기화 루프 |
| A3 | [SOAP Coverage Dashboard](graphify_out/portfolio/A3_soap_coverage.png) | S/O/A/P 4축 SNOMED CT VET 매핑 커버리지 + 35,910/877/8,651+ 통계 |

![System Architecture](graphify_out/portfolio/A1_system_architecture.png)

### B. Deep Dive (심화 3종)

| # | 제목 | 핵심 내용 |
|---|---|---|
| B1 | [Enterprise Integration Layer](graphify_out/portfolio/B1_enterprise_integration.png) | VetSTT → Whisper → 도메인 탐지 → SNOMED → EMR 5단계 이기종 연계 |
| B2 | [Dual Backend Strategy Pattern](graphify_out/portfolio/B2_dual_backend_strategy.png) | Gemini(Primary) / Claude(Optional) Strategy 구조 + L2 Cache 분리 |
| B3 | [AI OS 3-Tier Model Routing](graphify_out/portfolio/B3_ai_os_routing.png) | Complexity Gate → Opus/Sonnet/Haiku 차등 배정 + Spec 비교 |

### C. Context (맥락 2종)

| # | 제목 | 핵심 내용 |
|---|---|---|
| C1 | [Data Scale Infographic](graphify_out/portfolio/C1_data_scale.png) | 414,848 · 1,379,816 · 877 · 8,651+ 숫자 요약 |
| C2 | [Project Timeline](graphify_out/portfolio/C2_project_timeline.png) | 2026-03 AI OS 착수 → 04-20 v1.0 Public GitHub 마일스톤 |

---

## 데이터 소스

| 데이터 | 규모 | 설명 |
|--------|------|------|
| SNOMED CT INT | 378,938 concepts | 국제 표준 (RF2 2026-02-01) |
| SNOMED CT VET Extension | 35,910 concepts | 수의학 확장 (RF2 2026-03-31) |
| Relationships | 1,379,816 | is-a, finding_site, associated_morphology 등 |
| Descriptions | 1,480,357 | FSN, preferred term, synonyms |
| Vector Index | 366,570 | ChromaDB 임상 핵심 개념 벡터 |
| Post-coordination | 877 expressions | A-axis 346 + P-axis 495 + O-axis 36 |
| 번역 사전 | 160+ terms | 한국어→영어 수의학 용어 매핑 |

---

## Quick Start with Docker

Docker를 사용하면 Python 환경 세팅 없이 **1줄로** 앱을 실행할 수 있다.

### 사전 요구사항

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 설치
- SNOMED CT 데이터 (라이선스 필요 — 아래 참조)
- API 키 (Gemini SOAP 추출기 필수, Claude 선택)

### 1단계: 환경변수 설정

```bash
cp .env.example .env
# .env 편집: GOOGLE_API_KEY, ANTHROPIC_API_KEY 입력
```

### 2단계: 데이터 준비

SNOMED CT 데이터는 라이선스 제한으로 이미지에 미포함. 로컬 빌드 후 아래 경로에 배치해야 한다.

```bash
# SNOMED DB (SQLite, ~1.1 GB) → ./data/snomed_ct_vet.db
# ChromaDB 벡터 인덱스 (1.1 GB) → ./data/chroma_db/

# 처음 구축하는 경우: 로컬 Python 환경으로 먼저 인덱싱 실행
bash setup_env.sh
source .venv/bin/activate
python src/indexing/vectorize_snomed.py
```

### 3단계: 실행 (1줄)

```bash
docker-compose up
# → http://localhost:8501
```

### 포트 및 환경변수 안내

| 항목 | 값 | 설명 |
|------|-----|------|
| 포트 | `8501` | Streamlit UI (호스트:8501 → 컨테이너:8501) |
| `GOOGLE_API_KEY` | `.env` 필수 | Gemini SOAP 추출기 (Clinical Encoding 탭) |
| `ANTHROPIC_API_KEY` | `.env` 선택 | Claude LLM 백엔드 (Search 탭에서 선택 가능) |

### 이미지 정보

```bash
# 이미지 크기: ~3.5 GB (PyTorch + chromadb + sentence-transformers 포함)
# 기본 LLM 백엔드: ollama (사이드바에서 전환 가능)
# 오디오 처리: ffmpeg 내장 (m4a/wav/mp3/mp4 지원)
```

### 개별 명령어

```bash
# 빌드만 (캐시 활용)
docker-compose build

# 백그라운드 실행
docker-compose up -d

# 컨테이너 내에서 인덱싱 실행
docker-compose run --rm app python src/indexing/vectorize_snomed.py

# 중지
docker-compose down
```

---

## 빠른 시작

### 사전 요구사항

- Python 3.11+
- [Ollama](https://ollama.com) (로컬 LLM 사용 시)

### 설치

```bash
cd vet-snomed-rag

# 환경 세팅 (가상환경 + 의존성 + 데이터 심볼릭 링크)
bash setup_env.sh

# 가상환경 활성화
source .venv/bin/activate

# 벡터 인덱싱 (최초 1회, ~10분 소요)
python src/indexing/vectorize_snomed.py
```

### 실행

```bash
# 하이브리드 검색 테스트 (LLM 없이, 검색 결과만)
python src/retrieval/hybrid_search.py --interactive

# RAG 파이프라인 — Ollama 로컬 LLM (무료)
ollama pull gemma2:9b
python src/retrieval/rag_pipeline.py --interactive --llm ollama --ollama-model gemma2:9b

# RAG 파이프라인 — Claude API (유료)
cp .env.example .env  # 편집해서 ANTHROPIC_API_KEY 채움
python src/retrieval/rag_pipeline.py --interactive --llm claude

# RAG 파이프라인 — LLM 없이 (검색 결과만 구조화)
python src/retrieval/rag_pipeline.py --interactive

# Streamlit 데모 UI (브라우저 기반 대화형 검색)
streamlit run app.py
# → http://localhost:8501
```

### CLI 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--llm` | none | LLM 백엔드 (claude / ollama / none) |
| `--ollama-model` | llama3.2 | Ollama 모델명 |
| `--claude-model` | claude-sonnet-4-20250514 | Claude 모델명 |
| `--top-k` | 10 | 검색 결과 수 |
| `--interactive` | - | 대화형 모드 |
| `--query` | - | 단일 질의 |

---

## 데모

### 한국어 질의 → SNOMED 코드 검색

```
질문> 고양이 범백혈구감소증의 SNOMED 코드는?
  [번역] 고양이 범백혈구감소증의 SNOMED 코드는?
       → What is the SNOMED code for feline panleukopenia?

══════════════════════════════════════════════════════
  Q: 고양이 범백혈구감소증의 SNOMED 코드는?
  → Search Query: What is the SNOMED code for feline panleukopenia?
══════════════════════════════════════════════════════

고양이 범백혈구감소증의 SNOMED 코드는 339181000009108입니다.
이 코드는 Feline panleukopenia (disorder)를 나타내며,
수의학확장 (VET) 데이터베이스에서 나왔습니다.

──────────────────────────────────────────────────────
  검색된 개념: 10건
  LLM: ollama (gemma2:9b)
──────────────────────────────────────────────────────
```

### 해부학적 관계 검색

```
질문> 말의 제엽염 진단 코드와 관련 해부학적 부위는?
  [번역] → Laminitis diagnostic codes and related anatomical regions in horses?

말의 제엽염 (Equine laminitis)은 concept_id 341801000009106,
FSN "Equine laminitis (disorder)"로 표기됩니다.
해부학적 부위는 Laminae of hoof이며 'Finding site' 관계를 통해
연결되어 있습니다.
```

### Streamlit 데모 UI

| 쿼리 | 스크린샷 |
|------|----------|
| `feline panleukopenia SNOMED code` | [01](docs/screenshots/01_query_feline_panleukopenia.png) |
| `고양이 당뇨` (한→영 + 종 특이 post-coord) | [02](docs/screenshots/02_query_goyangi_dangnyo.png) |
| `개 췌장염` | [03](docs/screenshots/03_query_gae_chejangyeom.png) |
| `pancreatitis in dog` | [04](docs/screenshots/04_query_pancreatitis_dog.png) |
| `말의 제엽염` | [05](docs/screenshots/05_query_malui_jeyeopyeom.png) |
| `Canine parvovirus` | [06](docs/screenshots/06_query_canine_parvovirus.png) |

![Streamlit demo — feline panleukopenia](docs/screenshots/01_query_feline_panleukopenia.png)

---

## Supported Input Formats

Streamlit UI의 두 탭(SNOMED Search · Clinical Encoding)에서 지원하는 입력 포맷.

| Format | v2.1 | v2.2 | Notes |
|---|:---:|:---:|---|
| Text (직접 입력) | ✅ | ✅ | SNOMED Search 탭 + Clinical Encoding 탭 공통 |
| Audio (m4a / wav / mp3 / mp4) | ✅ | ✅ | faster-whisper STT → SOAP → SNOMED 자동 태깅 |
| PDF (text layer) | ❌ | ✅ | pdfplumber 텍스트 추출 후 기존 파이프라인 통과 (Stage 1) |
| PDF (scanned / 이미지 전용) | ❌ | ✅ | pdf2image + tesseract(kor+eng) OCR fallback (Stage 2) |
| Image (JPG / PNG / WEBP) | ❌ | ✅ | Gemini 2.5 Flash Vision 기반 이미지 → 진료 텍스트 (Stage 3) |

→ **v2.2 달성: 5-input multimodal pipeline.** 실 Gemini API E2E 벤치마크
(`benchmark/v2.2_multimodal_e2e_report.md`) 에서 **도메인 탐지 6/6 hit, SNOMED
UNMAPPED 0/25**.

시스템 의존성 (Stage 2 OCR 사용 시):

```bash
brew install poppler tesseract tesseract-lang   # macOS
# Ubuntu: apt-get install poppler-utils tesseract-ocr tesseract-ocr-kor
```

---

## 벤치마크 — Gemini Reformulator 회귀 테스트

11건 쿼리(영문 기본·한국어·종 특이 질환 혼합)에 대해 baseline vs Gemini Reformulator 비교 결과:

| 지표 | Before (none) | After (Gemini) | 변화 |
|------|---------------|----------------|------|
| PASS 수 (10건 평가 대상) | 6/10 (60%) | **10/10 (100%)** | +4건 |
| Top-10 밖 실패(NF) 수 | 5건 | 1건 | −4건 |
| 평균 latency | 1,247 ms | **1,064 ms** | −184 ms (−14.7%) |

### PASS 율
![PASS rate](graphify_out/charts/pass_rate.png)

### 쿼리별 정답 순위 (lower is better)
![Rank per query](graphify_out/charts/rank_per_query.png)

### 평균 레이턴시
![Latency comparison](graphify_out/charts/latency.png)

회귀 테스트 원본 데이터: [`graphify_out/regression_metrics.json`](graphify_out/regression_metrics.json)
차트 생성 스크립트: [`scripts/generate_charts.py`](scripts/generate_charts.py)

---

## 핵심 기술 상세

### 한국어→영어 번역 레이어

DB와 임베딩 모델이 영어 전용이므로, 2단계 번역 파이프라인을 구현했다.

1. **사전 치환:** `vet_term_dictionary_ko_en.json`의 160+ 수의학 용어로 핵심 의학 용어를 정확히 영어로 변환
2. **LLM 번역:** 잔여 한국어(조사, 문법)를 Ollama LLM으로 번역

이 설계로 LLM 단독 번역 시 발생하는 수의학 전문 용어 오역(예: 제엽염→pharyngitis)을 원천 차단한다.

### Reciprocal Rank Fusion (RRF)

Vector Search(의미 기반)와 SQL Search(키워드 기반)를 단일 순위로 병합한다. 의미적 유사어와 정확한 용어 매칭을 동시에 포착할 수 있다.

```
RRF_score(d) = 0.6 × 1/(60 + rank_vector) + 0.4 × 1/(60 + rank_sql)
```

### SNOMED CT 관계 활용

검색된 개념의 온톨로지 관계를 컨텍스트에 포함하여 LLM이 더 풍부한 답변을 생성한다.

| 관계 유형 | 예시 |
|----------|------|
| Is a | Equine laminitis → Laminitis |
| Finding site | Equine laminitis → Laminae of hoof |
| Associated morphology | Equine laminitis → Separation, Inflammatory morphology |
| Causative agent | Feline panleukopenia → Feline panleukopenia virus |

---

## 기술 스택

| 계층 | 기술 | 역할 |
|------|------|------|
| Embedding | all-MiniLM-L6-v2 | 텍스트 → 384차원 벡터 |
| Vector DB | ChromaDB (HNSW) | 의미 기반 유사도 검색 |
| Relational DB | SQLite | 키워드 검색 + SNOMED 관계 |
| Re-ranking | Reciprocal Rank Fusion | 멀티 트랙 결과 병합 |
| Translation | 수의학 사전 + Ollama | 한국어→영어 번역 |
| LLM (Local) | Ollama (gemma2:9b) | 로컬 답변 생성 |
| LLM (Cloud) | Claude API (Sonnet) | 클라우드 답변 생성 |
| 의료 표준 | SNOMED CT RF2 + VET | 수의학 온톨로지 |
| Language | Python 3.13 | 전체 구현 |

---

## 프로젝트 구조

```
vet-snomed-rag/
├── README.md
├── LICENSE                             # MIT License (프로젝트 코드)
├── .env.example                        # 환경변수 템플릿
├── requirements.txt
├── setup_env.sh                        # 환경 자동 세팅
├── app.py                              # Streamlit 데모 UI 엔트리포인트
├── src/
│   ├── indexing/
│   │   └── vectorize_snomed.py         # ChromaDB 벡터 인덱싱 (최초 1회)
│   └── retrieval/
│       ├── hybrid_search.py            # 하이브리드 검색 (Vector + SQL + RRF)
│       ├── rag_pipeline.py             # RAG 파이프라인 (번역 + 검색 + LLM)
│       └── graph_rag.py                # GraphRAG traversal (Week 2)
├── lib/
│   └── reformulator/                   # Gemini Reformulator (rate limiter + cache)
├── scripts/
│   ├── generate_charts.py              # 회귀 테스트 Before/After 차트 생성
│   ├── graphify_lite.py                # 경량 지식 그래프 빌더
│   └── run_regression.py               # 11-쿼리 회귀 테스트 러너
├── data/                               # .gitignore (원본·파생 SNOMED 재배포 금지)
│   ├── snomed_ct_vet.db                # SNOMED CT 통합 DB (414K concepts)
│   ├── chroma_db/                      # ChromaDB 벡터 인덱스 (366K vectors)
│   └── *.json                          # 용어 사전·매핑 규칙
├── graphify_out/
│   ├── regression_metrics.json         # 11-쿼리 회귀 테스트 결과
│   ├── charts/                         # Before/After 차트 (PNG × 3)
│   └── *.md, graph.html, nodes.csv     # 지식 그래프 산출물
├── docs/
│   ├── architecture.md                 # 상세 아키텍처 문서
│   └── screenshots/                    # Streamlit 데모 캡처 (PNG × 6)
├── src/pipeline/                       # v2.0 신규
│   ├── stt_wrapper.py                  # Whisper STT 래퍼 (faster-whisper)
│   ├── soap_extractor.py               # SOAP 추출 (Gemini/Claude multi-backend)
│   ├── snomed_tagger.py                # SNOMED 자동 태깅 + MRCM 검증
│   └── e2e.py                          # ClinicalEncoder E2E 오케스트레이터
├── scripts/eval/                       # v2.0 신규
│   └── metrics.py                      # strict / superset / synonym 평가 모드
├── scripts/evaluate_e2e.py             # E2E 평가 스크립트
├── data/synthetic_scenarios/           # 합성 임상 시나리오 5건 + gold-label
│   └── GOLD_AUDIT.md                   # 역공학 감사 기록 (30건 변경, 0건 역공학)
├── benchmark/                          # v2.0 벤치마크 리포트
│   ├── v2_e2e_report_text.md           # E2E 텍스트 모드 결과
│   ├── v2_e2e_report_audio.md          # E2E 오디오 모드 결과
│   ├── v2_headline_metrics.md          # 핵심 지표 요약
│   └── charts/                         # v2.0 차트 (PNG × 6)
└── tests/                              # 86건 pytest (85 passed, 1 skipped)
```

---

## 로드맵

- [x] v1.0 (2026-04-20): 하이브리드 RAG 파이프라인
  - [x] ChromaDB 벡터 인덱싱 (366,570 concepts)
  - [x] 하이브리드 검색 엔진 (Vector + SQL + RRF)
  - [x] 한국어→영어 번역 레이어 (사전 + LLM)
  - [x] Claude API / Ollama 이중 LLM 백엔드
  - [x] Streamlit 데모 UI
  - [x] 11-쿼리 회귀 테스트 벤치마크 (6/10 → 10/10)
  - [x] Gemini 2.5 Flash 기반 쿼리 재정식화 (후조합 힌트 포함)
  - [x] 경량 지식 그래프 (graphify_lite) + 회귀 테스트 자동화
- [x] v2.0 (2026-04-22): End-to-End 임상 인코딩 파이프라인
  - [x] Whisper STT 래퍼 (faster-whisper, 한국어, 3포맷)
  - [x] SOAP 추출기 (Gemini 3.1 Flash Lite Preview / Claude Haiku+Sonnet)
  - [x] SNOMED 자동 태깅 + MRCM 25도메인 검증 + 후조합 SCG
  - [x] ClinicalEncoder E2E 오케스트레이터 (JSONL 출력)
  - [x] Streamlit "Clinical Encoding" 탭
  - [x] E2E 평가 프레임워크 (strict / superset / synonym 모드)
  - [x] 5건 합성 시나리오 + gold-label (역공학 감사 PASS)
  - [x] 3모델 비교 (2.5 Flash / 2.5 Flash Lite / 3.1 Flash Lite)
  - [x] pytest 85/86 PASS (v1.0 회귀 포함)
- [x] v2.1 (2026-04-23): SNOMED 품질 개선 + Docker 배포
  - [x] SNOMED Match 0.584 → 0.889 (+52.2%, 4단계 전략)
  - [x] BGE Reranker 활성화 (`enable_rerank=True`) + semantic_tag 우선순위
  - [x] MRCM 직접 매핑 확대 (OPH_CORNEA, OR_PATELLAR_LUXATION, GI_VOMIT_FREQ)
  - [x] Docker 원클릭 배포 (`docker-compose up`)
  - [x] Gemini Reformulator 3.1 Flash Lite Preview 전환 (RPD 500)
  - [x] GOLD_AUDIT.md §7 — S03 gold 불일치 투명 공개

---

## v2.2 Roadmap

v2.2 이슈는 [GitHub Issues](https://github.com/ricocopapa/vet-snomed-rag/issues)에서 트래킹된다.

- [#1](https://github.com/ricocopapa/vet-snomed-rag/issues/1) — Replace gTTS synthetic audio with real veterinarian recordings
- [#2](https://github.com/ricocopapa/vet-snomed-rag/issues/2) — Improve SNOMED match rate 0.889 → 0.95 via ChromaDB vector index retraining + LCA-based scoring
- [#3](https://github.com/ricocopapa/vet-snomed-rag/issues/3) — Optimize Audio mode latency p95 < 60s (Gemini 2.5 Flash Lite GA path)
- [#4](https://github.com/ricocopapa/vet-snomed-rag/issues/4) — Claude fallback backend for multi-provider resilience (Gemini 503 / rate limit)
- [#5](https://github.com/ricocopapa/vet-snomed-rag/issues/5) — Redesign gold dataset under multi-reviewer Cohen's κ agreement (50–100 real recordings)
- [#6](https://github.com/ricocopapa/vet-snomed-rag/issues/6) — PDF input support: Stage 1 text layer (pdfplumber) + Stage 2 OCR fallback

> **PDF 지원 우선 배경 ([#6](https://github.com/ricocopapa/vet-snomed-rag/issues/6)):** 기업 임상 기록의 상당수가 PDF 포맷이다. v2.1 기준 PDF는 미지원(❌)이며, v2.2에서 text layer → OCR 2단계로 지원 예정이다. 현재 지원 포맷 전체 매트릭스는 [Supported Input Formats](#supported-input-formats) 참조.

---

## 기여·보안·변경 이력

| 문서 | 내용 |
|------|------|
| [CONTRIBUTING.md](./CONTRIBUTING.md) | 이슈·PR·코드 스타일 가이드 |
| [SECURITY.md](./SECURITY.md) | 보안 취약점 리포트 절차 |
| [CHANGELOG.md](./CHANGELOG.md) | 버전별 변경 이력 |
| [Releases](https://github.com/ricocopapa/vet-snomed-rag/releases) | 태그별 릴리즈 노트 |

---

## v2.3 Roadmap — AI OS Governance Layer (Experimental)

> v2.2 5-input multimodal pipeline 안정화 후, **AI OS 거버넌스 PoC 3종**을 본 레포에 통합하여
> LG CNS JD 우대 3.2 ("Evaluation, Observability, Guardrails/PII") 정면 매칭 자산으로 발전시킨다.

위치: [`experimental/ai_os_governance/`](./experimental/ai_os_governance/) (Issue [#8](https://github.com/ricocopapa/vet-snomed-rag/issues/8) · [#9](https://github.com/ricocopapa/vet-snomed-rag/issues/9) · [#10](https://github.com/ricocopapa/vet-snomed-rag/issues/10) · [#11](https://github.com/ricocopapa/vet-snomed-rag/issues/11))

### v2.3.0 — Google Cloud AI 에이전트 표준 6범주 매핑 (외부 검증)

본 PoC 3종 + 기존 AI OS Sub Agents의 Google Cloud 표준 분류 매핑:

| 범주 | 본 시스템 자산 | 상태 |
|---|---|---|
| 고객 에이전트 | 미구현 (B2B 포지션) | ❌ |
| 직원 에이전트 | orchestrator + reviewer + evaluator | ✅ |
| 크리에이티브 | emr-designer | ✅ |
| 코드 | workflow-architect + GSD 30+ | ✅ |
| 데이터 | data-analyzer + invest-analyzer | ✅ |
| 보안 | security-audit + IAM-Lite + PII 마스킹 (Issue [#9](https://github.com/ricocopapa/vet-snomed-rag/issues/9)) | ✅ |

**5/6 (83.3%) 자체 구현.** 추가로 **XAI 레이어 4종**(Audit Trail JSONL · Provenance Tracking via Source-First Rule · IAM Registry · Adversarial Verification) 구현으로 "AI 블랙박스 한계" 정량 대응.

추론 전략 적용: **CoT** (Chain-of-Verification, Dhuliawala et al. Meta AI 2023) + **ReAct** (Sub Agent tool_use loop, Hong et al. ICLR 2024 MetaGPT 패턴) + **ToT** (vet-snomed-rag v2.1 4단계 개선 분기 탐색).

### v2.3.1 — Objective Drift Detection (Observability)

사용자 원본 의도와 에이전트 Task Definition의 임베딩 코사인 유사도로 **Drift Score**를 측정,
임계값 초과 시 HITL을 트리거하는 **Enterprise AI 핵심 리스크 정량 감지 시스템**.

- **현재 상태**: 캘리브레이션 9/10 (90% detection accuracy) — 한국어 특화 모델 적용 시 100% 목표
- **모델**: `paraphrase-multilingual-mpnet-base-v2` → `jhgan/ko-sroberta-multitask` 전환 예정
- **검증 데이터**: 정상 5 + 이상 5 시나리오 실측 로그 (`drift_log.jsonl`)

### v2.3.2 — IAM-Lite + PII Masking (Guardrails/PII)

Enterprise IAM 핵심 원리 3종 + PII 자동 마스킹 개인 환경 실증.

- **Permission Scope Registry**: 6 Sub Agents `allowed_tools`/`denied_tools` YAML 등록
- **2단계 승인 프로토콜**: 비가역 작업(DELETE, push, DB UPDATE) 실행자+승인자 두 서명
- **Audit Trail JSON Lines**: `~/.audit_log/YYYYMMDD.jsonl` 5필드 표준
- **PII 마스킹 4종**: 전화·이메일·주민·계좌번호 정규식 round-trip (pytest 5/5 PASS)

### v2.3.3 — A2A (Agent-to-Agent) Protocol Early Adopter

Google A2A Protocol(2025-04 공식)을 Claude 생태계 내에서 실증한 **드문 사례**.

- **JSON Schema** (Draft-07) + 검증 테스트 8/8 PASS
- **Mailbox 디렉토리**: inbox / outbox / archive / dead_letter
- **벤더 간 브릿지**: Claude reviewer ↔ `gemini-2.5-flash` 독립 감사 E2E PoC
  - 실측 결과: consensus_estimate **0.75** (이력서 v2.2 첫 5,000자 대상)
- **dead_letter**: retry_count > 3 자동 격리

자세한 내용은 [experimental/ai_os_governance/README.md](./experimental/ai_os_governance/README.md) 참조.

### v2.3.4 — Logic RAG PoC (Sionic AI 방법론) — Issue [#11](https://github.com/ricocopapa/vet-snomed-rag/issues/11)

사전 그래프 구축 비용 부담을 해소하기 위해 **질의 시점에 동적 지도를 만드는** Logic RAG PoC.
정적 SNOMED CT 그래프(v2.0~v2.2) + **동적 Query Decomposition + DAG 위상 정렬** hybrid 검증.

- **3단계 파이프라인**: Query Decomposition (LLM) → DAG Topological Sort (Kahn) → Recursive Solve + Synthesize
- **DAG 단위 테스트**: pytest **7/7 PASS** (cyclic 거부, unknown dep 거부, diamond 등)
- **E2E Gemini 호출**: 작성 시점 503 UNAVAILABLE 과부하로 미검증 (다음 세션 재시도)
- 출처: 평범한 사업가 채널 #74 (2026), Sionic AI 정세민·박진형

### v2.3.5 — Palantir 의료 온톨로지 사례 1:1 매핑

본 프로젝트의 도메인·방법론은 **Palantir의 미국 의료 보험 온톨로지 사례** (100억 미지급 회수 + 4조 영업이익) 와 정확히 일치하며, **1/1000 비용 (OSS 0원)** 으로 핵심 원리를 자체 실증한다.

| 차원 | Palantir 의료 사례 | 본 vet-snomed-rag |
|---|---|---|
| 도메인 | 미국 의료 보험 청구 | 수의 임상 인코딩 |
| 통합 단위 | 환자 ID | 환자/필드 ID + EMR 4축 |
| LLM 추출 | 거절 사유 → 소명서 생성 | STT → SOAP → SNOMED 태깅 → MRCM 검증 |
| 온톨로지 | 병원 시스템 전체 | SNOMED CT 414K + VET 35.9K + Post-Coord 877건 |
| 도입 비용 | **100억~1,000억** | **0원 (OSS)** |
| 매핑 방법 | 90% 현장 엔지니어 수작업 | 1,462건 직접 검수 + 향남병원 PDF 101건 익명화 |
| 결과 | 100억 회수 + 4조 영업이익 | F1 0.827 (FDA Class II) + Match 0.889 (8/9 gold) |

**그래프 4요소 ↔ SNOMED CT 1:1 매핑**:
- Entity = concept (414,848개)
- Relationship = is-a / finding_site / has_specimen 등 (1,379,816 관계)
- Property = concept_id, semantic_tag, MRCM, Post-Coordination 877건
- Community = 25 임상 도메인 × 4축 (S/A/P/O)

→ "내년 AI 핵심 화두 = GraphRAG + 온톨로지" (Sionic AI 채널, 2026) 두 축 모두 자체 자산 보유.

---

## 라이선스

본 프로젝트는 **2개의 서로 다른 라이선스 영역**으로 구성된다.

### 1) 프로젝트 코드·문서 (MIT License)

본 저장소의 소스코드·스크립트·문서·스크린샷·차트는 [MIT License](./LICENSE)로 배포한다.
자유롭게 사용·수정·재배포 가능하며, 저작권 및 라이선스 고지만 유지하면 된다.

### 2) SNOMED CT 데이터 (SNOMED International 라이선스)

SNOMED CT INT / VET Extension은 **SNOMED International**의 라이선스 하에 있으며,
본 저장소에는 **원본 RF2 파일 및 파생 산출물(벡터 인덱스, 개념별 MD 문서 등)을 포함하지 않는다**.

사용자는 다음 절차로 본인 환경에서 데이터를 구축해야 한다.

1. 소속 국가의 SNOMED International Affiliate Licence를 확인·취득
2. 공식 RF2 파일 다운로드 (SNOMED CT INT + VET Extension)
3. `bash setup_env.sh` → `python src/indexing/vectorize_snomed.py` 실행

SNOMED CT 사용 관련 상세: [SNOMED International](https://www.snomed.org/snomed-ct/get-snomed)
