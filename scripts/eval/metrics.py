"""
metrics.py — C2 메트릭 계산 모듈
===================================

함수:
  field_precision_recall(predicted_fields, gold_fields)
      → {precision, recall, f1, tp, fp, fn}

  snomed_match_rate(predicted_tags, gold_tags, mode="exact")
      → {match_count, total, rate, mode}

  latency_stats(records)
      → {stt: {p50, p95, mean}, soap: ..., snomed: ..., total: ...}

[절대 원칙]
  - 통계 계산만 수행. 임상/투자 판단 금지 (data-analyzer 원칙)
  - 추측 수치 금지. 측정 불가 항목은 명시 (P3 원칙)
  - 모든 수치는 소수점 3자리까지 계산
  - division by zero 방지 — 분모 0이면 NaN 아닌 None 반환 + 이유 명시
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SNOMED_DB = PROJECT_ROOT / "data" / "snomed_ct_vet.db"
DEFAULT_FIELD_SCHEMA = PROJECT_ROOT / "data" / "field_schema_v26.json"

# ─── field_schema_v26.json 로드 (superset 모드 실존 field_code 검증용) ──────────

_VALID_FIELD_CODES: Optional[set] = None


def _load_valid_field_codes(schema_path: Path = DEFAULT_FIELD_SCHEMA) -> set:
    """field_schema_v26.json에서 전체 field_code 집합을 로드한다.

    반환값은 모듈 레벨 캐시(_VALID_FIELD_CODES)에 저장하여 중복 로드를 방지한다.
    파일 미존재 시 빈 set을 반환하며, superset 모드에서 비실존 코드를 FP로 처리한다.
    """
    global _VALID_FIELD_CODES
    if _VALID_FIELD_CODES is not None:
        return _VALID_FIELD_CODES
    if not schema_path.exists():
        _VALID_FIELD_CODES = set()
        return _VALID_FIELD_CODES
    try:
        with open(schema_path, encoding="utf-8") as f:
            raw = json.load(f)
        codes: set = set()
        for domain in raw.get("domains", []):
            for field in domain.get("fields", []):
                fc = field.get("field_code", "").strip()
                if fc:
                    codes.add(fc)
        _VALID_FIELD_CODES = codes
    except Exception:
        _VALID_FIELD_CODES = set()
    return _VALID_FIELD_CODES


# ─── 필드 precision / recall ──────────────────────────────────────────────────

def field_precision_recall(
    predicted_fields: list[dict],
    gold_fields: list[dict],
    mode: str = "strict",
    schema_path: Path = DEFAULT_FIELD_SCHEMA,
) -> dict[str, Any]:
    """필드 추출 precision / recall / f1 을 계산한다.

    Args:
        predicted_fields : ClinicalEncoder 출력의 fields 배열
                           [{"field_code": str, "value": Any, ...}, ...]
        gold_fields      : gold-label의 fields 배열
                           [{"field_code": str, "value": str, ...}, ...]
        mode             : "strict" (기본) | "superset"
                           "strict"   — gold-label 외 추가 필드는 FP로 계산 (기존 동작)
                           "superset" — Gemini가 gold 외 필드를 추가 추출한 경우:
                                        · 스키마 실존 field_code → 중립 (TP 아님, FP 아님)
                                        · 스키마 비실존 field_code → FP (hallucination)
                                        ※ gold-label은 최소 기대치이며 superset 추출을 허용
        schema_path      : field_schema_v26.json 경로 (superset 모드 실존 검증용)

    Returns:
        {
          "precision": float | None,  # TP / (TP + FP)
          "recall":    float | None,  # TP / (TP + FN)
          "f1":        float | None,  # 2*P*R / (P+R)
          "tp":        int,
          "fp":        int,           # strict: gold 외 전부 / superset: 비실존 코드만
          "fn":        int,
          "neutral":   int,           # superset 모드: 스키마 실존 추가 필드 수 (strict=0)
          "mode":      str,
          "note":      str  # precision/recall None 이유 명시
        }

    판단 기준 (strict):
      - TP: predicted_fields 중 gold_fields에 동일 field_code가 있는 건
      - FP: predicted_fields에 있지만 gold_fields에 없는 건
      - FN: gold_fields에 있지만 predicted_fields에 없는 건

    판단 기준 (superset):
      - TP: predicted_fields 중 gold_fields에 동일 field_code가 있는 건
      - FP: gold에 없고 스키마에도 없는 field_code (hallucination)
      - Neutral: gold에 없지만 스키마에는 실존하는 field_code (합법적 추가 추출)
      - FN: gold_fields에 있지만 predicted_fields에 없는 건
      - Precision 분모: TP + FP (neutral 제외)
    """
    if mode not in ("strict", "superset"):
        raise ValueError(f"mode는 'strict' 또는 'superset'만 허용됩니다. 입력: {mode!r}")

    pred_codes = {f.get("field_code", "").strip() for f in predicted_fields if f.get("field_code")}
    gold_codes = {f.get("field_code", "").strip() for f in gold_fields if f.get("field_code")}

    tp = len(pred_codes & gold_codes)
    fn = len(gold_codes - pred_codes)
    extra_codes = pred_codes - gold_codes  # gold에 없는 추가 필드

    note = ""
    neutral = 0
    fp = 0

    if mode == "strict":
        fp = len(extra_codes)
    else:  # superset
        valid_codes = _load_valid_field_codes(schema_path)
        for fc in extra_codes:
            if valid_codes and fc in valid_codes:
                neutral += 1  # 스키마 실존 → 중립 (합법적 추가 추출)
            else:
                fp += 1       # 스키마 비실존 → FP (hallucination)
        if not valid_codes:
            # 스키마 로드 실패 시 strict 방식으로 폴백
            fp = len(extra_codes)
            neutral = 0
            note += "superset 모드: 스키마 로드 실패 → strict 폴백; "

    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None

    if tp + fp > 0:
        precision = round(tp / (tp + fp), 3)
    else:
        note += "precision=None(분모 0: predicted_fields 없음); "

    if tp + fn > 0:
        recall = round(tp / (tp + fn), 3)
    else:
        note += "recall=None(분모 0: gold_fields 없음); "

    if precision is not None and recall is not None:
        if precision + recall > 0:
            f1 = round(2 * precision * recall / (precision + recall), 3)
        else:
            f1 = 0.0
            note += "f1=0.0(P+R=0); "

    return {
        "precision": precision,
        "recall":    recall,
        "f1":        f1,
        "tp":        tp,
        "fp":        fp,
        "fn":        fn,
        "neutral":   neutral,
        "mode":      mode,
        "note":      note.strip(),
    }


def field_precision_recall_by_domain(
    predicted_fields: list[dict],
    gold_fields: list[dict],
    domain: str,
) -> dict[str, Any]:
    """도메인별 precision/recall 계산 (domain 필드 기준 필터링).

    Args:
        predicted_fields: 전체 예측 필드 목록
        gold_fields     : 전체 gold-label 필드 목록
        domain          : 필터링할 도메인 코드 (예: "OPHTHALMOLOGY")

    Returns:
        field_precision_recall() 반환값에 "domain" 키 추가
    """
    # domain 필드 기준 필터 (없으면 전체 사용)
    pred = [f for f in predicted_fields if f.get("domain", "").upper() == domain.upper()]
    gold = [f for f in gold_fields if f.get("domain", "").upper() == domain.upper()]

    result = field_precision_recall(pred, gold)
    result["domain"] = domain
    return result


# ─── SNOMED 태깅 일치율 ────────────────────────────────────────────────────────

def snomed_match_rate(
    predicted_tags: list[dict],
    gold_tags: list[dict],
    mode: str = "exact",
    snomed_db_path: Path = DEFAULT_SNOMED_DB,
) -> dict[str, Any]:
    """SNOMED 태깅 일치율을 계산한다.

    Args:
        predicted_tags : ClinicalEncoder 출력의 snomed_tagging 배열
                         [{"field_code": str, "concept_id": str, ...}, ...]
        gold_tags      : gold-label의 snomed 배열
                         [{"field_code": str, "concept_id": str, ...}, ...]
        mode           : "exact" — concept_id 완전 일치
                         "synonym" — IS-A 상위/하위 2단계 허용 (SQLite 조회)
        snomed_db_path : SNOMED CT VET SQLite DB 경로 (synonym 모드 전용)

    Returns:
        {
          "match_count": int,
          "total":       int,  # gold_tags 건수
          "rate":        float | None,
          "mode":        str,
          "unmatched":   [{"field_code", "gold_concept_id", "predicted_concept_id"}, ...],
          "note":        str
        }

    판단 기준:
      - gold_tags의 field_code 기준으로 predicted_tags와 매칭
      - UNMAPPED는 일치 불가 처리
      - total=0이면 rate=None
    """
    # gold_tags field_code → concept_id 매핑
    gold_map: dict[str, str] = {}
    for tag in gold_tags:
        fc = tag.get("field_code", "").strip()
        cid = tag.get("concept_id", "").strip()
        if fc and cid:
            gold_map[fc] = cid

    # predicted_tags field_code → concept_id 매핑 (중복 시 첫 번째)
    pred_map: dict[str, str] = {}
    for tag in predicted_tags:
        fc = tag.get("field_code", "").strip()
        cid = tag.get("concept_id", "").strip()
        if fc and fc not in pred_map:
            pred_map[fc] = cid

    total = len(gold_map)
    match_count = 0
    unmatched: list[dict[str, str]] = []

    if mode == "exact":
        for fc, gold_cid in gold_map.items():
            pred_cid = pred_map.get(fc, "UNMAPPED")
            if pred_cid == gold_cid:
                match_count += 1
            else:
                unmatched.append({
                    "field_code":          fc,
                    "gold_concept_id":     gold_cid,
                    "predicted_concept_id": pred_cid,
                })

    elif mode == "synonym":
        # IS-A 상위/하위 2단계 허용 (SQLite 조회)
        related_cache: dict[str, set[str]] = {}

        def _get_related(concept_id: str) -> set[str]:
            """IS-A 상위/하위 2단계 concept_id 집합을 반환한다."""
            if concept_id in related_cache:
                return related_cache[concept_id]
            related: set[str] = {concept_id}
            if not snomed_db_path.exists():
                related_cache[concept_id] = related
                return related
            try:
                conn = sqlite3.connect(str(snomed_db_path))
                cur = conn.cursor()
                # 상위 2단계 (부모, 조부모)
                cur.execute(
                    """
                    WITH RECURSIVE ancestors(id, depth) AS (
                        SELECT CAST(destination_id AS TEXT), 1
                        FROM relationship
                        WHERE CAST(source_id AS TEXT) = ? AND type_id = 116680003
                        UNION ALL
                        SELECT CAST(r.destination_id AS TEXT), a.depth + 1
                        FROM relationship r
                        JOIN ancestors a ON CAST(r.source_id AS TEXT) = a.id
                        WHERE r.type_id = 116680003 AND a.depth < 2
                    )
                    SELECT id FROM ancestors
                    """,
                    (str(concept_id),),
                )
                for (cid_row,) in cur.fetchall():
                    related.add(str(cid_row))
                # 하위 2단계 (자식, 손자)
                cur.execute(
                    """
                    WITH RECURSIVE descendants(id, depth) AS (
                        SELECT CAST(source_id AS TEXT), 1
                        FROM relationship
                        WHERE CAST(destination_id AS TEXT) = ? AND type_id = 116680003
                        UNION ALL
                        SELECT CAST(r.source_id AS TEXT), d.depth + 1
                        FROM relationship r
                        JOIN descendants d ON CAST(r.destination_id AS TEXT) = d.id
                        WHERE r.type_id = 116680003 AND d.depth < 2
                    )
                    SELECT id FROM descendants
                    """,
                    (str(concept_id),),
                )
                for (cid_row,) in cur.fetchall():
                    related.add(str(cid_row))
                conn.close()
            except Exception:
                pass  # DB 접근 실패 시 exact 매칭만 수행
            related_cache[concept_id] = related
            return related

        for fc, gold_cid in gold_map.items():
            pred_cid = pred_map.get(fc, "UNMAPPED")
            if pred_cid == "UNMAPPED":
                unmatched.append({
                    "field_code":          fc,
                    "gold_concept_id":     gold_cid,
                    "predicted_concept_id": pred_cid,
                })
                continue
            related = _get_related(gold_cid)
            if pred_cid in related:
                match_count += 1
            else:
                unmatched.append({
                    "field_code":          fc,
                    "gold_concept_id":     gold_cid,
                    "predicted_concept_id": pred_cid,
                })
    else:
        raise ValueError(f"mode는 'exact' 또는 'synonym'만 허용됩니다. 입력: {mode!r}")

    note = ""
    rate: Optional[float] = None
    if total > 0:
        rate = round(match_count / total, 3)
    else:
        note = "rate=None(total=0: gold_tags 없음)"

    return {
        "match_count": match_count,
        "total":       total,
        "rate":        rate,
        "mode":        mode,
        "unmatched":   unmatched,
        "note":        note,
    }


# ─── Latency 통계 ──────────────────────────────────────────────────────────────

def latency_stats(records: list[dict]) -> dict[str, Any]:
    """JSONL 레코드 목록에서 단계별 latency 통계를 계산한다.

    Args:
        records: ClinicalEncoder 출력 레코드 목록.
                 각 레코드에 latency_ms: {stt, soap, snomed, total} 포함.

    Returns:
        {
          "stt":    {"p50": float, "p95": float, "mean": float, "n": int},
          "soap":   {...},
          "snomed": {...},
          "total":  {...},
          "note":   str
        }

    판단 기준:
      - 수치 없는 단계는 p50/p95/mean = None
      - n=0이면 모든 수치 None
      - 소수점 3자리 반올림
    """
    stages = ("stt", "soap", "snomed", "total")
    stage_values: dict[str, list[float]] = {s: [] for s in stages}

    for rec in records:
        latency = rec.get("latency_ms", {})
        if isinstance(latency, dict):
            for stage in stages:
                val = latency.get(stage)
                if isinstance(val, (int, float)) and val >= 0:
                    stage_values[stage].append(float(val))

    result: dict[str, Any] = {}
    notes: list[str] = []

    for stage in stages:
        vals = stage_values[stage]
        n = len(vals)
        if n == 0:
            result[stage] = {"p50": None, "p95": None, "mean": None, "n": 0}
            notes.append(f"{stage}: n=0 — 수치 없음")
        else:
            sorted_vals = sorted(vals)
            # p50: 중앙값
            p50 = round(statistics.median(sorted_vals), 3)
            # p95: 하위 95% 분위수
            idx_95 = max(0, int(len(sorted_vals) * 0.95) - 1)
            p95 = round(sorted_vals[idx_95], 3)
            mean = round(statistics.mean(sorted_vals), 3)
            result[stage] = {"p50": p50, "p95": p95, "mean": mean, "n": n}

    result["note"] = "; ".join(notes) if notes else ""
    return result


# ─── 집계 헬퍼: 시나리오별 메트릭 계산 ──────────────────────────────────────────

def compute_scenario_metrics(
    scenario_id: int,
    gold: dict,
    predicted_record: dict,
    snomed_mode: str = "exact",
) -> dict[str, Any]:
    """단일 시나리오의 모든 메트릭을 계산한다.

    Args:
        scenario_id      : 시나리오 번호
        gold             : parse_gold_labels.parse_scenario_file() 반환값
        predicted_record : ClinicalEncoder.encode() 반환값
        snomed_mode      : "exact" or "synonym"

    Returns:
        {
          "scenario_id": int,
          "domain": str,
          "field_metrics": {...},
          "snomed_metrics": {...},
          "latency": {...}
        }
    """
    gold_fields = gold.get("fields", [])
    pred_fields = predicted_record.get("fields", [])

    gold_snomed = gold.get("snomed", [])
    pred_snomed = predicted_record.get("snomed_tagging", [])

    field_m = field_precision_recall(pred_fields, gold_fields)
    snomed_m = snomed_match_rate(pred_snomed, gold_snomed, mode=snomed_mode)
    lat = latency_stats([predicted_record])

    return {
        "scenario_id":    scenario_id,
        "domain":         gold.get("domain", "UNKNOWN"),
        "field_metrics":  field_m,
        "snomed_metrics": snomed_m,
        "latency":        lat,
    }


def aggregate_metrics(
    per_scenario: list[dict],
) -> dict[str, Any]:
    """시나리오별 메트릭을 집계하여 전체 요약을 반환한다.

    Args:
        per_scenario: compute_scenario_metrics() 반환값 목록

    Returns:
        {
          "n_scenarios": int,
          "field": {
            "precision_mean": float | None,
            "recall_mean":    float | None,
            "f1_mean":        float | None,
            "total_tp": int, "total_fp": int, "total_fn": int
          },
          "snomed": {
            "exact_rate_mean": float | None,
            "synonym_rate_mean": float | None
          },
          "latency_total_p95_ms": float | None
        }
    """
    n = len(per_scenario)
    if n == 0:
        return {"n_scenarios": 0, "field": {}, "snomed": {}, "latency_total_p95_ms": None}

    # 필드 집계
    prec_list = [m["field_metrics"]["precision"] for m in per_scenario
                 if m["field_metrics"]["precision"] is not None]
    rec_list  = [m["field_metrics"]["recall"] for m in per_scenario
                 if m["field_metrics"]["recall"] is not None]
    f1_list   = [m["field_metrics"]["f1"] for m in per_scenario
                 if m["field_metrics"]["f1"] is not None]
    total_tp = sum(m["field_metrics"]["tp"] for m in per_scenario)
    total_fp = sum(m["field_metrics"]["fp"] for m in per_scenario)
    total_fn = sum(m["field_metrics"]["fn"] for m in per_scenario)

    # SNOMED 집계
    snomed_rate_list = [m["snomed_metrics"]["rate"] for m in per_scenario
                        if m["snomed_metrics"]["rate"] is not None]

    # Latency 집계 — 전체 시나리오 p95
    total_vals = []
    for m in per_scenario:
        total_lat = m["latency"].get("total", {})
        if isinstance(total_lat, dict):
            p95 = total_lat.get("p95")
            if p95 is not None:
                total_vals.append(p95)

    lat_p95: Optional[float] = None
    if total_vals:
        sorted_vals = sorted(total_vals)
        idx = max(0, int(len(sorted_vals) * 0.95) - 1)
        lat_p95 = round(sorted_vals[idx], 3)

    return {
        "n_scenarios": n,
        "field": {
            "precision_mean": round(sum(prec_list) / len(prec_list), 3) if prec_list else None,
            "recall_mean":    round(sum(rec_list) / len(rec_list), 3) if rec_list else None,
            "f1_mean":        round(sum(f1_list) / len(f1_list), 3) if f1_list else None,
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn,
        },
        "snomed": {
            "exact_rate_mean": round(sum(snomed_rate_list) / len(snomed_rate_list), 3)
                               if snomed_rate_list else None,
        },
        "latency_total_p95_ms": lat_p95,
    }
