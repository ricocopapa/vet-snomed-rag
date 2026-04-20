"""
graphify_lite.py — vet-snomed-rag 코드 지식 그래프 생성기

[역할]
Python AST + NetworkX + pyvis를 사용하여 src/ 디렉토리의 Python 코드 구조를
정적 분석하고, 인터랙티브 지식 그래프를 생성한다.

[주의]
- 이 스크립트는 Python 코드 구조 그래프 전용이다.
- src/retrieval/graph_rag.py의 SNOMED 온톨로지 그래프와 역할이 다르다.
- LLM API 호출 없음 — 순수 AST + networkx + pyvis만 사용.

[실행]
    cd ~/claude-cowork/07_Projects/vet-snomed-rag
    source venv/bin/activate
    python scripts/graphify_lite.py

[산출물]
    graphify_out/
    ├── graph.json              # NetworkX node-link 포맷
    ├── nodes.csv               # id, type, file, line, community_id, degree
    ├── edges.csv               # source, target, type, confidence
    ├── report.md               # 분석 리포트
    ├── graph.html              # pyvis 인터랙티브 HTML
    ├── graph.png               # matplotlib 정적 이미지
    ├── cache.json              # SHA256 해시 캐시
    └── suggested_questions.md  # 탐색 추천 질문 5+
"""

import ast
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
OUT_DIR = PROJECT_ROOT / "graphify_out"

# 민감 파일 패턴 (스캔 제외)
SENSITIVE_PATTERNS = [
    re.compile(r'API_KEY', re.IGNORECASE),
    re.compile(r'SECRET', re.IGNORECASE),
    re.compile(r'\.env$'),
    re.compile(r'credentials', re.IGNORECASE),
]


# ─── Step 1: Detect ─────────────────────────────────────

def detect_python_files(src_dir: Path) -> list[Path]:
    """src/ 디렉토리에서 Python 파일을 탐색한다 (민감 파일 제외)."""
    files = []
    for py_file in sorted(src_dir.rglob("*.py")):
        # 민감 파일 제외
        is_sensitive = False
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(str(py_file)):
                print(f"  [SKIP — 민감 파일] {py_file}")
                is_sensitive = True
                break
        if not is_sensitive:
            files.append(py_file)
    return files


# ─── Step 2: Extract ─────────────────────────────────────

