"""scripts/r8_phase2_sample_extract.py — R-8 Phase 2 Step 1: 1,000 샘플 추출 (Gold-Forced Inclusion).

[설계서] docs/20260427_r8_phase2_handoff.md §3-3 Step 1 (옵션 A 재설계, 2026-04-27)
[목적]   100쿼리 gold concept 96 unique를 1,000 sample에 강제 포함 + 904 tag-stratified random.
         이유: random 1,000 안에 gold 적중 0/11 (T1-T11) — 평가 불가능.
         해결: 96 gold 우선 → 6 핸드오프 tag별 보충 random (target_n - gold_in_tag).

분포 (핸드오프 §3-1·§4-2 + Gold-Forced 보정):
  semantic_tag       target  gold_unique  random_added
  disorder            300        44          256
  procedure           200        20          180
  body structure      150        15          135
  finding             150         2          148
  organism            100         5           95
  substance           100        10           90
  ─────────────────────────────────────────────────
  total              1,000       96          904

방식: 결정론적 random.seed(20260427) + random.sample (재현 가능).

산출: data/r8_phase2_sample_concepts.json
       _metadata + _distribution + _gold_forced_inclusion + samples[1000]

실행: venv/bin/python scripts/r8_phase2_sample_extract.py (data/r8_phase2_query_dataset.json 선행 필수)
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "snomed_ct_vet.db"
QUERY_PATH = PROJECT_ROOT / "data" / "r8_phase2_query_dataset.json"
OUT_PATH = PROJECT_ROOT / "data" / "r8_phase2_sample_concepts.json"

RANDOM_SEED = 20260427

TARGET_DISTRIBUTION = [
    ("disorder", 300),
    ("procedure", 200),
    ("body structure", 150),
    ("finding", 150),
    ("organism", 100),
    ("substance", 100),
]


def main() -> int:
    if not DB_PATH.exists():
        print(f"[ERROR] DB 없음: {DB_PATH}", file=sys.stderr)
        return 1
    if not QUERY_PATH.exists():
        print(f"[ERROR] query dataset 없음: {QUERY_PATH} (Step 2 먼저 실행)", file=sys.stderr)
        return 1

    random.seed(RANDOM_SEED)

    db = sqlite3.connect(str(DB_PATH))
    cur = db.cursor()

    total = cur.execute("SELECT COUNT(*) FROM concept").fetchone()[0]
    print(f"[INFO] SNOMED concept total: {total:,}")
    print(f"[INFO] random.seed({RANDOM_SEED})")

    # 1. 96 unique gold concept 로드
    queries = json.loads(QUERY_PATH.read_text())["queries"]
    gold_ids = sorted({q["gold_concept_id"] for q in queries})
    print(f"[INFO] gold unique concept_id: {len(gold_ids)}")

    gold_rows: list[tuple[str, str, str]] = []
    gold_tag_count: dict[str, int] = {}
    out_of_handoff: list[tuple[str, str, str]] = []
    target_tags = {t for t, _ in TARGET_DISTRIBUTION}

    for cid in gold_ids:
        row = cur.execute(
            "SELECT concept_id, preferred_term, semantic_tag FROM concept WHERE concept_id = ?",
            (cid,),
        ).fetchone()
        if row is None:
            print(f"[ERROR] gold 미존재: {cid}", file=sys.stderr)
            return 2
        cid2, pt, st = row
        if st not in target_tags:
            out_of_handoff.append(row)
            continue
        gold_rows.append(row)
        gold_tag_count[st] = gold_tag_count.get(st, 0) + 1

    if out_of_handoff:
        print(
            f"[ERROR] gold semantic_tag가 핸드오프 6-tag 외: "
            f"{[(r[0], r[2], r[1]) for r in out_of_handoff]}",
            file=sys.stderr,
        )
        return 3

    print(f"[INFO] gold tag distribution: {gold_tag_count}")

    # 2. 6 tag별 random 보충 (target_n - gold_in_tag)
    samples: list[dict] = []
    actual_random: dict[str, int] = {}

    # 2-A. gold 96 우선 포함
    for cid, pt, st in gold_rows:
        samples.append({"concept_id": cid, "preferred_term": pt, "semantic_tag": st})

    # 2-B. tag별 random 보충
    for tag, target_n in TARGET_DISTRIBUTION:
        gold_n = gold_tag_count.get(tag, 0)
        random_n = target_n - gold_n
        if random_n < 0:
            print(f"[ERROR] {tag} target {target_n} < gold {gold_n}", file=sys.stderr)
            return 4

        rows = cur.execute(
            "SELECT concept_id, preferred_term, semantic_tag FROM concept "
            "WHERE semantic_tag = ? ORDER BY concept_id",
            (tag,),
        ).fetchall()
        # gold 제외 풀
        gold_set = {r[0] for r in gold_rows if r[2] == tag}
        pool = [r for r in rows if r[0] not in gold_set]

        if len(pool) < random_n:
            print(f"[ERROR] {tag} pool 부족: {len(pool)} < {random_n}", file=sys.stderr)
            return 5

        picked = random.sample(pool, k=random_n)
        for cid, pt, st in picked:
            samples.append({"concept_id": cid, "preferred_term": pt, "semantic_tag": st})
        actual_random[tag] = random_n
        print(
            f"[OK] {tag:20s} target={target_n:>4d}  gold={gold_n:>3d}  random+={random_n:>4d}  "
            f"pool={len(pool):>6,}"
        )

    # 검증
    if len(samples) != 1000:
        print(f"[ERROR] 합계 불일치: {len(samples)} != 1000", file=sys.stderr)
        return 6

    sample_ids = {s["concept_id"] for s in samples}
    if len(sample_ids) != 1000:
        print(f"[ERROR] 중복 발생: unique={len(sample_ids)} != 1000", file=sys.stderr)
        return 7

    # gold 100% 포함 검증
    missing_gold = set(gold_ids) - sample_ids
    if missing_gold:
        print(f"[ERROR] gold 누락: {missing_gold}", file=sys.stderr)
        return 8

    # 최종 분포
    from collections import Counter
    final_dist = Counter(s["semantic_tag"] for s in samples)
    print()
    print("=== FINAL DISTRIBUTION (target vs actual) ===")
    for tag, target_n in TARGET_DISTRIBUTION:
        actual = final_dist[tag]
        mark = "✓" if actual == target_n else "✗"
        print(f"  {mark} {tag:20s} target={target_n:>4d}  actual={actual:>4d}")

    payload = {
        "_metadata": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "random_seed": RANDOM_SEED,
            "source_db": "data/snomed_ct_vet.db",
            "source_total": total,
            "method": "Gold-Forced Inclusion (96 gold 우선) + tag-stratified random 904",
            "handoff": "docs/20260427_r8_phase2_handoff.md §3-3 Step 1 (옵션 A 재설계)",
            "rationale": "random 1,000 안에 T1-T11 gold 적중 0/11 → 평가 불가능. gold 강제 포함 필수.",
        },
        "_distribution": dict(final_dist),
        "_gold_forced_inclusion": {
            "gold_unique_count": len(gold_ids),
            "gold_tag_distribution": gold_tag_count,
            "random_added_per_tag": actual_random,
            "query_dataset": "data/r8_phase2_query_dataset.json",
        },
        "samples": samples,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print()
    print(f"[OK] Wrote {OUT_PATH.relative_to(PROJECT_ROOT)} ({len(samples)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
