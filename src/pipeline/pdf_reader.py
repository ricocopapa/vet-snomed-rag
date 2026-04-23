"""
pdf_reader.py
=============
vet-snomed-rag v2.2 Stage 1 — PDF text layer reader.

기능:
  - pdfplumber 기반 텍스트 레이어 추출 (Stage 1: text-only)
  - has_text_layer 판정 (빈 스캔 PDF 구별)
  - Stage 2 (OCR fallback) / Stage 3 (Vision LLM) 진입 훅 마련

Stage 범위:
  Stage 1: text_layer only — 본 파일
  Stage 2: OCR fallback    — pdf2image + tesseract
  Stage 3: Vision LLM      — vision_reader.py 별도 모듈

사용 예시:
  from src.pipeline.pdf_reader import read_pdf
  info = read_pdf("data/synthetic_scenarios_pdf/hyangnam_anon_01_ophthalmology.pdf")
  # {"text": str, "pages": 2, "has_text_layer": True, "source": "text_layer"}
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# 텍스트 레이어 존재 판정 임계값 (문자 수).
# 향남 Chart_Data.PDF 샘플 최소 chars=870 기준, 공백 위주의 빈 페이지를
# 필터링할 수 있도록 50 으로 설정. Stage 2 OCR fallback 트리거 경계.
TEXT_LAYER_MIN_CHARS = 50

SOURCE_TEXT_LAYER = "text_layer"
SOURCE_OCR = "ocr"
SOURCE_VISION = "vision"


def read_pdf(path: str | Path) -> dict[str, Any]:
    """PDF 에서 텍스트 레이어를 추출한다.

    Args:
        path: PDF 파일 경로.

    Returns:
        {
            "text": str,             # 전체 페이지 텍스트 (\n 으로 연결)
            "pages": int,            # 페이지 수
            "has_text_layer": bool,  # 유의미한 텍스트 레이어 존재 여부
            "source": str,           # "text_layer" | "ocr" | "vision"
        }

    Raises:
        FileNotFoundError: path 가 존재하지 않을 때.
        ValueError: path 가 .pdf 확장자가 아닐 때.
        RuntimeError: pdfplumber 가 파일을 파싱할 수 없을 때.
    """
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"PDF 확장자가 아닙니다: {pdf_path.suffix!r}")

    try:
        import pdfplumber
    except ImportError as e:
        raise ImportError(
            "pdfplumber 가 필요합니다. pip install 'pdfplumber>=0.10.0'"
        ) from e

    page_texts: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                page_texts.append(page.extract_text() or "")
    except Exception as e:
        raise RuntimeError(f"PDF 파싱 실패 ({pdf_path.name}): {e}") from e

    full_text = "\n".join(page_texts).strip()
    has_text_layer = len(full_text) >= TEXT_LAYER_MIN_CHARS

    return {
        "text": full_text,
        "pages": page_count,
        "has_text_layer": has_text_layer,
        "source": SOURCE_TEXT_LAYER if has_text_layer else SOURCE_OCR,
    }
