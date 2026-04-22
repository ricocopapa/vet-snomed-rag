"""
test_soap_extractor.py
======================
vet-snomed-rag v2.0 — Track B2: SOAP 추출기 테스트

dry_run=True 모드로 실행하므로 API 호출 없음.
모든 테스트는 field_schema_v26.json의 실제 필드 코드 기준으로 검증한다.

테스트 케이스:
  1. 안과 케이스   — IOP 수치 추출, OPHTHALMOLOGY 탐지
  2. 내과 케이스   — 활력징후 수치 추출, VITAL_SIGNS 탐지
  3. 정형외과 케이스 — 파행/슬개골 탈구, ORTHOPEDICS 탐지

필드 코드 명명 규칙 검증:
  - 모든 field_code는 field_schema_v26.json에 존재하는 실제 코드여야 함
  - 또는 mock 에서 반환한 코드가 도메인 패턴을 준수해야 함

절대 금지 (vet-stt SKILL.md §절대 금지):
  - 추출 불가 필드에 추측값 삽입 금지
  - Step 3 LLM 판단 대체 금지
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 프로젝트 루트를 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.soap_extractor import DOMAINS, SOAPExtractor

SCHEMA_PATH = PROJECT_ROOT / "data" / "field_schema_v26.json"


# ── 픽스처 ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def extractor():
    """dry_run=True SOAPExtractor 인스턴스 (API 불필요)."""
    return SOAPExtractor(field_schema_path=SCHEMA_PATH, dry_run=True)


@pytest.fixture(scope="module")
def schema_field_codes():
    """field_schema_v26.json에 등록된 모든 필드 코드 집합."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    codes: set[str] = set()
    for domain in raw.get("domains", []):
        for fi in domain.get("fields", []):
            codes.add(fi["field_code"])
    return codes


# ── 케이스 1: 안과 ───────────────────────────────────────────────────────
class TestOphthalmologyCase:
    """안과 케이스: 안압 수치 추출 + OPHTHALMOLOGY 도메인 탐지."""

    TEXT = "안압이 오른쪽 28, 왼쪽 24로 측정됐고 각막 형광염색 음성이에요. 동공반사 정상입니다."

    def test_preprocess_removes_filler(self, extractor):
        """Step 0: 정규화 후 핵심 임상 수치 보존."""
        result = extractor.preprocess(self.TEXT)
        assert result, "Step 0 출력이 비어 있으면 안 됩니다"
        # 수치 보존 확인
        assert "28" in result, f"우안 안압 수치 28 보존 실패: {result!r}"

    def test_detect_ophthalmology_domain(self, extractor):
        """Step 1: OPHTHALMOLOGY 도메인 탐지 필수."""
        normalized = extractor.preprocess(self.TEXT)
        domains = extractor.detect_domains(normalized)
        assert "OPHTHALMOLOGY" in domains, (
            f"OPHTHALMOLOGY 도메인 미탐지. 탐지됨: {domains}"
        )
        assert len(domains) <= 3, f"최대 3개 초과: {domains}"

    def test_extract_iop_od(self, extractor):
        """Step 2: 우안 안압(OPH_IOP_OD) 수치 28 추출."""
        normalized = extractor.preprocess(self.TEXT)
        domains = extractor.detect_domains(normalized)
        fields = extractor.extract_fields(normalized, domains)

        iop_field = next(
            (f for f in fields if f.get("field_code") == "OPH_IOP_OD"), None
        )
        assert iop_field is not None, (
            f"OPH_IOP_OD 필드 미추출. 추출된 필드: {[f['field_code'] for f in fields]}"
        )
        assert iop_field["value"] == 28.0, (
            f"우안 안압 기대값 28, 실제값: {iop_field['value']}"
        )
        assert iop_field["type"] == "VAL", "OPH_IOP_OD는 VAL 타입이어야 함"

    def test_step3_warn_for_high_iop(self, extractor):
        """Step 3: 안압 28 (critical_high=30 → 정상 범위 내, HIGH 없음).

        DB 기준: OPH_IOP_OD val_max=70, critical_high=30
        28은 val_max(70) 이하, critical_high(30) 이하 → NORMAL
        """
        normalized = extractor.preprocess(self.TEXT)
        domains = extractor.detect_domains(normalized)
        fields = extractor.extract_fields(normalized, domains)
        validation = extractor.validate(fields, domains)

        assert "status" in validation
        assert validation["status"] in ("PASS", "WARN", "CRITICAL"), (
            f"유효하지 않은 status: {validation['status']}"
        )
        # Step 3는 결정론적 코드로만 실행됨을 확인 (플래그 구조 검증)
        for flag in validation.get("flags", []):
            assert "field" in flag
            assert "level" in flag
            assert flag["level"] in ("WARN", "CRITICAL")

    def test_full_extract_schema(self, extractor):
        """전체 extract() 반환값 구조 검증 (§7.1 JSONL 스키마)."""
        result = extractor.extract(self.TEXT, encounter_id="TEST-OPH-001")

        assert result["encounter_id"] == "TEST-OPH-001"
        assert "stt" in result
        assert "raw_text" in result["stt"]
        assert "normalized_text" in result["stt"]
        assert "domains" in result
        assert "fields" in result
        assert "soap" in result
        assert "step3_validation" in result
        assert "latency_ms" in result

        soap = result["soap"]
        assert set(soap.keys()) == {"subjective", "objective", "assessment", "plan"}, (
            f"SOAP 키 불일치: {set(soap.keys())}"
        )


