"""scripts/r8_phase2_query_dataset.py — R-8 Phase 2 Step 2: 100쿼리 dataset 작성.

[설계서] docs/20260427_r8_phase2_handoff.md §3-3 Step 2
[목적]   T1-T11 (11) + 89 신규 쿼리 = 100쿼리, 각 query_text + gold_concept_id + category.

분류 분포 (핸드오프 §3-1·§4-2):
  vet-specific          20  (T1·T2·T6·T11 + 16 신규)
  범용 disorder         25  (T3·T4·T5·T7·T8 + 20 신규)  [T7=T3=73211009 중복; T5 gold 부여 709044004]
  procedure             20  (신규 20)
  body structure        15  (신규 15)
  drug                  10  (신규 10)
  한국어 reformulate     10  (T9·T10 + 8 신규)

산출: data/r8_phase2_query_dataset.json
       _metadata + _category_distribution + queries[100]

실행: venv/bin/python scripts/r8_phase2_query_dataset.py
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
OUT_PATH = PROJECT_ROOT / "data" / "r8_phase2_query_dataset.json"

RANDOM_SEED = 20260427


# T1-T11 manual mapping. T5 gold 신규 부여 (709044004 일반 CKD), T1·T11 중복, T3·T7·T9 중복, T4·T10 중복.
T_QUERIES = [
    {"qid": "T1",  "query_text": "feline panleukopenia SNOMED code", "gold_concept_id": "339181000009108",
     "category": "vet-specific", "language": "en", "source": "regression_metrics.json"},
    {"qid": "T2",  "query_text": "canine parvovirus enteritis", "gold_concept_id": "47457000",
     "category": "vet-specific", "language": "en", "source": "regression_metrics.json"},
    {"qid": "T3",  "query_text": "diabetes mellitus in cat", "gold_concept_id": "73211009",
     "category": "vet-specific", "language": "en", "source": "regression_metrics.json"},
    {"qid": "T4",  "query_text": "pancreatitis in dog", "gold_concept_id": "75694006",
     "category": "vet-specific", "language": "en", "source": "regression_metrics.json"},
    {"qid": "T5",  "query_text": "chronic kidney disease in cat", "gold_concept_id": "709044004",
     "category": "general-disorder", "language": "en",
     "source": "regression_metrics.json (gold None) — Phase 2 신규 부여 (Chronic kidney disease 일반)"},
    {"qid": "T6",  "query_text": "cat bite wound", "gold_concept_id": "283782004",
     "category": "vet-specific", "language": "en", "source": "regression_metrics.json"},
    {"qid": "T7",  "query_text": "feline diabetes", "gold_concept_id": "73211009",
     "category": "vet-specific", "language": "en", "source": "regression_metrics.json"},
    {"qid": "T8",  "query_text": "diabetes mellitus type 1", "gold_concept_id": "46635009",
     "category": "general-disorder", "language": "en", "source": "regression_metrics.json"},
    {"qid": "T9",  "query_text": "고양이 당뇨", "gold_concept_id": "73211009",
     "category": "korean-reformulate", "language": "ko", "source": "regression_metrics.json"},
    {"qid": "T10", "query_text": "개 췌장염", "gold_concept_id": "75694006",
     "category": "korean-reformulate", "language": "ko", "source": "regression_metrics.json"},
    {"qid": "T11", "query_text": "고양이 범백혈구감소증 SNOMED 코드", "gold_concept_id": "339181000009108",
     "category": "korean-reformulate", "language": "ko", "source": "regression_metrics.json"},
]


# 89 신규 쿼리 — DB에서 결정론적 sample 추출 + query_text 변형
# 분류별 신규 N: vet 16 / disorder 20 / procedure 20 / body 15 / drug 10 / korean 8
NEW_BUDGET = {
    "vet-specific": 16,
    "general-disorder": 20,
    "procedure": 20,
    "body-structure": 15,
    "drug": 10,
    "korean-reformulate": 8,
}


def fetch_vet_specific(cur, n: int, exclude: set[str]) -> list[dict]:
    """수의학 종 키워드 포함 disorder/finding/organism."""
    rows = cur.execute("""
        SELECT concept_id, semantic_tag, preferred_term FROM concept
        WHERE semantic_tag IN ('disorder', 'finding', 'organism')
          AND (
              LOWER(preferred_term) LIKE '%feline%' OR
              LOWER(preferred_term) LIKE '%canine%' OR
              LOWER(preferred_term) LIKE '%bovine%' OR
              LOWER(preferred_term) LIKE '%equine%' OR
              LOWER(preferred_term) LIKE '%porcine%' OR
              LOWER(preferred_term) LIKE '%avian%' OR
              LOWER(preferred_term) LIKE '%ovine%'
          )
          AND LENGTH(preferred_term) BETWEEN 8 AND 60
        ORDER BY concept_id
    """).fetchall()
    pool = [r for r in rows if r[0] not in exclude]
    picked = random.sample(pool, k=n)
    return [
        {
            "qid": f"N-vet-{i+1:02d}",
            "query_text": pt,
            "gold_concept_id": cid,
            "category": "vet-specific",
            "language": "en",
            "source": f"SNOMED preferred_term ({st})",
        }
        for i, (cid, st, pt) in enumerate(picked)
    ]


def fetch_general_disorder(cur, n: int, exclude: set[str]) -> list[dict]:
    rows = cur.execute("""
        SELECT concept_id, semantic_tag, preferred_term FROM concept
        WHERE semantic_tag = 'disorder'
          AND LOWER(preferred_term) NOT LIKE '%feline%'
          AND LOWER(preferred_term) NOT LIKE '%canine%'
          AND LOWER(preferred_term) NOT LIKE '%bovine%'
          AND LOWER(preferred_term) NOT LIKE '%equine%'
          AND LOWER(preferred_term) NOT LIKE '%porcine%'
          AND LOWER(preferred_term) NOT LIKE '%avian%'
          AND LENGTH(preferred_term) BETWEEN 8 AND 50
          AND preferred_term NOT LIKE '%co-occurrent%'
        ORDER BY concept_id
    """).fetchall()
    pool = [r for r in rows if r[0] not in exclude]
    picked = random.sample(pool, k=n)
    return [
        {
            "qid": f"N-dis-{i+1:02d}",
            "query_text": pt,
            "gold_concept_id": cid,
            "category": "general-disorder",
            "language": "en",
            "source": "SNOMED preferred_term (disorder)",
        }
        for i, (cid, st, pt) in enumerate(picked)
    ]


def fetch_procedure(cur, n: int, exclude: set[str]) -> list[dict]:
    rows = cur.execute("""
        SELECT concept_id, semantic_tag, preferred_term FROM concept
        WHERE semantic_tag = 'procedure'
          AND LENGTH(preferred_term) BETWEEN 8 AND 50
          AND LOWER(preferred_term) NOT LIKE '%measurement%'
          AND LOWER(preferred_term) NOT LIKE '%screening for%'
          AND LOWER(preferred_term) NOT LIKE '%resettlement%'
          AND LOWER(preferred_term) NOT LIKE '%adoption%'
        ORDER BY concept_id
    """).fetchall()
    pool = [r for r in rows if r[0] not in exclude]
    picked = random.sample(pool, k=n)
    return [
        {
            "qid": f"N-proc-{i+1:02d}",
            "query_text": pt,
            "gold_concept_id": cid,
            "category": "procedure",
            "language": "en",
            "source": "SNOMED preferred_term (procedure)",
        }
        for i, (cid, st, pt) in enumerate(picked)
    ]


def fetch_body_structure(cur, n: int, exclude: set[str]) -> list[dict]:
    rows = cur.execute("""
        SELECT concept_id, semantic_tag, preferred_term FROM concept
        WHERE semantic_tag = 'body structure'
          AND LENGTH(preferred_term) BETWEEN 8 AND 50
          AND LOWER(preferred_term) NOT LIKE 'entire %'
          AND LOWER(preferred_term) NOT LIKE 'all %'
        ORDER BY concept_id
    """).fetchall()
    pool = [r for r in rows if r[0] not in exclude]
    picked = random.sample(pool, k=n)
    return [
        {
            "qid": f"N-body-{i+1:02d}",
            "query_text": pt,
            "gold_concept_id": cid,
            "category": "body-structure",
            "language": "en",
            "source": "SNOMED preferred_term (body structure)",
        }
        for i, (cid, st, pt) in enumerate(picked)
    ]


def fetch_drug(cur, n: int, exclude: set[str]) -> list[dict]:
    """약물: substance만 (1,000 샘플의 6-tag 분포에 포함)."""
    rows = cur.execute("""
        SELECT concept_id, semantic_tag, preferred_term FROM concept
        WHERE semantic_tag = 'substance'
          AND LENGTH(preferred_term) BETWEEN 5 AND 40
          AND LOWER(preferred_term) NOT LIKE '% and %'
          AND LOWER(preferred_term) NOT LIKE 'product containing%'
        ORDER BY concept_id
    """).fetchall()
    pool = [r for r in rows if r[0] not in exclude]
    picked = random.sample(pool, k=n)
    return [
        {
            "qid": f"N-drug-{i+1:02d}",
            "query_text": pt,
            "gold_concept_id": cid,
            "category": "drug",
            "language": "en",
            "source": f"SNOMED preferred_term ({st})",
        }
        for i, (cid, st, pt) in enumerate(picked)
    ]


# 8 신규 한국어 reformulate — 영어 SNOMED concept을 한국어로 수동 번역
KOREAN_NEW = [
    {"qid": "N-ko-01", "en_term": "Hypothyroidism", "query_text": "갑상선 기능 저하증", "gold_concept_id": "40930008"},
    {"qid": "N-ko-02", "en_term": "Hyperthyroidism", "query_text": "갑상선 기능 항진증", "gold_concept_id": "34486009"},
    {"qid": "N-ko-03", "en_term": "Cataract", "query_text": "백내장", "gold_concept_id": "193570009"},
    {"qid": "N-ko-04", "en_term": "Glaucoma", "query_text": "녹내장", "gold_concept_id": "23986001"},
    {"qid": "N-ko-05", "en_term": "Otitis externa", "query_text": "외이염", "gold_concept_id": "3135009"},
    {"qid": "N-ko-06", "en_term": "Cardiac murmur", "query_text": "심장 잡음", "gold_concept_id": "88610006"},
    {"qid": "N-ko-07", "en_term": "Congenital hip dysplasia", "query_text": "고관절 이형성증", "gold_concept_id": "52781008"},
    {"qid": "N-ko-08", "en_term": "Lymphoma", "query_text": "림프종", "gold_concept_id": "118600007"},
]


def main() -> int:
    if not DB_PATH.exists():
        print(f"[ERROR] DB 없음: {DB_PATH}", file=sys.stderr)
        return 1

    random.seed(RANDOM_SEED)

    db = sqlite3.connect(str(DB_PATH))
    cur = db.cursor()

    queries: list[dict] = list(T_QUERIES)
    used = {q["gold_concept_id"] for q in queries}

    print(f"[INFO] T1-T11 loaded: {len(queries)} queries, {len(used)} unique gold")

    # 신규 추가 — 카테고리별 결정론적 sample
    for_category = [
        ("vet-specific", fetch_vet_specific, NEW_BUDGET["vet-specific"]),
        ("general-disorder", fetch_general_disorder, NEW_BUDGET["general-disorder"]),
        ("procedure", fetch_procedure, NEW_BUDGET["procedure"]),
        ("body-structure", fetch_body_structure, NEW_BUDGET["body-structure"]),
        ("drug", fetch_drug, NEW_BUDGET["drug"]),
    ]
    for cat, fetcher, n in for_category:
        added = fetcher(cur, n, used)
        for q in added:
            used.add(q["gold_concept_id"])
        queries.extend(added)
        print(f"[OK] {cat:18s} new={n:>2d}  cumulative={len(queries):>3d}")

    # 한국어 신규 8건 — gold concept 존재 검증
    for q in KOREAN_NEW:
        row = cur.execute(
            "SELECT preferred_term, semantic_tag FROM concept WHERE concept_id = ?",
            (q["gold_concept_id"],),
        ).fetchone()
        if row is None:
            print(f"[ERROR] Korean new gold 미존재: {q['qid']} {q['gold_concept_id']}", file=sys.stderr)
            return 4
        if q["gold_concept_id"] in used:
            print(f"[WARN] Korean new gold 중복: {q['qid']} {q['gold_concept_id']}", file=sys.stderr)
        q["category"] = "korean-reformulate"
        q["language"] = "ko"
        q["source"] = f"manual translation: {q['en_term']} → {row[0]}"
        used.add(q["gold_concept_id"])
        del q["en_term"]
    queries.extend(KOREAN_NEW)
    print(f"[OK] korean-reformulate new={len(KOREAN_NEW)}  cumulative={len(queries)}")

    if len(queries) != 100:
        print(f"[ERROR] 합계 불일치: {len(queries)} != 100", file=sys.stderr)
        return 5

    # 카테고리 분포 검증
    from collections import Counter
    cat_dist = Counter(q["category"] for q in queries)
    print()
    print("=== CATEGORY DISTRIBUTION ===")
    for k, v in cat_dist.most_common():
        print(f"  {k:20s} {v:3d}")

    # gold 분포 (semantic_tag별 — 1,000 샘플 강제 포함 시 보충 분포 계산용)
    gold_tags: list[str] = []
    for q in queries:
        row = cur.execute(
            "SELECT semantic_tag FROM concept WHERE concept_id = ?",
            (q["gold_concept_id"],),
        ).fetchone()
        gold_tags.append(row[0] if row else "MISSING")
    tag_dist = Counter(gold_tags)
    print()
    print("=== GOLD semantic_tag DISTRIBUTION ===")
    for k, v in tag_dist.most_common():
        print(f"  {k:20s} {v:3d}")

    payload = {
        "_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "random_seed": RANDOM_SEED,
            "source_db": "data/snomed_ct_vet.db",
            "method": "T1-T11 manual + 89 deterministic SNOMED sample + 8 Korean manual",
            "handoff": "docs/20260427_r8_phase2_handoff.md §3-3 Step 2",
        },
        "_category_distribution": dict(cat_dist),
        "_gold_semantic_tag_distribution": dict(tag_dist),
        "_unique_gold_count": len(set(q["gold_concept_id"] for q in queries)),
        "queries": queries,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print()
    print(f"[OK] Wrote {OUT_PATH.relative_to(PROJECT_ROOT)} ({len(queries)} queries, {payload['_unique_gold_count']} unique gold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
