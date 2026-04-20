"""
SNOMED CT VET → Obsidian Knowledge Graph 변환기.

VET(수의학 확장) 임상 개념을 중심으로 Obsidian 위키링크 기반
지식 그래프를 생성한다. VET가 참조하는 INT 개념도 포함하여
"수의학 확장이 국제 표준 위에 어떻게 구축되는지"를 시각화한다.

[실행]
    python src/tools/export_obsidian.py
    python src/tools/export_obsidian.py --output-dir /path/to/vault/SNOMED_Graph

[구조]
    중심 노드: VET disorder, procedure, medicinal product, finding
    연결 노드: VET/INT body structure, organism, substance, morphology
    엣지: Is a, Finding site, Causative agent, Associated morphology 등
"""

import sqlite3
import json
import re
import argparse
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "snomed_graph_v2"

# VET 임상 핵심 카테고리 (중심 노드)
VET_CLINICAL_TAGS = ["disorder", "procedure", "medicinal product", "finding"]

# 연결 대상 카테고리 (주변 노드 — VET/INT 모두)
RELATED_TAGS = [
    "body structure", "organism", "substance",
    "morphologic abnormality", "qualifier value",
    "observable entity", "cell", "physical force",
]

# 주요 관계 유형 (그래프에 포함할 것)
KEY_RELATIONSHIP_TYPES = [
    "Is a", "Finding site", "Associated morphology",
    "Causative agent", "Pathological process", "Due to",
    "Occurrence", "Clinical course", "Has active ingredient",
    "Plays role", "Method", "Procedure site - Direct",
    "Has interpretation", "Interprets", "Laterality",
    "After", "Associated with", "Has definitional manifestation",
    "Direct substance", "Has physiologic state",
]


# ─── 데이터 추출 ───────────────────────────────────────

def extract_vet_clinical_concepts(conn: sqlite3.Connection) -> dict:
    """VET 임상 핵심 개념을 추출한다."""
    cur = conn.cursor()
    concepts = {}

    tag_list = ",".join(f"'{t}'" for t in VET_CLINICAL_TAGS)
    cur.execute(f"""
        SELECT concept_id, preferred_term, fsn, semantic_tag, source
        FROM concept
        WHERE source = 'VET' AND semantic_tag IN ({tag_list})
    """)

    for row in cur.fetchall():
        concepts[row[0]] = {
            "concept_id": row[0],
            "preferred_term": row[1],
            "fsn": row[2],
            "semantic_tag": row[3],
            "source": row[4],
            "role": "clinical",  # 중심 노드
        }

    print(f"[Step 1] VET 임상 개념 추출: {len(concepts):,}개")
    for tag in VET_CLINICAL_TAGS:
        cnt = sum(1 for c in concepts.values() if c["semantic_tag"] == tag)
        print(f"         {tag}: {cnt:,}개")

    return concepts


def extract_related_concepts(
    conn: sqlite3.Connection,
    clinical_ids: set,
) -> tuple[dict, list]:
    """임상 개념이 참조하는 연결 개념과 관계를 추출한다."""
    cur = conn.cursor()
    related_concepts = {}
    relationships = []

    # 배치 처리
    id_list = list(clinical_ids)
    batch_size = 500

    for i in range(0, len(id_list), batch_size):
        batch = id_list[i:i + batch_size]
        placeholders = ",".join("?" * len(batch))

        # 임상 개념 → 대상 (outgoing)
        cur.execute(f"""
            SELECT r.source_id, r.destination_id, r.type_id,
                   c_type.preferred_term as type_term,
                   c_dst.concept_id, c_dst.preferred_term, c_dst.fsn,
                   c_dst.semantic_tag, c_dst.source
            FROM relationship r
            JOIN concept c_type ON r.type_id = c_type.concept_id
            JOIN concept c_dst ON r.destination_id = c_dst.concept_id
            WHERE r.source_id IN ({placeholders})
        """, batch)

        for row in cur.fetchall():
            type_term = row[3]
            dst_id = row[4]

            relationships.append({
                "source_id": row[0],
                "destination_id": row[1],
                "type_term": type_term,
            })

            if dst_id not in clinical_ids and dst_id not in related_concepts:
                related_concepts[dst_id] = {
                    "concept_id": dst_id,
                    "preferred_term": row[5],
                    "fsn": row[6],
                    "semantic_tag": row[7],
                    "source": row[8],
                    "role": "related",  # 연결 노드
                }

        # 대상 → 임상 개념 (incoming, Is a 역방향 등)
        cur.execute(f"""
            SELECT r.source_id, r.destination_id, r.type_id,
                   c_type.preferred_term as type_term,
                   c_src.concept_id, c_src.preferred_term, c_src.fsn,
                   c_src.semantic_tag, c_src.source
            FROM relationship r
            JOIN concept c_type ON r.type_id = c_type.concept_id
            JOIN concept c_src ON r.source_id = c_src.concept_id
            WHERE r.destination_id IN ({placeholders})
            AND c_src.source = 'VET'
        """, batch)

        for row in cur.fetchall():
            src_id = row[4]

            relationships.append({
                "source_id": row[0],
                "destination_id": row[1],
                "type_term": row[3],
            })

            if src_id not in clinical_ids and src_id not in related_concepts:
                related_concepts[src_id] = {
                    "concept_id": src_id,
                    "preferred_term": row[5],
                    "fsn": row[6],
                    "semantic_tag": row[7],
                    "source": row[8],
                    "role": "related",
                }

    # 중복 관계 제거
    seen = set()
    unique_rels = []
    for r in relationships:
        key = (r["source_id"], r["destination_id"], r["type_term"])
        if key not in seen:
            seen.add(key)
            unique_rels.append(r)

    print(f"[Step 2] 연결 개념 추출: {len(related_concepts):,}개 (VET→INT/VET 참조)")
    print(f"[Step 3] 관계 추출: {len(unique_rels):,}개")

    return related_concepts, unique_rels