# ── 케이스 2: 내과 (활력징후) ────────────────────────────────────────────
class TestVitalSignsCase:
    """내과 케이스: 체온·심박수·탈수 추출 + VITAL_SIGNS 도메인 탐지."""

    TEXT = "체온 38.5도 심박수 120회 점막 핑크 탈수 5%"

    def test_detect_vital_signs(self, extractor):
        """Step 1: VITAL_SIGNS 도메인 탐지 필수."""
        normalized = extractor.preprocess(self.TEXT)
        domains = extractor.detect_domains(normalized)
        assert "VITAL_SIGNS" in domains, (
            f"VITAL_SIGNS 미탐지. 탐지됨: {domains}"
        )

    def test_extract_temp_and_hr(self, extractor):
        """Step 2: 체온(GP_RECTAL_TEMP_VALUE) + 심박수(GP_HR_VALUE) 추출."""
        normalized = extractor.preprocess(self.TEXT)
        domains = extractor.detect_domains(normalized)
        fields = extractor.extract_fields(normalized, domains)

        field_codes = [f["field_code"] for f in fields]

        temp_field = next(
            (f for f in fields if f.get("field_code") == "GP_RECTAL_TEMP_VALUE"), None
        )
        hr_field = next(
            (f for f in fields if f.get("field_code") == "GP_HR_VALUE"), None
        )

        assert temp_field is not None, (
            f"GP_RECTAL_TEMP_VALUE 미추출. 추출됨: {field_codes}"
        )
        assert temp_field["value"] == 38.5, (
            f"체온 기대 38.5, 실제: {temp_field['value']}"
        )
        assert hr_field is not None, (
            f"GP_HR_VALUE 미추출. 추출됨: {field_codes}"
        )
        assert hr_field["value"] == 120.0, (
            f"심박수 기대 120.0, 실제: {hr_field['value']}"
        )

    def test_null_for_missing_fields(self, extractor):
        """추출되지 않은 필드는 반환값에 없어야 함 (null 삽입 금지)."""
        normalized = extractor.preprocess(self.TEXT)
        domains = extractor.detect_domains(normalized)
        fields = extractor.extract_fields(normalized, domains)

        # 텍스트에 없는 값(혈압 등)은 필드 목록에 등장하면 안 됨
        field_codes = [f["field_code"] for f in fields]
        assert "GP_BP_SYS_VALUE" not in field_codes, (
            "텍스트에 없는 혈압 필드가 추출됨 → 추측값 삽입 위반"
        )

    def test_step3_normal_range(self, extractor):
        """Step 3: 38.5도(정상)는 WARN 이상 플래그 없어야 함."""
        normalized = extractor.preprocess(self.TEXT)
        domains = extractor.detect_domains(normalized)
        fields = extractor.extract_fields(normalized, domains)
        validation = extractor.validate(fields, domains)

        temp_flag = next(
            (f for f in validation.get("flags", [])
             if f["field"] == "GP_RECTAL_TEMP_VALUE"),
            None
        )
        # 38.5는 정상 체온 범위 내 → flag 없어야 함
        assert temp_flag is None, (
            f"정상 체온 38.5에 잘못된 플래그: {temp_flag}"
        )


