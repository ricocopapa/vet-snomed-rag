"""
test_metrics.py — scripts/eval/metrics.py 단위 테스트
======================================================

테스트 항목:
  1. field_precision_recall — 정상 케이스
  2. field_precision_recall — 빈 predicted (precision=None 방지)
  3. field_precision_recall — 빈 gold (recall=None 방지)
  4. snomed_match_rate — exact 완전 일치
  5. snomed_match_rate — exact 일부 불일치
  6. snomed_match_rate — UNMAPPED 처리
  7. snomed_match_rate — gold_tags 빈 리스트 (rate=None)
  8. latency_stats — 정상 레코드 5건
  9. latency_stats — n=0 케이스
  10. aggregate_metrics — 시나리오 3건 집계

[절대 원칙]
  - 통계 수치만 검증. 임상 판단 금지
  - 수치 범위: 0.0 ~ 1.0 (precision/recall/rate)
  - division by zero 없음 확인
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.eval.metrics import (
    field_precision_recall,
    snomed_match_rate,
    latency_stats,
    aggregate_metrics,
    compute_scenario_metrics,
    _load_valid_field_codes,
)


# ─── 픽스처 ──────────────────────────────────────────────────────────────────

GOLD_FIELDS_OPH = [
    {"field_code": "OPH_IOP_OD",               "value": "32", "section": "O"},
    {"field_code": "OPH_IOP_CD",               "value": "ELEVATED", "section": "O"},
    {"field_code": "OPH_CORNEA_CLARITY_OD_CD", "value": "EDEMATOUS", "section": "O"},
    {"field_code": "OPH_AC_DEPTH_OD_CD",       "value": "SHALLOW", "section": "O"},
    {"field_code": "OPH_PLR_DIRECT_OD",        "value": "DECREASED", "section": "O"},
]

GOLD_SNOMED_OPH = [
    {"field_code": "OPH_IOP_OD",               "concept_id": "41633001",
     "preferred_term": "Intraocular pressure", "confidence": 0.95},
    {"field_code": "OPH_CORNEA_CLARITY_OD_CD", "concept_id": "27194006",
     "preferred_term": "Corneal edema",        "confidence": 0.90},
    {"field_code": "Assessment(진단)",          "concept_id": "23986001",
     "preferred_term": "Glaucoma",             "confidence": 0.90},
]

SAMPLE_RECORD = {
    "encounter_id": "550e8400-e29b-41d4-a716-446655440000",
    "latency_ms": {"stt": 0.0, "soap": 1200.5, "snomed": 800.3, "total": 2001.8},
    "fields": [],
    "snomed_tagging": [],
    "errors": [],
}


# ─── Test 1: field_precision_recall 정상 케이스 ──────────────────────────────

def test_field_precision_recall_normal():
    """TP=3, FP=1, FN=2 케이스에서 precision/recall/f1 정확히 계산되는지 확인."""
    predicted = [
        {"field_code": "OPH_IOP_OD"},
        {"field_code": "OPH_IOP_CD"},
        {"field_code": "OPH_CORNEA_CLARITY_OD_CD"},
        {"field_code": "OPH_EXTRA_FIELD"},    # FP
    ]
    gold = [
        {"field_code": "OPH_IOP_OD"},
        {"field_code": "OPH_IOP_CD"},
        {"field_code": "OPH_CORNEA_CLARITY_OD_CD"},
        {"field_code": "OPH_AC_DEPTH_OD_CD"},  # FN
        {"field_code": "OPH_PLR_DIRECT_OD"},   # FN
    ]
    result = field_precision_recall(predicted, gold)

    assert result["tp"] == 3
    assert result["fp"] == 1
    assert result["fn"] == 2
    # precision = 3/4 = 0.75
    assert result["precision"] == pytest.approx(0.75, abs=0.001)
    # recall = 3/5 = 0.60
    assert result["recall"] == pytest.approx(0.60, abs=0.001)
    # f1 = 2*0.75*0.60 / (0.75+0.60) ≈ 0.667
    assert result["f1"] == pytest.approx(0.667, abs=0.001)
    # 수치 범위 검증 (0~1)
    assert 0.0 <= result["precision"] <= 1.0
    assert 0.0 <= result["recall"] <= 1.0
    assert 0.0 <= result["f1"] <= 1.0


# ─── Test 2: 빈 predicted → precision=None ────────────────────────────────────

def test_field_precision_recall_empty_predicted():
    """predicted_fields가 빈 경우 precision=None, recall=0.0, division by zero 없음."""
    result = field_precision_recall([], GOLD_FIELDS_OPH)

    assert result["precision"] is None
    assert result["tp"] == 0
    assert result["fp"] == 0
    assert result["fn"] == len(GOLD_FIELDS_OPH)
    # recall = 0/5 = 0.0
    assert result["recall"] == pytest.approx(0.0, abs=0.001)
    # precision이 None이므로 f1도 None
    assert result["f1"] is None
    assert "precision=None" in result["note"]


# ─── Test 3: 빈 gold → recall=None ────────────────────────────────────────────

def test_field_precision_recall_empty_gold():
    """gold_fields가 빈 경우 recall=None, precision=0.0, division by zero 없음."""
    predicted = [{"field_code": "OPH_IOP_OD"}, {"field_code": "OPH_IOP_CD"}]
    result = field_precision_recall(predicted, [])

    assert result["recall"] is None
    assert result["fn"] == 0
    # precision = 0/(0+2) = 0.0 (TP=0이므로)
    assert result["precision"] == pytest.approx(0.0, abs=0.001)
    assert result["f1"] is None
    assert "recall=None" in result["note"]


# ─── Test 4: snomed_match_rate exact 완전 일치 ───────────────────────────────

def test_snomed_match_rate_exact_full_match():
    """predicted가 gold와 완전 일치하는 경우 rate=1.0."""
    predicted_tags = [
        {"field_code": "OPH_IOP_OD",               "concept_id": "41633001"},
        {"field_code": "OPH_CORNEA_CLARITY_OD_CD", "concept_id": "27194006"},
        {"field_code": "Assessment(진단)",          "concept_id": "23986001"},
    ]
    result = snomed_match_rate(predicted_tags, GOLD_SNOMED_OPH, mode="exact")

    assert result["match_count"] == 3
    assert result["total"] == 3
    assert result["rate"] == pytest.approx(1.0, abs=0.001)
    assert result["mode"] == "exact"
    assert len(result["unmatched"]) == 0


# ─── Test 5: snomed_match_rate exact 일부 불일치 ─────────────────────────────

def test_snomed_match_rate_exact_partial_match():
    """일부 concept_id 불일치 → rate 계산 정확성."""
    predicted_tags = [
        {"field_code": "OPH_IOP_OD",               "concept_id": "41633001"},  # 일치
        {"field_code": "OPH_CORNEA_CLARITY_OD_CD", "concept_id": "99999999"},  # 불일치
        {"field_code": "Assessment(진단)",          "concept_id": "23986001"},  # 일치
    ]
    result = snomed_match_rate(predicted_tags, GOLD_SNOMED_OPH, mode="exact")

    assert result["match_count"] == 2
    assert result["total"] == 3
    assert result["rate"] == pytest.approx(2 / 3, abs=0.001)
    assert 0.0 <= result["rate"] <= 1.0
    assert len(result["unmatched"]) == 1
    assert result["unmatched"][0]["field_code"] == "OPH_CORNEA_CLARITY_OD_CD"


# ─── Test 6: snomed_match_rate UNMAPPED 처리 ─────────────────────────────────

def test_snomed_match_rate_unmapped():
    """UNMAPPED concept_id는 불일치로 처리되어야 한다."""
    predicted_tags = [
        {"field_code": "OPH_IOP_OD",               "concept_id": "UNMAPPED"},
        {"field_code": "OPH_CORNEA_CLARITY_OD_CD", "concept_id": "UNMAPPED"},
        {"field_code": "Assessment(진단)",          "concept_id": "UNMAPPED"},
    ]
    result = snomed_match_rate(predicted_tags, GOLD_SNOMED_OPH, mode="exact")

    assert result["match_count"] == 0
    assert result["total"] == 3
    assert result["rate"] == pytest.approx(0.0, abs=0.001)
    assert len(result["unmatched"]) == 3


# ─── Test 7: snomed_match_rate gold 빈 리스트 → rate=None ────────────────────

def test_snomed_match_rate_empty_gold():
    """gold_tags가 빈 경우 total=0, rate=None, division by zero 없음."""
    predicted_tags = [{"field_code": "OPH_IOP_OD", "concept_id": "41633001"}]
    result = snomed_match_rate(predicted_tags, [], mode="exact")

    assert result["total"] == 0
    assert result["rate"] is None
    assert "rate=None" in result["note"]


# ─── Test 8: latency_stats 정상 5건 ──────────────────────────────────────────

def test_latency_stats_normal():
    """5개 레코드에서 p50/p95/mean이 올바르게 계산되는지 확인."""
    records = [
        {"latency_ms": {"stt": 0.0,  "soap": 1000.0, "snomed": 500.0,  "total": 1500.0}},
        {"latency_ms": {"stt": 0.0,  "soap": 1200.0, "snomed": 600.0,  "total": 1800.0}},
        {"latency_ms": {"stt": 0.0,  "soap": 900.0,  "snomed": 450.0,  "total": 1350.0}},
        {"latency_ms": {"stt": 0.0,  "soap": 1100.0, "snomed": 550.0,  "total": 1650.0}},
        {"latency_ms": {"stt": 0.0,  "soap": 1300.0, "snomed": 700.0,  "total": 2000.0}},
    ]
    result = latency_stats(records)

    # soap: [900, 1000, 1100, 1200, 1300]
    assert result["soap"]["n"] == 5
    assert result["soap"]["p50"] == pytest.approx(1100.0, abs=1.0)
    # p95: index = max(0, int(5*0.95)-1) = max(0, 3) = 3 → sorted[3] = 1200
    assert result["soap"]["p95"] == pytest.approx(1200.0, abs=1.0)
    assert result["soap"]["mean"] == pytest.approx(1100.0, abs=1.0)

    # total: [1350, 1500, 1650, 1800, 2000]
    assert result["total"]["n"] == 5
    assert result["total"]["p50"] == pytest.approx(1650.0, abs=1.0)

    # 수치 범위: latency는 0 이상
    assert result["total"]["p50"] >= 0
    assert result["total"]["p95"] >= result["total"]["p50"]


# ─── Test 9: latency_stats n=0 케이스 ────────────────────────────────────────

def test_latency_stats_empty():
    """레코드 없는 경우 모든 스테이지 p50/p95/mean=None, division by zero 없음."""
    result = latency_stats([])

    for stage in ("stt", "soap", "snomed", "total"):
        assert result[stage]["n"] == 0
        assert result[stage]["p50"] is None
        assert result[stage]["p95"] is None
        assert result[stage]["mean"] is None


# ─── Test 10: aggregate_metrics 3건 집계 ─────────────────────────────────────

def test_aggregate_metrics_three_scenarios():
    """3개 시나리오 메트릭 집계 결과가 올바른 범위인지 확인."""
    per_scenario = [
        {
            "scenario_id": 1, "domain": "OPHTHALMOLOGY",
            "field_metrics":  {"precision": 0.857, "recall": 0.600, "f1": 0.706,
                               "tp": 6, "fp": 1, "fn": 4, "note": ""},
            "snomed_metrics": {"rate": 0.667, "match_count": 2, "total": 3,
                               "mode": "exact", "unmatched": [], "note": ""},
            "latency":        {
                "stt":   {"p50": 0.0,   "p95": 0.0,   "mean": 0.0,   "n": 1},
                "soap":  {"p50": 1200.0,"p95": 1200.0,"mean": 1200.0,"n": 1},
                "snomed":{"p50": 800.0, "p95": 800.0, "mean": 800.0, "n": 1},
                "total": {"p50": 2000.0,"p95": 2000.0,"mean": 2000.0,"n": 1},
                "note": "",
            },
        },
        {
            "scenario_id": 2, "domain": "GASTROINTESTINAL",
            "field_metrics":  {"precision": 1.0,  "recall": 0.875, "f1": 0.933,
                               "tp": 7, "fp": 0, "fn": 1, "note": ""},
            "snomed_metrics": {"rate": 0.800, "match_count": 4, "total": 5,
                               "mode": "exact", "unmatched": [], "note": ""},
            "latency":        {
                "stt":   {"p50": 0.0,   "p95": 0.0,   "mean": 0.0,   "n": 1},
                "soap":  {"p50": 1500.0,"p95": 1500.0,"mean": 1500.0,"n": 1},
                "snomed":{"p50": 1000.0,"p95": 1000.0,"mean": 1000.0,"n": 1},
                "total": {"p50": 2500.0,"p95": 2500.0,"mean": 2500.0,"n": 1},
                "note": "",
            },
        },
        {
            "scenario_id": 3, "domain": "ORTHOPEDICS",
            "field_metrics":  {"precision": 0.800, "recall": 0.800, "f1": 0.800,
                               "tp": 4, "fp": 1, "fn": 1, "note": ""},
            "snomed_metrics": {"rate": 1.0,   "match_count": 3, "total": 3,
                               "mode": "exact", "unmatched": [], "note": ""},
            "latency":        {
                "stt":   {"p50": 0.0,   "p95": 0.0,   "mean": 0.0,   "n": 1},
                "soap":  {"p50": 1100.0,"p95": 1100.0,"mean": 1100.0,"n": 1},
                "snomed":{"p50": 700.0, "p95": 700.0, "mean": 700.0, "n": 1},
                "total": {"p50": 1800.0,"p95": 1800.0,"mean": 1800.0,"n": 1},
                "note": "",
            },
        },
    ]

    agg = aggregate_metrics(per_scenario)

    assert agg["n_scenarios"] == 3

    # precision_mean = (0.857 + 1.0 + 0.800) / 3 ≈ 0.886
    assert agg["field"]["precision_mean"] == pytest.approx(0.886, abs=0.001)
    # recall_mean = (0.600 + 0.875 + 0.800) / 3 ≈ 0.758
    assert agg["field"]["recall_mean"] == pytest.approx(0.758, abs=0.001)
    # 총 TP/FP/FN
    assert agg["field"]["total_tp"] == 17
    assert agg["field"]["total_fp"] == 2
    assert agg["field"]["total_fn"] == 6

    # snomed exact_rate_mean = (0.667 + 0.800 + 1.0) / 3 ≈ 0.822
    assert agg["snomed"]["exact_rate_mean"] == pytest.approx(0.822, abs=0.001)

    # latency p95 (3개 시나리오 total p95: [2000, 2500, 1800] → sorted → [1800,2000,2500]
    # idx = max(0, int(3*0.95)-1) = max(0, 1) = 1 → 2000.0)
    assert agg["latency_total_p95_ms"] == pytest.approx(2000.0, abs=1.0)

    # 수치 범위 검증
    assert 0.0 <= agg["field"]["precision_mean"] <= 1.0
    assert 0.0 <= agg["field"]["recall_mean"] <= 1.0
    assert 0.0 <= agg["snomed"]["exact_rate_mean"] <= 1.0


# ─── Test 11 (보너스): snomed_match_rate mode 오류 처리 ──────────────────────

def test_snomed_match_rate_invalid_mode():
    """잘못된 mode 입력 시 ValueError 발생 확인."""
    with pytest.raises(ValueError, match="mode는"):
        snomed_match_rate([], [], mode="fuzzy")


# ─── Test 12 (보너스): field_precision_recall 완전 일치 ──────────────────────

def test_field_precision_recall_perfect():
    """predicted == gold일 때 precision=1.0, recall=1.0, f1=1.0."""
    fields = [{"field_code": f"CODE_{i}"} for i in range(5)]
    result = field_precision_recall(fields, fields)

    assert result["tp"] == 5
    assert result["fp"] == 0
    assert result["fn"] == 0
    assert result["precision"] == pytest.approx(1.0, abs=0.001)
    assert result["recall"] == pytest.approx(1.0, abs=0.001)
    assert result["f1"] == pytest.approx(1.0, abs=0.001)


# ─── Test 13~15: field_precision_recall superset 모드 ────────────────────────

def test_field_precision_recall_superset_schema_exists():
    """superset 모드: 스키마 실존 추가 필드는 중립(neutral)으로 처리되어 Precision 개선.

    시나리오:
      gold = [OPH_IOP_OD, OPH_IOP_CD, OPH_CORNEA_CLARITY_OD_CD] (3건)
      predicted = gold 3건 + OPH_AC_DEPTH_OD_CD (스키마 실존) + FAKE_GHOST_FIELD_XYZ (비실존)

    strict 모드: FP=2 → precision = 3/(3+2) = 0.600
    superset 모드: OPH_AC_DEPTH_OD_CD는 neutral, FAKE_GHOST_FIELD_XYZ는 FP
      → FP=1, neutral=1 → precision = 3/(3+1) = 0.750
    """
    gold = [
        {"field_code": "OPH_IOP_OD"},
        {"field_code": "OPH_IOP_CD"},
        {"field_code": "OPH_CORNEA_CLARITY_OD_CD"},
    ]
    # OPH_AC_DEPTH_OD_CD: field_schema_v26.json 실존 코드
    # FAKE_GHOST_FIELD_XYZ: 비실존 코드 (hallucination)
    predicted = [
        {"field_code": "OPH_IOP_OD"},
        {"field_code": "OPH_IOP_CD"},
        {"field_code": "OPH_CORNEA_CLARITY_OD_CD"},
        {"field_code": "OPH_AC_DEPTH_OD_CD"},      # 스키마 실존 → neutral
        {"field_code": "FAKE_GHOST_FIELD_XYZ"},    # 비실존 → FP
    ]

    strict_result = field_precision_recall(predicted, gold, mode="strict")
    superset_result = field_precision_recall(predicted, gold, mode="superset")

    # strict 모드 확인
    assert strict_result["tp"] == 3
    assert strict_result["fp"] == 2
    assert strict_result["neutral"] == 0
    assert strict_result["mode"] == "strict"
    assert strict_result["precision"] == pytest.approx(0.600, abs=0.001)

    # superset 모드: Precision 개선 확인
    assert superset_result["tp"] == 3
    assert superset_result["fn"] == 0
    assert superset_result["mode"] == "superset"
    # neutral은 스키마 로드 성공 시 1건 (OPH_AC_DEPTH_OD_CD)
    # fp는 1건 (FAKE_GHOST_FIELD_XYZ) 또는 스키마 로드 실패 시 2건
    if superset_result["neutral"] == 1:
        # 스키마 로드 성공 경로
        assert superset_result["fp"] == 1
        assert superset_result["precision"] == pytest.approx(0.750, abs=0.001)
    else:
        # 스키마 로드 실패 → strict 폴백
        assert superset_result["fp"] == 2
        assert superset_result["precision"] == pytest.approx(0.600, abs=0.001)
        assert "strict 폴백" in superset_result["note"]

    # recall은 모드와 무관하게 동일
    assert strict_result["recall"] == pytest.approx(1.0, abs=0.001)
    assert superset_result["recall"] == pytest.approx(1.0, abs=0.001)


def test_field_precision_recall_superset_all_schema():
    """superset 모드: 추가 필드가 모두 스키마 실존이면 FP=0, precision=1.0.

    시나리오:
      gold = [OPH_IOP_OD] (1건)
      predicted = [OPH_IOP_OD, OPH_IOP_CD, OPH_PLR_DIRECT_OD] (모두 실존)

    superset 모드: neutral=2, FP=0 → precision = 1/(1+0) = 1.0
    strict 모드: FP=2 → precision = 1/(1+2) = 0.333
    """
    gold = [{"field_code": "OPH_IOP_OD"}]
    predicted = [
        {"field_code": "OPH_IOP_OD"},
        {"field_code": "OPH_IOP_CD"},
        {"field_code": "OPH_PLR_DIRECT_OD"},
    ]

    strict_result = field_precision_recall(predicted, gold, mode="strict")
    superset_result = field_precision_recall(predicted, gold, mode="superset")

    # strict 모드
    assert strict_result["tp"] == 1
    assert strict_result["fp"] == 2
    assert strict_result["precision"] == pytest.approx(1 / 3, abs=0.001)

    # superset 모드: 스키마 실존 필드만 있으므로 FP=0 기대
    assert superset_result["tp"] == 1
    assert superset_result["fn"] == 0
    assert superset_result["mode"] == "superset"
    if superset_result["neutral"] == 2:
        # 스키마 로드 성공 → precision = 1.0
        assert superset_result["fp"] == 0
        assert superset_result["precision"] == pytest.approx(1.0, abs=0.001)
    else:
        # 스키마 로드 실패 → strict 폴백
        assert superset_result["fp"] == 2


def test_field_precision_recall_superset_invalid_mode():
    """잘못된 mode 입력 시 ValueError 발생 확인."""
    with pytest.raises(ValueError, match="mode는"):
        field_precision_recall([], [], mode="loose")
