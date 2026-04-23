"""
vet-snomed-rag v2.2 Stage 1 — pdf_reader 단위 테스트
==================================================
테스트 대상: src/pipeline/pdf_reader.py

테스트 5건:
  1. 존재하지 않는 파일 → FileNotFoundError
  2. PDF 확장자 아님 → ValueError
  3. 향남 익명화 PDF 3건 → has_text_layer=True, source="text_layer",
     pages>=1, 반환 스키마 (4 keys) 검증 + 임상 키워드 추출 확인
  4. 반환 dict 스키마 계약 (keys 정확히 4종)
  5. pdf_reader 단독 latency p95 < 5s (핸드오프 §2.1 수락 기준)

실행:
  cd vet-snomed-rag
  .venv/bin/python -m pytest tests/test_pdf_reader.py -v
"""
from __future__ import annotations

import statistics
import sys
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.pdf_reader import (  # noqa: E402
    SOURCE_TEXT_LAYER,
    TEXT_LAYER_MIN_CHARS,
    read_pdf,
)

SAMPLE_DIR = PROJECT_ROOT / "data" / "synthetic_scenarios_pdf"
SAMPLES = [
    SAMPLE_DIR / "hyangnam_anon_01_ophthalmology.pdf",
    SAMPLE_DIR / "hyangnam_anon_02_dermatology.pdf",
    SAMPLE_DIR / "hyangnam_anon_03_gastrointestinal.pdf",
]

# 샘플별 임상 키워드 — 익명화 후에도 반드시 텍스트에 남아야 할 도메인 용어
CLINICAL_KEYWORDS = {
    "hyangnam_anon_01_ophthalmology.pdf":   ["각막", "형광염색", "Cefazolin"],
    "hyangnam_anon_02_dermatology.pdf":      ["외이염", "Cephalexin", "Prednisolone"],
    "hyangnam_anon_03_gastrointestinal.pdf": ["설사", "Loperamide", "Metoclopramide"],
}

# PHI 가 절대 노출되면 안 되는 원본 값 목록 — 익명화 검증
PHI_FORBIDDEN = [
    "이미정", "양정희", "김수민",
    "뭉뭉이", "티즈",
    "10053", "10024", "10146",
    "이근용", "이현정",
    "010-9519-9537", "010-2416-9785", "010-8388-1481",
]


class TestPdfReaderBasic(unittest.TestCase):
    """기본 동작: 예외 처리와 반환 스키마 계약."""

    def test_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            read_pdf("/tmp/nonexistent_vet_pdf_12345.pdf")

    def test_invalid_extension(self) -> None:
        """PDF 가 아닌 확장자는 ValueError."""
        tmp = Path("/tmp/test_pdf_reader_not_pdf.txt")
        tmp.write_text("not a pdf")
        try:
            with self.assertRaises(ValueError):
                read_pdf(tmp)
        finally:
            tmp.unlink(missing_ok=True)

    def test_return_schema_contract(self) -> None:
        """반환 dict 는 정확히 4 키: text / pages / has_text_layer / source."""
        self.assertTrue(SAMPLES[0].exists(), f"샘플 부재: {SAMPLES[0]}")
        result = read_pdf(SAMPLES[0])
        self.assertEqual(
            set(result.keys()), {"text", "pages", "has_text_layer", "source"},
            f"예상치 못한 반환 키: {set(result.keys())}"
        )
        self.assertIsInstance(result["text"], str)
        self.assertIsInstance(result["pages"], int)
        self.assertIsInstance(result["has_text_layer"], bool)
        self.assertIsInstance(result["source"], str)


class TestPdfReaderHyangnamSamples(unittest.TestCase):
    """향남 익명화 PDF 3건 — 도메인 다양성 및 텍스트 품질 검증."""

    def test_all_samples_text_layer_extracted(self) -> None:
        """3건 모두 has_text_layer=True, source="text_layer"."""
        for pdf_path in SAMPLES:
            with self.subTest(pdf=pdf_path.name):
                self.assertTrue(pdf_path.exists(), f"샘플 부재: {pdf_path}")
                result = read_pdf(pdf_path)
                self.assertTrue(
                    result["has_text_layer"],
                    f"{pdf_path.name}: has_text_layer=False (chars={len(result['text'])})",
                )
                self.assertEqual(result["source"], SOURCE_TEXT_LAYER)
                self.assertGreaterEqual(result["pages"], 1)
                self.assertGreater(len(result["text"]), TEXT_LAYER_MIN_CHARS)

    def test_clinical_keywords_preserved(self) -> None:
        """익명화 후에도 도메인별 임상 키워드가 원문에 남아 있어야 한다."""
        for pdf_path in SAMPLES:
            expected_kws = CLINICAL_KEYWORDS[pdf_path.name]
            result = read_pdf(pdf_path)
            text = result["text"]
            for kw in expected_kws:
                with self.subTest(pdf=pdf_path.name, kw=kw):
                    self.assertIn(kw, text, f"{pdf_path.name}: 임상 키워드 {kw!r} 누락")

    def test_phi_fully_redacted(self) -> None:
        """PHI 원본 값이 샘플 PDF 에 남아 있지 않아야 한다."""
        for pdf_path in SAMPLES:
            result = read_pdf(pdf_path)
            text = result["text"]
            for phi in PHI_FORBIDDEN:
                with self.subTest(pdf=pdf_path.name, phi=phi):
                    self.assertNotIn(phi, text, f"{pdf_path.name}: PHI {phi!r} 미마스킹")


class TestPdfReaderLatency(unittest.TestCase):
    """핸드오프 §2.1 수락 기준: pdf_reader 단독 p95 < 5s."""

    def test_latency_p95_under_5s(self) -> None:
        samples_per_run = 3
        runs = 5
        latencies: list[float] = []
        for _ in range(runs):
            for pdf_path in SAMPLES[:samples_per_run]:
                t0 = time.perf_counter()
                read_pdf(pdf_path)
                latencies.append(time.perf_counter() - t0)
        latencies.sort()
        # 15 샘플 중 p95 = idx 14 (100%) 근사, 보수적으로 quantile 사용
        p95 = statistics.quantiles(latencies, n=20)[-1] if len(latencies) >= 20 else max(latencies)
        self.assertLess(p95, 5.0, f"pdf_reader p95={p95:.3f}s ≥ 5s")


if __name__ == "__main__":
    unittest.main()
