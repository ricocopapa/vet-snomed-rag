"""
SNOMED CT GraphRAG 모듈: 온톨로지 그래프 탐색 기반 컨텍스트 확장.

[역할]
기존 하이브리드 검색(Vector + SQL)으로 찾은 개념에서 출발하여,
SNOMED CT 온톨로지 그래프를 2-hop까지 탐색하고 관련 개념과
경로 정보를 LLM 컨텍스트에 추가한다.

[기존 파이프라인 대비 개선점]
- 기존: 검색된 개념의 1-hop 관계만 단순 나열 (LIMIT 30)
- GraphRAG: 2-hop 탐색으로 간접 관련 개념 발견 + 경로 설명 생성
  예) Feline panleukopenia → Causative agent → Feline panleucopenia virus
      → Is a → Parvovirus (2-hop으로 상위 병원체 계통 파악)

[아키텍처]
    SQLite relationship 테이블
        → NetworkX DiGraph (노드: concept, 엣지: relationship)
        → 검색 결과 개념에서 2-hop BFS 탐색
        → 관계 경로 + 이웃 개념 → LLM 컨텍스트 주입

[실행]
    # 단독 테스트
    python src/retrieval/graph_rag.py --concept-id 339181000009108
    python src/retrieval/graph_rag.py --interactive
"""

import sqlite3
import time
import argparse
import networkx as nx
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "snomed_ct_vet.db"

# 임상적으로 의미 있는 관계 유형 (Is a 제외 — 별도 계층 탐색)
CLINICAL_REL_TYPES = {
    "Finding site",
    "Associated morphology",
    "Causative agent",
    "Pathological process",
    "Has active ingredient",
    "Interprets",
    "Has interpretation",
    "Due to",
    "Clinical course",
    "Occurrence",
    "Method",
    "Procedure site - Direct",
    "Procedure site - Indirect",
    "Procedure site",
    "Direct substance",
    "Direct device",
    "Has definitional manifestation",
    "Using device",
    "Using substance",
    "Has specimen",
    "Direct morphology",
    "Has focus",
    "After",
    "Associated with",
    "Plays role",
    "Has physiologic state",
    "Component",
    "Has intent",
    "Route of administration",
}

# 관계 유형별 한국어 설명
REL_TYPE_DESCRIPTIONS = {
    "Is a": "상위 개념",
    "Finding site": "해부학적 위치",
    "Associated morphology": "관련 형태학적 변화",
    "Causative agent": "원인 병원체",
    "Pathological process": "병리적 과정",
    "Has active ingredient": "유효 성분",
    "Interprets": "해석 대상",
    "Has interpretation": "해석 결과",
    "Due to": "원인",
    "Clinical course": "임상 경과",
    "Occurrence": "발생 시기",
    "Method": "시술 방법",
    "Procedure site - Direct": "시술 부위(직접)",
    "Procedure site - Indirect": "시술 부위(간접)",
    "Procedure site": "시술 부위",
    "Direct substance": "직접 물질",
    "Direct device": "직접 장비",
    "Has definitional manifestation": "정의적 징후",
    "Using device": "사용 장비",
    "Using substance": "사용 물질",
    "Has specimen": "검체",
    "Direct morphology": "직접 형태",
    "Has focus": "초점",
    "After": "선행 조건",
    "Associated with": "관련",
    "Plays role": "역할",
    "Has physiologic state": "생리적 상태",
    "Component": "구성 요소",
    "Has intent": "의도",
    "Route of administration": "투여 경로",
}


# ─── 데이터 모델 ─────────────────────────────────────────

@dataclass
class GraphNeighbor:
    """그래프 탐색으로 발견된 이웃 개념."""
    concept_id: str
    preferred_term: str
    semantic_tag: str
    source: str  # INT / VET
    hop_distance: int  # 시작 노드로부터의 거리
    path: list  # 경로 [(rel_type, concept_term), ...]


