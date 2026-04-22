"""
e2e.py — vet-snomed-rag v2.0 Track B4: End-to-End 파이프라인 통합
=================================================================

ClinicalEncoder 클래스:
  - 입력: 텍스트 또는 오디오 파일
  - 출력: §7.1 JSONL 레코드 (encounter_id, timestamp, audio, stt, soap, domains,
          fields, snomed_tagging, latency_ms)

[절대 원칙]
  - B1/B2/B3 모듈 내부 로직 무변경 (통합 레이어만 담당)
  - v1.0 src/retrieval/* 변경 금지
  - encounter_id: UUID4 형식 엄수 (feedback_uuid_format_verify)
  - 각 단계 실패 시 errors[] 배열에 기록, null 반환 금지
  - concept_id는 RF2 DB 실존 검증된 것만 (AI 추론 생성 금지)
"""

from __future__ import annotations

import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ─── 프로젝트 루트 경로 ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
sys.path.insert(0, str(PROJECT_ROOT))

# ─── B1/B2/B3 모듈 임포트 (내부 로직 무변경) ────────────────────────────
from src.pipeline.stt_wrapper import transcribe as stt_transcribe
from src.pipeline.soap_extractor import SOAPExtractor
from src.pipeline.snomed_tagger import SNOMEDTagger

# ─── 기본 설정값 (Day 3 승인 사항: M2 최적 설정) ────────────────────────
DEFAULT_FIELD_SCHEMA_PATH = DATA_DIR / "field_schema_v26.json"
DEFAULT_SNOMED_DB_PATH = DATA_DIR / "snomed_ct_vet.db"
DEFAULT_MRCM_RULES_PATH = DATA_DIR / "mrcm_rules_v1.json"

# ─── UUID4 형식 검증 정규식 (feedback_uuid_format_verify) ────────────────
_UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _validate_uuid4(value: str) -> bool:
    """UUID4 형식(36자, 8-4-4-4-12) 검증 (feedback_uuid_format_verify)."""
    return bool(_UUID4_PATTERN.match(value.lower()))


class ClinicalEncoderConfig:
    """ClinicalEncoder 설정 컨테이너.

    Attributes:
        field_schema_path: field_schema_v26.json 경로
        snomed_db_path:    snomed_ct_vet.db 경로
        mrcm_rules_path:   mrcm_rules_v1.json 경로
        reformulator_backend: RAG 쿼리 리포매터 (기본: "gemini" — M2 최적)
        enable_rerank:     리랭커 활성화 여부 (기본: False — M2 최적)
        dry_run:           True이면 Claude API 미호출 (SOAP mock 사용)
        api_key:           Anthropic API 키 (None이면 환경변수 사용)
        whisper_model:     Whisper 모델 크기 (기본: "small")
    """

    def __init__(
        self,
        field_schema_path: str | Path = DEFAULT_FIELD_SCHEMA_PATH,
        snomed_db_path: str | Path = DEFAULT_SNOMED_DB_PATH,
        mrcm_rules_path: str | Path = DEFAULT_MRCM_RULES_PATH,
        reformulator_backend: str = "gemini",   # M2 최적 기본값
        enable_rerank: bool = False,             # M2 최적 기본값
        dry_run: bool = False,
        api_key: Optional[str] = None,
        whisper_model: str = "small",
    ):
        self.field_schema_path = Path(field_schema_path)
        self.snomed_db_path = Path(snomed_db_path)
        self.mrcm_rules_path = Path(mrcm_rules_path)
        self.reformulator_backend = reformulator_backend
        self.enable_rerank = enable_rerank
        self.dry_run = dry_run
        self.api_key = api_key
        self.whisper_model = whisper_model