def compute_sha256(filepath: Path) -> str:
    """파일의 SHA256 해시를 계산한다."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def get_relative_path(filepath: Path, src_dir: Path) -> str:
    """src/ 기준 상대 경로를 반환한다."""
    try:
        return str(filepath.relative_to(src_dir.parent))
    except ValueError:
        return str(filepath)


def extract_ast_nodes_edges(filepath: Path, src_dir: Path) -> tuple[list[dict], list[dict]]:
    """Python 파일에서 AST 기반 노드/엣지를 추출한다.

    노드:
        - module: 파일 자체
        - class: 클래스 정의
        - function: 함수 정의 (top-level)
        - method: 클래스 내부 메서드

    엣지:
        - imports: import 구문 (confidence=1.0, EXTRACTED)
        - inherits: 상속 관계 (confidence=1.0, EXTRACTED)
        - calls: 직접 함수 호출 (confidence=1.0 / 0.8 INFERRED / 0.3 AMBIGUOUS)
        - uses: 변수 참조 (confidence=0.7, INFERRED)
    """
    rel_path = get_relative_path(filepath, src_dir)
    nodes = []
    edges = []

    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        print(f"  [파싱 에러] {rel_path}: {e}")
        # 파일 수준 노드만 생성 (AMBIGUOUS)
        nodes.append({
            "id": rel_path,
            "type": "module",
            "file": rel_path,
            "line": 0,
            "confidence": 0.1,
            "tag": "AMBIGUOUS",
            "error": str(e),
        })
        return nodes, edges

    # 모듈 노드 (EXTRACTED)
    module_id = rel_path
    nodes.append({
        "id": module_id,
        "type": "module",
        "file": rel_path,
        "line": 0,
        "confidence": 1.0,
        "tag": "EXTRACTED",
        "error": None,
    })

    # 현재 파일에서 정의된 클래스명 수집 (상속 관계 엣지 생성용)
    defined_classes: dict[str, str] = {}  # class_name → node_id

    # AST Visitor로 노드/엣지 추출
    class GraphVisitor(ast.NodeVisitor):
        def __init__(self):
            self.current_class: Optional[str] = None
            self.current_class_id: Optional[str] = None

        def visit_ClassDef(self, node: ast.ClassDef):
            class_id = f"{module_id}::{node.name}"
            defined_classes[node.name] = class_id

            nodes.append({
                "id": class_id,
                "type": "class",
                "file": rel_path,
                "line": node.lineno,
                "confidence": 1.0,
                "tag": "EXTRACTED",
                "error": None,
            })
            # module → class 엣지
            edges.append({
                "source": module_id,
                "target": class_id,
                "type": "contains",
                "confidence": 1.0,
                "tag": "EXTRACTED",
            })

            # 상속 관계 (confidence=1.0 EXTRACTED)
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr

                if base_name:
                    # 같은 파일 내 클래스면 정확한 ID 사용
                    base_id = defined_classes.get(base_name, base_name)
                    edges.append({
                        "source": class_id,
                        "target": base_id,
                        "type": "inherits",
                        "confidence": 1.0,
                        "tag": "EXTRACTED",
                    })

            # 클래스 내부 순회 (메서드 추출)
            prev_class = self.current_class
            prev_class_id = self.current_class_id
            self.current_class = node.name
            self.current_class_id = class_id
            self.generic_visit(node)
            self.current_class = prev_class
            self.current_class_id = prev_class_id

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self._visit_func(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            self._visit_func(node)

        def _visit_func(self, node):
            if self.current_class_id:
                # 메서드
                func_id = f"{self.current_class_id}::{node.name}"
                func_type = "method"
                parent_id = self.current_class_id
            else:
                # 함수
                func_id = f"{module_id}::{node.name}"
                func_type = "function"
                parent_id = module_id

            nodes.append({
                "id": func_id,
                "type": func_type,
                "file": rel_path,
                "line": node.lineno,
                "confidence": 1.0,
                "tag": "EXTRACTED",
                "error": None,
            })
            # parent → function/method 엣지
            edges.append({
                "source": parent_id,
                "target": func_id,
                "type": "contains",
                "confidence": 1.0,
                "tag": "EXTRACTED",
            })

            # 함수 내부 Call 추출 (클래스 방문 없이 직접 walk)
            self._extract_calls(node, func_id)

        def _extract_calls(self, func_node, caller_id: str):
            """함수 내부의 모든 ast.Call을 추출한다."""
            for child in ast.walk(func_node):
                if not isinstance(child, ast.Call):
                    continue

                func = child.func
                if isinstance(func, ast.Name):
                    # 직접 이름 호출: foo() → confidence=1.0 EXTRACTED
                    callee_name = func.id
                    # 동적 호출 탐지
                    if callee_name in ("getattr", "eval", "exec"):
                        conf, tag = 0.3, "AMBIGUOUS"
                    else:
                        conf, tag = 1.0, "EXTRACTED"
                    edges.append({
                        "source": caller_id,
                        "target": callee_name,
                        "type": "calls",
                        "confidence": conf,
                        "tag": tag,
                    })
                elif isinstance(func, ast.Attribute):
                    # 메서드 체인: obj.method() → confidence=0.8 INFERRED
                    callee_name = func.attr
                    edges.append({
                        "source": caller_id,
                        "target": callee_name,
                        "type": "calls",
                        "confidence": 0.8,
                        "tag": "INFERRED",
                    })

        def visit_Import(self, node: ast.Import):
            """import 구문 처리 (confidence=1.0 EXTRACTED)."""
            for alias in node.names:
                target_name = alias.asname if alias.asname else alias.name
                edges.append({
                    "source": module_id,
                    "target": alias.name,
                    "type": "imports",
                    "confidence": 1.0,
                    "tag": "EXTRACTED",
                })

        def visit_ImportFrom(self, node: ast.ImportFrom):
            """from X import Y 구문 처리 (confidence=1.0 EXTRACTED)."""
            module_name = node.module or ""
            for alias in node.names:
                target = f"{module_name}.{alias.name}" if module_name else alias.name
                edges.append({
                    "source": module_id,
                    "target": target,
                    "type": "imports",
                    "confidence": 1.0,
                    "tag": "EXTRACTED",
                })

        def visit_Name(self, node: ast.Name):
            """변수 참조 (Load 컨텍스트, confidence=0.7 INFERRED)."""
            # 전역 Name 참조는 너무 많으므로 함수 수준에서만 처리됨
            # 여기서는 최상위 모듈 수준 Name 참조만 처리 (호출 내부는 _extract_calls에서)
            pass

    visitor = GraphVisitor()
    visitor.visit(tree)

    return nodes, edges


# ─── Step 3: Cache ────────────────────────────────────────

def load_cache(cache_path: Path) -> dict:
    """캐시 파일을 로드한다."""
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache_path: Path, cache_data: dict):
    """캐시 파일을 저장한다."""
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)


# ─── Step 4: Build ────────────────────────────────────────

def build_graph(all_nodes: list[dict], all_edges: list[dict]):
    """NetworkX DiGraph를 구축한다."""
    import networkx as nx

    G = nx.DiGraph()

    # 노드 추가
    node_ids = set()
    for node in all_nodes:
        G.add_node(
            node["id"],
            type=node["type"],
            file=node.get("file", ""),
            line=node.get("line", 0),
            confidence=node.get("confidence", 1.0),
            tag=node.get("tag", "EXTRACTED"),
        )
        node_ids.add(node["id"])

    # 엣지 추가 (중복 엣지는 weight 합산)
    edge_weights = defaultdict(float)
    edge_attrs = {}

    for edge in all_edges:
        src = edge["source"]
        tgt = edge["target"]
        etype = edge["type"]
        conf = edge.get("confidence", 1.0)

        # 타겟 노드가 없으면 외부 심볼 노드 생성
        if tgt not in node_ids:
            G.add_node(
                tgt,
                type="external",
                file="",
                line=0,
                confidence=conf,
                tag="INFERRED",
            )
            node_ids.add(tgt)

        key = (src, tgt, etype)
        edge_weights[key] += conf
        if key not in edge_attrs:
            edge_attrs[key] = {
                "type": etype,
                "confidence": conf,
                "tag": edge.get("tag", "EXTRACTED"),
            }

    for (src, tgt, etype), weight in edge_weights.items():
        attrs = edge_attrs[(src, tgt, etype)]
        G.add_edge(src, tgt,
                   type=etype,
                   confidence=attrs["confidence"],
                   tag=attrs["tag"],
                   weight=weight)

    return G


# ─── Step 5: Analyze ─────────────────────────────────────

def analyze_graph(G):
    """그래프 분석: degree centrality, community, surprising connections."""
    import networkx as nx
    from networkx.algorithms import community as nx_community

    # Degree Centrality (God Node 식별)
    degree_centrality = nx.degree_centrality(G)

    # Community Detection (Louvain)
    undirected = G.to_undirected()
    try:
        communities = list(nx_community.louvain_communities(undirected, seed=42))
    except Exception:
        # Louvain 실패 시 greedy_modularity_communities 폴백
        try:
            communities = list(nx_community.greedy_modularity_communities(undirected))
        except Exception:
            communities = [set(G.nodes())]

    community_map: dict[str, int] = {}
    for i, comm in enumerate(communities):
        for node in comm:
            community_map[node] = i

    # Surprising Connections: 2-hop 간접 경로 탐색
    # module 노드에서 다른 module까지의 간접 경로
    module_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "module"]
    surprising = []

    for i, src in enumerate(module_nodes):
        for tgt in module_nodes:
            if src == tgt:
                continue
            # 직접 엣지가 없는데 2-hop 경로가 있으면 Surprising
            if not G.has_edge(src, tgt):
                try:
                    paths = list(nx.all_simple_paths(G, src, tgt, cutoff=2))
                    if paths:
                        for path in paths[:2]:
                            surprising.append({
                                "src": src,
                                "tgt": tgt,
                                "path": path,
                                "hops": len(path) - 1,
                            })
                except nx.NetworkXNoPath:
                    pass
                except Exception:
                    pass

    return degree_centrality, community_map, communities, surprising


# ─── Step 6: Visualize ────────────────────────────────────

COMMUNITY_COLORS = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
    "#1abc9c", "#e67e22", "#34495e", "#27ae60", "#2980b9",
]


def confidence_to_edge_color(confidence: float) -> str:
    """신뢰도를 엣지 색상으로 변환."""
    if confidence >= 1.0:
        return "#27ae60"   # 녹색 (EXTRACTED)
    elif confidence >= 0.6:
        return "#f39c12"   # 노랑 (INFERRED)
    else:
        return "#e74c3c"   # 빨강 (AMBIGUOUS)


def generate_pyvis_html(G, community_map: dict, degree_centrality: dict, out_path: Path):
    """pyvis 인터랙티브 HTML 그래프를 생성한다."""
    from pyvis.network import Network

    net = Network(
        height="800px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="#ecf0f1",
        directed=True,
    )
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -8000,
          "springConstant": 0.04,
          "damping": 0.09
        }
      },
      "nodes": {
        "font": {"size": 12, "color": "#ecf0f1"},
        "borderWidth": 2
      },
      "edges": {
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}},
        "smooth": {"type": "dynamic"}
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100
      }
    }
    """)

    # 외부 심볼 노드는 시각화에서 제외 (너무 많아지면 가독성 저하)
    internal_nodes = [n for n, d in G.nodes(data=True)
                      if d.get("type") != "external"]
    internal_node_set = set(internal_nodes)

    # degree centrality 최대값 (노드 크기 정규화용)
    max_degree = max(degree_centrality.get(n, 0) for n in internal_nodes) if internal_nodes else 1.0
    if max_degree == 0:
        max_degree = 0.001

    # 노드 추가
    for node_id in internal_nodes:
        data = G.nodes[node_id]
        ntype = data.get("type", "unknown")
        comm_id = community_map.get(node_id, 0)
        color = COMMUNITY_COLORS[comm_id % len(COMMUNITY_COLORS)]
        dc = degree_centrality.get(node_id, 0)
        size = max(10, min(60, 10 + dc / max_degree * 50))

        # 노드 모양 (type별)
        shape_map = {
            "module": "box",
            "class": "diamond",
            "function": "ellipse",
            "method": "circle",
        }
        shape = shape_map.get(ntype, "ellipse")

        # 레이블 (짧게)
        label = node_id.split("::")[-1] if "::" in node_id else node_id
        if len(label) > 25:
            label = label[:22] + "..."

        # 툴팁
        title = (
            f"<b>{node_id}</b><br>"
            f"type: {ntype}<br>"
            f"file: {data.get('file', '')}<br>"
            f"line: {data.get('line', 0)}<br>"
            f"community: C{comm_id}<br>"
            f"degree_centrality: {dc:.4f}"
        )

        net.add_node(
            node_id,
            label=label,
            title=title,
            color=color,
            size=size,
            shape=shape,
        )

    # 엣지 추가 (내부 노드 간만)
    for src, tgt, data in G.edges(data=True):
        if src not in internal_node_set or tgt not in internal_node_set:
            continue
        etype = data.get("type", "unknown")
        conf = data.get("confidence", 1.0)
        color = confidence_to_edge_color(conf)
        tag = data.get("tag", "EXTRACTED")

        title = f"{etype} | conf={conf:.2f} | {tag}"
        net.add_edge(src, tgt, title=title, color=color, width=max(0.5, conf * 2))

    net.save_graph(str(out_path))