@dataclass
class GraphContext:
    """GraphRAG 탐색 결과."""
    seed_concept_id: str
    seed_term: str
    hierarchy_up: list  # Is-a 상위 계층 (부모 → 조부모)
    hierarchy_down: list  # Is-a 하위 개념 (자식)
    clinical_neighbors: list[GraphNeighbor]  # 임상 관계 이웃
    subgraph_stats: dict  # 탐색 통계


# ─── SNOMED 그래프 빌더 ──────────────────────────────────

class SNOMEDGraph:
    """SNOMED CT 관계를 NetworkX DiGraph로 관리한다."""

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self.graph = nx.DiGraph()
        self.concept_info = {}  # concept_id → {preferred_term, semantic_tag, source}
        self._build_graph()

    def _build_graph(self):
        """SQLite에서 관계를 로드하여 NetworkX 그래프를 구축한다."""
        start = time.time()
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # 1) 개념 정보 로드 (노드 속성)
        print("[GraphRAG] 개념 정보 로드 중...")
        cur.execute("""
            SELECT concept_id, preferred_term, semantic_tag, source
            FROM concept
        """)
        for row in cur.fetchall():
            cid, term, tag, source = row
            self.concept_info[cid] = {
                "preferred_term": term or "",
                "semantic_tag": tag or "",
                "source": source or "",
            }
            self.graph.add_node(cid)

        # 2) 관계 로드 (엣지)
        print("[GraphRAG] 관계 로드 중...")
        cur.execute("""
            SELECT r.source_id, r.destination_id, c_type.preferred_term
            FROM relationship r
            LEFT JOIN concept c_type ON r.type_id = c_type.concept_id
        """)

        edge_count = 0
        for row in cur.fetchall():
            src, dst, rel_type = row
            if src and dst:
                self.graph.add_edge(src, dst, rel_type=rel_type or "unknown")
                edge_count += 1

        conn.close()
        elapsed = time.time() - start
        print(f"[GraphRAG] 그래프 구축 완료: "
              f"노드 {self.graph.number_of_nodes():,}개, "
              f"엣지 {edge_count:,}개 ({elapsed:.1f}초)")

    def get_term(self, concept_id: str) -> str:
        """개념의 preferred_term을 반환한다."""
        info = self.concept_info.get(concept_id, {})
        return info.get("preferred_term", concept_id)

    def get_info(self, concept_id: str) -> dict:
        """개념의 전체 정보를 반환한다."""
        return self.concept_info.get(concept_id, {
            "preferred_term": concept_id,
            "semantic_tag": "",
            "source": "",
        })

    # ─── Is-a 계층 탐색 ─────────────────────────────────

    def get_ancestors(self, concept_id: str, max_depth: int = 3) -> list[dict]:
        """Is-a 관계를 따라 상위 개념을 탐색한다 (부모 → 조부모)."""
        ancestors = []
        visited = set()
        queue = [(concept_id, 0)]

        while queue:
            current, depth = queue.pop(0)
            if depth > max_depth:
                break

            for _, neighbor, data in self.graph.out_edges(current, data=True):
                if data.get("rel_type") == "Is a" and neighbor not in visited:
                    visited.add(neighbor)
                    info = self.get_info(neighbor)
                    ancestors.append({
                        "concept_id": neighbor,
                        "preferred_term": info["preferred_term"],
                        "semantic_tag": info["semantic_tag"],
                        "source": info["source"],
                        "depth": depth + 1,
                    })
                    if depth + 1 < max_depth:
                        queue.append((neighbor, depth + 1))

        return ancestors

    def get_children(self, concept_id: str, max_count: int = 10) -> list[dict]:
        """Is-a 관계의 직접 하위 개념을 조회한다."""
        children = []
        for source, _, data in self.graph.in_edges(concept_id, data=True):
            if data.get("rel_type") == "Is a":
                info = self.get_info(source)
                children.append({
                    "concept_id": source,
                    "preferred_term": info["preferred_term"],
                    "semantic_tag": info["semantic_tag"],
                    "source": info["source"],
                })
                if len(children) >= max_count:
                    break
        return children

    # ─── 임상 관계 2-hop 탐색 ────────────────────────────

    def explore_clinical_neighbors(
        self,
        concept_id: str,
        max_hops: int = 2,
        max_neighbors: int = 20,
    ) -> list[GraphNeighbor]:
        """임상적으로 의미 있는 관계를 따라 2-hop BFS 탐색한다.

        Is-a를 제외한 관계(Finding site, Causative agent 등)를 따라
        이웃 개념을 탐색하고, 각 개념까지의 경로를 기록한다.
        """
        neighbors = []
        visited = {concept_id}
        # (current_id, hop_distance, path)
        queue = [(concept_id, 0, [])]

        while queue and len(neighbors) < max_neighbors:
            current, hops, path = queue.pop(0)
            if hops >= max_hops:
                continue

            # outgoing 관계 탐색
            for _, target, data in self.graph.out_edges(current, data=True):
                rel_type = data.get("rel_type", "")
                if rel_type in CLINICAL_REL_TYPES and target not in visited:
                    visited.add(target)
                    info = self.get_info(target)
                    new_path = path + [(rel_type, info["preferred_term"])]

                    neighbors.append(GraphNeighbor(
                        concept_id=target,
                        preferred_term=info["preferred_term"],
                        semantic_tag=info["semantic_tag"],
                        source=info["source"],
                        hop_distance=hops + 1,
                        path=new_path,
                    ))

                    if hops + 1 < max_hops:
                        queue.append((target, hops + 1, new_path))

            # incoming 관계도 탐색 (역방향)
            for source, _, data in self.graph.in_edges(current, data=True):
                rel_type = data.get("rel_type", "")
                if rel_type in CLINICAL_REL_TYPES and source not in visited:
                    visited.add(source)
                    info = self.get_info(source)
                    new_path = path + [(f"←{rel_type}", info["preferred_term"])]

                    neighbors.append(GraphNeighbor(
                        concept_id=source,
                        preferred_term=info["preferred_term"],
                        semantic_tag=info["semantic_tag"],
                        source=info["source"],
                        hop_distance=hops + 1,
                        path=new_path,
                    ))

                    if hops + 1 < max_hops:
                        queue.append((source, hops + 1, new_path))

            if len(neighbors) >= max_neighbors:
                break

        return neighbors[:max_neighbors]

    # ─── 통합 탐색 ──────────────────────────────────────

    def explore(
        self,
        concept_id: str,
        hierarchy_depth: int = 3,
        clinical_hops: int = 2,
        max_clinical_neighbors: int = 20,
        max_children: int = 5,
    ) -> GraphContext:
        """개념에 대한 전체 그래프 탐색을 수행한다.

        1) Is-a 상위 계층 (부모→조부모, max 3단계)
        2) Is-a 하위 개념 (직접 자식, max 5개)
        3) 임상 관계 2-hop 이웃 (Finding site, Causative agent 등)
        """
        term = self.get_term(concept_id)

        # 1) 계층 탐색
        ancestors = self.get_ancestors(concept_id, max_depth=hierarchy_depth)
        children = self.get_children(concept_id, max_count=max_children)

        # 2) 임상 관계 탐색
        clinical = self.explore_clinical_neighbors(
            concept_id,
            max_hops=clinical_hops,
            max_neighbors=max_clinical_neighbors,
        )

        # 3) 통계
        stats = {
            "ancestors": len(ancestors),
            "children": len(children),
            "clinical_1hop": sum(1 for n in clinical if n.hop_distance == 1),
            "clinical_2hop": sum(1 for n in clinical if n.hop_distance == 2),
            "total_explored": len(ancestors) + len(children) + len(clinical),
        }

        return GraphContext(
            seed_concept_id=concept_id,
            seed_term=term,
            hierarchy_up=ancestors,
            hierarchy_down=children,
            clinical_neighbors=clinical,
            subgraph_stats=stats,
        )


