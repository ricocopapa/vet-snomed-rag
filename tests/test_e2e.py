"""
vet-snomed-rag v2.0 — Track B4: ClinicalEncoder E2E 단위 테스트
================================================================

테스트 3건:
  1. 텍스트 입력 → JSONL 레코드 §7.1 스키마 검증
  2. 존재하지 않는 오디오 파일 → graceful 에러 처리 (errors[] 기록, null 미반환)
  3. encounter_id UUID4 형식 검증 (36자, 8-4-4-4-12 패턴)

성공 기준:
  - 테스트 1: JSONL 레코드 required 키 전부 포함, encounter_id UUID4
  - 테스트 2: FileNotFoundError 미발생, errors[] 비어있지 않음
  - 테스트 3: encounter_id UUID4 형식 PASS (N=10회 반복)
  - 전 테스트: mock 모드 (dry_run=True) — 실 API 없이 동작 보장

실행:
  cd vet-snomed-rag
  venv/bin/python -m pytest tests/test_e2e.py -v
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.e2e import ClinicalEncoder, ClinicalEncoderConfig, _validate_uuid4

# §7.1 JSONL required 키 목록
REQUIRED_TOP_KEYS = [
    "encounter_id", "timestamp", "audio", "stt", "soap",
    "domains", "fields", "snomed_tagging", "latency_ms", "errors",
]
REQUIRED_AUDIO_KEYS = ["path", "duration_sec", "language"]
REQUIRED_STT_KEYS = ["raw_text", "normalized_text"]
REQUIRED_SOAP_KEYS = ["subjective", "objective", "assessment", "plan"]
REQUIRED_LATENCY_KEYS = ["stt", "soap", "snomed", "total"]


def make_encoder(dry_run: bool = True) -> ClinicalEncoder:
    """테스트용 ClinicalEncoder 생성 (dry_run 기본값 = API 미호출)."""
    config = ClinicalEncoderConfig(
        dry_run=dry_run,
        reformulator_backend="none",  # 테스트 시 RAG 파이프라인 최소화
        enable_rerank=False,
    )
    return ClinicalEncoder(config=config)


class TestClinicalEncoderSchema(unittest.TestCase):
    """테스트 1: 텍스트 입력 → §7.1 JSONL 스키마 검증 (mock 모드)."""

    @classmethod
    def setUpClass(cls):
        cls.encoder = make_encoder(dry_run=True)
        cls.record = cls.encoder.encode(
            "안압이 오른쪽 28mmHg, 왼쪽 14mmHg입니다. 우안 고안압으로 판단됩니다.",
            input_type="text",
        )
        print(f"\n[setup] record keys: {list(cls.record.keys())}")

    @classmethod
    def tearDownClass(cls):
        cls.encoder.close()

    def test_01a_required_top_keys_present(self):
        """§7.1 required 최상위 키 전부 존재 (O1: 필드 누락 0건)."""
        for key in REQUIRED_TOP_KEYS:
            self.assertIn(key, self.record, f"required 키 누락: {key!r}")

    def test_01b_audio_keys_present(self):
        """audio 서브 키 전부 존재."""
        audio = self.record.get("audio", {})
        for key in REQUIRED_AUDIO_KEYS:
            self.assertIn(key, audio, f"audio.{key} 누락")

    def test_01c_stt_keys_present(self):
        """stt 서브 키 전부 존재."""
        stt = self.record.get("stt", {})
        for key in REQUIRED_STT_KEYS:
            self.assertIn(key, stt, f"stt.{key} 누락")

    def test_01d_soap_keys_present(self):
        """soap 서브 키 전부 존재."""
        soap = self.record.get("soap", {})
        for key in REQUIRED_SOAP_KEYS:
            self.assertIn(key, soap, f"soap.{key} 누락")

    def test_01e_latency_keys_present(self):
        """latency_ms 서브 키 전부 존재."""
        latency = self.record.get("latency_ms", {})
        for key in REQUIRED_LATENCY_KEYS:
            self.assertIn(key, latency, f"latency_ms.{key} 누락")

    def test_01f_encounter_id_uuid4(self):
        """encounter_id가 UUID4 형식."""
        eid = self.record.get("encounter_id", "")
        self.assertTrue(
            _validate_uuid4(eid),
            f"encounter_id UUID4 형식 아님: {eid!r}"
        )

    def test_01g_domains_is_list(self):
        """domains는 list 타입."""
        self.assertIsInstance(self.record.get("domains"), list)

    def test_01h_fields_is_list(self):
        """fields는 list 타입."""
        self.assertIsInstance(self.record.get("fields"), list)

    def test_01i_snomed_tagging_is_list(self):
        """snomed_tagging는 list 타입."""
        self.assertIsInstance(self.record.get("snomed_tagging"), list)

    def test_01j_errors_is_list(self):
        """errors는 list 타입."""
        self.assertIsInstance(self.record.get("errors"), list)

    def test_01k_stt_raw_text_matches_input(self):
        """텍스트 입력 시 stt.raw_text = 입력 텍스트."""
        stt = self.record.get("stt", {})
        self.assertIn(
            "안압", stt.get("raw_text", ""),
            "stt.raw_text에 입력 텍스트가 반영되지 않음"
        )

    def test_01l_snomed_no_null_concept(self):
        """snomed_tagging 배열에 concept_id=null 없음 — UNMAPPED 또는 실존 ID만 허용.

        피드백 feedback_null_not_design_intent 준수.
        """
        for entry in self.record.get("snomed_tagging", []):
            concept_id = entry.get("concept_id")
            self.assertIsNotNone(
                concept_id,
                f"concept_id=None 발견 — UNMAPPED 또는 실존 ID만 허용: {entry}"
            )

    def test_01m_record_json_serializable(self):
        """레코드가 JSON 직렬화 가능 (JSONL 출력 요건)."""
        try:
            json.dumps(self.record, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            self.fail(f"레코드 JSON 직렬화 실패: {e}")

    def test_01n_latency_total_positive(self):
        """latency_ms.total > 0 (실제 처리 발생 증거)."""
        total = self.record.get("latency_ms", {}).get("total", 0)
        self.assertGreater(total, 0, "latency_ms.total이 0 이하")


class TestClinicalEncoderAudioError(unittest.TestCase):
    """테스트 2: 존재하지 않는 오디오 파일 → graceful 에러 처리."""

    @classmethod
    def setUpClass(cls):
        cls.encoder = make_encoder(dry_run=True)

    @classmethod
    def tearDownClass(cls):
        cls.encoder.close()

    def test_02a_nonexistent_audio_no_exception(self):
        """존재하지 않는 오디오 경로 → FileNotFoundError 미발생, errors[] 기록."""
        try:
            record = self.encoder.encode(
                "/tmp/nonexistent_audio_vet_smoke_test_99999.m4a",
                input_type="audio",
            )
        except Exception as e:
            self.fail(f"존재하지 않는 오디오 파일에서 예외 발생: {type(e).__name__}: {e}")

        # errors 배열에 STT_ERROR 기록
        errors = record.get("errors", [])
        self.assertTrue(
            len(errors) > 0,
            "존재하지 않는 오디오 파일인데 errors 배열이 비어 있음"
        )
        has_stt_error = any("STT_ERROR" in str(e) or "파일" in str(e) for e in errors)
        self.assertTrue(
            has_stt_error,
            f"errors에 STT 관련 오류 메시지 없음: {errors}"
        )

    def test_02b_nonexistent_audio_required_keys(self):
        """에러 발생해도 §7.1 required 키 모두 반환 (graceful)."""
        record = self.encoder.encode(
            "/tmp/nonexistent_audio_vet_smoke_test_99999.m4a",
            input_type="audio",
        )
        for key in REQUIRED_TOP_KEYS:
            self.assertIn(key, record, f"에러 시에도 required 키 유지: {key!r} 누락")

    def test_02c_audio_meta_preserved(self):
        """에러 발생 시에도 audio.path 기록."""
        path = "/tmp/nonexistent_audio_vet_smoke_test_99999.m4a"
        record = self.encoder.encode(path, input_type="audio")
        self.assertEqual(
            record.get("audio", {}).get("path"), path,
            "audio.path가 기록되지 않음"
        )

    def test_02d_encounter_id_still_uuid4(self):
        """에러 발생 시에도 encounter_id는 UUID4 형식."""
        record = self.encoder.encode(
            "/tmp/nonexistent_audio_vet_smoke_test_99999.m4a",
            input_type="audio",
        )
        eid = record.get("encounter_id", "")
        self.assertTrue(
            _validate_uuid4(eid),
            f"에러 시 encounter_id UUID4 형식 아님: {eid!r}"
        )


class TestClinicalEncoderUUID4(unittest.TestCase):
    """테스트 3: encounter_id UUID4 형식 검증 (N=10회 반복).

    피드백 feedback_uuid_format_verify:
    NULL 체크만으로 부족. uuid4 형식(36자, 8-4-4-4-12) + 중복 검증 필수.
    """

    UUID4_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    )

    @classmethod
    def setUpClass(cls):
        cls.encoder = make_encoder(dry_run=True)

    @classmethod
    def tearDownClass(cls):
        cls.encoder.close()

    def _generate_n_records(self, n: int) -> list[dict]:
        """N건 레코드 생성."""
        records = []
        for _ in range(n):
            r = self.encoder.encode("심박수 120회, 체온 38.5도", input_type="text")
            records.append(r)
        return records

    def test_03a_uuid4_format_valid(self):
        """encounter_id UUID4 형식 검증 (N=10)."""
        records = self._generate_n_records(10)
        for i, r in enumerate(records):
            eid = r.get("encounter_id", "")
            # 길이 검증 (36자)
            self.assertEqual(len(eid), 36, f"레코드 {i}: UUID4 길이 오류 ({len(eid)}자)")
            # 패턴 검증 (8-4-4-4-12)
            self.assertRegex(
                eid.lower(), self.UUID4_PATTERN,
                f"레코드 {i}: UUID4 패턴 불일치 — {eid!r}"
            )
            # version=4 확인 (하이픈 위치 14번째 문자)
            self.assertEqual(eid[14], "4", f"레코드 {i}: UUID version != 4 — {eid}")

    def test_03b_uuid4_uniqueness(self):
        """N=10 생성 시 모든 encounter_id 고유값 (중복 없음).

        피드백 feedback_uuid_format_verify: 중복 검증 필수.
        """
        records = self._generate_n_records(10)
        ids = [r.get("encounter_id") for r in records]
        unique_ids = set(ids)
        self.assertEqual(
            len(ids), len(unique_ids),
            f"encounter_id 중복 발생: {len(ids) - len(unique_ids)}건"
        )

    def test_03c_validate_uuid4_helper(self):
        """_validate_uuid4 헬퍼 함수 직접 검증."""
        # 유효한 UUID4
        valid = "550e8400-e29b-41d4-a716-446655440000"
        # UUID4 version=4, variant=[89ab]로 생성된 것 사용
        import uuid
        for _ in range(5):
            real_uuid4 = str(uuid.uuid4())
            self.assertTrue(
                _validate_uuid4(real_uuid4),
                f"실제 uuid4가 검증 실패: {real_uuid4!r}"
            )
        # 유효하지 않은 형식
        invalid_cases = [
            "not-a-uuid",
            "550e8400-e29b-31d4-a716-446655440000",  # version=3
            "550e8400-e29b-41d4-a716",               # 짧음
            "",
            "550e8400e29b41d4a716446655440000",       # 하이픈 없음
        ]
        for bad in invalid_cases:
            self.assertFalse(
                _validate_uuid4(bad),
                f"유효하지 않은 UUID4가 통과됨: {bad!r}"
            )


class TestClinicalEncoderBatch(unittest.TestCase):
    """배치 JSONL 출력 테스트."""

    @classmethod
    def setUpClass(cls):
        cls.encoder = make_encoder(dry_run=True)

    @classmethod
    def tearDownClass(cls):
        cls.encoder.close()

    def test_04a_encode_to_jsonl_file(self):
        """encode_to_jsonl → JSONL 파일 생성 및 파싱 검증."""
        inputs = [
            {"data": "안압 우안 28mmHg 고안압", "type": "text"},
            {"data": "심박수 120회/분, 호흡수 24회/분", "type": "text"},
        ]
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", delete=False, mode="w"
        ) as tmp:
            tmp_path = tmp.name

        try:
            records = self.encoder.encode_to_jsonl(inputs, output_path=tmp_path)
            self.assertEqual(len(records), 2, "2건 입력 → 2건 레코드 기대")

            # 파일 읽기 검증
            with open(tmp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 2, "JSONL 파일 2줄 기대")

            # 각 줄 JSON 파싱 가능
            for line in lines:
                record = json.loads(line)
                for key in REQUIRED_TOP_KEYS:
                    self.assertIn(key, record, f"JSONL 레코드 키 누락: {key}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