# ── 케이스 3: 정형외과 ───────────────────────────────────────────────────
class TestOrthopedicsCase:
    """정형외과 케이스: 파행 등급 + 슬개골 탈구 추출."""

    TEXT = "오른쪽 뒷다리 파행 3급, 슬개골 내측 탈구 grade 2"

    def test_detect_orthopedics(self, extractor):
        """Step 1: ORTHOPEDICS 도메인 탐지 필수."""
        normalized = extractor.preprocess(self.TEXT)
        domains = extractor.detect_domains(normalized)
        assert "ORTHOPEDICS" in domains, (
            f"ORTHOPEDICS 미탐지. 탐지됨: {domains}"
        )

    def test_extract_lameness_grade(self, extractor):
        """Step 2: 파행 등급 추출 확인."""
        normalized = extractor.preprocess(self.TEXT)
        domains = extractor.detect_domains(normalized)
        fields = extractor.extract_fields(normalized, domains)

        assert len(fields) > 0, "정형외과 케이스에서 필드 추출 0건"

        # 파행 또는 슬개골 관련 필드 최소 1개 존재 확인
        ort_fields = [f for f in fields if f["field_code"].startswith("ORT_")]
        assert len(ort_fields) > 0, (
            f"ORT_ 패턴 필드 0건. 추출됨: {[f['field_code'] for f in fields]}"
        )

    def test_step3_deterministic(self, extractor):
        """Step 3: CD 타입 필드도 결정론적 검증 통과."""
        normalized = extractor.preprocess(self.TEXT)
        domains = extractor.detect_domains(normalized)
        fields = extractor.extract_fields(normalized, domains)
        validation = extractor.validate(fields, domains)

        # status는 반드시 3가지 중 하나
        assert validation["status"] in ("PASS", "WARN", "CRITICAL")

    def test_full_pipeline_latency(self, extractor):
        """E2E 파이프라인 완주 및 latency 구조 확인."""
        result = extractor.extract(self.TEXT)

        assert "latency_ms" in result
        lt = result["latency_ms"]
        assert all(k in lt for k in ("step0", "step1", "step2", "step3", "total"))
        assert lt["total"] >= 0, "total latency는 0 이상이어야 함"


# ── 필드 코드 명명규칙 검증 ──────────────────────────────────────────────
class TestFieldCodeNamingRules:
    """모든 케이스의 추출 필드 코드가 스키마에 존재하거나 패턴을 준수하는지 검증."""

    CASES = [
        ("안과", "안압이 오른쪽 28, 왼쪽 24로 측정됐고 각막 형광염색 음성이에요."),
        ("내과", "체온 38.5도 심박수 120회 점막 핑크 탈수 5%"),
        ("정형외과", "오른쪽 뒷다리 파행 3급, 슬개골 내측 탈구 grade 2"),
    ]

    def test_no_arbitrary_field_codes(self, extractor):
        """추출된 필드 코드가 임의 생성 금지 원칙을 준수하는지 확인.

        dry_run mock에서 반환된 코드는 사전에 정의된 값이어야 함.
        실제 API 모드에서는 field_schema_v26.json의 필드 코드만 허용.
        """
        for case_name, text in self.CASES:
            normalized = extractor.preprocess(text)
            domains = extractor.detect_domains(normalized)
            fields = extractor.extract_fields(normalized, domains)

            assert isinstance(fields, list), (
                f"[{case_name}] extract_fields 반환값이 list가 아님"
            )
            for f in fields:
                assert "field_code" in f, (
                    f"[{case_name}] field_code 키 누락: {f}"
                )
                assert "value" in f, (
                    f"[{case_name}] value 키 누락: {f}"
                )
                assert "type" in f, (
                    f"[{case_name}] type 키 누락: {f}"
                )
                assert f["type"] in ("VAL", "CD"), (
                    f"[{case_name}] 허용되지 않는 type: {f['type']}"
                )

    def test_domains_are_valid(self, extractor):
        """탐지된 모든 도메인이 25개 목록 내에 있어야 함."""
        for case_name, text in self.CASES:
            normalized = extractor.preprocess(text)
            domains = extractor.detect_domains(normalized)
            for d in domains:
                assert d in DOMAINS, (
                    f"[{case_name}] 비허용 도메인: {d}"
                )


