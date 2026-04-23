"""
generate_scan_pdf_samples.py
============================
v2.2 Stage 2 — 스캔 PDF 시뮬레이션 샘플 생성.

전략:
  기존 텍스트 레이어 PDF(향남 익명화 2건) 를 pdf2image 로 렌더링 후
  다시 이미지 기반 PDF 로 저장하여 "텍스트 레이어가 없는 스캔 PDF" 를
  시뮬레이션한다. 원본 텍스트와 같은 진료 내용을 유지하므로 Korean CER
  (OCR 결과 vs pdfplumber 원본) 측정이 가능하다.

대상:
  hyangnam_anon_01_ophthalmology.pdf      → scan_01_ophthalmology.pdf
  hyangnam_anon_03_gastrointestinal.pdf   → scan_03_gastrointestinal.pdf

실행:
  .venv/bin/python scripts/generate_scan_pdf_samples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "synthetic_scenarios_pdf"

SOURCES = [
    ("hyangnam_anon_01_ophthalmology.pdf",    "scan_01_ophthalmology.pdf"),
    ("hyangnam_anon_03_gastrointestinal.pdf", "scan_03_gastrointestinal.pdf"),
]

DPI = 200  # 시뮬레이션 용 — 실제 스캐너 해상도 근사


def pdf_to_scan_pdf(src: Path, dst: Path, dpi: int = DPI) -> int:
    """src 를 이미지 시퀀스로 렌더링 후 이미지 기반 PDF 로 재저장."""
    from pdf2image import convert_from_path
    from PIL import Image

    images = convert_from_path(str(src), dpi=dpi)
    if not images:
        raise RuntimeError(f"렌더링 실패 (빈 이미지 시퀀스): {src}")

    rgb_images = [img.convert("RGB") for img in images]
    rgb_images[0].save(
        dst,
        save_all=True,
        append_images=rgb_images[1:],
        format="PDF",
        resolution=float(dpi),
    )
    return len(rgb_images)


def main() -> int:
    if not OUT_DIR.exists():
        print(f"ERROR: 출력 디렉토리 없음: {OUT_DIR}")
        return 1

    ok = 0
    for src_name, dst_name in SOURCES:
        src = OUT_DIR / src_name
        dst = OUT_DIR / dst_name
        if not src.exists():
            print(f"  SKIP (source not found): {src}")
            continue
        try:
            pages = pdf_to_scan_pdf(src, dst)
            size_kb = dst.stat().st_size / 1024
            print(f"  OK  {dst.name}  pages={pages}  size={size_kb:.1f}KB")
            ok += 1
        except Exception as e:
            print(f"  FAIL {dst.name}: {e}")

    print(f"\ndone: {ok}/{len(SOURCES)}")
    return 0 if ok == len(SOURCES) else 1


if __name__ == "__main__":
    sys.exit(main())