# ─── 컨텍스트 포매터 ────────────────────────────────────

def format_graph_context(
    graph_contexts: list[GraphContext],
    max_per_concept: int = 3,
) -> str:
    """GraphRAG 탐색 결과를 LLM 프롬프트용 텍스트로 포맷팅한다.

    Args:
        graph_contexts: 여러 검색 결과 개념의 그래프 탐색 결과
        max_per_concept: 개념당 최대 표시 이웃 수
    """
    if not graph_contexts:
        return ""

    parts = ["\n=== SNOMED CT 온톨로지 그래프 컨텍스트 (GraphRAG) ===\n"]

    for ctx in graph_contexts:
        parts.append(f"■ {ctx.seed_term} ({ctx.seed_concept_id})")

        # Is-a 계층
        if ctx.hierarchy_up:
            chain = " → ".join(
                a["preferred_term"] for a in ctx.hierarchy_up[:3]
            )
            parts.append(f"  계층: {ctx.seed_term} → {chain}")

        # 하위 개념
        if ctx.hierarchy_down:
            children_str = ", ".join(
                c["preferred_term"] for c in ctx.hierarchy_down[:3]
            )
            if len(ctx.hierarchy_down) > 3:
                children_str += f" 외 {len(ctx.hierarchy_down) - 3}개"
            parts.append(f"  하위 개념: {children_str}")

        # 임상 관계 이웃 (1-hop)
        hop1 = [n for n in ctx.clinical_neighbors if n.hop_distance == 1]
        if hop1:
            parts.append(f"  직접 관계 (1-hop):")
            for n in hop1[:max_per_concept * 2]:
                rel_type = n.path[-1][0] if n.path else "관련"
                # 역방향 표시 정리
                display_rel = rel_type.replace("←", "← ")
                desc = REL_TYPE_DESCRIPTIONS.get(
                    rel_type.replace("←", ""), display_rel
                )
                parts.append(
                    f"    [{desc}] {n.preferred_term} "
                    f"({n.semantic_tag}, {n.source})"
                )

        # 2-hop 이웃 (간접 관계)
        hop2 = [n for n in ctx.clinical_neighbors if n.hop_distance == 2]
        if hop2:
            parts.append(f"  간접 관계 (2-hop):")
            for n in hop2[:max_per_concept]:
                # 경로 표시: A →[rel1] B →[rel2] C
                path_str = ctx.seed_term
                for rel, term in n.path:
                    rel_clean = rel.replace("←", "← ")
                    path_str += f" →[{rel_clean}] {term}"
                parts.append(f"    {path_str}")

        parts.append("")  # 빈 줄

    # 통계 요약
    total_explored = sum(
        ctx.subgraph_stats["total_explored"] for ctx in graph_contexts
    )
    parts.append(f"[GraphRAG 탐색 규모: {len(graph_contexts)}개 개념, "
                 f"총 {total_explored}개 관련 노드 탐색]\n")

    return "\n".join(parts)


