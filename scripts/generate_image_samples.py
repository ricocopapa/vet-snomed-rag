"""
generate_image_samples.py
=========================
v2.2 Stage 3 — 이미지 샘플 생성 (향남 익명화 PDF 첫 페이지를 PNG 로 렌더링).

대상:
  hyangnam_anon_01_ophthalmology.pdf    → image_01_ophthalmology.png
  hyangnam_anon_03_gastrointestinal.pdf → image_03_gastrointestinal.png

실행:
  .venv/bin/python scripts/generate_image_samples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "synthetic_scenarios_pdf"

SOURCES = [
    ("hyangnam_anon_01_ophthalmology.pdf",    "image_01_ophthalmology.png"),
    ("hyangnam_anon_03_gastrointestinal.pdf", "image_03_gastrointestinal.png"),
]

DPI = 200


def pdf_first_page_to_png(src: Path, dst: Path, dpi: int = DPI) -> tuple[int, int]:
    from pdf2image import convert_from_path
    images = convert_from_path(str(src), dpi=dpi)
    if not images:
        raise RuntimeError(f"렌더링 실패: {src}")
    img = images[0].convert("RGB")
    img.save(dst, format="PNG", optimize=True)
    return img.size  # (w, h)


def main() -> int:
    ok = 0
    for src_name, dst_name in SOURCES:
        src = OUT_DIR / src_name
        dst = OUT_DIR / dst_name
        if not src.exists():
            print(f"  SKIP: {src}")
            continue
        try:
            w, h = pdf_first_page_to_png(src, dst)
            kb = dst.stat().st_size / 1024
            print(f"  OK  {dst.name}  {w}x{h}  {kb:.1f}KB")
            ok += 1
        except Exception as e:
            print(f"  FAIL {dst.name}: {e}")
    print(f"\ndone: {ok}/{len(SOURCES)}")
    return 0 if ok == len(SOURCES) else 1


if __name__ == "__main__":
    sys.exit(main())
