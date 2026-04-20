"""
SNOMED CT 쿼리 리포매터 — Strategy 패턴 Dual Backend.

[설계]
설계서: 20260419_vet_snomed_rag_T7_fix_design_v1.md §4.1~§4.8

[아키텍처]
BaseReformulator (ABC)
    ├── GeminiReformulator   (gemini-2.5-flash, google-genai SDK)
    └── ClaudeReformulator   (claude-sonnet-4-6, anthropic SDK)

[캐싱]
L1: 벤더 네이티브 (Gemini Implicit / Claude Ephemeral 5분)
L2: 로컬 파일 캐시 (src/retrieval/cache/reformulations_{backend}.json)
    키: SHA256(query + backend + model_id)

[폴백 원칙]
리포매터 실패 시 원본 쿼리로 fallthrough — T7 이외 regression 방지 최우선.
ANTHROPIC_API_KEY 미설정 시 ClaudeReformulator는 graceful skip.

[사용 예시]
    from src.retrieval.query_reformulator import get_reformulator
    r = get_reformulator("gemini")
    result = r.reformulate("feline diabetes")
    print(result.reformulated)  # "diabetes mellitus"
    print(result.confidence)    # 0.90
"""

import json
import os
import hashlib
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# .env 로드 (프로젝트 루트 기준)
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

# 캐시 디렉토리
_CACHE_DIR = Path(__file__).resolve().parent / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ─── SNOMED 리포매팅 프롬프트 (양 백엔드 공유) ─────────────

SYSTEM_PROMPT = """You are a SNOMED CT query reformatter. Your task is to reformat veterinary
search queries to match the SNOMED CT concept structure.

[SNOMED Design Principles]
1. Most disease concepts are species-agnostic. Species-specific concepts exist for only a few
   (e.g., "Feline panleukopenia", "Canine parvovirus").
2. Species specificity is expressed via post-coordination:
   Base concept + "Occurs in" = Species concept
3. Therefore, "feline diabetes" should be reformatted to "diabetes mellitus" +
   post_coord_hint "Occurs in = Feline species".

[Reformatting Rules]
- Remove standalone species qualifiers ONLY when the species word is purely a qualifier,
  NOT when it forms part of the clinical concept name.
  Examples of species as QUALIFIER (remove): "diabetes in cat", "pancreatitis dog", "고양이 당뇨"
  Examples of species as PART OF CONCEPT (preserve): "cat bite wound", "cat bite", "dog bite"
- "cat bite wound" → PRESERVE as-is. "cat bite" is a registered wound mechanism in SNOMED CT.
- Remove official species adjectives (feline/canine) ONLY when no species-specific SNOMED concept exists.
- PRESERVE species-specific SNOMED concepts: "Feline panleukopenia", "Canine parvovirus", "cat bite wound"
- Remove meta terms (SNOMED/code/concept/코드/개념)
- If the input is Korean, translate the clinical term to English in "reformulated"
- Keep organism names intact (e.g., "parvovirus" must remain in "Canine parvovirus")

[Examples]
- "feline diabetes" → reformulated: "diabetes mellitus", post_coord_hint: "Occurs in = Feline species"
- "canine parvovirus enteritis" → reformulated: "canine parvovirus enteritis" (preserved)
- "cat bite wound" → reformulated: "cat bite wound" (preserved — cat bite is the mechanism)
- "Feline panleukopenia SNOMED code" → reformulated: "feline panleukopenia" (meta removed only)
- "고양이 당뇨" → reformulated: "diabetes mellitus", post_coord_hint: "Occurs in = Feline species"
- "개 췌장염" → reformulated: "pancreatitis", post_coord_hint: "Occurs in = Canine species"
- "고양이 범백혈구감소증" → reformulated: "feline panleukopenia" (translate + preserve species-specific)

[Output JSON — keep reasoning SHORT (1 sentence, English only)]
{
  "reformulated": "...",
  "post_coord_hint": "Occurs in = <species>" | null,
  "confidence": 0.0~1.0,
  "reasoning": "one sentence in English"
}"""


# ─── 데이터 클래스 ──────────────────────────────────────────

@dataclass
class ReformulatedQuery:
    """쿼리 리포매팅 결과."""
    original: str
    reformulated: str
    post_coord_hint: Optional[str]
    confidence: float
    cached: bool
    model_used: str          # "gemini-2.5-flash" | "claude-sonnet-4-6"
    backend: str             # "gemini" | "claude"
    tokens_input: int
    tokens_output: int
    cost_usd: float
    latency_ms: int
    rank_improvement: Optional[int] = None


