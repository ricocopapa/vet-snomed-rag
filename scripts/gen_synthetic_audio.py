"""
gen_synthetic_audio.py — gTTS 합성 오디오 생성
================================================

data/synthetic_scenarios/scripts_text.json의 시나리오 스크립트를
gTTS로 합성하여 mp3 파일로 저장한다.

사용법:
  python scripts/gen_synthetic_audio.py

출력:
  data/synthetic_scenarios/scenario_{N}.mp3

[절대 원칙]
  - 생성된 오디오는 gTTS 기계음 합성 (실 수의사 녹음 아님) — 명시 필수
  - 파일 생성 후 duration 검증 (30~90초 범위 권장, 벗어나면 경고만)
  - 임상/투자 판단 금지 (data-analyzer 원칙)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "synthetic_scenarios"
SCRIPTS_JSON = DATA_DIR / "scripts_text.json"


def _get_audio_duration(mp3_path: Path) -> float | None:
    """mp3 파일의 재생 시간(초)을 추정한다.

    mutagen 또는 ffprobe 사용. 실패 시 None 반환.
    """
    # mutagen 시도
    try:
        from mutagen.mp3 import MP3
        audio = MP3(str(mp3_path))
        return float(audio.info.length)
    except ImportError:
        pass
    except Exception:
        pass

    # ffprobe 시도
    try:
        import subprocess
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(mp3_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass

    # 파일 크기 기반 추정 (mp3 @128kbps ≒ 16KB/s)
    try:
        size_bytes = mp3_path.stat().st_size
        estimated = size_bytes / 16_000  # 128kbps = 16000 bytes/s
        return estimated
    except Exception:
        return None


def generate_audio(scripts_json: Path = SCRIPTS_JSON, output_dir: Path = DATA_DIR) -> list[dict]:
    """gTTS로 시나리오 스크립트를 합성 오디오 mp3로 변환한다.

    Returns:
        [{"scenario_id": int, "path": str, "duration_sec": float|None, "status": "OK"|"FAIL"}, ...]
    """
    try:
        from gtts import gTTS
    except ImportError:
        print("[FAIL] gTTS 미설치. pip install gtts 실행 후 재시도.")
        sys.exit(1)

    if not scripts_json.exists():
        print(f"[FAIL] scripts_text.json 없음: {scripts_json}")
        sys.exit(1)

    with open(scripts_json, encoding="utf-8") as f:
        scripts = json.load(f)

    results = []
    print(f"\ngTTS 합성 오디오 생성 (한국어 TTS — 기계음, 실 수의사 녹음 아님)")
    print(f"총 {len(scripts)}건 처리\n")

    for item in scripts:
        sid    = item["scenario_id"]
        domain = item["domain"]
        script = item["script"]
        out_path = output_dir / f"scenario_{sid}.mp3"

        print(f"[{sid}/5] S{sid:02d} [{domain}] — {len(script)}자 → {out_path.name}")
        t0 = time.perf_counter()
        try:
            tts = gTTS(text=script, lang="ko", slow=False)
            tts.save(str(out_path))
            elapsed = time.perf_counter() - t0

            duration = _get_audio_duration(out_path)
            dur_str = f"{duration:.1f}s" if duration is not None else "N/A"
            size_kb = out_path.stat().st_size / 1024

            # duration 범위 검증 (30~90초)
            if duration is not None and (duration < 30 or duration > 90):
                dur_warn = f" [WARN: 권장 30~90s 벗어남]"
            else:
                dur_warn = ""

            print(f"  OK: {size_kb:.1f} KB | duration={dur_str}{dur_warn} | 생성 {elapsed:.1f}s")
            results.append({
                "scenario_id": sid,
                "path": str(out_path),
                "duration_sec": duration,
                "status": "OK",
            })
        except Exception as e:
            elapsed = time.perf_counter() - t0
            print(f"  FAIL: {e} ({elapsed:.1f}s)")
            results.append({
                "scenario_id": sid,
                "path": str(output_dir / f"scenario_{sid}.mp3"),
                "duration_sec": None,
                "status": f"FAIL: {e}",
            })

    ok_count   = sum(1 for r in results if r["status"] == "OK")
    fail_count = sum(1 for r in results if r["status"] != "OK")
    print(f"\n결과: {ok_count}건 OK / {fail_count}건 FAIL")
    print("[주의] 본 오디오는 gTTS 기계음 합성입니다. 실 수의사 녹음이 아닙니다.")
    return results


def main():
    results = generate_audio()
    print("\n생성 파일 목록:")
    for r in results:
        status = r["status"]
        dur = f"{r['duration_sec']:.1f}s" if r["duration_sec"] is not None else "N/A"
        print(f"  S{r['scenario_id']:02d}: {Path(r['path']).name} | dur={dur} | {status}")


if __name__ == "__main__":
    main()