class ClinicalEncoder:
    """
    End-to-End 임상 인코더.

    입력(텍스트 or 오디오) → STT → SOAP 추출 → SNOMED 태깅 → JSONL 레코드 반환.

    파이프라인:
        1. STT (입력 타입 "audio" 시만 실행, "text"는 skip)
        2. SOAP 추출 (B2 SOAPExtractor)
        3. SNOMED 태깅 (B3 SNOMEDTagger)
        4. §7.1 JSONL 레코드 조립

    에러 처리:
        각 단계 실패 시 graceful — 다음 단계를 빈 값으로 계속 진행.
        모든 오류는 errors[] 배열에 기록. null 반환 금지.
    """

    def __init__(self, config: Optional[ClinicalEncoderConfig] = None):
        """
        Args:
            config: ClinicalEncoderConfig 인스턴스.
                    None이면 기본 설정 사용 (M2 최적: reformulator=gemini, rerank=False).
        """
        if config is None:
            config = ClinicalEncoderConfig()
        self.config = config

        print("[ClinicalEncoder] 초기화 시작")
        print(f"  reformulator={config.reformulator_backend}, rerank={config.enable_rerank}")
        print(f"  dry_run={config.dry_run}, whisper_model={config.whisper_model}")

        # ── B2 SOAPExtractor 초기화 ──────────────────────────────────────
        self._soap: Optional[SOAPExtractor] = None
        self._soap_error: Optional[str] = None
        try:
            self._soap = SOAPExtractor(
                field_schema_path=config.field_schema_path,
                api_key=config.api_key,
                dry_run=config.dry_run,
            )
            print(f"  [OK] SOAPExtractor 초기화 완료")
        except Exception as e:
            self._soap_error = str(e)
            print(f"  [WARN] SOAPExtractor 초기화 실패: {e}")

        # ── B3 SNOMEDTagger 초기화 ───────────────────────────────────────
        self._tagger: Optional[SNOMEDTagger] = None
        self._tagger_error: Optional[str] = None
        self._rag_init_error: Optional[str] = None  # RAG 초기화 실패 메시지 보존
        try:
            # RAG 파이프라인 초기화 (선택적)
            rag = None
            try:
                from src.retrieval.rag_pipeline import SNOMEDRagPipeline
                rag = SNOMEDRagPipeline(
                    reformulator_backend=config.reformulator_backend,
                    enable_rerank=config.enable_rerank,
                )
                print(f"  [OK] SNOMEDRagPipeline 초기화 완료")
            except Exception as e:
                self._rag_init_error = f"RAG_INIT_ERROR: {type(e).__name__}: {e}"
                print(f"  [WARN] RAG 파이프라인 초기화 실패 (SNOMEDTagger는 MRCM 직접지정만 사용): {e}")
                print(f"         → SNOMED 태깅은 MRCM 규칙 적용 필드만 매핑됩니다. 나머지는 UNMAPPED.")

            self._tagger = SNOMEDTagger(
                rag_pipeline=rag,
                sqlite_path=config.snomed_db_path,
                mrcm_rules_path=config.mrcm_rules_path,
            )
            print(f"  [OK] SNOMEDTagger 초기화 완료")
        except Exception as e:
            self._tagger_error = str(e)
            print(f"  [WARN] SNOMEDTagger 초기화 실패: {e}")

        print("[ClinicalEncoder] 초기화 완료")

    # ─── 단일 입력 인코딩 ──────────────────────────────────────────────

    def encode(
        self,
        input_data: str,
        input_type: str = "text",
    ) -> dict[str, Any]:
        """단일 입력을 §7.1 JSONL 레코드로 변환한다.

        Args:
            input_data: 텍스트 내용 (input_type="text") 또는 오디오 파일 경로 (input_type="audio")
            input_type: "text" 또는 "audio"

        Returns:
            §7.1 JSONL 레코드 dict:
                encounter_id, timestamp, audio, stt, soap, domains, fields,
                snomed_tagging, latency_ms, errors

        Raises:
            ValueError: input_type이 "text" 또는 "audio"가 아닐 때
        """
        if input_type not in ("text", "audio"):
            raise ValueError(f"input_type은 'text' 또는 'audio'만 허용됩니다. 입력: {input_type!r}")

        # UUID4 encounter_id 생성 (feedback_uuid_format_verify)
        encounter_id = str(uuid.uuid4())
        assert _validate_uuid4(encounter_id), f"UUID4 형식 오류: {encounter_id}"

        timestamp = datetime.now(timezone.utc).isoformat()
        errors: list[str] = []

        # RAG 초기화 실패 경고를 errors[]에 전파 (feedback_null_not_design_intent)
        # → UNMAPPED가 발생하는 경우 원인이 명시적으로 기록됨
        if self._rag_init_error:
            errors.append(self._rag_init_error)

        # ─── latency 측정 ────────────────────────────────────────────
        t_total_start = time.perf_counter()
        ms_stt = 0.0
        ms_soap = 0.0
        ms_snomed = 0.0

        # ─── Step 1: STT ─────────────────────────────────────────────
        audio_meta: dict[str, Any] = {
            "path": None,
            "duration_sec": 0.0,
            "language": "ko",
        }
        raw_text = ""

        if input_type == "audio":
            audio_path = input_data
            audio_meta["path"] = str(audio_path)
            t0 = time.perf_counter()
            try:
                stt_result = stt_transcribe(
                    audio_path=audio_path,
                    model_size=self.config.whisper_model,
                    language="ko",
                    beam_size=5,
                )
                raw_text = stt_result.get("text", "")
                audio_meta["duration_sec"] = stt_result.get("duration_sec", 0.0)
                audio_meta["language"] = stt_result.get("language", "ko")
                print(f"  [STT] 완료: {len(raw_text)}자 전사")
            except FileNotFoundError as e:
                errors.append(f"STT_ERROR: 오디오 파일 없음 — {e}")
                print(f"  [STT ERROR] 파일 없음: {e}")
            except Exception as e:
                errors.append(f"STT_ERROR: {e}")
                print(f"  [STT ERROR] {e}")
            ms_stt = (time.perf_counter() - t0) * 1000

        else:
            # 텍스트 입력: STT 단계 skip
            raw_text = input_data
            audio_meta["path"] = None
            audio_meta["duration_sec"] = 0.0

        # STT 실패 시 텍스트가 없으면 최소 레코드 반환
        if not raw_text and input_type == "audio":
            errors.append("STT_ERROR: 전사 결과 없음 — 텍스트 입력 필요")
            return self._build_record(
                encounter_id=encounter_id,
                timestamp=timestamp,
                audio=audio_meta,
                stt={"raw_text": "", "normalized_text": ""},
                soap={"subjective": None, "objective": None, "assessment": None, "plan": None},
                domains=[],
                fields=[],
                snomed_tagging=[],
                latency_ms={"stt": round(ms_stt, 1), "soap": 0.0, "snomed": 0.0,
                             "total": round((time.perf_counter() - t_total_start) * 1000, 1)},
                errors=errors,
            )

        # ─── Step 2: SOAP 추출 ───────────────────────────────────────
        t0 = time.perf_counter()
        normalized_text = raw_text
        soap_result: dict[str, Any] = {}
        domains: list[str] = []
        fields: list[dict] = []

        if self._soap is None:
            errors.append(f"SOAP_ERROR: SOAPExtractor 초기화 실패 — {self._soap_error}")
            print(f"  [SOAP ERROR] 초기화 실패")
        else:
            try:
                soap_result = self._soap.extract(
                    text=raw_text,
                    encounter_id=encounter_id,
                )
                normalized_text = soap_result.get("stt", {}).get("normalized_text", raw_text)
                domains = soap_result.get("domains", [])
                fields = soap_result.get("fields", [])
                print(f"  [SOAP] 완료: 도메인={domains}, 필드={len(fields)}개")
            except Exception as e:
                errors.append(f"SOAP_ERROR: {e}")
                print(f"  [SOAP ERROR] {e}")

        ms_soap = (time.perf_counter() - t0) * 1000

        # SOAP 분리 구조
        soap_section = soap_result.get("soap", {
            "subjective": None, "objective": None,
            "assessment": None, "plan": None,
        })

        # ─── Step 3: SNOMED 태깅 ─────────────────────────────────────
        t0 = time.perf_counter()
        snomed_tagging: list[dict] = []

        if self._tagger is None:
            errors.append(f"SNOMED_ERROR: SNOMEDTagger 초기화 실패 — {self._tagger_error}")
            print(f"  [SNOMED ERROR] 초기화 실패")
            # 태거 실패 시 UNMAPPED 강제 (NULL 금지)
            for f in fields:
                snomed_tagging.append({
                    "field_code": f.get("field_code", "UNKNOWN"),
                    "concept_id": "UNMAPPED",
                    "preferred_term": "",
                    "semantic_tag": "",
                    "source": "UNMAPPED",
                    "post_coordination": "",
                    "mrcm_validated": False,
                    "confidence": 0.0,
                })
        elif not fields:
            print(f"  [SNOMED] fields 배열 비어 있음 — 태깅 건너뜀")
        else:
            try:
                snomed_tagging = self._tagger.tag_all(fields)
                print(f"  [SNOMED] 완료: {len(snomed_tagging)}개 태깅")
            except Exception as e:
                errors.append(f"SNOMED_ERROR: {e}")
                print(f"  [SNOMED ERROR] {e}")
                # 실패 시 UNMAPPED 강제
                for f in fields:
                    snomed_tagging.append({
                        "field_code": f.get("field_code", "UNKNOWN"),
                        "concept_id": "UNMAPPED",
                        "preferred_term": "",
                        "semantic_tag": "",
                        "source": "UNMAPPED",
                        "post_coordination": "",
                        "mrcm_validated": False,
                        "confidence": 0.0,
                    })

        ms_snomed = (time.perf_counter() - t0) * 1000
        ms_total = (time.perf_counter() - t_total_start) * 1000

        return self._build_record(
            encounter_id=encounter_id,
            timestamp=timestamp,
            audio=audio_meta,
            stt={"raw_text": raw_text, "normalized_text": normalized_text},
            soap=soap_section,
            domains=domains,
            fields=fields,
            snomed_tagging=snomed_tagging,
            latency_ms={
                "stt": round(ms_stt, 1),
                "soap": round(ms_soap, 1),
                "snomed": round(ms_snomed, 1),
                "total": round(ms_total, 1),
            },
            errors=errors,
        )

    # ─── JSONL 배치 처리 ────────────────────────────────────────────────

    def encode_to_jsonl(
        self,
        inputs: list[dict],
        output_path: str | Path,
    ) -> list[dict]:
        """다건 입력을 JSONL 파일로 저장한다.

        Args:
            inputs: [{"data": str, "type": "text"|"audio"}, ...] 목록
            output_path: 출력 JSONL 파일 경로

        Returns:
            생성된 레코드 목록
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        records = []

        with open(output_path, "w", encoding="utf-8") as f:
            for i, item in enumerate(inputs, 1):
                data = item.get("data", "")
                itype = item.get("type", "text")
                print(f"\n[encode_to_jsonl] {i}/{len(inputs)} — type={itype}")
                record = self.encode(data, input_type=itype)
                records.append(record)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"\n[encode_to_jsonl] 완료: {len(records)}건 → {output_path}")
        return records

    # ─── §7.1 레코드 빌더 ────────────────────────────────────────────────

    @staticmethod
    def _build_record(
        encounter_id: str,
        timestamp: str,
        audio: dict,
        stt: dict,
        soap: dict,
        domains: list,
        fields: list,
        snomed_tagging: list,
        latency_ms: dict,
        errors: list[str],
    ) -> dict[str, Any]:
        """§7.1 스키마 준수 JSONL 레코드를 조립한다.

        O1 필드 누락 0건 — 모든 required 키 포함 보장.
        O12 NA 보호 — null vs 빈문자열 명확 구분.
        """
        return {
            "encounter_id": encounter_id,            # UUID4
            "timestamp": timestamp,                  # ISO8601
            "audio": {
                "path": audio.get("path"),           # str | null
                "duration_sec": audio.get("duration_sec", 0.0),
                "language": audio.get("language", "ko"),
            },
            "stt": {
                "raw_text": stt.get("raw_text", ""),
                "normalized_text": stt.get("normalized_text", ""),
            },
            "soap": {
                "subjective": soap.get("subjective"),
                "objective": soap.get("objective"),
                "assessment": soap.get("assessment"),
                "plan": soap.get("plan"),
            },
            "domains": domains,
            "fields": fields,
            "snomed_tagging": snomed_tagging,
            "latency_ms": {
                "stt": latency_ms.get("stt", 0.0),
                "soap": latency_ms.get("soap", 0.0),
                "snomed": latency_ms.get("snomed", 0.0),
                "total": latency_ms.get("total", 0.0),
            },
            "errors": errors,  # 빈 리스트 = 오류 없음
        }

    def close(self):
        """리소스를 해제한다."""
        if self._tagger is not None:
            self._tagger.close()
        if hasattr(self, "_soap") and self._soap is not None:
            pass  # SOAPExtractor는 별도 close 불필요


# ─── CLI 스모크 ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ClinicalEncoder E2E 스모크")
    parser.add_argument("--text", type=str,
                        default="안압이 오른쪽 28, 왼쪽 14로 측정됐습니다. 우안 고안압으로 판단되어 녹내장 약물 시작합니다.",
                        help="입력 텍스트")
    parser.add_argument("--dry-run", action="store_true",
                        help="API 미호출 (mock 응답 사용)")
    args = parser.parse_args()

    config = ClinicalEncoderConfig(
        dry_run=args.dry_run,
        reformulator_backend="gemini",
        enable_rerank=False,
    )

    encoder = ClinicalEncoder(config=config)
    record = encoder.encode(args.text, input_type="text")
    encoder.close()

    print("\n" + "=" * 60)
    print("[E2E 결과]")
    print(json.dumps(record, ensure_ascii=False, indent=2))