# ─── BaseReformulator (Abstract) ────────────────────────────

class BaseReformulator(ABC):
    """Strategy 패턴 기반 추상 리포매터."""

    MODEL_ID: str = ""
    BACKEND_NAME: str = ""
    CACHE_FILE_NAME: str = ""  # reformulations_{backend}.json

    def _get_cache_path(self) -> Path:
        return _CACHE_DIR / self.CACHE_FILE_NAME

    def _load_cache(self) -> dict:
        path = self._get_cache_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self, cache: dict) -> None:
        path = self._get_cache_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

    def _make_cache_key(self, query: str) -> str:
        raw = f"{query}|{self.BACKEND_NAME}|{self.MODEL_ID}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @abstractmethod
    def _call_api(self, query: str) -> dict:
        """API 호출 → {reformulated, post_coord_hint, confidence, reasoning, tokens_in, tokens_out, cost, latency_ms}"""
        ...

    def reformulate(self, query: str) -> ReformulatedQuery:
        """쿼리를 리포매팅한다.

        단계:
            1. L2 캐시 확인
            2. 캐시 miss 시 _call_api 호출 (3회 지수 백오프)
            3. confidence < 0.5 시 원본 사용
            4. 결과 캐싱 후 반환
            5. API 키 미설정 또는 오류 시 fallback (confidence=0.0)
        """
        cache = self._load_cache()
        key = self._make_cache_key(query)

        # L2 캐시 히트
        if key in cache:
            logger.info(f"[{self.BACKEND_NAME}] L2 캐시 히트: {query}")
            entry = cache[key]
            return ReformulatedQuery(
                original=query,
                reformulated=entry.get("reformulated", query),
                post_coord_hint=entry.get("post_coord_hint"),
                confidence=entry.get("confidence", 0.0),
                cached=True,
                model_used=self.MODEL_ID,
                backend=self.BACKEND_NAME,
                tokens_input=entry.get("tokens_in", 0),
                tokens_output=entry.get("tokens_out", 0),
                cost_usd=entry.get("cost", 0.0),
                latency_ms=entry.get("latency_ms", 0),
            )

        # API 호출 (3회 지수 백오프)
        raw: Optional[dict] = None
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                raw = self._call_api(query)
                break
            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(f"[{self.BACKEND_NAME}] API 호출 실패 ({attempt+1}/3): {e}. {wait}초 대기")
                time.sleep(wait)

        if raw is None:
            logger.error(f"[{self.BACKEND_NAME}] API 최종 실패: {last_error}. 원본 쿼리 반환.")
            return ReformulatedQuery(
                original=query,
                reformulated=query,
                post_coord_hint=None,
                confidence=0.0,
                cached=False,
                model_used=self.MODEL_ID,
                backend=f"{self.BACKEND_NAME}-fallback",
                tokens_input=0,
                tokens_output=0,
                cost_usd=0.0,
                latency_ms=0,
            )

        # confidence < 0.5 시 원본 사용
        reformulated_text = raw.get("reformulated", query)
        confidence = raw.get("confidence", 0.0)
        if confidence < 0.5:
            logger.info(f"[{self.BACKEND_NAME}] confidence={confidence:.2f} < 0.5, 원본 사용: {query}")
            reformulated_text = query

        # L2 캐시 저장
        cache[key] = {
            "reformulated": raw.get("reformulated", query),
            "post_coord_hint": raw.get("post_coord_hint"),
            "confidence": confidence,
            "reasoning": raw.get("reasoning", ""),
            "tokens_in": raw.get("tokens_in", 0),
            "tokens_out": raw.get("tokens_out", 0),
            "cost": raw.get("cost", 0.0),
            "latency_ms": raw.get("latency_ms", 0),
        }
        self._save_cache(cache)

        return ReformulatedQuery(
            original=query,
            reformulated=reformulated_text,
            post_coord_hint=raw.get("post_coord_hint"),
            confidence=confidence,
            cached=False,
            model_used=self.MODEL_ID,
            backend=self.BACKEND_NAME,
            tokens_input=raw.get("tokens_in", 0),
            tokens_output=raw.get("tokens_out", 0),
            cost_usd=raw.get("cost", 0.0),
            latency_ms=raw.get("latency_ms", 0),
        )