# ─── Obsidian 노트 생성 ────────────────────────────────

TAG_EMOJI = {
    "disorder": "🔴", "finding": "🟡", "procedure": "🔵",
    "body structure": "🟢", "organism": "🟣", "medicinal product": "💊",
    "substance": "⚗️", "morphologic abnormality": "🔶",
    "observable entity": "📊", "qualifier value": "🏷️",
    "cell": "🔬", "physical force": "⚡", "event": "📅",
}

REL_EMOJI = {
    "Is a": "⬆️", "Finding site": "📍", "Associated morphology": "🔬",
    "Causative agent": "🦠", "Pathological process": "⚙️",
    "Due to": "↩️", "Has active ingredient": "💉",
    "Plays role": "🎭", "Clinical course": "📈",
    "Laterality": "↔️", "Occurrence": "🕐",
    "Method": "🔧", "Procedure site - Direct": "📍",
}


def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자를 제거한다."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.replace('\n', ' ').strip()
    return name[:120] if len(name) > 120 else name


def generate_concept_note(
    info: dict,
    outgoing: list,
    incoming: list,
    all_concepts: dict,
) -> str:
    """개별 개념의 Obsidian 마크다운 노트를 생성한다."""
    emoji = TAG_EMOJI.get(info["semantic_tag"], "⚪")
    source_label = {"INT": "국제표준", "VET": "수의학확장", "LOCAL": "로컬"}.get(info["source"], info["source"])

    lines = [
        "---",
        f'concept_id: "{info["concept_id"]}"',
        f'fsn: "{info["fsn"]}"',
        f'semantic_tag: "{info["semantic_tag"]}"',
        f'source: "{info["source"]}"',
        f'role: "{info["role"]}"',
        "tags:",
        "  - SNOMED",
        f'  - {info["semantic_tag"].replace(" ", "_")}',
        f'  - {info["source"]}',
    ]
    if info["role"] == "clinical":
        lines.append("  - clinical_core")
    lines.extend(["---", ""])

    # 제목
    lines.append(f"# {emoji} {info['preferred_term']}")
    lines.append("")
    lines.append(f"| 항목 | 값 |")
    lines.append(f"|------|-----|")
    lines.append(f"| Concept ID | `{info['concept_id']}` |")
    lines.append(f"| FSN | {info['fsn']} |")
    lines.append(f"| Category | {info['semantic_tag']} |")
    lines.append(f"| Source | {info['source']} ({source_label}) |")
    lines.append("")

    # Outgoing 관계 (이 개념 → 대상)
    if outgoing:
        lines.append("## 관계")
        lines.append("")

        by_type = defaultdict(list)
        for r in outgoing:
            dst = all_concepts.get(r["destination_id"])
            if dst:
                by_type[r["type_term"]].append(dst)

        for rel_type in KEY_RELATIONSHIP_TYPES:
            targets = by_type.get(rel_type, [])
            if not targets:
                continue
            rel_em = REL_EMOJI.get(rel_type, "🔗")
            lines.append(f"### {rel_em} {rel_type}")
            lines.append("")
            for t in targets:
                t_em = TAG_EMOJI.get(t["semantic_tag"], "⚪")
                src_badge = f"`{t['source']}`" if t["source"] != info["source"] else ""
                lines.append(f"- {t_em} [[{sanitize_filename(t['preferred_term'])}]] {src_badge}")
            lines.append("")

        # 위 목록에 없는 관계 유형도 출력
        remaining = {k: v for k, v in by_type.items() if k not in KEY_RELATIONSHIP_TYPES and v}
        for rel_type, targets in remaining.items():
            lines.append(f"### 🔗 {rel_type}")
            lines.append("")
            for t in targets:
                t_em = TAG_EMOJI.get(t["semantic_tag"], "⚪")
                lines.append(f"- {t_em} [[{sanitize_filename(t['preferred_term'])}]]")
            lines.append("")

    # Incoming 관계 (대상 → 이 개념)
    if incoming:
        lines.append("## 역관계 (→ 이 개념)")
        lines.append("")

        by_type = defaultdict(list)
        for r in incoming:
            src = all_concepts.get(r["source_id"])
            if src:
                by_type[r["type_term"]].append(src)

        for rel_type, sources in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
            rel_em = REL_EMOJI.get(rel_type, "🔗")
            # 역관계가 너무 많으면 상위 20개만
            display = sources[:20]
            lines.append(f"### {rel_em} {rel_type} ({len(sources)}건)")
            lines.append("")
            for s in display:
                s_em = TAG_EMOJI.get(s["semantic_tag"], "⚪")
                lines.append(f"- {s_em} [[{sanitize_filename(s['preferred_term'])}]]")
            if len(sources) > 20:
                lines.append(f"- _... 외 {len(sources) - 20}개_")
            lines.append("")

    return "\n".join(lines)


