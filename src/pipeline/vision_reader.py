"""
vision_reader.py
================
vet-snomed-rag v2.2 Stage 3 — Vision LLM 이미지 리더.

기능:
  - 수의 진료 이미지(.jpg/.png/.jpeg) 를 Gemini Vision 에게 보내 구조화된
    진료 텍스트를 추출.
  - 시스템 프롬프트는 SOAP 프레임워크 + 한국어 수의 도메인 용어 보존을 강제.
  - 출력은 후속 `SOAPExtractor` 가 그대로 소비할 수 있는 평문 텍스트 블록.

사용 예시:
  from src.pipeline.vision_reader import read_image
  info = read_image("data/synthetic_scenarios_pdf/image_01_ophthalmology.png")
  # {"text": "...", "source": "vision", "model": "gemini-…", "cost_usd": 0.0015, ...}

주의:
  - GOOGLE_API_KEY 필요 (환경변수 또는 .env).
  - Gemini 2.5 Flash 계열은 vision 지원. Lite preview 는 컨텍스트 제약이 있어
    vision 용도로는 `gemini-2.5-flash` 를 기본값으로 둔다.
  - dry_run=True 이면 API 미호출 + mock 응답 반환 (테스트 용).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

# 기본 Vision 모델. 공식 GA 모델. 3.1 lite preview 는 vision 컨텍스트가 제한적이라
# 본 경로에서는 2.5-flash 를 우선 사용.
DEFAULT_VISION_MODEL = "gemini-2.5-flash"

# Gemini 2.5 Flash 가격 (2026 기준)
VISION_INPUT_PRICE_PER_M  = 0.30    # $ / 1M input tokens
VISION_OUTPUT_PRICE_PER_M = 2.50    # $ / 1M output tokens

SOURCE_VISION = "vision"

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

_SYSTEM_PROMPT = (
    "당신은 수의학 진료 이미지에서 임상 정보를 추출하는 전문가다.\n"
    "입력 이미지는 수의사 진료 기록의 스캔본 또는 사진이다.\n\n"
    "[출력 규칙]\n"
    "1. 이미지에 보이는 한국어·영어 진료 텍스트를 있는 그대로 추출한다.\n"
    "2. SOAP 섹션(Subject/Object/Assessment/Plan) 이 명시되어 있으면 그 구조를 유지한다.\n"
    "3. 처방 코드·약물명·용량·경로(PO/IM/SC/IV) 는 원본 그대로 보존한다.\n"
    "4. 수치·단위(mmHg, mg/kg, cm 등) 는 변경하지 않는다.\n"
    "5. 환자 이름·보호자 이름 등 개인정보는 추출 대상에 포함하되 변조하지 않는다.\n"
    "6. 설명·요약·추측 없이, 이미지에 존재하는 텍스트만 평문으로 출력한다.\n"
)


def _mock_image_response(image_path: Path) -> str:
    """dry_run 용 mock. 파일명 키워드로 도메인 분기."""
    name = image_path.name.lower()
    if "oph" in name or "cornea" in name or "ophthalm" in name:
        return (
            "Subject\nCC : 외상성 각막염\n\n"
            "Object\n각막 형광염색 양성(우안). 동공 반사 감소.\n\n"
            "Assessment\nDX 외상성 각막염\n\n"
            "Plan\nCefazolin Inj. 20 mg/kg 1 IM\nCephalexin Cap. 20 mg/kg 3 6 PO\n"
        )
    if "gastro" in name or "diarrhea" in name or "gi_" in name:
        return (
            "Subject\nCC : 설사\n\nObject\n체온 38.5°C. 장음 항진.\n\n"
            "Assessment\nDDX 설사 / 혈변 (원인 불명)\n\n"
            "Plan\nLoperamide Cap. 0.1 mg/kg 3 6 PO\nMetoclopramide Tab. 0.2 mg/kg 3 6 PO\n"
        )
    return "Subject\nCC : 진료\n\nObject\n검사 진행 중.\n\nAssessment\n평가 미정.\n\nPlan\n경과 관찰.\n"


def read_image(
    path: str | Path,
    *,
    model: str = DEFAULT_VISION_MODEL,
    api_key: str | None = None,
    dry_run: bool = False,
    timeout_sec: int = 60,
) -> dict[str, Any]:
    """이미지에서 진료 텍스트를 추출한다.

    Args:
        path:        이미지 파일 경로 (.jpg / .jpeg / .png / .webp).
        model:       Gemini 모델 ID. 기본 "gemini-2.5-flash".
        api_key:     None 이면 환경변수 GOOGLE_API_KEY 사용 (또는 .env).
        dry_run:     True 이면 API 미호출, 파일명 기반 mock 반환.
        timeout_sec: Gemini API 호출 타임아웃.

    Returns:
        {
            "text": str,          # 추출된 진료 텍스트
            "source": "vision",
            "model": str,
            "latency_ms": int,
            "cost_usd": float,
            "tokens_input": int,
            "tokens_output": int,
        }

    Raises:
        FileNotFoundError : path 부재
        ValueError        : 지원 외 확장자
        ImportError       : google-genai / Pillow 미설치
        EnvironmentError  : GOOGLE_API_KEY 미설정 (dry_run=False 경로)
        RuntimeError      : Gemini API 호출 실패
    """
    img_path = Path(path)
    if not img_path.exists():
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {img_path}")
    suffix = img_path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_EXTS:
        raise ValueError(
            f"지원하지 않는 이미지 확장자: {suffix!r} "
            f"(허용: {', '.join(sorted(SUPPORTED_IMAGE_EXTS))})"
        )

    if dry_run:
        return {
            "text": _mock_image_response(img_path),
            "source": SOURCE_VISION,
            "model": "mock",
            "latency_ms": 0,
            "cost_usd": 0.0,
            "tokens_input": 0,
            "tokens_output": 0,
        }

    # API key
    if api_key is None:
        # .env 로드 시도
        try:
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
        except ImportError:
            pass
        api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY 가 설정되지 않았습니다. .env 또는 export 로 지정하세요."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise ImportError(
            "google-genai 가 필요합니다. pip install google-genai>=0.8.0"
        ) from e
    try:
        from PIL import Image
    except ImportError as e:
        raise ImportError("Pillow 가 필요합니다. pip install Pillow") from e

    client = genai.Client(api_key=api_key)
    image = Image.open(img_path)

    t0 = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=model,
            contents=[_SYSTEM_PROMPT, image],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2048,
            ),
        )
    except Exception as e:
        raise RuntimeError(f"Gemini Vision API 호출 실패: {e}") from e
    latency_ms = int((time.perf_counter() - t0) * 1000)

    text_out = response.text or ""

    try:
        in_tok  = response.usage_metadata.prompt_token_count or 0
        out_tok = response.usage_metadata.candidates_token_count or 0
    except (AttributeError, TypeError):
        in_tok, out_tok = 0, 0

    cost = (
        in_tok * VISION_INPUT_PRICE_PER_M + out_tok * VISION_OUTPUT_PRICE_PER_M
    ) / 1_000_000

    return {
        "text": text_out.strip(),
        "source": SOURCE_VISION,
        "model": model,
        "latency_ms": latency_ms,
        "cost_usd": round(cost, 8),
        "tokens_input": in_tok,
        "tokens_output": out_tok,
    }
