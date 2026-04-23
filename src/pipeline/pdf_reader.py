"""
pdf_reader.py
=============
vet-snomed-rag v2.2 Stage 1+2 — PDF text-layer reader with OCR fallback.

기능:
  Stage 1: pdfplumber 기반 텍스트 레이어 추출
  Stage 2: pdfplumber 로 텍스트 부족 시 pdf2image + pytesseract OCR fallback

Stage 범위:
  Stage 1: text_layer only          — has_text_layer=True 경로
  Stage 2: OCR fallback             — pdf2image + tesseract(kor+eng)
  Stage 3: Vision LLM (별도 모듈)   — vision_reader.py

시스템 의존 (Stage 2):
  - poppler  (pdf2image 용)      : `brew install poppler`
  - tesseract + kor/eng lang pack : `brew install tesseract tesseract-lang`

사용 예시:
  from src.pipeline.pdf_reader import read_pdf
  info = read_pdf("data/synthetic_scenarios_pdf/hyangnam_anon_01_ophthalmology.pdf")
  # {"text": str, "pages": 2, "has_text_layer": True, "source": "text_layer"}

  # OCR 강제
  info = read_pdf("scan.pdf", enable_ocr=True)
  # {"text": "...", "pages": 2, "has_text_layer": False, "source": "ocr"}
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# 텍스트 레이어 존재 판정 임계값 (문자 수).
# 향남 Chart_Data.PDF 샘플 최소 chars=870 기준, 공백 위주의 빈 페이지를
# 필터링할 수 있도록 50 으로 설정. Stage 2 OCR fallback 트리거 경계.
TEXT_LAYER_MIN_CHARS = 50

# OCR 경로 기본 해상도. 높을수록 정확도↑, 속도↓. 한글 수의 기록 실측으로 300 DPI
# 에서 CER < 10% 충족 확인.
OCR_DEFAULT_DPI = 300

# OCR 언어 팩 (tesseract). "kor+eng" = 한국어 주 + 영문(약어/브랜드) 보조.
OCR_DEFAULT_LANG = "kor+eng"

SOURCE_TEXT_LAYER = "text_layer"
SOURCE_OCR = "ocr"
SOURCE_VISION = "vision"


def _extract_text_layer(pdf_path: Path) -> tuple[list[str], int]:
    """pdfplumber 로 페이지별 텍스트 레이어를 추출한다.

    Returns: (page_texts, page_count)
    Raises:  RuntimeError 파싱 실패 시.
    """
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
    return page_texts, page_count


def _ocr_pdf(pdf_path: Path, dpi: int, lang: str) -> tuple[list[str], int]:
    """pdf2image 로 페이지 이미지화 후 pytesseract 로 OCR.

    Returns: (page_texts, page_count)
    Raises:
      ImportError : pdf2image / pytesseract 미설치
      RuntimeError: poppler / tesseract 실행 실패, OCR 파이프라인 예외
    """
    try:
        from pdf2image import convert_from_path
    except ImportError as e:
        raise ImportError(
            "pdf2image 가 필요합니다. pip install 'pdf2image>=1.17.0' "
            "(시스템 poppler 도 설치 필요: brew install poppler)"
        ) from e
    try:
        import pytesseract
    except ImportError as e:
        raise ImportError(
            "pytesseract 가 필요합니다. pip install 'pytesseract>=0.3.13' "
            "(시스템 tesseract 도 설치 필요: brew install tesseract tesseract-lang)"
        ) from e

    try:
        images = convert_from_path(str(pdf_path), dpi=dpi)
    except Exception as e:
        raise RuntimeError(
            f"pdf2image 변환 실패 ({pdf_path.name}): {e}. poppler 설치 확인."
        ) from e

    page_texts: list[str] = []
    for i, img in enumerate(images):
        try:
            text = pytesseract.image_to_string(img, lang=lang)
        except pytesseract.TesseractNotFoundError as e:
            raise RuntimeError(
                "tesseract 실행 파일을 찾을 수 없습니다. "
                "brew install tesseract tesseract-lang"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"pytesseract OCR 실패 (page {i + 1}, {pdf_path.name}): {e}"
            ) from e
        page_texts.append(text or "")

    return page_texts, len(images)


def read_pdf(
    path: str | Path,
    *,
    enable_ocr: bool = True,
    ocr_dpi: int = OCR_DEFAULT_DPI,
    ocr_lang: str = OCR_DEFAULT_LANG,
) -> dict[str, Any]:
    """PDF 에서 텍스트를 추출한다. text_layer 부족 시 OCR 로 fallback.

    Args:
        path:       PDF 파일 경로.
        enable_ocr: text_layer 가 부족할 때 OCR fallback 을 허용할지 여부.
                    False 이면 `has_text_layer=False` + `source="ocr"` 로 빈 text 반환.
        ocr_dpi:    OCR 용 페이지 이미지 해상도 (DPI). 기본 300.
        ocr_lang:   tesseract 언어 팩 코드. 기본 "kor+eng".

    Returns:
        {
            "text": str,             # 전체 페이지 텍스트 (\n 으로 연결)
            "pages": int,            # 페이지 수
            "has_text_layer": bool,  # 유의미한 텍스트 레이어 존재 여부
            "source": str,           # "text_layer" | "ocr" | "vision"
        }

    Raises:
        FileNotFoundError: path 가 존재하지 않을 때.
        ValueError       : path 가 .pdf 확장자가 아닐 때.
        RuntimeError     : PDF 파싱 또는 OCR 파이프라인 실패.
        ImportError      : OCR 경로 진입 시 pdf2image / pytesseract 미설치.
    """
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"PDF 확장자가 아닙니다: {pdf_path.suffix!r}")

    # ── Stage 1: text_layer 시도 ────────────────────────────────────────
    page_texts, page_count = _extract_text_layer(pdf_path)
    full_text = "\n".join(page_texts).strip()
    has_text_layer = len(full_text) >= TEXT_LAYER_MIN_CHARS

    if has_text_layer:
        return {
            "text": full_text,
            "pages": page_count,
            "has_text_layer": True,
            "source": SOURCE_TEXT_LAYER,
        }

    # ── Stage 2: OCR fallback ───────────────────────────────────────────
    if not enable_ocr:
        return {
            "text": full_text,     # 빈 문자열 또는 아주 짧은 문자
            "pages": page_count,
            "has_text_layer": False,
            "source": SOURCE_OCR,  # OCR 필요 신호 (실제 OCR 은 생략)
        }

    ocr_texts, ocr_pages = _ocr_pdf(pdf_path, dpi=ocr_dpi, lang=ocr_lang)
    ocr_full = "\n".join(ocr_texts).strip()

    return {
        "text": ocr_full,
        # pdfplumber 와 pdf2image 가 보는 페이지 수가 이론적으로 동일해야 하나,
        # 둘 중 더 큰 값을 보수적으로 반환 (incomplete PDF 대응).
        "pages": max(page_count, ocr_pages),
        "has_text_layer": False,
        "source": SOURCE_OCR,
    }
