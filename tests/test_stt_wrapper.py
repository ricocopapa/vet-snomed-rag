"""
vet-snomed-rag v2.0 — Track B1: stt_wrapper 단위 테스트
=======================================================
테스트 3건:
  1. 파일 없음 → FileNotFoundError
  2. 지원 포맷 외 확장자 → ValueError("unsupported format: ...")
  3. 합성 오디오 1건 (gTTS) → 텍스트 출력 확인 + duration_sec 검증

실행 방법:
  cd vet-snomed-rag
  venv/bin/python -m pytest tests/test_stt_wrapper.py -v

주의:
  - 테스트 3번은 faster-whisper "small" 모델을 자동 다운로드합니다 (~240MB).
  - 실환자 녹음 데이터 사용 금지. 합성 오디오(gTTS)만 사용합니다.
  - 모델 캐시 위치: ~/.cache/huggingface/ (프로젝트 외부)
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (venv 외부 실행 대응)
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.stt_wrapper import transcribe


class TestSttWrapperErrors(unittest.TestCase):
    """에러 처리 테스트 (모델 다운로드 불필요)"""

    def test_file_not_found_raises(self):
        """존재하지 않는 경로 → FileNotFoundError 발생 확인"""
        with self.assertRaises(FileNotFoundError) as ctx:
            transcribe("/tmp/nonexistent_audio_99999.wav")
        self.assertIn("찾을 수 없습니다", str(ctx.exception))

    def test_unsupported_format_raises(self):
        """지원 포맷 외 확장자 → ValueError 발생 확인"""
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            tmp_path = f.name
            f.write(b"dummy ogg content")  # 실제 오디오 아님, 포맷 체크용
        try:
            with self.assertRaises(ValueError) as ctx:
                transcribe(tmp_path)
            self.assertIn("unsupported format", str(ctx.exception))
            self.assertIn(".ogg", str(ctx.exception))
        finally:
            os.unlink(tmp_path)


class TestSttWrapperSmoke(unittest.TestCase):
    """합성 오디오 smoke 테스트 (faster-whisper 모델 자동 다운로드)"""

    def test_synthetic_korean_audio_transcription(self):
        """gTTS 합성 오디오 → 한국어 텍스트 전사 + duration_sec 검증

        입력: "체온 삼십팔도 심박수 백이십" (수의 임상 발화 합성)
        기대: text가 비어있지 않음 + duration_sec > 0
        """
        # gTTS import 검사
        try:
            from gtts import gTTS
        except ImportError:
            self.skipTest("gtts 미설치. pip install gtts 후 재실행하세요.")

        synthetic_text = "체온 삼십팔도 심박수 백이십"

        # gTTS로 합성 오디오 생성 (mp3 포맷)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        try:
            tts = gTTS(text=synthetic_text, lang="ko")
            tts.save(tmp_path)

            # faster-whisper 미설치 대응
            try:
                from faster_whisper import WhisperModel  # noqa: F401
            except ImportError:
                self.skipTest("faster-whisper 미설치. pip install faster-whisper 후 재실행하세요.")

            # 전사 실행 (tiny 모델 사용 — 테스트 속도 최적화)
            result = transcribe(tmp_path, model_size="tiny", language="ko", beam_size=5)

            # --- 검증 ---
            # 1. 반환 키 완전성
            required_keys = {"text", "segments", "language", "duration_sec", "model_size", "elapsed_sec"}
            self.assertTrue(required_keys.issubset(result.keys()), f"반환 키 누락: {required_keys - result.keys()}")

            # 2. 텍스트 비어있지 않음
            self.assertIsInstance(result["text"], str)
            self.assertGreater(len(result["text"]), 0, "전사 텍스트가 비어 있습니다.")

            # 3. duration_sec > 0 (합성 오디오는 항상 양수)
            self.assertGreater(result["duration_sec"], 0.0, "duration_sec가 0 이하입니다.")

            # 4. language 필드 존재
            self.assertIsInstance(result["language"], str)
            self.assertGreater(len(result["language"]), 0)

            # 5. segments 리스트
            self.assertIsInstance(result["segments"], list)

            print(f"\n[Smoke 결과]")
            print(f"  입력 텍스트 (gTTS): {synthetic_text!r}")
            print(f"  전사 결과:          {result['text']!r}")
            print(f"  duration_sec:       {result['duration_sec']}")
            print(f"  elapsed_sec:        {result['elapsed_sec']}")
            print(f"  language:           {result['language']}")
            print(f"  segments 수:        {len(result['segments'])}")

        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
