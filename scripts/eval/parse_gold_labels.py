"""
parse_gold_labels.py — C2 Gold-Label 파서
==========================================

입력 : data/synthetic_scenarios/scenario_{1..5}_*.md
출력 : List[GoldLabel] (JSON 직렬화 가능)

GoldLabel 구조:
  scenario_id : int
  domain      : str (PRIMARY 도메인)
  secondary   : List[str]
  fields      : List[{field_code, label, value, section}]
  snomed      : List[{field_code, concept_id, preferred_term, semantic_tag, confidence}]

[절대 원칙]
  - 파싱 실패 시 FAIL (추측값 대체 금지)
  - gold-label 조작 금지 — 원본 마크다운 값만 사용
  - 임상/투자 판단 금지 (data-analyzer 원칙)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "synthetic_scenarios"


def _parse_markdown_table(block: str) -> list[dict[str, str]]:
    """마크다운 파이프 테이블을 dict 리스트로 변환한다.

    Args:
        block: | 헤더 | ... 형식의 테이블 문자열

    Returns:
        [{"헤더1": "값1", "헤더2": "값2"}, ...] 형태의 리스트

    Raises:
        ValueError: 헤더 파싱 실패 또는 테이블 구조 오류
    """
    lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
    # 최소 구조: 헤더 행 + 구분 행 + 데이터 행 1개
    if len(lines) < 3:
        return []

    # 헤더 파싱
    header_line = lines[0]
    if not header_line.startswith("|"):
        raise ValueError(f"마크다운 테이블 헤더 오류: {header_line!r}")
    headers = [h.strip() for h in header_line.split("|") if h.strip()]
    if not headers:
        raise ValueError(f"헤더를 찾을 수 없음: {header_line!r}")

    # 구분 행 건너뜀 (lines[1])
    rows = []
    for line in lines[2:]:
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        # 앞뒤 빈 셀 제거 (| 로 시작/끝나는 경우)
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        if len(cells) != len(headers):
            # 열 수 불일치 — 경고 후 건너뜀
            continue
        rows.append(dict(zip(headers, cells)))

    return rows


def _extract_section(text: str, section_header: str) -> str:
    """마크다운에서 특정 헤더 아래의 텍스트 블록을 추출한다.

    Args:
        text          : 전체 마크다운 문자열
        section_header: "### 기대 필드" 등 헤더 문자열

    Returns:
        해당 섹션의 텍스트 (다음 ### 헤더 또는 문서 끝까지)
    """
    # 헤더를 정규식으로 탈출 처리
    escaped = re.escape(section_header)
    pattern = re.compile(
        rf"{escaped}.*?(?=^###|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pattern.search(text)
    if not m:
        return ""
    return m.group(0)


def parse_scenario_file(md_path: Path) -> dict[str, Any]:
    """시나리오 마크다운 파일 1개를 파싱하여 gold-label dict를 반환한다.

    Args:
        md_path: 마크다운 파일 경로

    Returns:
        {
          scenario_id, domain, secondary, fields, snomed
        }

    Raises:
        FileNotFoundError  : 파일 없음
        ValueError         : 필수 섹션(Gold-Label, 기대 필드, 기대 SNOMED 태깅) 미존재
        RuntimeError       : 파싱 실패
    """
    if not md_path.exists():
        raise FileNotFoundError(f"파일 없음: {md_path}")

    text = md_path.read_text(encoding="utf-8")

    # ── frontmatter 파싱 ─────────────────────────────────────────────────
    scenario_id: int = -1
    fm_match = re.search(r"^scenario_id:\s*(\d+)", text, re.MULTILINE)
    if fm_match:
        scenario_id = int(fm_match.group(1))
    else:
        # 파일명에서 fallback (scenario_3_... → 3)
        id_match = re.search(r"scenario_(\d+)", md_path.stem)
        if id_match:
            scenario_id = int(id_match.group(1))
        else:
            raise ValueError(f"scenario_id 파싱 실패: {md_path.name}")

    # ── Gold-Label 섹션 추출 ────────────────────────────────────────────
    gold_section_match = re.search(
        r"^## Gold-Label\s*$(.*)",
        text,
        re.DOTALL | re.MULTILINE,
    )
    if not gold_section_match:
        raise ValueError(f"'## Gold-Label' 섹션 없음: {md_path.name}")
    gold_text = gold_section_match.group(1)

    # ── 기대 도메인 파싱 ─────────────────────────────────────────────────
    primary_match = re.search(r"PRIMARY:\s*([^\n]+)", gold_text)
    if not primary_match:
        raise ValueError(f"'PRIMARY:' 도메인 없음: {md_path.name}")
    domain = primary_match.group(1).strip()
    # 복합 도메인 (e.g., "GASTROINTESTINAL + VITAL_SIGNS") → 첫 번째만 primary
    primary_domain = re.split(r"\s*[\+/]\s*", domain)[0].strip()

    secondary_domains: list[str] = []
    for sec_match in re.finditer(r"SECONDARY:\s*([^\n]+)", gold_text):
        sec_raw = sec_match.group(1).strip()
        # 괄호 안 설명 제거
        sec_clean = re.sub(r"\s*\(.*?\)", "", sec_raw).strip()
        secondary_domains.append(sec_clean)

    # ── 기대 필드 테이블 파싱 ───────────────────────────────────────────
    field_section = _extract_section(gold_text, "### 기대 필드")
    if not field_section:
        raise ValueError(f"'### 기대 필드' 섹션 없음: {md_path.name}")

    # 테이블 블록 추출 (연속된 | 로 시작하는 줄)
    table_match = re.search(r"(\|.+\|.*\n(?:\|[-:| ]+\|.*\n)(?:\|.+\|.*\n?)+)", field_section)
    if not table_match:
        raise ValueError(f"'기대 필드' 테이블 없음: {md_path.name}")

    field_rows = _parse_markdown_table(table_match.group(1))
    # (MASS) 도메인 연계 필드 등 추가 테이블 처리
    extra_tables = re.findall(
        r"### MASS 도메인.*?(\|.+\|.*\n(?:\|[-:| ]+\|.*\n)(?:\|.+\|.*\n?)+)",
        gold_text,
        re.DOTALL,
    )
    for extra_table in extra_tables:
        extra_rows = _parse_markdown_table(extra_table)
        field_rows.extend(extra_rows)

    # 필드 목록 정제
    fields: list[dict[str, str]] = []
    for row in field_rows:
        fc = row.get("field_code", "").strip()
        if not fc or fc.startswith("-") or fc.startswith("field_code"):
            continue  # 헤더 중복 행 무시
        fields.append({
            "field_code": fc,
            "label":      row.get("label", "").strip(),
            "value":      row.get("value", "").strip(),
            "section":    row.get("section", "").strip(),
        })

    if not fields:
        raise ValueError(f"'기대 필드' 파싱 결과 0건: {md_path.name}")

    # ── 기대 SNOMED 태깅 테이블 파싱 ────────────────────────────────────
    snomed_section = _extract_section(gold_text, "### 기대 SNOMED 태깅")
    if not snomed_section:
        raise ValueError(f"'### 기대 SNOMED 태깅' 섹션 없음: {md_path.name}")

    snomed_table_match = re.search(
        r"(\|.+\|.*\n(?:\|[-:| ]+\|.*\n)(?:\|.+\|.*\n?)+)", snomed_section
    )
    snomed: list[dict[str, Any]] = []
    if snomed_table_match:
        snomed_rows = _parse_markdown_table(snomed_table_match.group(1))
        for row in snomed_rows:
            fc = row.get("field_code", "").strip()
            cid = row.get("concept_id", "").strip()
            if not fc or not cid or fc == "field_code":
                continue
            # confidence: 문자열 → float
            conf_raw = row.get("confidence", "0.0").strip()
            try:
                confidence = float(conf_raw)
            except ValueError:
                confidence = 0.0
            snomed.append({
                "field_code":     fc,
                "concept_id":     cid,
                "preferred_term": row.get("preferred_term", "").strip(),
                "semantic_tag":   row.get("semantic_tag", "").strip(),
                "confidence":     confidence,
            })
    # snomed=0건 허용 — gold SNOMED 태깅이 없는 시나리오(전수 DIFFERENT 판정)는 정상

    return {
        "scenario_id": scenario_id,
        "domain":      primary_domain,
        "secondary":   secondary_domains,
        "fields":      fields,
        "snomed":      snomed,
    }


def load_all_gold_labels(
    scenarios_dir: Path = DATA_DIR,
) -> list[dict[str, Any]]:
    """scenarios 디렉토리의 모든 시나리오 파일을 파싱한다.

    Args:
        scenarios_dir: synthetic_scenarios 디렉토리

    Returns:
        List[GoldLabel] — scenario_id 오름차순 정렬

    Raises:
        RuntimeError: 1건 이상 파싱 실패 시 (FAIL, 추측값 대체 금지)
    """
    if not scenarios_dir.exists():
        raise FileNotFoundError(f"시나리오 디렉토리 없음: {scenarios_dir}")

    md_files = sorted(
        [f for f in scenarios_dir.glob("scenario_*.md") if f.stem != "README"],
        key=lambda p: int(re.search(r"scenario_(\d+)", p.stem).group(1))
        if re.search(r"scenario_(\d+)", p.stem) else 999,
    )

    if not md_files:
        raise FileNotFoundError(f"시나리오 마크다운 파일 없음: {scenarios_dir}")

    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for md_path in md_files:
        try:
            label = parse_scenario_file(md_path)
            results.append(label)
            print(f"  [OK] {md_path.name}: scenario_id={label['scenario_id']}, "
                  f"domain={label['domain']}, "
                  f"fields={len(label['fields'])}, snomed={len(label['snomed'])}")
        except Exception as e:
            errors.append(f"FAIL {md_path.name}: {e}")
            print(f"  [FAIL] {md_path.name}: {e}")

    if errors:
        # 파싱 실패 시 FAIL — 추측값 대체 금지 (P3 원칙)
        raise RuntimeError(
            f"gold-label 파싱 실패 {len(errors)}건:\n" + "\n".join(errors)
        )

    # scenario_id 오름차순 정렬
    results.sort(key=lambda x: x["scenario_id"])
    return results


# ─── CLI (검증용) ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=== Gold-Label 파서 검증 ===")
    print(f"입력 디렉토리: {DATA_DIR}")
    try:
        labels = load_all_gold_labels()
        print(f"\n파싱 성공: {len(labels)}/5 시나리오")
        total_fields = sum(len(lb["fields"]) for lb in labels)
        total_snomed = sum(len(lb["snomed"]) for lb in labels)
        print(f"총 필드 수: {total_fields}")
        print(f"총 concept_id 수: {total_snomed}")
        print("\n상세 요약:")
        for lb in labels:
            print(f"  S{lb['scenario_id']:02d} [{lb['domain']}]"
                  f" fields={len(lb['fields'])} snomed={len(lb['snomed'])}")
        # JSON 덤프 확인
        out_path = PROJECT_ROOT / "benchmark" / "gold_labels_debug.json"
        out_path.parent.mkdir(exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(labels, f, ensure_ascii=False, indent=2)
        print(f"\n[DEBUG] JSON 저장: {out_path}")
    except Exception as e:
        print(f"\n[FAIL] {e}", file=sys.stderr)
        sys.exit(1)
