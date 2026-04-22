"""
vet-snomed-rag v2.0 — Track B1: Whisper STT 래퍼
================================================
기능:
  - faster-whisper 기반 로컬 STT (한국어 수의 발화 특화)
  - 지원 포맷: m4a / wav / mp3 / mp4
  - 파라미터: language="ko", beam_size=5 (향남병원 파이프라인 기준)
  - fallback: faster-whisper 미설치 시 openai-whisper로 자동 전환

사용 예시:
  result = transcribe("sample.m4a")
  print(result["text"])      # 전사 텍스트
  print(result["duration_sec"])  # 오디오 길이 (초)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

# 지원 오디오 확장자 목록
SUPPORTED_FORMATS = {".m4a", ".wav", ".mp3", ".mp4"}


def _get_audio_duration(audio_path: Path) -> float:
    """오디오 파일의 재생 시간(초)을 반환한다.

    ffprobe → mutagen → soundfile 순서로 시도한다.
    모두 실패하면 -1.0 반환 (duration 미확인 상태).
    """
    # 방법 1: ffprobe (가장 정확, 외부 도구)
    try:
        import subprocess
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass

    # 방법 2: mutagen
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(str(audio_path))
        if audio is not None and hasattr(audio, "info") and hasattr(audio.info, "length"):
            return float(audio.info.length)
    except Exception:
        pass

    # 방법 3: soundfile (wav 전용)
    try:
        import soundfile as sf
        info = sf.info(str(audio_path))
        return float(info.duration)
    except Exception:
        pass

    return -1.0


def transcribe(
    audio_path: str | Path,
    model_size: str = "small",
    language: str = "ko",
    beam_size: int = 5,
) -> dict[str, Any]:
    """오디오 파일을 한국어 텍스트로 전사한다.

    Args:
        audio_path: 전사할 오디오 파일 경로 (m4a / wav / mp3 / mp4)
        model_size: Whisper 모델 크기
                    ("tiny" / "base" / "small" / "medium" / "large-v3")
        language:   전사 언어 코드 (기본값 "ko" — 한국어 강제)
        beam_size:  빔 서치 크기 (기본값 5 — 향남병원 파이프라인 기준)

    Returns:
        dict:
            - text (str): 전체 전사 텍스트 (세그먼트 합산)
            - segments (list[dict]): 세그먼트별 상세 정보
                - id, start, end, text, avg_logprob, no_speech_prob
            - language (str): 감지/강제된 언어 코드
            - duration_sec (float): 오디오 재생 시간(초), 미확인 시 -1.0
            - model_size (str): 사용된 모델 크기
            - elapsed_sec (float): 전사 소요 시간(초)

    Raises:
        FileNotFoundError: audio_path가 존재하지 않을 때
        ValueError("unsupported format: ..."): 지원하지 않는 확장자일 때
        ValueError("empty audio"): 오디오 재생 시간이 0이거나 세그먼트가 없을 때
        RuntimeError: faster-whisper 및 openai-whisper 모두 미설치일 때
    """
    audio_path = Path(audio_path)

    # --- 입력 검증 ---
    if not audio_path.exists():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

    suffix = audio_path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(
            f"unsupported format: '{suffix}' "
            f"(지원 포맷: {', '.join(sorted(SUPPORTED_FORMATS))})"
        )

    # duration 사전 확인 (빈 오디오 조기 차단)
    duration_sec = _get_audio_duration(audio_path)
    if duration_sec == 0.0:
        raise ValueError("empty audio: 재생 시간이 0초인 오디오는 전사할 수 없습니다.")

    # --- 전사 실행 ---
    start_time = time.perf_counter()

    # faster-whisper 우선 시도
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments_gen, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=beam_size,
        )

        segments: list[dict] = []
        full_text_parts: list[str] = []

        for seg in segments_gen:
            segments.append(
                {
                    "id": seg.id,
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip(),
                    "avg_logprob": seg.avg_logprob,
                    "no_speech_prob": seg.no_speech_prob,
                }
            )
            full_text_parts.append(seg.text.strip())

        full_text = " ".join(full_text_parts).strip()

        # 빈 결과 검사 (오디오는 있지만 세그먼트가 0건인 경우)
        if not segments and duration_sec > 0:
            raise ValueError("empty audio: 전사 결과가 비어 있습니다 (무음 구간만 존재할 수 있습니다).")

        # duration_sec 보완 — ffprobe 실패 시 faster-whisper info 사용
        if duration_sec < 0:
            duration_sec = float(info.duration) if hasattr(info, "duration") else -1.0

        elapsed_sec = time.perf_counter() - start_time

        return {
            "text": full_text,
            "segments": segments,
            "language": info.language if hasattr(info, "language") else language,
            "duration_sec": round(duration_sec, 3),
            "model_size": model_size,
            "elapsed_sec": round(elapsed_sec, 3),
        }

    except ImportError:
        pass  # faster-whisper 미설치 → fallback

    # openai-whisper fallback
    try:
        import whisper

        model_ow = whisper.load_model(model_size)
        result_ow = model_ow.transcribe(
            str(audio_path),
            language=language,
            beam_size=beam_size,
        )

        segments_ow: list[dict] = []
        for seg in result_ow.get("segments", []):
            segments_ow.append(
                {
                    "id": seg.get("id"),
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "text": seg.get("text", "").strip(),
                    "avg_logprob": seg.get("avg_logprob"),
                    "no_speech_prob": seg.get("no_speech_prob"),
                }
            )

        full_text_ow = result_ow.get("text", "").strip()

        if not segments_ow and duration_sec > 0:
            raise ValueError("empty audio: 전사 결과가 비어 있습니다.")

        elapsed_sec = time.perf_counter() - start_time

        return {
            "text": full_text_ow,
            "segments": segments_ow,
            "language": result_ow.get("language", language),
            "duration_sec": round(duration_sec, 3),
            "model_size": model_size,
            "elapsed_sec": round(elapsed_sec, 3),
        }

    except ImportError:
        pass  # openai-whisper도 미설치

    raise RuntimeError(
        "STT 엔진을 찾을 수 없습니다. "
        "faster-whisper 또는 openai-whisper 중 하나를 설치하세요.\n"
        "  pip install faster-whisper>=1.0\n"
        "  또는: pip install openai-whisper"
    )