def generate_index_note(all_concepts: dict, relationships: list, output_dir: Path):
    """MOC (Map of Content) 인덱스 노트를 생성한다."""

    clinical = {k: v for k, v in all_concepts.items() if v["role"] == "clinical"}
    related = {k: v for k, v in all_concepts.items() if v["role"] == "related"}

    # 관계 유형 통계
    rel_types = defaultdict(int)
    for r in relationships:
        rel_types[r["type_term"]] += 1

    # 소스별 통계
    vet_cnt = sum(1 for c in all_concepts.values() if c["source"] == "VET")
    int_cnt = sum(1 for c in all_concepts.values() if c["source"] == "INT")

    lines = [
        "---",
        "tags: [MOC, SNOMED, knowledge_graph]",
        "---",
        "",
        "# 🩺 SNOMED CT VET Knowledge Graph",
        "",
        "수의학 확장(VET) 임상 개념을 중심으로 한 SNOMED CT 온톨로지 지식 그래프.",
        "",
        "## 📊 그래프 규모",
        "",
        "| 항목 | 값 |",
        "|------|-----|",
        f"| 전체 노드 | {len(all_concepts):,}개 |",
        f"| 전체 엣지 | {len(relationships):,}개 |",
        f"| VET 개념 | {vet_cnt:,}개 |",
        f"| INT 개념 | {int_cnt:,}개 |",
        f"| 임상 핵심 (clinical) | {len(clinical):,}개 |",
        f"| 연결 노드 (related) | {len(related):,}개 |",
        "",
        "## 🔗 관계 유형",
        "",
        "| 유형 | 건수 | 설명 |",
        "|------|------|------|",
    ]

    rel_descriptions = {
        "Is a": "계층 구조 (상위 개념)",
        "Finding site": "해부학적 위치",
        "Associated morphology": "관련 형태학적 변화",
        "Causative agent": "원인 병원체",
        "Pathological process": "병리적 과정",
        "Due to": "원인 관계",
        "Has active ingredient": "백신/약물 성분",
        "Plays role": "역할",
        "Clinical course": "임상 경과",
        "Laterality": "좌/우 측성",
        "Occurrence": "발생 시기",
        "Method": "시술 방법",
        "Procedure site - Direct": "시술 부위",
    }

    for rt, cnt in sorted(rel_types.items(), key=lambda x: x[1], reverse=True):
        desc = rel_descriptions.get(rt, "")
        lines.append(f"| {rt} | {cnt:,} | {desc} |")

    lines.extend(["", "## 🔴 VET Disorder (수의학 질환)", ""])

    # disorder를 관계 수 기준 정렬
    disorder_rels = defaultdict(int)
    for r in relationships:
        if r["source_id"] in clinical and clinical.get(r["source_id"], {}).get("semantic_tag") == "disorder":
            disorder_rels[r["source_id"]] += 1

    disorders_sorted = sorted(
        [(k, v) for k, v in clinical.items() if v["semantic_tag"] == "disorder"],
        key=lambda x: disorder_rels.get(x[0], 0),
        reverse=True,
    )

    for cid, info in disorders_sorted[:50]:
        rel_cnt = disorder_rels.get(cid, 0)
        lines.append(f"- [[{sanitize_filename(info['preferred_term'])}]] ({rel_cnt} rels)")

    if len(disorders_sorted) > 50:
        lines.append(f"- _... 외 {len(disorders_sorted) - 50}개_")

    lines.extend(["", "## 🔵 VET Procedure (수의학 시술)", ""])
    procedures = [(k, v) for k, v in clinical.items() if v["semantic_tag"] == "procedure"]
    for cid, info in procedures[:30]:
        lines.append(f"- [[{sanitize_filename(info['preferred_term'])}]]")
    if len(procedures) > 30:
        lines.append(f"- _... 외 {len(procedures) - 30}개_")

    lines.extend(["", "## 💊 VET Medicinal Product (수의학 의약품)", ""])
    meds = [(k, v) for k, v in clinical.items() if v["semantic_tag"] == "medicinal product"]
    for cid, info in meds[:30]:
        lines.append(f"- [[{sanitize_filename(info['preferred_term'])}]]")
    if len(meds) > 30:
        lines.append(f"- _... 외 {len(meds) - 30}개_")

    lines.extend(["", "## 🟡 VET Finding (수의학 소견)", ""])
    findings = [(k, v) for k, v in clinical.items() if v["semantic_tag"] == "finding"]
    for cid, info in findings[:30]:
        lines.append(f"- [[{sanitize_filename(info['preferred_term'])}]]")
    if len(findings) > 30:
        lines.append(f"- _... 외 {len(findings) - 30}개_")

    # 데이터 소스 정보
    lines.extend([
        "",
        "## 📁 전체 데이터 규모 (참고)",
        "",
        "| 항목 | 규모 |",
        "|------|------|",
        "| SNOMED CT INT | 378,938 concepts |",
        "| SNOMED CT VET Extension | 35,910 concepts |",
        "| Relationships (전체) | 1,379,816 |",
        "| Descriptions (전체) | 1,480,357 |",
    ])

    filepath = output_dir / "_SNOMED_VET_Knowledge_Graph.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[MOC] _SNOMED_VET_Knowledge_Graph.md 생성")