# ─── GeminiReformulator ─────────────────────────────────────

class GeminiReformulator(BaseReformulator):
    """Gemini 2.5 Flash 기반 리포매터.

    SDK: google-genai (google-generativeai 아님)
    가격 (2026): input $0.30/1M, output $2.50/1M
    Prompt Caching: Implicit (system_instruction 1024+ tokens 자동)
    """

    MODEL_ID = "gemini-2.5-flash"
    BACKEND_NAME = "gemini"
    CACHE_FILE_NAME = "reformulations_gemini.json"

    # 가격 상수
    _INPUT_PRICE_PER_M = 0.30
    _OUTPUT_PRICE_PER_M = 2.50

    def _call_api(self, query: str) -> dict:
        """Gemini API 호출 — JSON mode 사용."""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않음")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        t0 = time.perf_counter()
        response = client.models.generate_content(
            model=self.MODEL_ID,
            contents=f"Input query: {query}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=1024,
            ),
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # JSON 파싱
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(f"[Gemini] JSON 파싱 실패: {e}. 응답: {response.text[:200]}")
            raise ValueError(f"JSON 파싱 실패: {e}") from e

        # 토큰 카운트 & 비용
        try:
            in_tok = response.usage_metadata.prompt_token_count or 0
            out_tok = response.usage_metadata.candidates_token_count or 0
        except (AttributeError, TypeError):
            in_tok, out_tok = 0, 0
        cost = (in_tok * self._INPUT_PRICE_PER_M + out_tok * self._OUTPUT_PRICE_PER_M) / 1_000_000

        return {
            **result,
            "tokens_in": in_tok,
            "tokens_out": out_tok,
            "cost": cost,
            "latency_ms": latency_ms,
        }


# ─── ClaudeReformulator ─────────────────────────────────────

class ClaudeReformulator(BaseReformulator):
    """Claude Sonnet 4.6 기반 리포매터.

    SDK: anthropic (기존 설치됨)
    가격 (2026): input $3/1M, output $15/1M
    Prompt Caching: Ephemeral (5분 TTL)
    주의: ANTHROPIC_API_KEY 미설정 시 graceful skip (FAIL 아님)
    """

    MODEL_ID = "claude-sonnet-4-6"
    BACKEND_NAME = "claude"
    CACHE_FILE_NAME = "reformulations_claude.json"

    # 가격 상수
    _INPUT_PRICE_PER_M = 3.0
    _OUTPUT_PRICE_PER_M = 15.0

    def _call_api(self, query: str) -> dict:
        """Claude API 호출 — prompt caching 포함."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않음")

        import anthropic

        client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 자동 인식
        t0 = time.perf_counter()
        message = client.messages.create(
            model=self.MODEL_ID,
            max_tokens=512,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # 5분 TTL 캐시
            }],
            messages=[{"role": "user", "content": f"입력 쿼리: {query}"}],
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # JSON 파싱
        try:
            result = json.loads(message.content[0].text)
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            logger.error(f"[Claude] JSON 파싱 실패: {e}")
            raise ValueError(f"JSON 파싱 실패: {e}") from e

        # 토큰 카운트 & 비용
        in_tok = message.usage.input_tokens
        out_tok = message.usage.output_tokens
        cost = (in_tok * self._INPUT_PRICE_PER_M + out_tok * self._OUTPUT_PRICE_PER_M) / 1_000_000

        return {
            **result,
            "tokens_in": in_tok,
            "tokens_out": out_tok,
            "cost": cost,
            "latency_ms": latency_ms,
        }


# ─── 팩토리 함수 ─────────────────────────────────────────────

def get_reformulator(backend: str = "gemini") -> BaseReformulator:
    """backend 이름으로 Reformulator 인스턴스를 반환한다.

    Args:
        backend: "gemini" | "claude"

    Returns:
        해당 backend의 BaseReformulator 구현체

    Raises:
        ValueError: 알 수 없는 backend 이름
    """
    registry: dict[str, type[BaseReformulator]] = {
        "gemini": GeminiReformulator,
        "claude": ClaudeReformulator,
    }
    if backend not in registry:
        raise ValueError(f"Unknown backend: {backend}. 사용 가능: {list(registry.keys())}")
    return registry[backend]()