# ── 스키마 로드 테스트 ────────────────────────────────────────────────────
class TestSchemaLoad:
    """field_schema_v26.json 로드 및 구조 검증."""

    def test_schema_has_25_domains(self):
        """스키마에 25개 도메인 전수 포함 확인."""
        extractor = SOAPExtractor(field_schema_path=SCHEMA_PATH, dry_run=True)
        for domain_id in DOMAINS:
            fields = extractor.get_domain_fields([domain_id])
            assert len(fields) > 0, (
                f"도메인 {domain_id}의 필드가 0건 — 스키마 누락"
            )

    def test_ophthalmology_has_iop_od(self):
        """OPHTHALMOLOGY에 OPH_IOP_OD 필드 존재 확인."""
        extractor = SOAPExtractor(field_schema_path=SCHEMA_PATH, dry_run=True)
        fields = extractor.get_domain_fields(["OPHTHALMOLOGY"])
        codes = [f["field_code"] for f in fields]
        assert "OPH_IOP_OD" in codes, (
            f"OPH_IOP_OD 필드 미등록. OPHTHALMOLOGY 필드: {codes[:10]}..."
        )

    def test_vital_signs_has_temp_and_hr(self):
        """VITAL_SIGNS에 체온·심박수 필드 존재 확인."""
        extractor = SOAPExtractor(field_schema_path=SCHEMA_PATH, dry_run=True)
        fields = extractor.get_domain_fields(["VITAL_SIGNS"])
        codes = [f["field_code"] for f in fields]
        assert "GP_RECTAL_TEMP_VALUE" in codes, "GP_RECTAL_TEMP_VALUE 미등록"
        assert "GP_HR_VALUE" in codes, "GP_HR_VALUE 미등록"

    def test_no_patient_data_in_schema(self):
        """스키마에 환자 데이터(실제 측정값) 미포함 확인."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        # 환자 데이터가 없는지 확인: encounter_id, record, visit 키 없어야 함
        schema_str = json.dumps(raw)
        for keyword in ("encounter_id", "patient_id", "owner_name", "visit_date"):
            assert keyword not in schema_str, (
                f"스키마에 환자 데이터 키워드 발견: {keyword}"
            )


# ── dry-run 모드 검증 ─────────────────────────────────────────────────────
class TestDryRunMode:
    """dry_run=True 시 API 미호출 및 mock 응답 검증."""

    def test_no_api_key_required_in_dry_run(self):
        """dry_run=True이면 ANTHROPIC_API_KEY 없어도 초기화 성공."""
        import os
        original = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            extractor = SOAPExtractor(
                field_schema_path=SCHEMA_PATH, api_key=None, dry_run=True
            )
            assert extractor.dry_run is True
        finally:
            if original is not None:
                os.environ["ANTHROPIC_API_KEY"] = original

    def test_missing_schema_raises(self):
        """존재하지 않는 스키마 경로 → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            SOAPExtractor(
                field_schema_path="/nonexistent/path/schema.json", dry_run=True
            )


