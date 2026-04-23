"""
vet-snomed-rag v2.2 Stage 3 — vision_reader 단위 테스트
======================================================
테스트 대상: src/pipeline/vision_reader.py

테스트 5건 (실 API 미호출):
  1. 존재하지 않는 파일 → FileNotFoundError
  2. 지원 외 확장자 → ValueError
  3. dry_run mock 반환 스키마 계약 (7 키)
  4. dry_run 파일명 키워드 분기 (ophthalmology / gastrointestinal)
  5. 이미지 샘플 2건 존재 + dry_run 분기 검증

실행:
  .venv/bin/python -m pytest tests/test_vision_reader.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.vision_reader import (  # noqa: E402
    SOURCE_VISION,
    SUPPORTED_IMAGE_EXTS,
    read_image,
)

SAMPLE_DIR = PROJECT_ROOT / "data" / "synthetic_scenarios_pdf"
IMG_OPH = SAMPLE_DIR / "image_01_ophthalmology.png"
IMG_GI  = SAMPLE_DIR / "image_03_gastrointestinal.png"


class TestVisionReaderBasic(unittest.TestCase):

    def test_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            read_image("/tmp/nonexistent_vision_img_12345.png", dry_run=True)

    def test_invalid_extension(self) -> None:
        tmp = Path("/tmp/test_vision_not_image.txt")
        tmp.write_text("not an image")
        try:
            with self.assertRaises(ValueError):
                read_image(tmp, dry_run=True)
        finally:
            tmp.unlink(missing_ok=True)

    def test_supported_extensions_set(self) -> None:
        self.assertEqual(
            SUPPORTED_IMAGE_EXTS,
            {".jpg", ".jpeg", ".png", ".webp"},
        )

    def test_dry_run_schema_contract(self) -> None:
        """dry_run 모드 반환 dict 는 7 키 계약."""
        self.assertTrue(IMG_OPH.exists(), f"샘플 부재: {IMG_OPH}")
        result = read_image(IMG_OPH, dry_run=True)
        self.assertEqual(
            set(result.keys()),
            {"text", "source", "model", "latency_ms", "cost_usd",
             "tokens_input", "tokens_output"},
        )
        self.assertEqual(result["source"], SOURCE_VISION)
        self.assertEqual(result["model"], "mock")
        self.assertEqual(result["cost_usd"], 0.0)


class TestVisionReaderDryRunBranching(unittest.TestCase):
    """dry_run mock 의 파일명 기반 도메인 분기가 의도대로 작동하는지."""

    def test_dry_run_ophthalmology_branch(self) -> None:
        r = read_image(IMG_OPH, dry_run=True)
        # mock 은 각막 / Cefazolin 관련 텍스트를 반환
        self.assertIn("각막", r["text"])
        self.assertIn("Cefazolin", r["text"])

    def test_dry_run_gastrointestinal_branch(self) -> None:
        r = read_image(IMG_GI, dry_run=True)
        self.assertIn("설사", r["text"])
        self.assertIn("Loperamide", r["text"])


class TestVisionReaderSamplesExist(unittest.TestCase):
    def test_image_samples_present(self) -> None:
        for p in (IMG_OPH, IMG_GI):
            with self.subTest(img=p.name):
                self.assertTrue(p.exists(), f"샘플 이미지 부재: {p}")
                # 파일 크기 > 100KB (유의미한 진료 기록 이미지)
                self.assertGreater(p.stat().st_size, 100_000)


if __name__ == "__main__":
    unittest.main()
