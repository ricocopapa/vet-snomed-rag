"""
vet-snomed-rag v2.0 — Track B3+: MRCM 규칙 단위 테스트 (Day 4)
================================================================

테스트 4건:
  1. 25도메인 전부 로드 가능 (JSON 파싱)
  2. 각 도메인의 expected_semantic_tag는 표준 SCT semantic tag 중 하나
  3. forbidden attribute가 observable entity에 Procedure site(405813007) 포함
  4. 샘플 concept_id 5개 DB 실존 검증 PASS

성공 기준:
  - 테스트 1: domains_covered 25개 키 모두 로드
  - 테스트 2: 허용 semantic tag 화이트리스트 외 tag 존재 시 FAIL
  - 테스트 3: observable entity를 base로 하는 규칙 중 forbidden에 405813007 포함
  - 테스트 4: 지정 5개 concept_id DB 실존 PASS

실행:
  cd vet-snomed-rag
  venv/bin/python -m pytest tests/test_mrcm_rules.py -v
"""

from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MRCM_PATH = DATA_DIR / "mrcm_rules_v1.json"
DB_PATH = DATA_DIR / "snomed_ct_vet.db"

# 표준 SNOMED CT semantic tag 화이트리스트 (SKILL.md §2 원칙 1 기준)
VALID_SEMANTIC_TAGS = {
    "disorder",
    "finding",
    "observable entity",
    "procedure",
    "qualifier value",
    "body structure",
    "substance",
    "organism",
    "morphologic abnormality",
    "situation",
    "event",
    "product",
    "medicinal product",
    "regime/therapy",
    "specimen",
    "attribute",
}

# Day 4 B3+ 추가 25도메인 전수 커버 목록
EXPECTED_DOMAINS = {
    "OPH", "VITAL_SIGNS", "CARDIOLOGY", "ORTHOPEDICS", "DERMATOLOGY",
    "HEMATOLOGY", "CHEMISTRY", "URINALYSIS", "NEUROLOGY", "EAR_NOSE",
    "RESPIRATORY", "GASTROINTESTINAL", "DENTISTRY", "ENDOCRINE", "COAGULATION",
    "BLOOD_GAS", "MASS", "SCORING", "WOUND_TRAUMA", "NURSING",
    "ONCOLOGY", "ANESTHESIA", "SURGICAL_RECORD", "TRIAGE", "TOXICOLOGY",
}

# 테스트 4: 샘플 5개 concept_id (도메인별 대표 — DB 실존 검증 대상)
SAMPLE_CONCEPT_IDS = [
    ("103228002", "Hemoglobin saturation with oxygen", "HEMATOLOGY"),
    ("28317006",  "Hematocrit determination",          "HEMATOLOGY"),
    ("6942003",   "Level of consciousness",            "NEUROLOGY"),
    ("225390008", "Triage",                            "TRIAGE"),
    ("4192000",   "Toxicology testing for organophosphate insecticide", "TOXICOLOGY"),
]


class TestMRCMRulesLoad(unittest.TestCase):
    """테스트 1: 25도메인 전부 로드 가능 (JSON 파싱)"""

    @classmethod
    def setUpClass(cls):
        with open(MRCM_PATH, encoding="utf-8") as f:
            cls.rules = json.load(f)

    def test_01_json_parseable(self):
        """mrcm_rules_v1.json이 유효한 JSON이고 파싱 가능."""
        self.assertIsInstance(
            self.rules, dict,
            f"JSON 파싱 실패: 결과 타입={type(self.rules)}"
        )
        print(f"  [PASS] 테스트 1-A: JSON 파싱 OK — 키 {len(self.rules)}개")

    def test_01_all_25_domains_present(self):
        """25개 도메인 키가 모두 존재해야 함."""
        loaded_domains = {k for k in self.rules if not k.startswith("_")}
        missing = EXPECTED_DOMAINS - loaded_domains
        extra = loaded_domains - EXPECTED_DOMAINS

        self.assertEqual(
            len(missing), 0,
            f"누락 도메인 {len(missing)}개: {missing}"
        )

        # 메타 키(_meta 등) 외 도메인이 정확히 25개
        self.assertEqual(
            len(loaded_domains), 25,
            f"도메인 수 불일치: 기대=25, 실제={len(loaded_domains)}, extra={extra}"
        )

        print(f"  [PASS] 테스트 1-B: 25도메인 전수 로드 확인 — {sorted(loaded_domains)}")

    def test_01_each_domain_has_fields(self):
        """각 도메인은 최소 2개 이상의 필드 패턴 규칙을 포함해야 함."""
        insufficient = []
        for domain_key, domain_val in self.rules.items():
            if domain_key.startswith("_"):
                continue
            fields = domain_val.get("fields", {})
            if len(fields) < 2:
                insufficient.append((domain_key, len(fields)))

        self.assertEqual(
            len(insufficient), 0,
            f"필드 패턴 2개 미만 도메인 {len(insufficient)}개: {insufficient}"
        )

        total_fields = sum(
            len(v.get("fields", {}))
            for k, v in self.rules.items() if not k.startswith("_")
        )
        print(f"  [PASS] 테스트 1-C: 도메인별 최소 2개 필드 패턴 확인 — 총 {total_fields}개 규칙")