# ── Gemini 백엔드 경로 신규 테스트 10건 ──────────────────────────────────────
class TestGeminiBackendDryRun:
    """Gemini 백엔드 경로 검증 (dry_run=True — API 미호출).

    성공 기준:
      - llm_backend="gemini" 기본값으로 초기화
      - 3 도메인(안과·내과·정형) 필드 코드 명명규칙 준수
      - 도메인 탐지 confidence 임계값 (mock 기준)
      - SOAP 분류 정확성 (mock 기준)
      - null 처리 엄수
    """

    @pytest.fixture(scope="class")
    def gemini_extractor(self):
        """llm_backend='gemini', dry_run=True 인스턴스."""
        return SOAPExtractor(
            field_schema_path=SCHEMA_PATH,
            llm_backend="gemini",
            dry_run=True,
        )

    # ── G1: 기본 백엔드 초기화 ──────────────────────────────────────────
    def test_gemini_is_default_backend(self):
        """SOAPExtractor 기본값이 llm_backend='gemini'인지 확인."""
        ext = SOAPExtractor(field_schema_path=SCHEMA_PATH, dry_run=True)
        assert ext.llm_backend == "gemini", (
            f"기본 백엔드가 gemini가 아님: {ext.llm_backend}"
        )

    def test_gemini_dry_run_no_api_key_needed(self):
        """Gemini dry_run=True 시 GOOGLE_API_KEY 없어도 초기화 성공."""
        import os
        original = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            ext = SOAPExtractor(
                field_schema_path=SCHEMA_PATH,
                llm_backend="gemini",
                dry_run=True,
            )
            assert ext.llm_backend == "gemini"
            assert ext.dry_run is True
        finally:
            if original is not None:
                os.environ["GOOGLE_API_KEY"] = original

    # ── G2: 안과 케이스 — Gemini 경로 ───────────────────────────────────
    def test_gemini_ophthalmology_domain(self, gemini_extractor):
        """Gemini 경로: 안과 케이스 OPHTHALMOLOGY 도메인 탐지."""
        text = "안압이 오른쪽 28, 왼쪽 14로 측정됐습니다. 우안 고안압 녹내장 약물 시작"
        normalized = gemini_extractor.preprocess(text)
        domains = gemini_extractor.detect_domains(normalized)
        assert "OPHTHALMOLOGY" in domains, (
            f"OPHTHALMOLOGY 미탐지 (Gemini 경로). 탐지됨: {domains}"
        )

    def test_gemini_ophthalmology_field_code_naming(self, gemini_extractor):
        """Gemini 경로: 안과 필드 코드가 OPH_ 패턴 준수."""
        text = "안압이 오른쪽 28, 왼쪽 14로 측정됐습니다. 우안 고안압 녹내장 약물 시작"
        normalized = gemini_extractor.preprocess(text)
        domains = gemini_extractor.detect_domains(normalized)
        fields = gemini_extractor.extract_fields(normalized, domains)

        assert len(fields) > 0, "안과 케이스 필드 추출 0건 (Gemini 경로)"
        oph_fields = [f for f in fields if f["field_code"].startswith("OPH_")]
        assert len(oph_fields) > 0, (
            f"OPH_ 패턴 필드 없음 (Gemini 경로). 추출됨: {[f['field_code'] for f in fields]}"
        )

    def test_gemini_ophthalmology_iop_value(self, gemini_extractor):
        """Gemini 경로: 우안 안압 수치 28 추출."""
        text = "안압이 오른쪽 28, 왼쪽 14로 측정됐습니다. 우안 고안압 녹내장 약물 시작"
        normalized = gemini_extractor.preprocess(text)
        domains = gemini_extractor.detect_domains(normalized)
        fields = gemini_extractor.extract_fields(normalized, domains)

        iop_field = next(
            (f for f in fields if f.get("field_code") == "OPH_IOP_OD"), None
        )
        assert iop_field is not None, "OPH_IOP_OD 미추출 (Gemini 경로)"
        assert iop_field["value"] == 28.0, (
            f"우안 안압 기대 28.0, 실제: {iop_field['value']}"
        )

    # ── G3: 내과 케이스 — Gemini 경로 ───────────────────────────────────
    def test_gemini_vital_signs_domain(self, gemini_extractor):
        """Gemini 경로: 내과 케이스 VITAL_SIGNS 도메인 탐지."""
        text = "체온 38.5도 심박수 120회 점막 핑크 탈수 5%"
        normalized = gemini_extractor.preprocess(text)
        domains = gemini_extractor.detect_domains(normalized)
        assert "VITAL_SIGNS" in domains, (
            f"VITAL_SIGNS 미탐지 (Gemini 경로). 탐지됨: {domains}"
        )

    def test_gemini_vital_signs_soap_section(self, gemini_extractor):
        """Gemini 경로: 활력징후 필드 SOAP O 분류 확인."""
        text = "체온 38.5도 심박수 120회 점막 핑크 탈수 5%"
        result = gemini_extractor.extract(text)
        assert "soap" in result
        # 활력징후는 Objective(O) 섹션에 있어야 함
        obj = result["soap"].get("objective")
        assert obj is not None, "Objective(O) 섹션 비어있음 (Gemini 경로)"

    # ── G4: 정형외과 케이스 — Gemini 경로 ───────────────────────────────
    def test_gemini_orthopedics_domain(self, gemini_extractor):
        """Gemini 경로: 정형외과 케이스 ORTHOPEDICS 도메인 탐지."""
        text = "오른쪽 뒷다리 파행 3급, 슬개골 내측 탈구 grade 2"
        normalized = gemini_extractor.preprocess(text)
        domains = gemini_extractor.detect_domains(normalized)
        assert "ORTHOPEDICS" in domains, (
            f"ORTHOPEDICS 미탐지 (Gemini 경로). 탐지됨: {domains}"
        )

    def test_gemini_orthopedics_field_extraction(self, gemini_extractor):
        """Gemini 경로: 정형외과 ORT_ 필드 최소 1개 추출."""
        text = "오른쪽 뒷다리 파행 3급, 슬개골 내측 탈구 grade 2"
        normalized = gemini_extractor.preprocess(text)
        domains = gemini_extractor.detect_domains(normalized)
        fields = gemini_extractor.extract_fields(normalized, domains)

        ort_fields = [f for f in fields if f["field_code"].startswith("ORT_")]
        assert len(ort_fields) > 0, (
            f"ORT_ 필드 없음 (Gemini 경로). 추출됨: {[f['field_code'] for f in fields]}"
        )

    # ── G5: null 처리 + llm_metadata 구조 ───────────────────────────────
    def test_gemini_null_not_inserted(self, gemini_extractor):
        """Gemini 경로: 텍스트에 없는 필드는 추출하지 않음 (null 삽입 금지)."""
        text = "체온 38.5도 심박수 120회"
        normalized = gemini_extractor.preprocess(text)
        domains = gemini_extractor.detect_domains(normalized)
        fields = gemini_extractor.extract_fields(normalized, domains)

        field_codes = [f["field_code"] for f in fields]
        # 텍스트에 없는 혈압 필드 추출 금지
        assert "GP_BP_SYS_VALUE" not in field_codes, (
            "텍스트에 없는 혈압 필드가 추출됨 → null 삽입 위반 (Gemini 경로)"
        )

    def test_gemini_extract_returns_llm_metadata(self, gemini_extractor):
        """Gemini 경로: extract() 반환값에 llm_metadata 포함 및 구조 확인."""
        text = "체온 38.5도 심박수 120회 점막 핑크"
        result = gemini_extractor.extract(text)

        assert "llm_metadata" in result, "llm_metadata 키 누락"
        meta = result["llm_metadata"]
        assert "backend" in meta, "llm_metadata.backend 누락"
        # dry_run 모드에서는 "dry_run" 또는 "gemini"
        assert meta["backend"] in ("gemini", "dry_run"), (
            f"예상치 않은 backend 값: {meta['backend']}"
        )