# ─── CLI (단독 테스트) ───────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SNOMED CT GraphRAG 단독 테스트")
    parser.add_argument("--concept-id", type=str, help="탐색할 concept_id")
    parser.add_argument("--interactive", action="store_true", help="대화형 모드")
    parser.add_argument("--hops", type=int, default=2, help="최대 탐색 깊이 (기본: 2)")
    args = parser.parse_args()

    graph = SNOMEDGraph()

    if args.interactive:
        print("\n[GraphRAG 대화형 모드] concept_id 또는 용어를 입력하세요 (quit으로 종료)")
        while True:
            try:
                user_input = input("\nconcept_id> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if user_input.lower() in ("quit", "exit", "q"):
                break
            if not user_input:
                continue

            # concept_id로 직접 탐색
            ctx = graph.explore(user_input, clinical_hops=args.hops)
            print(format_graph_context([ctx]))
            print(f"  통계: {ctx.subgraph_stats}")

    elif args.concept_id:
        ctx = graph.explore(args.concept_id, clinical_hops=args.hops)
        print(format_graph_context([ctx]))
        print(f"\n통계: {ctx.subgraph_stats}")

    else:
        # 기본 데모: Feline panleukopenia
        demo_id = "339181000009108"
        print(f"\n[데모] {demo_id} (Feline panleukopenia) 탐색:")
        ctx = graph.explore(demo_id, clinical_hops=args.hops)
        print(format_graph_context([ctx]))
        print(f"통계: {ctx.subgraph_stats}")


if __name__ == "__main__":
    main()
