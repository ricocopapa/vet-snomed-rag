# vet-snomed-rag v2.2 Release Notes

**Release Date:** 2026-04-23
**Branch:** `v2.2-pdf-input` → `main`
**Tag:** `v2.2`
**Milestone:** [v2.2 Issue #6 — Add PDF input support](https://github.com/ricocopapa/vet-snomed-rag/milestone/1)

---

## Highlights

v2.1 텍스트·오디오 2-input 파이프라인을 **5-input multimodal pipeline** 으로 확장했다. 기업 임상 기록의 주요 포맷인 PDF (텍스트 레이어 + 스캔) 와 이미지 입력을 모두 동일한 SOAP → SNOMED 파이프라인으로 흘려보낸다.

| Format | v2.1 | v2.2 | 구현 위치 |
|---|:---:|:---:|---|
| Text | ✅ | ✅ | `app.py` |
| Audio (m4a/wav/mp3/mp4) | ✅ | ✅ | `src/pipeline/stt_wrapper.py` |
| PDF (text layer) | ❌ | ✅ | `src/pipeline/pdf_reader.py` (Stage 1) |
| PDF (scanned) | ❌ | ✅ | `src/pipeline/pdf_reader.py` OCR (Stage 2) |
| Image (jpg/png/jpeg/webp) | ❌ | ✅ | `src/pipeline/vision_reader.py` (Stage 3) |

**실 Gemini API E2E 벤치마크 (`benchmark/v2.2_multimodal_e2e_report.md`)**:

| Mode | cases | 도메인 hit | 평균 필드 | 평균 SNOMED 매핑 |
|---|---:|---:|---:|---:|
| text_layer | 2 | 2/2 | 2.5 | 2.5 |
| ocr        | 2 | 2/2 | 5.0 | 5.0 |
| vision     | 2 | 2/2 | 5.0 | 5.0 |
| **합계**   | **6** | **6/6** | **4.2** | **4.2** (UNMAPPED 0/25) |

---

## Stage 1 — PDF Text-Layer Ingestion

- 신규 모듈 `src/pipeline/pdf_reader.py` (~180 LOC).
- `read_pdf(path)` → `{text, pages, has_text_layer, source}`.
- `source` 가 `"text_layer"` / `"ocr"` / `"vision"` 3 가지로 구분되어 Stage 2/3 훅 마련.
- 의존성 추가: `pdfplumber>=0.10.0`.
- p95 latency **49 ms** (수락 기준 5,000 ms 대비 100 배 여유).
- 상세: [`benchmark/v2.2_pdf_stage1_report.md`](benchmark/v2.2_pdf_stage1_report.md)

## Stage 2 — Scanned PDF OCR Fallback

- 동일 모듈 `read_pdf(enable_ocr=True)` 로 확장.
- text_layer 가 비어 있으면 `pdf2image` 300DPI 렌더링 → `pytesseract(kor+eng)` 자동 호출.
- 의존성 추가: `pdf2image>=1.17.0`, `pytesseract>=0.3.13`.
- 시스템 의존: `brew install poppler tesseract tesseract-lang`.
- OCR latency **2.0~2.3 s/page** (수락 기준 15 s/page 의 6~7 배 여유).
- 임상 키워드 recall **92.9% / 100%**.
- 스캔 시뮬레이션 샘플 2 건 (`scan_*.pdf`) + 재생성 스크립트 (`scripts/generate_scan_pdf_samples.py`).
- 상세: [`benchmark/v2.2_pdf_stage2_report.md`](benchmark/v2.2_pdf_stage2_report.md)

## Stage 3 — Image Input via Gemini Vision

- 신규 모듈 `src/pipeline/vision_reader.py` (~160 LOC).
- `read_image(path)` → Gemini 2.5 Flash Vision 으로 진료 이미지 → 평문 SOAP 텍스트.
- dry-run 모드: 파일명 키워드 기반 mock 으로 unit test 시 실 API 호출 없이 분기 검증.
- 이미지 샘플 2 건 (`image_*.png`) + 재생성 스크립트 (`scripts/generate_image_samples.py`).
- 실 Gemini 경로 latency **23~33 s/image**, 평균 비용 **$0.004/image**.
- Streamlit UI "이미지 업로드 (v2.2 Vision)" 모드 + 이미지 미리보기 + 비용 표기.

## 테스트

```
17 passed, 59 subtests passed in 18.27s
```

- `tests/test_pdf_reader.py`: 10 cases (Basic 3 / Stage 1 Hyangnam 3 / Latency 1 / Stage 2 Scan 3).
- `tests/test_vision_reader.py`: 7 cases (Basic 4 / dry_run branching 2 / samples 1).
- Stage 1 에서 원본 PHI 14 종 × 3 샘플 = 42 assertion 으로 마스킹 누출 0 건 보장.

## 샘플 데이터 (PHI 안전)

향남메디동물병원 실제 진료 PDF 101 건 중 도메인 다양성 3 건을 선정, `scripts/anonymize_hyangnam_pdf.py` 로 PyMuPDF redact 처리하여 PHI 를 완전 익명화한 후 `data/synthetic_scenarios_pdf/` 에 커밋.

| Fixture | 도메인 | 원본 CC | 대표 처방 |
|---|---|---|---|
| `hyangnam_anon_01_ophthalmology.pdf`   | 안과 | 외상성 각막염 | Cefazolin, Cephalexin, 형광염색 |
| `hyangnam_anon_02_dermatology.pdf`     | 피부(외이염) | 외이염 재진 | Cephalexin, Prednisolone, Chlorpheniramine |
| `hyangnam_anon_03_gastrointestinal.pdf`| 소화기 | 설사/혈변 | Loperamide, Metoclopramide, TMP-SMX |
| `scan_01_ophthalmology.pdf` / `scan_03_gastrointestinal.pdf` | (상동) | 이미지화된 스캔 시뮬레이션 |
| `image_01_ophthalmology.png` / `image_03_gastrointestinal.png` | (상동) | 첫 페이지 PNG (1655x2340, 200DPI) |

PHI 마스킹 규칙: 보호자명 → `Owner_A/B/C`, 환자명 → `Pet_A/B/C`, Sign → `Vet_X`, Address → `[REDACTED]`, Tel → `000-0000-0000`, Client No → `9XXXX`.

## 커밋 히스토리 (main 기준 6 개)

```
794481e feat(v2.2): Stage 3 Gemini Vision image input + 5-mode multimodal benchmark
434cf93 feat(v2.2): Stage 2 OCR fallback + Stage 1 real-API smoke + artifacts
08686dd feat(v2.2): route PDF uploads to SOAP pipeline in Clinical Encoding tab
05c59d7 data(v2.2): add anonymized Hyangnam clinic chart PDFs (Stage 1 fixtures)
cafad9c feat(v2.2): add pdf_reader module for text-layer PDF ingestion
8100820 deps(v2.2): add pdfplumber>=0.10.0 for text-layer PDF extraction
```

## Breaking Changes

없음. 기존 텍스트·오디오 경로는 100% 호환 유지. Streamlit `input_mode` 라디오가 2 옵션에서 4 옵션으로 확장됨 (기본값 "텍스트 입력" 유지).

## Known Limitations

- **Gemini 3.1 Flash Lite Preview 503 일시 오류**: 실 API E2E latency 가 재시도 때문에 40~90 s 로 튈 수 있음. v2.2 Issue [#4](https://github.com/ricocopapa/vet-snomed-rag/issues/4) Claude backup backend 로 보완 예정.
- **구조화 표 추출**: 핸드오프 원안의 camelot-py 표 추출은 Ghostscript 의존성 부담으로 본 릴리즈에서는 스코프 아웃. pdfplumber 의 기본 텍스트 추출로 표 내용도 함께 캡처됨 (진료 내역 행 파싱 확인).
- **혼합 문서 페이지별 분기**: 현재 전체 PDF 단위로 text_layer/OCR 2 택. 페이지 단위 분기는 v2.3 후보.

## Roadmap After v2.2

잔여 v2.2 마일스톤 이슈 (Issue #1 ~ #5):
- #1 Replace gTTS with real veterinarian recordings
- #2 Improve SNOMED match 0.889 → 0.95
- #3 Optimize audio mode latency
- #4 Claude backup backend
- #5 Multi-reviewer gold Cohen's κ

---

**Contributors:** Claude Opus 4.7 (1M context)
**License:** MIT