def generate_matplotlib_png(G, community_map: dict, degree_centrality: dict, out_path: Path):
    """matplotlib 정적 PNG 이미지를 생성한다."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import networkx as nx

        # 내부 노드만
        internal_nodes = [n for n, d in G.nodes(data=True)
                          if d.get("type") != "external"]
        subG = G.subgraph(internal_nodes)

        fig, ax = plt.subplots(figsize=(20, 14), facecolor="#1a1a2e")
        ax.set_facecolor("#1a1a2e")

        # spring layout
        try:
            pos = nx.spring_layout(subG, k=2.0, seed=42)
        except Exception:
            pos = nx.random_layout(subG)

        node_colors = [
            COMMUNITY_COLORS[community_map.get(n, 0) % len(COMMUNITY_COLORS)]
            for n in subG.nodes()
        ]
        max_dc = max(degree_centrality.get(n, 0) for n in subG.nodes()) or 0.001
        node_sizes = [
            max(100, min(3000, 100 + degree_centrality.get(n, 0) / max_dc * 2900))
            for n in subG.nodes()
        ]

        nx.draw_networkx_nodes(
            subG, pos,
            node_color=node_colors,
            node_size=node_sizes,
            alpha=0.85,
            ax=ax,
        )
        nx.draw_networkx_edges(
            subG, pos,
            edge_color="#95a5a6",
            arrows=True,
            alpha=0.4,
            ax=ax,
            arrowsize=10,
        )

        # 주요 노드 (degree top 15)만 레이블 표시
        top_nodes = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:15]
        top_node_ids = {n for n, _ in top_nodes if n in subG.nodes()}
        labels = {n: n.split("::")[-1] for n in top_node_ids}
        nx.draw_networkx_labels(
            subG, pos, labels=labels,
            font_size=7, font_color="#ecf0f1",
            ax=ax,
        )

        ax.set_title("vet-snomed-rag 코드 지식 그래프", color="#ecf0f1", fontsize=16, pad=20)
        ax.axis("off")
        plt.tight_layout()
        plt.savefig(str(out_path), dpi=150, bbox_inches="tight",
                    facecolor="#1a1a2e", edgecolor="none")
        plt.close()
        print(f"  [PNG] {out_path}")
    except Exception as e:
        print(f"  [PNG 생성 실패] {e}")


def save_graph_json(G, out_path: Path):
    """NetworkX node-link 포맷 JSON으로 저장한다."""
    import networkx as nx
    data = nx.node_link_data(G)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [JSON] {out_path}")


# ─── Step 9: Report ──────────────────────────────────────

def generate_report(
    G,
    all_nodes: list[dict],
    all_edges: list[dict],
    degree_centrality: dict,
    community_map: dict,
    communities: list,
    surprising: list,
    parse_errors: list[str],
    out_path: Path,
) -> str:
    """마크다운 분석 리포트를 생성한다."""

    # 노드 타입별 집계
    type_counts = defaultdict(int)
    for n, d in G.nodes(data=True):
        type_counts[d.get("type", "unknown")] += 1

    # 엣지 타입별 집계
    edge_type_counts = defaultdict(int)
    for _, _, d in G.edges(data=True):
        edge_type_counts[d.get("type", "unknown")] += 1

    # God Nodes Top 5 (외부 노드 제외)
    internal_dc = {
        n: dc for n, dc in degree_centrality.items()
        if G.nodes[n].get("type") != "external"
    }
    god_nodes = sorted(internal_dc.items(), key=lambda x: x[1], reverse=True)[:5]

    # Community 분포 (상위 5)
    comm_sizes = defaultdict(list)
    for node_id, comm_id in community_map.items():
        if G.nodes[node_id].get("type") != "external":
            comm_sizes[comm_id].append(node_id)

    top_communities = sorted(comm_sizes.items(), key=lambda x: len(x[1]), reverse=True)[:5]

    # Community 대표 노드 (degree centrality 최고)
    def get_comm_representative(nodes: list) -> str:
        return max(nodes, key=lambda n: degree_centrality.get(n, 0), default="")

    # Community 응집 주제 추론 (파일명 기반)
    def infer_comm_theme(nodes: list) -> str:
        files = set()
        for n in nodes:
            data = G.nodes[n]
            f = data.get("file", "")
            if f:
                files.add(Path(f).stem)
        if not files:
            return "혼합"
        return " / ".join(sorted(files)[:3])

    # Surprising Connections (상위 3)
    unique_surprising = []
    seen_pairs = set()
    for s in surprising:
        pair = (s["src"], s["tgt"])
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            unique_surprising.append(s)
        if len(unique_surprising) >= 3:
            break

    # Suggested Questions 생성
    suggested_questions = generate_suggested_questions(
        god_nodes, top_communities, unique_surprising, G
    )

    # 리포트 작성
    lines = []
    lines.append("# vet-snomed-rag 코드베이스 지식 그래프 분석")
    lines.append("")
    lines.append(f"생성 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("## 요약")
    lines.append("")
    lines.append(f"- 파일: {type_counts.get('module', 0)}개")
    lines.append(f"- 노드: 총 {sum(1 for _, d in G.nodes(data=True) if d.get('type') != 'external')}개")
    lines.append(f"  - module: {type_counts.get('module', 0)}")
    lines.append(f"  - class: {type_counts.get('class', 0)}")
    lines.append(f"  - function: {type_counts.get('function', 0)}")
    lines.append(f"  - method: {type_counts.get('method', 0)}")
    lines.append(f"- 엣지: 총 {G.number_of_edges()}개")
    for etype, cnt in sorted(edge_type_counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  - {etype}: {cnt}")
    lines.append(f"- 커뮤니티: {len(communities)}개 감지됨")
    if parse_errors:
        lines.append(f"- 파싱 에러: {len(parse_errors)}건")
        for err in parse_errors:
            lines.append(f"  - {err}")
    else:
        lines.append(f"- 파싱 에러: 없음")
    lines.append("")

    lines.append("## God Nodes (Top 5)")
    lines.append("")
    lines.append("| 순위 | 노드 ID | degree_centrality | 해석 |")
    lines.append("|---|---|---|---|")

    def interpret_god_node(node_id: str, dc: float) -> str:
        """God Node 해석 생성."""
        ntype = G.nodes[node_id].get("type", "unknown")
        name = node_id.split("::")[-1]
        if ntype == "module":
            return f"모듈 전체 참조 허브"
        elif ntype == "class":
            return f"핵심 클래스 — 다수 모듈에서 참조됨"
        elif ntype == "function":
            return f"공통 유틸 함수 — 여러 곳에서 호출됨"
        elif ntype == "method":
            return f"핵심 메서드 — 파이프라인 중심"
        return f"{ntype} 노드"

    for rank, (node_id, dc) in enumerate(god_nodes, 1):
        interp = interpret_god_node(node_id, dc)
        short_id = node_id if len(node_id) <= 50 else "..." + node_id[-47:]
        lines.append(f"| {rank} | `{short_id}` | {dc:.4f} | {interp} |")
    lines.append("")

    lines.append("## Community 분포 (상위 5)")
    lines.append("")
    lines.append("| 커뮤니티 ID | 크기 | 대표 노드 | 응집 주제 |")
    lines.append("|---|---|---|---|")

    for comm_id, nodes_in_comm in top_communities:
        rep = get_comm_representative(nodes_in_comm)
        rep_short = rep.split("::")[-1] if "::" in rep else rep
        theme = infer_comm_theme(nodes_in_comm)
        lines.append(f"| C{comm_id} | {len(nodes_in_comm)} | `{rep_short}` | {theme} |")
    lines.append("")

    lines.append("## Surprising Connections (간접 2-hop 이상)")
    lines.append("")
    if unique_surprising:
        for s in unique_surprising:
            path_str = " → ".join(n.split("::")[-1] for n in s["path"])
            lines.append(f"- `{s['src']}` → ... → `{s['tgt']}`")
            lines.append(f"  경로: `{path_str}` ({s['hops']}-hop)")
            lines.append("")
    else:
        lines.append("- 직접 연결 없는 모듈 간 간접 경로 미발견 (모든 모듈이 직접 연결됨)")
        lines.append("")

    lines.append("## Suggested Questions")
    lines.append("")
    for i, q in enumerate(suggested_questions, 1):
        lines.append(f"{i}. {q}")
    lines.append("")

    content = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [리포트] {out_path}")

    return content


def generate_suggested_questions(
    god_nodes: list,
    top_communities: list,
    surprising: list,
    G,
) -> list[str]:
    """Suggested Questions 5개 이상 생성."""
    questions = []

    # God Node 기반 질문
    if god_nodes:
        top1_id = god_nodes[0][0]
        top1_name = top1_id.split("::")[-1]
        questions.append(
            f"`{top1_name}` 수정 시 영향을 받는 함수/메서드는 무엇인가?"
        )

    if len(god_nodes) >= 2:
        top2_id = god_nodes[1][0]
        top2_name = top2_id.split("::")[-1]
        questions.append(
            f"`{top2_name}`과 다른 검색 컴포넌트의 결합도는 어느 수준인가?"
        )

    # Community 기반 질문
    if len(top_communities) >= 2:
        comm_a_theme = infer_theme_for_question(top_communities[0][1], G)
        comm_b_theme = infer_theme_for_question(top_communities[1][1], G)
        questions.append(
            f"커뮤니티 C{top_communities[0][0]} ({comm_a_theme})와 "
            f"C{top_communities[1][0]} ({comm_b_theme}) 사이의 인터페이스는 무엇인가?"
        )

    # 구조 탐색 질문
    questions.append(
        "`query_reformulator.py` 모듈 추가 시 어느 God Node의 degree_centrality가 가장 많이 변화하는가?"
    )
    questions.append(
        "`rag_pipeline.py::SNOMEDRagPipeline.query`와 `hybrid_search.py::HybridSearchEngine.search`의 "
        "호출 체인을 추적하면 몇 단계인가?"
    )
    questions.append(
        "`export_obsidian.py`가 SNOMED 온톨로지 그래프(`graph_rag.py`)를 간접적으로 "
        "의존하는 경로가 있는가?"
    )
    questions.append(
        "`preprocess_query`와 `preprocess_for_vector`는 왜 분리되어 있으며, "
        "통합 시 God Node 순위는 어떻게 바뀌는가?"
    )

    # Surprising Connection 기반 질문
    for s in surprising[:2]:
        src_name = s["src"].split("::")[-1]
        tgt_name = s["tgt"].split("::")[-1]
        questions.append(
            f"`{src_name}`과 `{tgt_name}` 사이의 간접 연결({s['hops']}-hop)은 "
            f"의도된 설계인가, 리팩토링 대상인가?"
        )

    return questions[:10]  # 최대 10개


def infer_theme_for_question(nodes: list, G) -> str:
    """질문용 커뮤니티 테마 추론."""
    files = set()
    for n in nodes[:5]:
        data = G.nodes[n]
        f = data.get("file", "")
        if f:
            files.add(Path(f).stem)
    return "+".join(sorted(files)[:2]) if files else "혼합"


# ─── CSV 출력 ─────────────────────────────────────────────

def save_nodes_csv(G, community_map: dict, degree_centrality: dict, out_path: Path):
    """nodes.csv 저장."""
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "type", "file", "line", "community_id",
            "degree_centrality", "tag", "confidence"
        ])
        writer.writeheader()
        for node_id, data in G.nodes(data=True):
            writer.writerow({
                "id": node_id,
                "type": data.get("type", "unknown"),
                "file": data.get("file", ""),
                "line": data.get("line", 0),
                "community_id": community_map.get(node_id, -1),
                "degree_centrality": f"{degree_centrality.get(node_id, 0):.6f}",
                "tag": data.get("tag", "EXTRACTED"),
                "confidence": data.get("confidence", 1.0),
            })
    print(f"  [CSV] {out_path}")


def save_edges_csv(G, out_path: Path):
    """edges.csv 저장."""
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "source", "target", "type", "confidence", "tag", "weight"
        ])
        writer.writeheader()
        for src, tgt, data in G.edges(data=True):
            writer.writerow({
                "source": src,
                "target": tgt,
                "type": data.get("type", "unknown"),
                "confidence": data.get("confidence", 1.0),
                "tag": data.get("tag", "EXTRACTED"),
                "weight": data.get("weight", 1.0),
            })
    print(f"  [CSV] {out_path}")


def save_suggested_questions(questions: list, out_path: Path):
    """suggested_questions.md 저장."""
    lines = [
        "# vet-snomed-rag 탐색 추천 질문",
        "",
        "graphify_lite 분석 기반 코드베이스 탐색을 위한 추천 질문 목록.",
        "",
    ]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q}")

    lines.extend([
        "",
        "---",
        "",
        "## 활용 방법",
        "",
        "1. `graph.html`을 브라우저에서 열어 인터랙티브 그래프를 탐색한다.",
        "2. `nodes.csv`에서 degree_centrality 기준 상위 노드를 확인한다.",
        "3. `edges.csv`에서 confidence=1.0(EXTRACTED) 엣지만 필터링하여 확실한 의존 관계를 파악한다.",
        "4. `report.md`의 God Node 섹션과 Community 섹션을 연결하여 모듈 설계 패턴을 분석한다.",
    ])

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  [MD] {out_path}")


# ─── 메인 파이프라인 ──────────────────────────────────────

def main():
    """9단계 파이프라인 실행."""
    start_time = time.time()

    print("=" * 60)
    print(" graphify_lite — vet-snomed-rag 코드 지식 그래프")
    print("=" * 60)
    print(f" 프로젝트 루트: {PROJECT_ROOT}")
    print(f" 소스 디렉토리: {SRC_DIR}")
    print(f" 출력 디렉토리: {OUT_DIR}")
    print()

    # 출력 디렉토리 생성
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cache_path = OUT_DIR / "cache.json"
    cache_data = load_cache(cache_path)

    # ─── Step 1: Detect ──────────────────────────────────
    print("[Step 1] Python 파일 탐색...")
    py_files = detect_python_files(SRC_DIR)
    print(f"  → {len(py_files)}개 파일 발견")
    for f in py_files:
        rel = get_relative_path(f, SRC_DIR)
        print(f"     {rel}")
    print()

    # ─── Step 2: Extract ─────────────────────────────────
    print("[Step 2] AST 파싱 및 노드/엣지 추출...")
    all_nodes: list[dict] = []
    all_edges: list[dict] = []
    parse_errors: list[str] = []
    new_cache = {}

    parsed_count = 0
    for filepath in py_files:
        rel_path = get_relative_path(filepath, SRC_DIR)
        sha256 = compute_sha256(filepath)
        mtime = os.path.getmtime(filepath)

        # 캐시 히트 확인
        cached = cache_data.get(rel_path, {})
        if cached.get("sha256") == sha256:
            print(f"  [캐시 히트] {rel_path}")
            all_nodes.extend(cached.get("nodes", []))
            all_edges.extend(cached.get("edges", []))
            new_cache[rel_path] = cached
            parsed_count += 1
            continue

        # 새로 파싱
        print(f"  [파싱] {rel_path}")
        nodes, edges = extract_ast_nodes_edges(filepath, SRC_DIR)

        # 파싱 에러 수집
        for n in nodes:
            if n.get("error"):
                parse_errors.append(f"{rel_path}: {n['error']}")

        all_nodes.extend(nodes)
        all_edges.extend(edges)
        parsed_count += 1

        new_cache[rel_path] = {
            "sha256": sha256,
            "mtime": mtime,
            "nodes": nodes,
            "edges": edges,
        }

    print(f"  → 파싱 완료: {parsed_count}/{len(py_files)}개")
    print(f"  → 추출 노드: {len(all_nodes)}개, 엣지: {len(all_edges)}개")
    print()

    # ─── Step 3: Cache ──────────────────────────────────
    print("[Step 3] 캐시 저장...")
    save_cache(cache_path, new_cache)
    print(f"  → {cache_path}")
    print()

    # ─── Step 4: Build ──────────────────────────────────
    print("[Step 4] NetworkX 그래프 구축...")
    G = build_graph(all_nodes, all_edges)
    internal_node_count = sum(1 for _, d in G.nodes(data=True) if d.get("type") != "external")
    print(f"  → 전체 노드: {G.number_of_nodes()} (내부: {internal_node_count}, 외부 심볼: {G.number_of_nodes() - internal_node_count})")
    print(f"  → 전체 엣지: {G.number_of_edges()}")
    print()

    # ─── Step 5: Analyze ────────────────────────────────
    print("[Step 5] 그래프 분석 (degree centrality, community, surprising)...")
    degree_centrality, community_map, communities, surprising = analyze_graph(G)

    # God Node Top 5 출력
    internal_dc = {
        n: dc for n, dc in degree_centrality.items()
        if G.nodes[n].get("type") != "external"
    }
    god_nodes = sorted(internal_dc.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"  → 커뮤니티 수: {len(communities)}")
    print(f"  → God Node Top 5:")
    for rank, (nid, dc) in enumerate(god_nodes, 1):
        print(f"     [{rank}] {nid} (dc={dc:.4f})")
    print()

    # ─── Step 6: Visualize ──────────────────────────────
    print("[Step 6] 시각화 생성...")

    # JSON
    save_graph_json(G, OUT_DIR / "graph.json")

    # pyvis HTML
    print("  [HTML] pyvis 인터랙티브 그래프 생성 중...")
    try:
        generate_pyvis_html(G, community_map, degree_centrality, OUT_DIR / "graph.html")
        print(f"  [HTML] {OUT_DIR / 'graph.html'}")
    except Exception as e:
        print(f"  [HTML 실패] {e}")

    # matplotlib PNG
    generate_matplotlib_png(G, community_map, degree_centrality, OUT_DIR / "graph.png")
    print()

    # ─── Step 7, 8: 생략 (영상/오디오 없음, Query CLI 생략) ───

    # ─── Step 9: Report ──────────────────────────────────
    print("[Step 9] 리포트 생성...")

    # nodes.csv
    save_nodes_csv(G, community_map, degree_centrality, OUT_DIR / "nodes.csv")

    # edges.csv
    save_edges_csv(G, OUT_DIR / "edges.csv")

    # report.md
    report_content = generate_report(
        G, all_nodes, all_edges,
        degree_centrality, community_map, communities,
        surprising, parse_errors,
        OUT_DIR / "report.md",
    )

    # suggested_questions.md
    sq_lines = [line for line in report_content.split("\n")
                if re.match(r"^\d+\.", line)]
    questions = [re.sub(r"^\d+\.\s*", "", q) for q in sq_lines]
    save_suggested_questions(questions, OUT_DIR / "suggested_questions.md")
    print()

    # ─── 완료 요약 ────────────────────────────────────────
    elapsed = time.time() - start_time

    # 파일 크기 확인
    def fsize(p: Path) -> str:
        try:
            return f"{p.stat().st_size:,} bytes"
        except Exception:
            return "N/A"

    def frows(p: Path) -> str:
        try:
            with open(p) as f:
                return f"{sum(1 for _ in f) - 1} rows"
        except Exception:
            return "N/A"

    print("=" * 60)
    print(" 완료!")
    print(f" 실행 시간: {elapsed:.1f}초")
    print()
    print(" 산출물:")
    print(f"   graph.json:            {fsize(OUT_DIR / 'graph.json')}")
    print(f"   nodes.csv:             {frows(OUT_DIR / 'nodes.csv')}")
    print(f"   edges.csv:             {frows(OUT_DIR / 'edges.csv')}")
    print(f"   report.md:             {fsize(OUT_DIR / 'report.md')}")
    print(f"   graph.html:            {fsize(OUT_DIR / 'graph.html')}")
    print(f"   graph.png:             {fsize(OUT_DIR / 'graph.png')}")
    print(f"   cache.json:            {fsize(OUT_DIR / 'cache.json')}")
    print(f"   suggested_questions.md:{fsize(OUT_DIR / 'suggested_questions.md')}")
    print("=" * 60)

    # 성공 기준 자기 확인
    print()
    print("[성공 기준 확인]")

    nodes_csv_rows = 0
    edges_csv_rows = 0
    try:
        with open(OUT_DIR / "nodes.csv") as f:
            nodes_csv_rows = sum(1 for _ in f) - 1
        with open(OUT_DIR / "edges.csv") as f:
            edges_csv_rows = sum(1 for _ in f) - 1
    except Exception:
        pass

    html_size = 0
    try:
        html_size = (OUT_DIR / "graph.html").stat().st_size
    except Exception:
        pass

    report_exists = (OUT_DIR / "report.md").exists()
    report_sections = 0
    if report_exists:
        try:
            with open(OUT_DIR / "report.md") as f:
                content = f.read()
            report_sections = content.count("\n## ")
        except Exception:
            pass

    checks = [
        ("report.md 존재 + 3개 섹션 채워짐", report_exists and report_sections >= 3),
        (f"nodes.csv ≥ 100행 (실측: {nodes_csv_rows}행)", nodes_csv_rows >= 100),
        (f"edges.csv ≥ 50행 (실측: {edges_csv_rows}행)", edges_csv_rows >= 50),
        (f"graph.html > 10KB (실측: {html_size:,} bytes)", html_size > 10240),
    ]

    all_pass = True
    for name, result in checks:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
        if not result:
            all_pass = False

    print()
    if all_pass:
        print("  → 모든 성공 기준 통과")
    else:
        print("  → 일부 기준 미달 — 위 FAIL 항목 확인 필요")

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