class TestMRCMRulesSemanticTags(unittest.TestCase):
    """테스트 2: 각 도메인의 expected_semantic_tag는 표준 SCT semantic tag 중 하나"""

    @classmethod
    def setUpClass(cls):
        with open(MRCM_PATH, encoding="utf-8") as f:
            cls.rules = json.load(f)

    def test_02_all_expected_semantic_tags_valid(self):
        """
        모든 필드 규칙의 expected_semantic_tag이 VALID_SEMANTIC_TAGS 화이트리스트에 속해야 함.
        SKILL.md §2 원칙 1 (Semantic Tag 화이트리스트 강제) 준수 검증.
        """
        invalid_tags = []
        for domain_key, domain_val in self.rules.items():
            if domain_key.startswith("_"):
                continue
            for pattern, rule in domain_val.get("fields", {}).items():
                tag = rule.get("expected_semantic_tag", "")
                if tag not in VALID_SEMANTIC_TAGS:
                    invalid_tags.append((domain_key, pattern, tag))

        self.assertEqual(
            len(invalid_tags), 0,
            f"허용되지 않는 semantic tag {len(invalid_tags)}건: {invalid_tags}"
        )

        # 도메인별 tag 분포 출력
        tag_dist: dict[str, int] = {}
        for domain_key, domain_val in self.rules.items():
            if domain_key.startswith("_"):
                continue
            for _pattern, rule in domain_val.get("fields", {}).items():
                t = rule.get("expected_semantic_tag", "MISSING")
                tag_dist[t] = tag_dist.get(t, 0) + 1

        print(f"  [PASS] 테스트 2: 전 필드 expected_semantic_tag 유효 — 분포: {tag_dist}")


class TestMRCMRulesForbiddenAttributes(unittest.TestCase):
    """테스트 3: observable entity에 Procedure site(405813007) forbidden 포함 확인"""

    @classmethod
    def setUpClass(cls):
        with open(MRCM_PATH, encoding="utf-8") as f:
            cls.rules = json.load(f)

    def test_03_observable_entity_forbids_procedure_site(self):
        """
        expected_semantic_tag='observable entity'인 필드 규칙 중
        mrcm_forbidden_attributes에 405813007(Procedure site - Direct)이 포함된 규칙이
        반드시 1개 이상 존재해야 함.

        근거: observable entity hierarchy는 MRCM상 Procedure site 부착이 허용되지 않는다.
        (feedback_mrcm_constraint_check 준수)
        """
        observable_rules_with_forbidden_proc_site = []
        observable_rules_without = []

        for domain_key, domain_val in self.rules.items():
            if domain_key.startswith("_"):
                continue
            for pattern, rule in domain_val.get("fields", {}).items():
                if rule.get("expected_semantic_tag") == "observable entity":
                    forbidden = rule.get("mrcm_forbidden_attributes", [])
                    if "405813007" in forbidden:
                        observable_rules_with_forbidden_proc_site.append(
                            (domain_key, pattern)
                        )
                    else:
                        observable_rules_without.append(
                            (domain_key, pattern, forbidden)
                        )

        self.assertGreater(
            len(observable_rules_with_forbidden_proc_site), 0,
            "observable entity 규칙 중 Procedure site(405813007) forbidden 포함 규칙이 없음"
        )

        print(
            f"  [PASS] 테스트 3: observable entity + Procedure site forbidden "
            f"{len(observable_rules_with_forbidden_proc_site)}개 확인"
        )
        print(f"    (검증 대상 샘플: {observable_rules_with_forbidden_proc_site[:3]})")


class TestMRCMRulesConceptIdValidation(unittest.TestCase):
    """테스트 4: 샘플 concept_id 5개 DB 실존 검증 PASS"""

    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(str(DB_PATH))

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _validate_concept(self, concept_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM concept WHERE concept_id = ? LIMIT 1",
            (concept_id,)
        ).fetchone()
        return row is not None

    def test_04_sample_concept_ids_exist_in_db(self):
        """
        Day 4 B3+ 신규 도메인 대표 concept_id 5개가 snomed_ct_vet.db에 실존해야 함.

        피드백 feedback_snomed_source_validation 준수:
        RF2 원본 DB 검증 없이 AI 추론 concept_id 사용 절대 금지.
        """
        failed = []
        passed = []

        for concept_id, label, domain in SAMPLE_CONCEPT_IDS:
            exists = self._validate_concept(concept_id)
            if exists:
                passed.append((concept_id, label, domain))
            else:
                failed.append((concept_id, label, domain))

        self.assertEqual(
            len(failed), 0,
            f"DB 실존 검증 실패 concept_id {len(failed)}개: {failed}"
        )

        self.assertEqual(
            len(passed), 5,
            f"샘플 5개 모두 PASS해야 함. 실제 PASS={len(passed)}"
        )

        print(f"  [PASS] 테스트 4: 샘플 concept_id 5/5 DB 실존 PASS")
        for cid, label, domain in passed:
            row = self.conn.execute(
                "SELECT preferred_term, semantic_tag FROM concept WHERE concept_id = ? LIMIT 1",
                (cid,)
            ).fetchone()
            print(f"    OK: {cid} | {row[0]} | {row[1]} ({domain})")

    def test_04_all_mrcm_base_concepts_exist(self):
        """
        mrcm_rules_v1.json 내 모든 base_concept_id가 DB에 실존해야 함.
        (기존 test_snomed_tagger.py test_mrcm_rule_concepts_all_exist와 동일 검증 강화)
        """
        with open(MRCM_PATH, encoding="utf-8") as f:
            rules = json.load(f)

        failed = []
        total = 0
        for domain_key, domain_val in rules.items():
            if domain_key.startswith("_"):
                continue
            for pattern, rule in domain_val.get("fields", {}).items():
                cid = rule.get("base_concept_id")
                if cid:
                    total += 1
                    if not self._validate_concept(cid):
                        failed.append((domain_key, pattern, cid))

        self.assertEqual(
            len(failed), 0,
            f"MRCM 규칙 내 DB 미존재 base_concept_id {len(failed)}건: {failed}"
        )

        print(
            f"  [PASS] 테스트 4-B: 전체 base_concept_id {total}개 DB 실존 검증 완료"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
