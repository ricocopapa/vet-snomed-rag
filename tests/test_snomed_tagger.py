"""
vet-snomed-rag v2.0 — Track B3: SNOMEDTagger 단위 테스트
=========================================================

테스트 3건:
  1. 단일 필드 매핑: CA_OPH_IOP_OD_VAL=28 (높은 IOP)
     → IOP concept_id(41633001) + "High" interpretation 후조합 SCG 검증
  2. MRCM 위반 시도: observable entity(IOP)에 procedure attribute(405813007) 부착
     → mrcm_validated=False 확인
  3. 매핑 실패: 존재하지 않는 field_code → concept_id="UNMAPPED"

성공 기준:
  - 테스트 1: concept_id=41633001 DB 실존, confidence>0, post_coordination 비어있지 않음
  - 테스트 2: check_mrcm() → False 반환
  - 테스트 3: concept_id="UNMAPPED", source="UNMAPPED"
  - 전 테스트: validate_concept_exists() 통과한 concept_id만 수용

실행:
  cd vet-snomed-rag
  venv/bin/python -m pytest tests/test_snomed_tagger.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.snomed_tagger import SNOMEDTagger


class TestSNOMEDTaggerValidation(unittest.TestCase):
    """DB 실존 검증 + MRCM 검증 테스트 (RAG 파이프라인 불필요)"""

    @classmethod
    def setUpClass(cls):
        """테스트용 SNOMEDTagger (RAG 없음 — DB 검증 전용)."""
        cls.tagger = SNOMEDTagger(rag_pipeline=None)

    @classmethod
    def tearDownClass(cls):
        cls.tagger.close()

    # ─────────────────────────────────────────────────────────────────
    # 테스트 1: 단일 필드 매핑 — CA_OPH_IOP_OD_VAL=28
    # ─────────────────────────────────────────────────────────────────

    def test_01_iop_field_mapping(self):
        """
        IOP 우안 필드(28mmHg, 정상 상한 초과) → MRCM 직접 지정 concept(41633001) 채택 확인.
        - concept_id는 RF2 DB 실존 검증 통과해야 함
        - post_coordination에 Has interpretation = High SCG 포함 확인
        - mrcm_validated=True
        """
        entry = self.tagger.tag_field(
            field_code="CA_OPH_IOP_OD_VAL",
            value=28,
            domain="OPH",
        )

        # concept_id 반드시 "UNMAPPED"가 아니어야 함
        self.assertNotEqual(
            entry["concept_id"], "UNMAPPED",
            f"IOP 필드가 UNMAPPED 처리됨: {entry}"
        )

        # MRCM 직접 지정 base_concept = 41633001 (Intraocular pressure)
        self.assertEqual(
            entry["concept_id"], "41633001",
            f"IOP concept_id 불일치: 기대=41633001, 실제={entry['concept_id']}"
        )

        # RF2 DB 실존 검증 통과 확인
        self.assertTrue(
            self.tagger.validate_concept_exists(entry["concept_id"]),
            f"concept_id={entry['concept_id']} DB 실존 검증 실패"
        )

        # MRCM 검증 통과
        self.assertTrue(
            entry["mrcm_validated"],
            f"mrcm_validated=False: {entry}"
        )

        # confidence > 0
        self.assertGreater(
            entry["confidence"], 0.0,
            f"confidence={entry['confidence']} — 0 이하 불가"
        )

        # post_coordination: 수치 28mmHg → High interpretation SCG 포함
        self.assertIn(
            "363713009",  # Has interpretation attribute_id
            entry["post_coordination"],
            f"SCG에 Has interpretation(363713009) 미포함: {entry['post_coordination']}"
        )
        self.assertIn(
            "75540009",  # High concept_id
            entry["post_coordination"],
            f"SCG에 High(75540009) 미포함: {entry['post_coordination']}"
        )

        # post_coordination SCG의 모든 concept_id DB 실존 검증
        if entry["post_coordination"]:
            import re
            scg_ids = re.findall(r"\b(\d{6,18})\b", entry["post_coordination"])
            for cid in scg_ids:
                self.assertTrue(
                    self.tagger.validate_concept_exists(cid),
                    f"SCG 내 concept_id={cid} DB 실존 검증 실패 (가짜 concept_id)"
                )

        print(f"  [PASS] 테스트 1: concept_id={entry['concept_id']}, "
              f"term={entry['preferred_term']}, SCG={entry['post_coordination'][:80]}...")

    # ─────────────────────────────────────────────────────────────────
    # 테스트 2: MRCM 위반 시도
    # ─────────────────────────────────────────────────────────────────

    def test_02_mrcm_violation(self):
        """
        observable entity(IOP, 41633001)에 procedure attribute(405813007: Procedure site - Direct) 부착 시도
        → check_mrcm() = False 반환 확인.

        피드백 feedback_mrcm_constraint_check 준수:
        observable entity에 procedure hierarchy 전용 attribute 부착은 MRCM 비허용.
        """
        # 405813007 = Procedure site - Direct (procedure 전용 attribute)
        result = self.tagger.check_mrcm(
            base_concept_id="41633001",   # Intraocular pressure (observable entity)
            attribute_id="405813007",      # Procedure site - Direct (procedure 전용)
        )

        self.assertFalse(
            result,
            "MRCM 위반 시도가 True 반환됨 — "
            "observable entity에 Procedure site 부착은 허용되어서는 안 됨"
        )

        # 역 확인: 허용 attribute(Has interpretation)는 True 반환
        result_allowed = self.tagger.check_mrcm(
            base_concept_id="41633001",
            attribute_id="363713009",  # Has interpretation (허용)
        )
        self.assertTrue(
            result_allowed,
            "Has interpretation(363713009)이 IOP에서 허용되어야 함"
        )

        print(f"  [PASS] 테스트 2: Procedure site on observable entity = False, "
              f"Has interpretation on observable entity = True")

    # ─────────────────────────────────────────────────────────────────
    # 테스트 3: 매핑 실패 — 존재하지 않는 field_code
    # ─────────────────────────────────────────────────────────────────

    def test_03_unmapped_field(self):
        """
        MRCM 규칙에 없고 RAG도 없는 상태에서 임의 field_code → UNMAPPED 정확 플래그.

        피드백 feedback_null_not_design_intent 준수:
        NULL 반환 금지. 매핑 실패 시 concept_id="UNMAPPED", source="UNMAPPED" 명시.
        """
        entry = self.tagger.tag_field(
            field_code="XX_NONEXISTENT_FIELD_99999",
            value="some_value",
            domain="DEFAULT",
        )

        # concept_id 반드시 "UNMAPPED"
        self.assertEqual(
            entry["concept_id"], "UNMAPPED",
            f"존재하지 않는 필드가 UNMAPPED 처리되지 않음: {entry}"
        )

        # source 반드시 "UNMAPPED"
        self.assertEqual(
            entry["source"], "UNMAPPED",
            f"source가 UNMAPPED가 아님: {entry['source']}"
        )

        # NULL 반환 절대 금지 — 모든 필드가 non-None
        for key in ["field_code", "concept_id", "preferred_term",
                    "semantic_tag", "source", "post_coordination",
                    "mrcm_validated", "confidence"]:
            self.assertIn(key, entry, f"필수 키 '{key}' 누락")
            self.assertIsNotNone(entry[key], f"키 '{key}' = None (NULL 반환 금지)")

        # confidence = 0.0
        self.assertEqual(
            entry["confidence"], 0.0,
            f"UNMAPPED confidence는 0.0이어야 함: {entry['confidence']}"
        )

        print(f"  [PASS] 테스트 3: UNMAPPED 정확 플래그 확인 — {entry}")


class TestSNOMEDTaggerConceptValidation(unittest.TestCase):
    """RF2 DB 실존 검증 전용 테스트"""

    @classmethod
    def setUpClass(cls):
        cls.tagger = SNOMEDTagger(rag_pipeline=None)

    @classmethod
    def tearDownClass(cls):
        cls.tagger.close()

    def test_known_concept_exists(self):
        """알려진 IOP concept_id(41633001)가 DB에 실존함을 검증."""
        self.assertTrue(
            self.tagger.validate_concept_exists("41633001"),
            "41633001(Intraocular pressure) DB 실존 검증 실패"
        )

    def test_fake_concept_rejected(self):
        """가짜 concept_id는 반드시 False 반환 — AI 추론 생성 방지."""
        fake_ids = ["99999999999", "00000000001", "123456789"]
        for fake_id in fake_ids:
            self.assertFalse(
                self.tagger.validate_concept_exists(fake_id),
                f"가짜 concept_id={fake_id}가 True 반환됨 — AI 추론 concept_id 방지 실패"
            )

    def test_unmapped_not_valid(self):
        """'UNMAPPED' 문자열은 validate_concept_exists에서 False 반환."""
        self.assertFalse(
            self.tagger.validate_concept_exists("UNMAPPED"),
            "'UNMAPPED' 문자열이 valid concept으로 처리됨"
        )

    def test_mrcm_rule_concepts_all_exist(self):
        """mrcm_rules_v1.json에 정의된 모든 base_concept_id가 DB에 실존."""
        import json
        mrcm_path = PROJECT_ROOT / "data" / "mrcm_rules_v1.json"
        with open(mrcm_path) as f:
            rules = json.load(f)

        failed = []
        for domain_key, domain_val in rules.items():
            if domain_key.startswith("_"):
                continue
            for pattern, rule in domain_val.get("fields", {}).items():
                cid = rule.get("base_concept_id")
                if cid and not self.tagger.validate_concept_exists(cid):
                    failed.append((domain_key, pattern, cid))

        self.assertEqual(
            len(failed), 0,
            f"MRCM 규칙 내 DB 미존재 concept_id {len(failed)}건: {failed}"
        )
        print(f"  [PASS] MRCM 규칙 base_concept_id 전수 검증 완료")


if __name__ == "__main__":
    unittest.main(verbosity=2)