# ─── 메인 실행 ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SNOMED CT VET → Obsidian Knowledge Graph")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    print("=" * 60)
    print(" SNOMED CT VET → Obsidian Knowledge Graph")
    print(f" 출력: {output_dir}")
    print("=" * 60)

    db_path = DATA_DIR / "snomed_ct_vet.db"
    if not db_path.exists():
        print(f"[ERROR] DB 없음: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))

    # Step 1: VET 임상 핵심 개념 추출
    clinical = extract_vet_clinical_concepts(conn)
    clinical_ids = set(clinical.keys())

    # Step 2: 연결 개념 + 관계 추출
    related, relationships = extract_related_concepts(conn, clinical_ids)

    # 전체 개념 병합
    all_concepts = {**clinical, **related}
    print(f"[합계] 전체 노드: {len(all_concepts):,}개, 엣지: {len(relationships):,}개")

    # 기존 파일 정리
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 3: 관계를 개념별로 그룹핑
    rels_by_source = defaultdict(list)
    rels_by_dest = defaultdict(list)
    for r in relationships:
        rels_by_source[r["source_id"]].append(r)
        rels_by_dest[r["destination_id"]].append(r)

    # Step 4: 노트 생성
    generated = 0
    for cid, info in all_concepts.items():
        outgoing = rels_by_source.get(cid, [])
        incoming = rels_by_dest.get(cid, [])

        # 관계가 전혀 없는 연결 노드는 스킵 (고립 노드 방지)
        if info["role"] == "related" and not outgoing and not incoming:
            continue

        content = generate_concept_note(info, outgoing, incoming, all_concepts)
        filename = sanitize_filename(info["preferred_term"])
        filepath = output_dir / f"{filename}.md"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        generated += 1

    print(f"[Step 4] Obsidian 노트 생성: {generated:,}개")

    # Step 5: MOC 인덱스
    generate_index_note(all_concepts, relationships, output_dir)

    # Step 6: 통계 JSON
    stats = {
        "total_nodes": len(all_concepts),
        "total_edges": len(relationships),
        "generated_notes": generated,
        "by_role": {
            "clinical": sum(1 for c in all_concepts.values() if c["role"] == "clinical"),
            "related": sum(1 for c in all_concepts.values() if c["role"] == "related"),
        },
        "by_source": defaultdict(int),
        "by_semantic_tag": defaultdict(int),
        "relationship_types": defaultdict(int),
    }
    for c in all_concepts.values():
        stats["by_source"][c["source"]] += 1
        stats["by_semantic_tag"][c["semantic_tag"]] += 1
    for r in relationships:
        stats["relationship_types"][r["type_term"]] += 1

    stats["by_source"] = dict(stats["by_source"])
    stats["by_semantic_tag"] = dict(stats["by_semantic_tag"])
    stats["relationship_types"] = dict(stats["relationship_types"])

    with open(output_dir / "_graph_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    conn.close()

    print()
    print("=" * 60)
    print(f" 완료: {generated:,}개 노트 생성")
    print(f" Obsidian에서 '{output_dir}' 폴더를 Vault로 열어 그래프 뷰를 확인하세요.")
    print("=" * 60)


if __name__ == "__main__":
    main()
