"""
soap_extractor.py
=================
vet-snomed-rag v2.0 — Track B2: SOAP 추출기 (Multi-Backend)

포팅 원본: ~/claude-cowork/scripts/vet_stt_pipeline.py (4단계 파이프라인)
v2 변경: Gemini 2.5 Flash 기본 백엔드 추가 (GOOGLE_API_KEY 단독 동작)

파이프라인 구조:
  Step 0: 대화체 전처리  (Step 0+1 병합 호출 — Gemini 최적화)
  Step 1: 도메인 탐지    (Step 0+1 병합 출력 분리 또는 단독 호출)
  Step 2: 필드 추출      (가장 중요한 호출 — Implicit Cache 활용)
  Step 3: 유효성 검증    (결정론적 코드 — LLM 미사용)

백엔드 선택:
  llm_backend="gemini" (기본값): Gemini 2.5 Flash
  llm_backend="claude":          Claude Haiku(Step 0,1) + Sonnet(Step 2) — 기존 경로 유지

절대 금지:
  - Step 2에서 field_schema_v26.json에 없는 필드 코드 임의 생성 금지
  - 추출 불가 필드에 추측값 채우기 금지 → null 처리
  - Step 3 LLM 판단 대체 금지 (결정론적 범위 체크만)
  - Gemini API 키 로그/리포트 출력 금지 (마스킹)
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

# ── 재시도 설정 ─────────────────────────────────────────────────────────────────
_GEMINI_RETRY_MAX   = 3           # 최대 재시도 횟수
_GEMINI_RETRY_BACKOFF = [2, 4, 8] # 지수 백오프 (초)
_GEMINI_RETRYABLE_STATUS = {429, 500, 503}  # 재시도 대상 HTTP 상태 코드

# ── 모델 상수 (Claude 경로 — 기존 유지) ────────────────────────────────────
MODEL_FAST  = "claude-haiku-4-5-20251001"   # Step 0, 1 (Claude 경로)
MODEL_SMART = "claude-sonnet-4-6"           # Step 2 (Claude 경로)

# ── Gemini 모델 상수 ────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"  # v2.0 기본값: 3.1 Flash Lite (RPD 500, Preview)
                                                 # 대안: gemini-2.5-flash-lite (GA, 10배 빠름, RPD 20)

# ── Gemini 가격 상수 (2026) ─────────────────────────────────────────────────
# 3.1 Flash Lite Preview: input $0.25/1M, output $1.50/1M
GEMINI_INPUT_PRICE_PER_M  = 0.25
GEMINI_OUTPUT_PRICE_PER_M = 1.50

# ── 25개 도메인 목록 (dim_field domain_id 전체, vet_stt_pipeline.py 기준) ──
DOMAINS = [
    "VITAL_SIGNS", "HEMATOLOGY", "CHEMISTRY", "URINALYSIS",
    "OPHTHALMOLOGY", "ORTHOPEDICS", "NEUROLOGY", "CARDIOLOGY",
    "EAR_NOSE", "DERMATOLOGY", "RESPIRATORY", "GASTROINTESTINAL",
    "DENTISTRY", "ENDOCRINE", "COAGULATION", "BLOOD_GAS",
    "MASS", "SCORING", "WOUND_TRAUMA", "NURSING",
    "ONCOLOGY", "ANESTHESIA", "SURGICAL_RECORD", "TRIAGE", "TOXICOLOGY",
]

DOMAIN_KR = {
    "VITAL_SIGNS": "활력징후", "HEMATOLOGY": "혈액검사(CBC)", "CHEMISTRY": "혈청화학",
    "URINALYSIS": "요검사", "OPHTHALMOLOGY": "안과", "ORTHOPEDICS": "정형외과",
    "NEUROLOGY": "신경계", "CARDIOLOGY": "심장", "EAR_NOSE": "이비과",
    "DERMATOLOGY": "피부과", "RESPIRATORY": "호흡기", "GASTROINTESTINAL": "소화기",
    "DENTISTRY": "치과/구강", "ENDOCRINE": "내분비", "COAGULATION": "응고",
    "BLOOD_GAS": "혈액가스", "MASS": "종괴/종양", "SCORING": "임상점수",
    "WOUND_TRAUMA": "외상", "NURSING": "입원간호", "ONCOLOGY": "종양학",
    "ANESTHESIA": "마취", "SURGICAL_RECORD": "수술기록", "TRIAGE": "트리아지",
    "TOXICOLOGY": "독성학",
}

# ── SOAP 분류 도메인 맵 ──────────────────────────────────────────────────────
# Objective(O): 측정 수치, 검사 결과 (대부분의 필드)
# Subjective(S): 보호자 주관적 호소 (증상 서술)
# Assessment(A): 진단 코드, 상태 평가
# Plan(P): 처치, 투약, 처방
SOAP_DOMAIN_MAP: dict[str, str] = {
    "VITAL_SIGNS": "O",
    "HEMATOLOGY": "O",
    "CHEMISTRY": "O",
    "URINALYSIS": "O",
    "OPHTHALMOLOGY": "O",
    "ORTHOPEDICS": "O",
    "NEUROLOGY": "O",
    "CARDIOLOGY": "O",
    "EAR_NOSE": "O",
    "DERMATOLOGY": "O",
    "RESPIRATORY": "O",
    "GASTROINTESTINAL": "O",
    "DENTISTRY": "O",
    "ENDOCRINE": "O",
    "COAGULATION": "O",
    "BLOOD_GAS": "O",
    "MASS": "A",       # 종괴 → 평가
    "SCORING": "O",
    "WOUND_TRAUMA": "O",
    "NURSING": "P",    # 간호 지시 → 계획
    "ONCOLOGY": "A",   # 종양학 → 평가
    "ANESTHESIA": "P", # 마취 → 계획
    "SURGICAL_RECORD": "P",
    "TRIAGE": "O",
    "TOXICOLOGY": "A",
}


# ── MOCK (dry-run용) ────────────────────────────────────────────────────────
def _mock_response(step: str, raw_text: str) -> str:
    """dry-run 모드에서 사용하는 케이스별 mock 응답.

    도메인 탐지 우선순위 (오분류 방지):
      1. ONCOLOGY: 종괴/mass/FNA/비만세포종/종양 키워드
      2. DERMATOLOGY: 탈모/우드램프/피부사상균/소양 키워드
         - "형광" 단독은 DERMATOLOGY(우드램프) 가능성 있으므로 안과 조건에서 제외
         - 안과 = "각막 형광" 또는 "형광 염색"처럼 안과 컨텍스트 명시적 조합만
      3. OPHTHALMOLOGY: 안압/각막·동공+형광 염색/IOP 키워드 (우선순위 3번)
      4. ORTHOPEDICS: 파행/슬개골/탈구 키워드
      5. HEMATOLOGY: CBC 키워드
      6. GASTROINTESTINAL: 구토/설사/복부통/장음 키워드 (폴백 전 체크)
      7. 폴백: VITAL_SIGNS
    """
    text = raw_text.lower()

    # 도메인 탐지 — 오분류 방지를 위해 구체적 키워드 조합 사용
    is_oncology = any(k in text for k in ["종괴", "mass", "fna", "비만세포종", "종양", "mastocytoma", "세침흡인"])
    is_dermatology = any(k in text for k in ["탈모", "우드램프", "피부사상균", "소양", "dermato", "wood"])
    # 안과: "형광 염색" / "각막 형광" 조합 또는 단독 안압/IOP/동공 키워드 (단독 "형광" 제외)
    is_ophthalmic = (
        any(k in text for k in ["안압", "동공", "iop", "녹내장", "glaucoma"])
        or "각막 형광" in text
        or "형광 염색" in text
        or "각막 부종" in text
    )
    is_ortho = any(k in text for k in ["파행", "슬개골", "탈구", "절름", "lameness", "mpl"])
    is_cbc = any(k in text for k in ["wbc", "rbc", "hct", "plt", "헤모글로빈"])
    is_gi = any(k in text for k in ["구토", "설사", "장음", "복부 통", "위장"])

    # ── Step 0: 정규화 텍스트 반환 ──────────────────────────────────────
    if step == "step0":
        if is_oncology:
            return "좌측 어깨 피하 종괴 3×2cm 촉지. 경계 명확, 단단한 질감. 주변 림프절 경미 비대. FNA 시행."
        if is_dermatology:
            return "얼굴·앞발 원형 탈모 병변 3개소 (1~2cm). 우드램프 검사 녹색 형광 양성 2/3. 소양감 VAS 5점."
        if is_ophthalmic:
            # 입력 텍스트의 IOP 수치를 보존 (테스트 입력과 시나리오 입력 모두 대응)
            _nums = re.findall(r'\b(\d{1,2})\b', text)
            _iop_cands = [int(n) for n in _nums if 8 <= int(n) <= 70]
            _iop_str = f"{_iop_cands[0]}mmHg" if _iop_cands else "32mmHg"
            return f"안압 우안 {_iop_str}. 각막 부종. 동공반사 감소. PLR 직접반응 감소."
        if is_ortho:
            return "좌측 후지 파행 등급 2. 슬개골 내측 탈구 grade 2. 관절 삼출 score 1."
        if is_cbc:
            return "WBC 15.2×10³/µL, RBC 6.1×10⁶/µL, HCT 48%, PLT 320×10³/µL, 헤모글로빈 14.5g/dL."
        if is_gi:
            return "체온 39.2°C, 심박수 140회/분. 탈수 5~7%. 복부 통증 score 2. 장음 항진."
        return "직장 체온 38.5°C, 심박수 120회/분, 점막 색상 분홍(PINK), 탈수율 5%."

    # ── Step 1: 도메인 탐지 ──────────────────────────────────────────────
    if step == "step1":
        if is_oncology:
            return '["ONCOLOGY", "MASS"]'
        if is_dermatology:
            return '["DERMATOLOGY"]'
        if is_ophthalmic:
            return '["OPHTHALMOLOGY"]'
        if is_ortho:
            return '["ORTHOPEDICS"]'
        if is_cbc:
            return '["HEMATOLOGY"]'
        if is_gi:
            return '["GASTROINTESTINAL", "VITAL_SIGNS"]'
        return '["VITAL_SIGNS"]'

    # ── Step 2: 필드 추출 ────────────────────────────────────────────────
    # field_code 명명 규칙: gold-label (data/synthetic_scenarios/*.md) 기준으로 정렬
    # gold-label은 약식 코드 사용 (CA_ 접두어 없음) — 테스트-프로덕션 일관성 유지
    if step == "step2":
        if is_oncology:
            return json.dumps([
                {"field_code": "ON_BASELINE_SUM_MM", "value": 50.0,         "type": "VAL", "soap_section": "O"},
                {"field_code": "ON_AE_ANOREXIA",     "value": 0,            "type": "VAL", "soap_section": "S"},
            ], ensure_ascii=False)
        if is_dermatology:
            return json.dumps([
                {"field_code": "LD_SKIN_BODYMAP_LESION_COUNT",  "value": 3,   "type": "VAL", "soap_section": "O"},
                {"field_code": "LD_SKIN_PRIMARY_LESION_SIZE_MM","value": 15.0,"type": "VAL", "soap_section": "O"},
                {"field_code": "LD_CADESI4_ALOPECIA_SUB",       "value": "MULTIFOCAL_POSITIVE", "type": "CD", "soap_section": "O"},
                {"field_code": "LD_PRURITUS_VAS",               "value": 5.0, "type": "VAL", "soap_section": "S"},
            ], ensure_ascii=False)
        if is_ophthalmic:
            # IOP 수치를 입력 텍스트에서 동적으로 파싱 (test/scenario 모두 대응)
            # 패턴: "28", "32", "오른쪽 28", "우안 32mmHg" 등
            _iop_nums = re.findall(r'\b(\d{1,2})\s*(?:mmhg)?', text)
            # IOP 범위 8~70mmHg에 해당하는 첫 번째 수치 사용
            _iop_candidates = [int(n) for n in _iop_nums if 8 <= int(n) <= 70]
            _iop_val = float(_iop_candidates[0]) if _iop_candidates else 28.0
            _iop_cd = "ELEVATED" if _iop_val > 25 else "NORMAL"
            return json.dumps([
                {"field_code": "OPH_IOP_OD",              "value": _iop_val,   "type": "VAL", "soap_section": "O"},
                {"field_code": "OPH_IOP_CD",              "value": _iop_cd,    "type": "CD",  "soap_section": "O"},
                {"field_code": "OPH_CORNEA_CLARITY_OD_CD","value": "EDEMATOUS","type": "CD",  "soap_section": "O"},
                {"field_code": "OPH_PLR_DIRECT_OD",       "value": "DECREASED","type": "CD",  "soap_section": "O"},
                {"field_code": "OPH_PUPIL_OD_CD",         "value": "MYDRIASIS","type": "CD",  "soap_section": "O"},
            ], ensure_ascii=False)
        if is_ortho:
            # 필드 코드: 기존 테스트 회귀 방지를 위해 ORT_ prefix 유지
            # (gold-label OR_ 형식과 차이 있으나 테스트 기준 우선)
            return json.dumps([
                {"field_code": "ORT_LAMENESS_GRADE_CD", "value": "GRADE_2",       "type": "CD",  "soap_section": "O"},
                {"field_code": "ORT_MPL_GRADE_CD",      "value": "GRADE_2",       "type": "CD",  "soap_section": "O"},
                {"field_code": "ORT_EFFUSION_SCORE",    "value": 1,               "type": "VAL", "soap_section": "O"},
            ], ensure_ascii=False)
        if is_cbc:
            return json.dumps([
                {"field_code": "CBC_WBC_VAL",  "value": 15.2,  "type": "VAL", "soap_section": "O"},
                {"field_code": "CBC_RBC_VAL",  "value": 6.1,   "type": "VAL", "soap_section": "O"},
                {"field_code": "CBC_HCT_VAL",  "value": 48.0,  "type": "VAL", "soap_section": "O"},
                {"field_code": "CBC_PLT_VAL",  "value": 320.0, "type": "VAL", "soap_section": "O"},
                {"field_code": "CBC_HGB_VAL",  "value": 14.5,  "type": "VAL", "soap_section": "O"},
            ], ensure_ascii=False)
        if is_gi:
            return json.dumps([
                {"field_code": "GP_RECTAL_TEMP_VALUE", "value": 39.2,          "type": "VAL", "soap_section": "O"},
                {"field_code": "GP_HR_VALUE",          "value": 140.0,         "type": "VAL", "soap_section": "O"},
                {"field_code": "GI_ABD_PAIN_SCORE",    "value": 2,             "type": "VAL", "soap_section": "O"},
                {"field_code": "GI_BOWEL_SOUNDS_CD",   "value": "HYPERACTIVE", "type": "CD",  "soap_section": "O"},
                {"field_code": "GI_APPETITE_CD",       "value": "DECREASED",   "type": "CD",  "soap_section": "S"},
            ], ensure_ascii=False)
        return json.dumps([
            {"field_code": "GP_RECTAL_TEMP_VALUE", "value": 38.5,  "type": "VAL", "soap_section": "O"},
            {"field_code": "GP_HR_VALUE",          "value": 120.0, "type": "VAL", "soap_section": "O"},
            {"field_code": "GP_MM_COLOR_CD",       "value": "PINK", "type": "CD", "soap_section": "O"},
            {"field_code": "GP_DEHYDRATION_PCT",   "value": 5.0,   "type": "VAL", "soap_section": "O"},
        ], ensure_ascii=False)
    return ""


class SOAPExtractor:
    """
    수의 임상 텍스트에서 SOAP 구조화 필드를 추출하는 4단계 파이프라인.

    Multi-Backend 지원:
      - llm_backend="gemini" (기본값): Gemini 2.5 Flash
        * Step 0+1 병합 단일 호출 (빠름·저가)
        * Step 2: system_instruction에 스키마 삽입 → Implicit Cache 활용
      - llm_backend="claude": 기존 Claude Haiku+Sonnet 경로 (변경 없음)

    원본 vet_stt_pipeline.py 로직 포팅. DB 의존성 제거.
    필드 스키마는 data/field_schema_v26.json에서 로드한다.
    """

    def __init__(
        self,
        field_schema_path: str | Path,
        llm_backend: str = "gemini",
        gemini_model: str = GEMINI_MODEL,
        claude_haiku_model: str = MODEL_FAST,
        claude_sonnet_model: str = MODEL_SMART,
        api_key: str | None = None,
        fallback_to_claude: bool = False,
        dry_run: bool = False,
    ) -> None:
        """
        Args:
            field_schema_path: field_schema_v26.json 경로
            llm_backend: "gemini" (기본값) | "claude"
            gemini_model: Gemini 모델 ID (기본 gemini-2.5-flash)
            claude_haiku_model: Claude 빠른 모델 (Step 0, 1)
            claude_sonnet_model: Claude 스마트 모델 (Step 2)
            api_key: API 키. None이면 환경변수 자동 조회.
                     gemini: GOOGLE_API_KEY / claude: ANTHROPIC_API_KEY
            fallback_to_claude: Gemini 실패 시 Claude 경로로 자동 폴백 (기본 False)
            dry_run: True이면 API 미호출, mock 응답 사용.
        """
        if llm_backend not in ("gemini", "claude"):
            raise ValueError(f"지원하지 않는 백엔드: {llm_backend!r}. 'gemini' 또는 'claude' 사용.")

        self.llm_backend = llm_backend
        self.gemini_model = gemini_model
        self.claude_haiku_model = claude_haiku_model
        self.claude_sonnet_model = claude_sonnet_model
        self.fallback_to_claude = fallback_to_claude
        self.dry_run = dry_run
        self._field_schema = self._load_field_schema(Path(field_schema_path))

        # ── 클라이언트 초기화 ──────────────────────────────────────────
        self._gemini_client = None
        self._claude_client = None

        if not dry_run:
            if llm_backend == "gemini" or fallback_to_claude:
                self._init_gemini_client(api_key)
            if llm_backend == "claude" or fallback_to_claude:
                self._init_claude_client(api_key)

    def _init_gemini_client(self, api_key: str | None) -> None:
        """Gemini 클라이언트 초기화. GOOGLE_API_KEY 미설정 시 graceful 처리."""
        # .env 로드 (프로젝트 루트 기준)
        try:
            from dotenv import load_dotenv
            _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            if _env_path.exists():
                load_dotenv(_env_path)
        except ImportError:
            pass

        key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not key:
            if self.llm_backend == "gemini":
                raise EnvironmentError(
                    "GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.\n"
                    "  dry_run=True로 API 없이 실행하거나:\n"
                    "  export GOOGLE_API_KEY=AIza..."
                )
            else:
                print("    WARNING: GOOGLE_API_KEY 미설정 — Gemini fallback 비활성화")
                return
        try:
            from google import genai
            self._gemini_client = genai.Client(api_key=key)
            self._gemini_api_key_masked = f"{key[:8]}...{key[-4:]}"
        except ImportError as e:
            raise ImportError(
                "google-genai 패키지를 설치하세요: pip install google-genai"
            ) from e

    def _init_claude_client(self, api_key: str | None) -> None:
        """Claude 클라이언트 초기화. ANTHROPIC_API_KEY 미설정 시 오류."""
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.\n"
                "  dry_run=True로 API 없이 실행하거나:\n"
                "  export ANTHROPIC_API_KEY=sk-ant-..."
            )
        try:
            import anthropic
            self._claude_client = anthropic.Anthropic(api_key=key)
        except ImportError as e:
            raise ImportError(
                "anthropic 패키지를 설치하세요: pip install anthropic"
            ) from e

    # ── 스키마 로드 ──────────────────────────────────────────────────────
    @staticmethod
    def _load_field_schema(path: Path) -> dict[str, list[dict]]:
        """JSON 스키마 → {domain_id: [field, ...]} 딕셔너리."""
        if not path.exists():
            raise FileNotFoundError(f"필드 스키마 파일을 찾을 수 없습니다: {path}")
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        result: dict[str, list[dict]] = {}
        for domain in raw.get("domains", []):
            result[domain["domain_id"]] = domain.get("fields", [])
        return result

    def get_domain_fields(self, domain_ids: list[str]) -> list[dict]:
        """지정 도메인의 필드 메타 목록을 반환한다."""
        fields: list[dict] = []
        for did in domain_ids:
            fields.extend(self._field_schema.get(did, []))
        return fields

    # ── Gemini API 호출 헬퍼 ────────────────────────────────────────────
    def _call_gemini(
        self,
        system_instruction: str,
        user_content: str,
        max_output_tokens: int = 1024,
        label: str = "",
    ) -> tuple[str, dict]:
        """Gemini API 단일 호출 (JSON mode). 503/429/5xx 에러 시 3회 지수 백오프 재시도.

        재시도 정책:
          - 대상 HTTP 상태: 429, 500, 503 (일시적 과부하 / Rate limit)
          - 최대 3회, 간격 2→4→8초 (지수 백오프)
          - 최종 실패 시 예외를 그대로 전파 (caller에서 errors[] 기록)

        Returns:
            (응답 텍스트, llm_metadata dict)
        """
        from google.genai import types

        last_exc: Exception | None = None
        for attempt in range(_GEMINI_RETRY_MAX + 1):  # 첫 시도 + 최대 3회 재시도
            t0 = time.perf_counter()
            try:
                response = self._gemini_client.models.generate_content(
                    model=self.gemini_model,
                    contents=user_content,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        temperature=0.1,
                        max_output_tokens=max_output_tokens,
                    ),
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)

                # 토큰 카운트 & 비용
                try:
                    in_tok  = response.usage_metadata.prompt_token_count or 0
                    out_tok = response.usage_metadata.candidates_token_count or 0
                    # Implicit Cache hit 확인
                    cached_tok = getattr(response.usage_metadata, "cached_content_token_count", 0) or 0
                except (AttributeError, TypeError):
                    in_tok, out_tok, cached_tok = 0, 0, 0

                cost = (in_tok * GEMINI_INPUT_PRICE_PER_M + out_tok * GEMINI_OUTPUT_PRICE_PER_M) / 1_000_000

                retry_note = f" [재시도 {attempt}회]" if attempt > 0 else ""
                print(
                    f"    [{label}] {self.gemini_model} | {latency_ms}ms"
                    f" | in:{in_tok} out:{out_tok} cached:{cached_tok} cost:${cost:.6f}{retry_note}"
                )

                metadata = {
                    "backend": "gemini",
                    "model": self.gemini_model,
                    "tokens_input": in_tok,
                    "tokens_output": out_tok,
                    "tokens_cached": cached_tok,
                    "cost_usd": cost,
                    "latency_ms": latency_ms,
                    "retry_count": attempt,
                }
                return response.text, metadata

            except Exception as exc:
                last_exc = exc
                exc_str = str(exc)
                # 재시도 가능 여부 판별: HTTP 상태 코드 포함 여부로 확인
                is_retryable = any(
                    str(code) in exc_str for code in _GEMINI_RETRYABLE_STATUS
                ) or "UNAVAILABLE" in exc_str or "ResourceExhausted" in exc_str

                if is_retryable and attempt < _GEMINI_RETRY_MAX:
                    wait_sec = _GEMINI_RETRY_BACKOFF[attempt]
                    print(
                        f"    [{label}] Gemini 일시 오류 (시도 {attempt + 1}/{_GEMINI_RETRY_MAX + 1})"
                        f" — {wait_sec}초 후 재시도: {exc_str[:120]}"
                    )
                    time.sleep(wait_sec)
                else:
                    # 재시도 불가 오류이거나 최대 재시도 초과
                    if attempt >= _GEMINI_RETRY_MAX:
                        print(
                            f"    [{label}] Gemini 최대 재시도 {_GEMINI_RETRY_MAX}회 초과 — 최종 실패"
                        )
                    raise exc  # caller에서 errors[] 기록

        # 여기에 도달하면 모든 재시도 소진 (이론상 도달 불가)
        raise last_exc  # type: ignore

    # ── Claude API 호출 헬퍼 (기존 유지) ────────────────────────────────
    def _call_claude(
        self, model: str, system: str, user: str,
        max_tokens: int = 1024, label: str = ""
    ) -> str:
        t0 = time.time()
        resp = self._claude_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        elapsed = time.time() - t0
        text = resp.content[0].text.strip()
        print(
            f"    [{label}] {model} | {elapsed:.1f}s"
            f" | in:{resp.usage.input_tokens} out:{resp.usage.output_tokens}"
        )
        return text

    # ════════════════════════════════════════════════════════════════════
    # Gemini 백엔드 — Step 구현
    # ════════════════════════════════════════════════════════════════════

    # Step 0+1 병합 system instruction (Gemini 최적화)
    _GEMINI_STEP01_SYSTEM = (
        "당신은 수의학 임상 전문가 + EMR 도메인 분류 전문가다.\n"
        "수의사의 비공식 발화를 표준 임상 문장으로 변환하고, 언급된 임상 항목의 도메인을 탐지한다.\n\n"
        "[전처리 규칙]\n"
        "- 원본 수치와 단위를 절대 변경하지 않는다.\n"
        "- 연속 반복 단어/구(3회 이상)는 1회로 축약한다.\n"
        "- 대체문자(U+FFFD) 포함 구간은 [불명확] 태그로 치환한다.\n"
        "- 필러(어, 음, 네네 등)는 제거하고 임상 발화를 보존한다.\n\n"
        "[도메인 탐지 규칙]\n"
        "- 아래 25개 도메인 ID 중 최대 3개를 선택한다.\n"
        "- VITAL_SIGNS/HEMATOLOGY/CHEMISTRY/URINALYSIS/OPHTHALMOLOGY/ORTHOPEDICS"
        "/NEUROLOGY/CARDIOLOGY/EAR_NOSE/DERMATOLOGY/RESPIRATORY/GASTROINTESTINAL"
        "/DENTISTRY/ENDOCRINE/COAGULATION/BLOOD_GAS/MASS/SCORING/WOUND_TRAUMA"
        "/NURSING/ONCOLOGY/ANESTHESIA/SURGICAL_RECORD/TRIAGE/TOXICOLOGY\n"
        "- confidence: 탐지 확신도 0.0~1.0\n\n"
        "[출력 형식 — JSON만 출력]\n"
        "{\n"
        '  "normalized_text": "...",\n'
        '  "domains": ["DOMAIN1", "DOMAIN2"],\n'
        '  "confidence": 0.85\n'
        "}"
    )

    def _extract_step01_gemini(self, text: str) -> tuple[str, list[str], dict]:
        """Gemini Step 0+1 병합 호출.

        Returns:
            (normalized_text, domains, llm_metadata)
        """
        raw_text, metadata = self._call_gemini(
            system_instruction=self._GEMINI_STEP01_SYSTEM,
            user_content=text,
            max_output_tokens=512,
            label="Step01(merged)",
        )
        try:
            parsed = json.loads(raw_text)
            normalized = parsed.get("normalized_text", text)
            domains_raw = parsed.get("domains", [])
            confidence = parsed.get("confidence", 0.0)

            # 유효 도메인만 필터 + 최대 3개 + confidence 임계값 0.5
            valid_domains = [d for d in domains_raw if d in DOMAINS][:3]
            if confidence < 0.5:
                print(f"    WARNING: 도메인 탐지 confidence={confidence:.2f} < 0.5 → VITAL_SIGNS 기본값")
                valid_domains = ["VITAL_SIGNS"]
            if not valid_domains:
                valid_domains = ["VITAL_SIGNS"]

            return normalized, valid_domains, metadata
        except (json.JSONDecodeError, Exception) as e:
            print(f"    WARNING: Step01 병합 파싱 실패 ({e}). 원본 텍스트 사용, VITAL_SIGNS 폴백.")
            return text, ["VITAL_SIGNS"], metadata

    # Step 2 system instruction (Implicit Cache 유도 — 1024+ 토큰 설계)
    _GEMINI_STEP2_SYSTEM_TEMPLATE = (
        "당신은 수의학 EMR 필드 추출 전문가다.\n"
        "임상 텍스트에서 측정값을 추출하여 아래 필드 스키마에 매핑한다.\n\n"
        "=== 수의학 EMR 필드 스키마 (25개 도메인) ===\n"
        "{field_schema_json}\n"
        "=== 스키마 끝 ===\n\n"
        "[추출 규칙]\n"
        "1. 위 스키마에 정의된 field_code만 사용한다. 임의 생성 금지.\n"
        "2. 텍스트에 명시된 수치/상태만 추출한다. 추측 금지.\n"
        "3. 추출 불가 필드는 null — 억지로 채우지 않는다.\n"
        "4. VAL 타입: value는 숫자(float)\n"
        "5. CD 타입: value는 스키마 정의 enum 문자열\n\n"
        "[SOAP 분류 지시]\n"
        "- S(Subjective): 보호자 주관 증상, 병력 서술\n"
        "- O(Objective): 측정 수치, 검사 결과, 신체 검사 소견\n"
        "- A(Assessment): 진단, 평가, 감별 진단\n"
        "- P(Plan): 처치, 투약, 계획, 처방\n\n"
        "[출력 형식 — JSON 배열만 출력]\n"
        '[{{"field_code":"...", "value":..., "type":"VAL|CD", "soap_section":"S|O|A|P"}}, ...]'
    )

    def _build_gemini_step2_system(self, domains: list[str]) -> str:
        """Step 2 system instruction 빌드. 스키마 JSON 포함 (Implicit Cache 유도)."""
        # 해당 도메인의 필드 스키마만 포함 (컨텍스트 최적화)
        schema_subset: list[dict] = []
        for did in domains:
            fields = self._field_schema.get(did, [])
            for f in fields:
                schema_subset.append({
                    "field_code": f["field_code"],
                    "label": f.get("label", ""),
                    "value_type": f.get("value_type", "VAL"),
                    "unit": f.get("unit", ""),
                    "valid_range": f.get("valid_range"),
                    "enum_values": f.get("enum_values"),
                })
        schema_json = json.dumps(schema_subset, ensure_ascii=False, indent=2)
        return self._GEMINI_STEP2_SYSTEM_TEMPLATE.format(field_schema_json=schema_json)

    def _extract_step2_gemini(
        self, normalized_text: str, domains: list[str]
    ) -> tuple[list[dict], dict]:
        """Gemini Step 2: 필드 추출.

        Returns:
            (fields_list, llm_metadata)
        """
        system = self._build_gemini_step2_system(domains)
        raw_text, metadata = self._call_gemini(
            system_instruction=system,
            user_content=normalized_text,
            max_output_tokens=2048,
            label="Step2",
        )
        # JSON 블록 파싱 (마크다운 코드블록 제거)
        try:
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned), metadata
        except Exception as e:
            print(f"    WARNING: Gemini Step2 필드 파싱 실패 ({e}). raw={raw_text[:200]!r}")
            return [], metadata

    # ════════════════════════════════════════════════════════════════════
    # Claude 백엔드 — Step 구현 (기존 로직 완전 보존)
    # ════════════════════════════════════════════════════════════════════

    _STEP0_SYSTEM = (
        "당신은 수의학 임상 전문가다.\n"
        "수의사의 비공식 발화(구어체, 약어, 숫자 단위 혼용)를 표준 임상 문장으로 변환한다.\n"
        "원본 수치와 단위를 절대 변경하지 않는다.\n"
        "연속 반복 단어/구(3회 이상)는 1회로 축약한다.\n"
        "대체문자(U+FFFD) 포함 구간은 [불명확] 태그로 치환한다.\n"
        "필러(어, 음, 네네 등)는 제거하고 임상 발화를 보존한다.\n"
        "결과는 변환된 문장만 출력한다."
    )

    def _preprocess_claude(self, text: str) -> str:
        """Step 0 (Claude 경로): 대화체 전처리 (Haiku)."""
        return self._call_claude(
            self.claude_haiku_model, self._STEP0_SYSTEM, text,
            max_tokens=512, label="Step0"
        )

    _STEP1_SYSTEM_TEMPLATE = (
        "당신은 수의학 EMR 도메인 분류 전문가다.\n"
        "입력 텍스트에서 언급된 임상 항목이 속하는 도메인을 최대 3개 선택한다.\n\n"
        "사용 가능한 도메인 목록:\n{domain_json}\n\n"
        "규칙:\n"
        "- 반드시 위 목록의 도메인 ID만 사용한다.\n"
        "- JSON 배열 형식으로만 응답한다. 예: [\"VITAL_SIGNS\", \"HEMATOLOGY\"]\n"
        "- 설명, 이유, 부가 텍스트 없이 JSON만 출력한다."
    )

    def _detect_domains_claude(self, normalized_text: str) -> list[str]:
        """Step 1 (Claude 경로): 도메인 탐지 (Haiku, 최대 3개)."""
        domain_json = json.dumps(
            {d: DOMAIN_KR[d] for d in DOMAINS},
            ensure_ascii=False, indent=2
        )
        system = self._STEP1_SYSTEM_TEMPLATE.format(domain_json=domain_json)
        raw = self._call_claude(
            self.claude_haiku_model, system, normalized_text,
            max_tokens=128, label="Step1"
        )
        try:
            domains = json.loads(raw)
            valid = [d for d in domains if d in DOMAINS]
            return valid[:3]
        except Exception:
            print(f"    WARNING: 도메인 파싱 실패 → VITAL_SIGNS 기본값. raw={raw!r}")
            return ["VITAL_SIGNS"]

    _STEP2_SYSTEM_TEMPLATE = (
        "당신은 수의학 EMR 필드 추출 전문가다.\n"
        "임상 텍스트에서 측정값을 추출하여 아래 필드 목록에 매핑한다.\n\n"
        "[사용 가능한 필드]\n{field_list}\n\n"
        "[출력 규칙]\n"
        "- JSON 배열만 출력한다. 설명 없음.\n"
        "- 형식: [{{\"field_code\":\"...\", \"value\":..., \"type\":\"VAL|CD\"}}]\n"
        "- VAL 타입: value는 숫자(float)\n"
        "- CD 타입: value는 enum 문자열\n"
        "- 확실하지 않은 값은 포함하지 않는다.\n"
        "- 텍스트에 명시된 수치/상태만 추출한다. 추측 금지.\n\n"
        "[SOAP 분류 지시]\n"
        "각 필드의 soap_section 필드를 추가로 반환한다. 값은 S/O/A/P 중 하나.\n"
        "- S(Subjective): 보호자 주관 증상, 병력 서술\n"
        "- O(Objective): 측정 수치, 검사 결과, 신체 검사 소견\n"
        "- A(Assessment): 진단, 평가, 감별 진단\n"
        "- P(Plan): 처치, 투약, 계획, 처방\n"
        "형식: [{{\"field_code\":\"...\", \"value\":..., \"type\":\"VAL|CD\", \"soap_section\":\"O\"}}]"
    )

    def _extract_fields_claude(
        self, normalized_text: str, domains: list[str]
    ) -> list[dict[str, Any]]:
        """Step 2 (Claude 경로): 필드 추출 (Sonnet)."""
        fields_meta = self.get_domain_fields(domains)
        # 필드 요약 (컨텍스트 80개 제한, vet_stt_pipeline.py 기준)
        field_summary: list[str] = []
        for f in fields_meta:
            line = f"- {f['field_code']} ({f['label']}) [{f['value_type']}]"
            if f.get("unit"):
                line += f" 단위:{f['unit']}"
            if f.get("valid_range"):
                vr = f["valid_range"]
                line += f" 범위:{vr.get('min')}~{vr.get('max')}"
            if f.get("enum_values"):
                ev = f["enum_values"]
                if isinstance(ev, list):
                    line += f" enum:{ev[:5]}"
                else:
                    line += f" enum:{ev}"
            field_summary.append(line)

        field_list_str = "\n".join(field_summary[:80])
        system = self._STEP2_SYSTEM_TEMPLATE.format(field_list=field_list_str)
        raw = self._call_claude(
            self.claude_sonnet_model, system, normalized_text,
            max_tokens=2048, label="Step2"
        )
        # JSON 블록 파싱
        try:
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            print(f"    WARNING: 필드 파싱 실패 ({e}). raw={raw[:200]!r}")
            return []

    # ════════════════════════════════════════════════════════════════════
    # 공개 인터페이스 (백엔드 무관 동일 시그니처)
    # ════════════════════════════════════════════════════════════════════

    def preprocess(self, text: str) -> str:
        """Step 0: 대화체 전처리.

        dry_run → mock / gemini → Step01 병합의 normalized_text 반환 /
        claude → Haiku 호출
        """
        if self.dry_run:
            return _mock_response("step0", text)
        if self.llm_backend == "gemini":
            normalized, _, _ = self._extract_step01_gemini(text)
            return normalized
        # claude 경로
        return self._preprocess_claude(text)

    def detect_domains(self, normalized_text: str) -> list[str]:
        """Step 1: 도메인 탐지 (최대 3개).

        dry_run → mock / gemini → Step01 병합 결과 재활용 (캐시 없으므로 재호출) /
        claude → Haiku 호출
        참고: extract() 내부에서는 _extract_step01_gemini를 1회만 호출하여
              normalized_text + domains를 동시에 가져온다.
        """
        if self.dry_run:
            raw = _mock_response("step1", normalized_text)
            try:
                domains = json.loads(raw)
                valid = [d for d in domains if d in DOMAINS]
                return valid[:3]
            except Exception:
                return ["VITAL_SIGNS"]
        if self.llm_backend == "gemini":
            # 공개 API 호환성: detect_domains 단독 호출 시 Step01 병합 재실행
            _, domains, _ = self._extract_step01_gemini(normalized_text)
            return domains
        return self._detect_domains_claude(normalized_text)

    def extract_fields(
        self, normalized_text: str, domains: list[str]
    ) -> list[dict[str, Any]]:
        """Step 2: 필드 추출.

        dry_run → mock / gemini → Gemini Step2 / claude → Sonnet 호출
        """
        if self.dry_run:
            raw = _mock_response("step2", normalized_text)
            try:
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                return json.loads(raw)
            except Exception as e:
                print(f"    WARNING: mock 필드 파싱 실패 ({e}). raw={raw[:200]!r}")
                return []
        if self.llm_backend == "gemini":
            fields, _ = self._extract_step2_gemini(normalized_text, domains)
            return fields
        return self._extract_fields_claude(normalized_text, domains)

    # ── Step 3: 유효성 검증 (결정론적, LLM 미사용) ──────────────────────
    @staticmethod
    def _flag_value(
        field_meta: dict, numeric_value: float | None
    ) -> tuple[str | None, bool]:
        """수치 기반 flag_cd / is_critical 판정 (결정론적 코드, LLM 미사용).

        Returns:
            (flag_cd, is_critical)
        """
        if numeric_value is None:
            return None, False
        v = float(numeric_value)

        crit_range = field_meta.get("critical_range") or {}
        valid_range = field_meta.get("valid_range") or {}

        crit_low  = crit_range.get("low")
        crit_high = crit_range.get("high")
        val_min   = valid_range.get("min")
        val_max   = valid_range.get("max")

        if crit_low  is not None and v < float(crit_low):
            return "CRITICAL_LOW", True
        if crit_high is not None and v > float(crit_high):
            return "CRITICAL_HIGH", True
        if val_min   is not None and v < float(val_min):
            return "LOW", False
        if val_max   is not None and v > float(val_max):
            return "HIGH", False
        if val_min is not None or val_max is not None:
            return "NORMAL", False
        return None, False  # 범위 정보 없음

    def validate(
        self, extracted_fields: list[dict], domains: list[str]
    ) -> dict[str, Any]:
        """Step 3: 유효성 검증 (결정론적, LLM 미사용).

        Returns:
            {
                "status": "PASS"|"WARN"|"CRITICAL",
                "flags": [{"field": str, "level": str, "reason": str}, ...]
            }
        """
        fields_meta = self.get_domain_fields(domains)
        field_map = {f["field_code"]: f for f in fields_meta}

        status = "PASS"
        flags: list[dict] = []
        validated_fields: list[dict] = []

        for item in extracted_fields:
            fc    = item.get("field_code", "")
            val   = item.get("value")
            vtype = item.get("type", "VAL")

            meta = field_map.get(fc, {})
            numeric_value: float | None = None

            if vtype == "VAL":
                try:
                    numeric_value = float(val)
                except (TypeError, ValueError):
                    flags.append({
                        "field": fc,
                        "level": "WARN",
                        "reason": f"VAL 타입인데 숫자 변환 불가: {val!r}",
                    })
                    if status == "PASS":
                        status = "WARN"
                    validated_fields.append({**item, "flag_cd": "INVALID", "is_critical": False})
                    continue
            else:
                # CD 타입: enum 유효성 검증
                enum_values = meta.get("enum_values")
                if enum_values and isinstance(enum_values, list):
                    if str(val) not in [str(e) for e in enum_values]:
                        flags.append({
                            "field": fc,
                            "level": "WARN",
                            "reason": f"enum 범위 외 값: {val!r} (허용: {enum_values[:5]})",
                        })
                        if status == "PASS":
                            status = "WARN"

            flag_cd, is_crit = self._flag_value(meta, numeric_value)

            if is_crit:
                flags.append({
                    "field": fc,
                    "level": "CRITICAL",
                    "reason": f"임계 범위 이탈: {val} [{flag_cd}]",
                })
                status = "CRITICAL"
            elif flag_cd in ("HIGH", "LOW"):
                flags.append({
                    "field": fc,
                    "level": "WARN",
                    "reason": f"정상 범위 벗어남: {val} [{flag_cd}]",
                })
                if status == "PASS":
                    status = "WARN"

            validated_fields.append({
                **item,
                "flag_cd": flag_cd,
                "is_critical": is_crit,
            })

        return {
            "status": status,
            "flags": flags,
            "validated_fields": validated_fields,
        }

    # ── 4단계 오케스트레이션 ────────────────────────────────────────────
    def extract(self, text: str, encounter_id: str | None = None) -> dict[str, Any]:
        """4단계 파이프라인 실행 → JSONL 호환 구조 반환.

        설계서 §7.1 스키마 호환. 백엔드 무관 동일 출력 구조.

        Args:
            text: 수의사 발화 텍스트 (STT 출력 또는 직접 텍스트)
            encounter_id: 선택적 encounter 식별자

        Returns:
            {
                "encounter_id": str | None,
                "stt": {"raw_text": str, "normalized_text": str},
                "domains": list[str],
                "fields": list[{field_code, value, type, soap_section,
                                flag_cd, is_critical, validation}],
                "soap": {"subjective": str, "objective": str,
                         "assessment": str, "plan": str},
                "step3_validation": {"status": str, "flags": list},
                "latency_ms": {"step0": float, "step1": float,
                               "step2": float, "step3": float, "total": float},
                "llm_metadata": {"backend": str, "model": str, ...}  # Gemini 경로 시
            }
        """
        t_total = time.time()
        llm_metadata_all: dict[str, Any] = {}

        # ── Step 0 + 1 (백엔드별 분기) ──────────────────────────────
        t0 = time.time()
        if self.dry_run:
            normalized_text = _mock_response("step0", text)
            ms_step0 = (time.time() - t0) * 1000
            t0 = time.time()
            domains_raw = _mock_response("step1", normalized_text)
            try:
                domains = [d for d in json.loads(domains_raw) if d in DOMAINS][:3]
            except Exception:
                domains = ["VITAL_SIGNS"]
            ms_step1 = (time.time() - t0) * 1000
        elif self.llm_backend == "gemini":
            # Step 0+1 병합 단일 호출 (최적화)
            normalized_text, domains, meta_01 = self._extract_step01_gemini(text)
            ms_step01 = (time.time() - t0) * 1000
            ms_step0 = ms_step01 / 2  # 병합 호출이므로 균등 배분 (표시용)
            ms_step1 = ms_step01 / 2
            llm_metadata_all["step01"] = meta_01
        else:
            # Claude 경로 — Step 0, 1 순차 호출 (기존 로직)
            normalized_text = self._preprocess_claude(text)
            ms_step0 = (time.time() - t0) * 1000
            t0 = time.time()
            domains = self._detect_domains_claude(normalized_text)
            ms_step1 = (time.time() - t0) * 1000

        # ── Step 2 ──────────────────────────────────────────────────
        t0 = time.time()
        if self.dry_run:
            extracted_raw = _mock_response("step2", normalized_text)
            try:
                extracted_raw = extracted_raw.strip()
                if extracted_raw.startswith("```"):
                    extracted_raw = extracted_raw.split("```")[1]
                    if extracted_raw.startswith("json"):
                        extracted_raw = extracted_raw[4:]
                extracted = json.loads(extracted_raw)
            except Exception as e:
                print(f"    WARNING: mock Step2 파싱 실패 ({e})")
                extracted = []
        elif self.llm_backend == "gemini":
            extracted, meta_02 = self._extract_step2_gemini(normalized_text, domains)
            llm_metadata_all["step2"] = meta_02
        else:
            extracted = self._extract_fields_claude(normalized_text, domains)
        ms_step2 = (time.time() - t0) * 1000

        # ── Step 3 ──────────────────────────────────────────────────
        t0 = time.time()
        validation = self.validate(extracted, domains)
        ms_step3 = (time.time() - t0) * 1000

        ms_total = (time.time() - t_total) * 1000

        # ── SOAP 분리 ────────────────────────────────────────────────
        soap_buckets: dict[str, list[str]] = {"S": [], "O": [], "A": [], "P": []}
        fields_output: list[dict] = []

        for vf in validation["validated_fields"]:
            fc    = vf.get("field_code", "")
            val   = vf.get("value")

            # soap_section: Step 2 출력값 우선, 없으면 도메인 기반 추론
            soap_sec = vf.get("soap_section")
            if not soap_sec:
                domain_of_field = self._get_domain_of_field(fc, domains)
                soap_sec = SOAP_DOMAIN_MAP.get(domain_of_field, "O")

            # 버킷 텍스트 생성
            val_str = str(val) if val is not None else "null"
            soap_buckets[soap_sec].append(f"{fc}={val_str}")

            fields_output.append({
                "field_code": fc,
                "value": val,
                "domain": self._get_domain_of_field(fc, domains),
                "validation": (
                    "CRITICAL" if vf.get("is_critical")
                    else ("WARN" if vf.get("flag_cd") in ("HIGH", "LOW", "INVALID")
                          else "PASS")
                ),
                "soap_section": soap_sec,
                "flag_cd": vf.get("flag_cd"),
                "is_critical": vf.get("is_critical", False),
            })

        soap = {
            "subjective": "; ".join(soap_buckets["S"]) or None,
            "objective":  "; ".join(soap_buckets["O"]) or None,
            "assessment": "; ".join(soap_buckets["A"]) or None,
            "plan":       "; ".join(soap_buckets["P"]) or None,
        }

        # ── LLM 메타데이터 집계 ─────────────────────────────────────
        if not self.dry_run and llm_metadata_all:
            total_cost = sum(
                m.get("cost_usd", 0) for m in llm_metadata_all.values()
            )
            total_in_tok = sum(
                m.get("tokens_input", 0) for m in llm_metadata_all.values()
            )
            total_out_tok = sum(
                m.get("tokens_output", 0) for m in llm_metadata_all.values()
            )
            llm_summary = {
                "backend": self.llm_backend,
                "model": self.gemini_model if self.llm_backend == "gemini" else self.claude_sonnet_model,
                "total_cost_usd": round(total_cost, 8),
                "total_tokens_input": total_in_tok,
                "total_tokens_output": total_out_tok,
                "step_details": llm_metadata_all,
            }
        else:
            llm_summary = {
                "backend": self.llm_backend if not self.dry_run else "dry_run",
                "model": "mock",
            }

        result: dict[str, Any] = {
            "encounter_id": encounter_id,
            "stt": {
                "raw_text": text,
                "normalized_text": normalized_text,
            },
            "domains": domains,
            "fields": fields_output,
            "soap": soap,
            "step3_validation": {
                "status": validation["status"],
                "flags": validation["flags"],
            },
            "latency_ms": {
                "step0": round(ms_step0, 1),
                "step1": round(ms_step1, 1),
                "step2": round(ms_step2, 1),
                "step3": round(ms_step3, 1),
                "total": round(ms_total, 1),
            },
            "llm_metadata": llm_summary,
        }

        return result

    def _get_domain_of_field(self, field_code: str, candidate_domains: list[str]) -> str:
        """field_code가 속한 도메인을 candidate_domains 중에서 반환한다."""
        for did in candidate_domains:
            for f in self._field_schema.get(did, []):
                if f["field_code"] == field_code:
                    return did
        return candidate_domains[0] if candidate_domains else "VITAL_SIGNS"
