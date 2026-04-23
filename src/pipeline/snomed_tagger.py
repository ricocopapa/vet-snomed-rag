"""
SNOMED 자동 태거 (B3 Track) — v2.0
=====================================
B2 출력 fields 배열을 입력받아 snomed_tagging 배열을 생성한다.

[핵심 원칙]
- LIKE 매칭 금지: v1.0 rag_pipeline.query() Top-1 결과만 사용
- AI 추론 concept_id 생성 금지: RF2 DB 실존 검증 후 통과한 것만 채택
- NULL → UNMAPPED 강제: null 출력 없음
- MRCM 검증 skip 금지: 후조합 전 반드시 check_mrcm() 호출
- v1.0 src/retrieval/* 코드 무변경

[출력 스키마 — §7.1 snomed_tagging 배열 엔트리]
{
    "field_code":       str,   # 입력 필드 코드
    "concept_id":       str,   # SNOMED concept_id 또는 "UNMAPPED"
    "preferred_term":   str,   # concept 선호 용어 (UNMAPPED이면 빈 문자열)
    "semantic_tag":     str,   # disorder / finding / observable entity / procedure 등
    "source":           str,   # INT / VET / LOCAL / UNMAPPED
    "post_coordination":str,   # SCG 표현식 (없으면 빈 문자열)
    "mrcm_validated":   bool,  # MRCM 허용 여부
    "confidence":       float, # 0.0~1.0 (RAG Top-1 스코어 정규화)
}
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "snomed_ct_vet.db"
MRCM_RULES_PATH = DATA_DIR / "mrcm_rules_v1.json"

# v1.0 RAG 파이프라인 임포트 (무변경)
sys.path.insert(0, str(PROJECT_ROOT))


# ─── 도메인 → semantic_tag 화이트리스트 (SKILL.md §2 원칙 1) ──────────

DOMAIN_TAG_WHITELIST: dict[str, list[str]] = {
    "ASSESSMENT": ["disorder", "finding", "situation", "event", "morphologic abnormality"],
    "SUBJECTIVE": ["finding", "observable entity", "qualifier value", "body structure"],
    "OBJECTIVE": ["observable entity", "finding", "procedure", "qualifier value", "body structure"],
    "PLAN_TX": ["procedure", "substance", "product", "regime/therapy"],
    "PLAN_RX": ["substance", "product", "medicinal product", "regime/therapy"],
    # 기본 (도메인 미지정)
    "DEFAULT": [
        "disorder", "finding", "observable entity", "procedure",
        "qualifier value", "body structure", "substance", "organism",
        "morphologic abnormality", "situation", "event",
    ],
}

# ─── field_code suffix → semantic_tag 우선순위 (전략 B: semantic_tag 소프트 필터) ──
# [수정 사유: 2026-04-23] 전략 B — BGE Reranker 활성화 + semantic_tag priority 가중치.
# rerank=True 경로에서 reranker 점수에 semantic_tag 일치 보너스를 부여한다.
# 설계서 §2.2 §전략 B 구현 변경 지점 준수.
FIELD_CODE_SUFFIX_TAG_PRIORITY: dict[str, list[str]] = {
    # 수치·측정값 필드: observable entity 우선
    "_VALUE": ["observable entity", "finding"],
    "_VAL": ["observable entity", "finding"],
    "_OD": ["observable entity", "finding"],       # Oculus Dexter
    "_OS": ["observable entity", "finding"],       # Oculus Sinister
    "_OU": ["observable entity", "finding"],       # Oculus Uterque
    # 코드·상태 필드: finding/disorder 우선
    "_CD": ["finding", "disorder", "observable entity"],
    "_STATUS": ["finding", "disorder"],
    "_GRADE": ["finding", "disorder", "qualifier value"],
    # 시술·처치 필드: procedure 우선
    "_PROC": ["procedure"],
    "_TX": ["procedure", "regime/therapy"],
    # 진단 필드: disorder/finding 우선
    "_DX": ["disorder", "finding"],
    "_DIAG": ["disorder", "finding"],
    # 행동·빈도 필드: finding 우선
    "_FREQ": ["finding", "observable entity"],
    "_BEHAVIOR": ["finding"],
    "_NM": ["finding", "disorder"],
}


def _get_tag_whitelist(domain: str) -> list[str]:
    """도메인 코드로 허용 semantic_tag 목록을 반환한다."""
    domain_upper = domain.upper()
    for key in DOMAIN_TAG_WHITELIST:
        if key in domain_upper:
            return DOMAIN_TAG_WHITELIST[key]
    return DOMAIN_TAG_WHITELIST["DEFAULT"]


def _get_tag_priority(field_code: str) -> list[str]:
    """field_code suffix 기반 semantic_tag 우선순위 목록을 반환한다.

    전략 B semantic_tag 소프트 필터: rerank=True 경로에서 사용.
    우선순위 태그에 일치하는 후보에 보너스 점수를 부여한다.
    반환값이 비어있으면 우선순위 미적용.
    """
    field_upper = field_code.upper()
    for suffix, priority in FIELD_CODE_SUFFIX_TAG_PRIORITY.items():
        if field_upper.endswith(suffix):
            return priority
    return []


# ─── MRCM 규칙 로더 ──────────────────────────────────────────────────

def _load_mrcm_rules(path: Path = MRCM_RULES_PATH) -> dict:
    """mrcm_rules_v1.json을 로드한다."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _match_mrcm_field_rule(field_code: str, mrcm_rules: dict) -> Optional[dict]:
    """
    field_code에 매칭되는 MRCM 필드 규칙을 반환한다.
    패턴 매칭: fnmatch (glob 스타일, * 와일드카드)
    매칭 없으면 None 반환.
    """
    for domain_key, domain_val in mrcm_rules.items():
        if domain_key.startswith("_"):
            continue
        fields = domain_val.get("fields", {})
        for pattern, rule in fields.items():
            if fnmatch(field_code, pattern):
                return rule
    return None


# ─── SNOMEDTagger ────────────────────────────────────────────────────

class SNOMEDTagger:
    """
    SNOMED 자동 태거.

    B2 출력 fields 배열을 입력받아 §7.1 snomed_tagging 배열을 생성한다.
    모든 concept_id는 RF2 DB 실존 검증 후 채택 — AI 추론 생성 절대 금지.
    """

    def __init__(
        self,
        rag_pipeline=None,
        sqlite_path: Path = DB_PATH,
        mrcm_rules_path: Path = MRCM_RULES_PATH,
        enable_rerank: bool = False,
    ):
        """
        Args:
            rag_pipeline: v1.0 SNOMEDRagPipeline 인스턴스 (None이면 검색 비활성).
            sqlite_path:  SNOMED DB 경로 (RF2 실존 검증용).
            mrcm_rules_path: MRCM 규칙 JSON 경로.
            enable_rerank: True면 Step 2 RAG fallback에서 BGEReranker 활성화 +
                           semantic_tag priority 가중치 적용 (전략 B, 기본 False).
        """
        self.rag = rag_pipeline
        self.sqlite_path = sqlite_path
        self.mrcm_rules = _load_mrcm_rules(mrcm_rules_path)
        self._db_conn: Optional[sqlite3.Connection] = None
        self._enable_rerank = enable_rerank
        print(f"[SNOMEDTagger] 초기화 완료 | DB: {sqlite_path.name} | MRCM 도메인: {self._count_mrcm_domains()}개 | rerank={'ON' if enable_rerank else 'OFF'}")

    def _count_mrcm_domains(self) -> int:
        return sum(1 for k in self.mrcm_rules if not k.startswith("_"))

    def _get_db(self) -> sqlite3.Connection:
        """SQLite 연결을 반환한다 (지연 연결, 캐싱)."""
        if self._db_conn is None:
            self._db_conn = sqlite3.connect(str(self.sqlite_path))
            self._db_conn.row_factory = sqlite3.Row
        return self._db_conn

    def close(self):
        """DB 연결을 닫는다."""
        if self._db_conn is not None:
            self._db_conn.close()
            self._db_conn = None

    # ── 1. RF2 DB 실존 검증 ─────────────────────────────────────────

    def validate_concept_exists(self, concept_id: str) -> bool:
        """
        concept_id가 snomed_ct_vet.db에 실존하는지 검증한다.

        피드백 feedback_snomed_source_validation 준수:
        RF2 원본 DB 검증 없이 AI 추론 concept_id 사용 절대 금지.

        Returns:
            True  — DB에 존재함 (채택 가능)
            False — DB에 없음 (UNMAPPED으로 처리해야 함)
        """
        if not concept_id or concept_id == "UNMAPPED":
            return False
        try:
            conn = self._get_db()
            row = conn.execute(
                "SELECT 1 FROM concept WHERE concept_id = ? LIMIT 1",
                (concept_id,)
            ).fetchone()
            return row is not None
        except Exception as e:
            print(f"  [검증 오류] concept_id={concept_id}: {e}")
            return False

    def _get_concept_meta(self, concept_id: str) -> Optional[dict]:
        """concept_id로 preferred_term, semantic_tag, source를 조회한다."""
        try:
            conn = self._get_db()
            row = conn.execute(
                "SELECT concept_id, preferred_term, semantic_tag, source FROM concept WHERE concept_id = ? LIMIT 1",
                (concept_id,)
            ).fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
        return None

    # ── 2. MRCM 검증 ────────────────────────────────────────────────

    def check_mrcm(self, base_concept_id: str, attribute_id: str) -> bool:
        """
        base_concept에 attribute 부착이 MRCM 규칙상 허용되는지 확인한다.

        피드백 feedback_mrcm_constraint_check 준수:
        concept 존재 ≠ 부착 가능. MRCM 허용 attribute 사전 확인 필수.

        Returns:
            True  — 허용 (또는 규칙 미정의로 통과)
            False — 금지 (mrcm_forbidden_attributes 목록에 있음)
        """
        # MRCM 규칙에서 base_concept_id와 매칭되는 필드 규칙 탐색
        for domain_key, domain_val in self.mrcm_rules.items():
            if domain_key.startswith("_"):
                continue
            fields = domain_val.get("fields", {})
            for _pattern, rule in fields.items():
                if rule.get("base_concept_id") == base_concept_id:
                    forbidden = rule.get("mrcm_forbidden_attributes", [])
                    if attribute_id in forbidden:
                        reason = rule.get("mrcm_forbidden_reason", "MRCM 비허용")
                        print(f"  [MRCM FAIL] base={base_concept_id}, attr={attribute_id}: {reason}")
                        return False
                    # allowed_attributes에 명시된 경우 True
                    allowed = [a["attribute_id"] for a in rule.get("allowed_attributes", [])]
                    if allowed and attribute_id in allowed:
                        return True
                    # allowed 목록이 있으나 해당 attribute가 없으면 비허용
                    if allowed and attribute_id not in allowed:
                        print(f"  [MRCM WARN] base={base_concept_id}, attr={attribute_id}: 허용 목록 외")
                        return False
        # 규칙 미정의: 통과 (보수적 허용)
        return True

    # ── 3. Post-coordination SCG 표현식 빌더 ────────────────────────

    def build_post_coordination(
        self,
        base_concept_id: str,
        attribute_id: str,
        value_concept_id: str,
    ) -> str:
        """
        SCG(SNOMED Compositional Grammar) 표현식을 생성한다.

        형식: {base_id} |{base_term}|: {attr_id} |{attr_term}| = {value_id} |{value_term}|

        Returns:
            SCG 문자열 (모든 concept_id DB 실존 검증 후 생성)
            검증 실패 시 빈 문자열 반환
        """
        # 모든 구성 요소 DB 실존 검증 (피드백 feedback_snomed_source_validation)
        for cid, label in [
            (base_concept_id, "base"),
            (attribute_id, "attribute"),
            (value_concept_id, "value"),
        ]:
            if not self.validate_concept_exists(cid):
                print(f"  [SCG FAIL] {label} concept_id={cid} DB 미존재 → SCG 생성 불가")
                return ""

        base_meta = self._get_concept_meta(base_concept_id)
        attr_meta = self._get_concept_meta(attribute_id)
        val_meta = self._get_concept_meta(value_concept_id)

        if not all([base_meta, attr_meta, val_meta]):
            return ""

        scg = (
            f"{base_concept_id} |{base_meta['preferred_term']}|"
            f": {attribute_id} |{attr_meta['preferred_term']}|"
            f" = {value_concept_id} |{val_meta['preferred_term']}|"
        )
        return scg

    # ── 4. 단일 필드 태깅 ────────────────────────────────────────────

    def tag_field(
        self,
        field_code: str,
        value,
        domain: str = "DEFAULT",
    ) -> dict:
        """
        단일 필드 → snomed_tagging 배열 1 엔트리를 생성한다.

        Args:
            field_code: 필드 코드 (예: "CA_OPH_IOP_OD_VAL")
            value:      필드 값 (수치, 코드, 텍스트 모두 허용)
            domain:     도메인 힌트 (예: "OPH", "VITAL_SIGNS")

        Returns:
            §7.1 snomed_tagging 엔트리 dict
        """
        start_ts = time.time()
        tag_whitelist = _get_tag_whitelist(domain)

        # MRCM 필드 규칙 탐색 (field_code 패턴 매칭)
        mrcm_rule = _match_mrcm_field_rule(field_code, self.mrcm_rules)

        # ── Step 1: MRCM 규칙에서 base_concept 직접 지정된 경우 우선 채택 ──
        base_concept_id = None
        base_concept_term = ""
        base_semantic_tag = ""
        base_source = ""
        confidence = 0.0
        post_coord_expr = ""
        mrcm_validated = True

        if mrcm_rule:
            cid = mrcm_rule.get("base_concept_id", "")
            if cid and self.validate_concept_exists(cid):
                meta = self._get_concept_meta(cid)
                if meta and meta["semantic_tag"] in tag_whitelist:
                    base_concept_id = cid
                    base_concept_term = meta["preferred_term"]
                    base_semantic_tag = meta["semantic_tag"]
                    base_source = meta["source"]
                    confidence = 0.95  # MRCM 규칙 직접 지정 → 높은 신뢰도
                    print(f"  [MRCM 직접지정] {field_code} → {cid} |{base_concept_term}| ({base_semantic_tag})")

        # ── Step 2: MRCM 규칙 없거나 실패 시 RAG Top-1 검색 ───────────
        # [수정 사유: 2026-04-23] 전략 B — enable_rerank=True 시 BGEReranker 경로 분기.
        # rerank=True: Top-20 후보 → CrossEncoder 재정렬 → semantic_tag priority 보너스 적용.
        # rerank=False: 기존 v1.0 경로 완전 동일 유지.
        if not base_concept_id and self.rag is not None:
            # field_code에서 검색 쿼리 파생 (언더스코어 → 공백, 접미사 제거)
            query = self._derive_query_from_field_code(field_code)
            try:
                if self._enable_rerank:
                    # 전략 B 경로: rerank=True → Top-20 후보 → BGEReranker 재정렬
                    rag_result = self.rag.query(query, top_k=5, rerank=True)
                    sr_list = rag_result.get("search_results", [])
                    # semantic_tag priority 가중치: field_code suffix 기반 선호 태그
                    tag_priority = _get_tag_priority(field_code)
                    # priority 태그 일치 후보를 우선, 나머지는 reranker 순서 유지
                    if tag_priority:
                        priority_hits = [
                            sr for sr in sr_list
                            if sr.semantic_tag in tag_priority
                            and sr.semantic_tag in tag_whitelist
                            and self.validate_concept_exists(sr.concept_id)
                        ]
                        other_hits = [
                            sr for sr in sr_list
                            if sr.semantic_tag not in tag_priority
                            and sr.semantic_tag in tag_whitelist
                            and self.validate_concept_exists(sr.concept_id)
                        ]
                        reranked_ordered = priority_hits + other_hits
                        print(f"  [Rerank+Priority] {field_code} | priority_hits={len(priority_hits)} | other_hits={len(other_hits)}")
                    else:
                        reranked_ordered = [
                            sr for sr in sr_list
                            if sr.semantic_tag in tag_whitelist
                            and self.validate_concept_exists(sr.concept_id)
                        ]
                    for sr in reranked_ordered:
                        base_concept_id = sr.concept_id
                        base_concept_term = sr.preferred_term
                        base_semantic_tag = sr.semantic_tag
                        base_source = sr.source
                        raw_score = getattr(sr, "rerank_score", getattr(sr, "score", 0.0))
                        confidence = min(1.0, max(0.0, float(raw_score)))
                        print(f"  [RAG+Rerank Top-1] {field_code} → {base_concept_id} |{base_concept_term}| (rerank_score={confidence:.4f})")
                        break
                else:
                    # v1.0 경로 (변경 없음)
                    rag_result = self.rag.query(query, top_k=5)
                    sr_list = rag_result.get("search_results", [])
                    for sr in sr_list:
                        # semantic_tag 화이트리스트 필터 (피드백 feedback_keyword_mapping_danger)
                        if sr.semantic_tag not in tag_whitelist:
                            continue
                        # RF2 DB 실존 검증 (피드백 feedback_snomed_source_validation)
                        if not self.validate_concept_exists(sr.concept_id):
                            continue
                        base_concept_id = sr.concept_id
                        base_concept_term = sr.preferred_term
                        base_semantic_tag = sr.semantic_tag
                        base_source = sr.source
                        # 스코어 정규화 (0~1)
                        raw_score = getattr(sr, "score", 0.0)
                        confidence = min(1.0, max(0.0, float(raw_score)))
                        print(f"  [RAG Top-1] {field_code} → {base_concept_id} |{base_concept_term}| (score={confidence:.3f})")
                        break
            except Exception as e:
                print(f"  [RAG 오류] {field_code}: {e}")

        # ── Step 3: 후조합 (Post-coordination) 시도 ─────────────────
        # IOP 수치 필드 → Has interpretation 후조합 (값 기반)
        if base_concept_id and mrcm_rule:
            post_coord_expr = self._try_post_coordination(
                base_concept_id=base_concept_id,
                value=value,
                field_code=field_code,
                mrcm_rule=mrcm_rule,
            )

        # ── Step 4: MRCM 최종 검증 ───────────────────────────────────
        if base_concept_id and post_coord_expr:
            # SCG 표현식에 포함된 attribute_id 추출하여 MRCM 검증
            attr_id = self._extract_attribute_from_scg(post_coord_expr)
            if attr_id:
                mrcm_validated = self.check_mrcm(base_concept_id, attr_id)
                if not mrcm_validated:
                    post_coord_expr = ""  # MRCM 위반 시 후조합 폐기

        # ── Step 5: 매핑 실패 처리 (NULL → UNMAPPED 강제) ───────────
        if not base_concept_id:
            return {
                "field_code": field_code,
                "concept_id": "UNMAPPED",
                "preferred_term": "",
                "semantic_tag": "",
                "source": "UNMAPPED",
                "post_coordination": "",
                "mrcm_validated": False,
                "confidence": 0.0,
                "latency_ms": int((time.time() - start_ts) * 1000),
            }

        return {
            "field_code": field_code,
            "concept_id": base_concept_id,
            "preferred_term": base_concept_term,
            "semantic_tag": base_semantic_tag,
            "source": base_source,
            "post_coordination": post_coord_expr,
            "mrcm_validated": mrcm_validated,
            "confidence": round(confidence, 4),
            "latency_ms": int((time.time() - start_ts) * 1000),
        }

    # ── 5. 전체 fields 배열 태깅 ─────────────────────────────────────

    def tag_all(self, fields: list[dict]) -> list[dict]:
        """
        B2 출력 fields 배열 전체를 snomed_tagging 배열로 변환한다.

        Args:
            fields: B2 출력 구조체 목록.
                    각 엔트리: {"field_code": str, "value": any, "domain": str (선택)}

        Returns:
            §7.1 snomed_tagging 배열
        """
        results = []
        total = len(fields)
        print(f"[SNOMEDTagger] tag_all 시작: {total}개 필드")
        for i, f in enumerate(fields, 1):
            field_code = f.get("field_code", "UNKNOWN")
            value = f.get("value")
            domain = f.get("domain", "DEFAULT")
            print(f"  [{i}/{total}] {field_code} (domain={domain}, value={value})")
            entry = self.tag_field(field_code, value, domain)
            results.append(entry)
        unmapped = sum(1 for r in results if r["concept_id"] == "UNMAPPED")
        print(f"[SNOMEDTagger] tag_all 완료: {total}개 처리, UNMAPPED={unmapped}건")
        return results

    # ── 내부 유틸 ────────────────────────────────────────────────────

    @staticmethod
    def _derive_query_from_field_code(field_code: str) -> str:
        """
        field_code에서 영어 검색 쿼리를 파생한다.
        예: CA_OPH_IOP_OD_VAL → "intraocular pressure"
        """
        # 접두어·접미사 제거 규칙
        strip_prefixes = ["CA_", "GP_", "CB_"]
        strip_suffixes = ["_VAL", "_CD", "_NM", "_DT", "_OD", "_OS", "_OU"]

        token = field_code
        for p in strip_prefixes:
            if token.startswith(p):
                token = token[len(p):]
        for s in strip_suffixes:
            if token.endswith(s):
                token = token[: -len(s)]

        # 언더스코어 → 공백, 소문자
        query = token.replace("_", " ").lower()
        # 도메인 접두어 약어 제거 (IOP = intraocular pressure 같은 건 RAG가 처리)
        return query

    def _try_post_coordination(
        self,
        base_concept_id: str,
        value,
        field_code: str,
        mrcm_rule: dict,
    ) -> str:
        """
        값(value)과 MRCM 규칙을 기반으로 후조합 SCG 표현식을 생성한다.
        MRCM 허용 attribute 중 Has interpretation(363713009) + Laterality(272741003) 지원.
        """
        allowed_attrs = {
            a["attribute_id"]: a
            for a in mrcm_rule.get("allowed_attributes", [])
        }

        # ── Has interpretation (363713009): 수치 필드 ───────────────
        if "363713009" in allowed_attrs and value is not None:
            interp_concept_id = self._map_value_to_interpretation(value, field_code)
            if interp_concept_id and self.validate_concept_exists(interp_concept_id):
                return self.build_post_coordination(
                    base_concept_id=base_concept_id,
                    attribute_id="363713009",
                    value_concept_id=interp_concept_id,
                )

        # ── Laterality (272741003): OD/OS/OU 접미사 필드 ────────────
        if "272741003" in allowed_attrs:
            lat_concept_id = self._map_field_code_to_laterality(field_code)
            if lat_concept_id and self.validate_concept_exists(lat_concept_id):
                return self.build_post_coordination(
                    base_concept_id=base_concept_id,
                    attribute_id="272741003",
                    value_concept_id=lat_concept_id,
                )

        return ""

    @staticmethod
    def _map_value_to_interpretation(value, field_code: str) -> Optional[str]:
        """
        수치/코드 값을 Has interpretation concept_id로 매핑한다.
        모든 concept_id는 DB 실존 검증된 값만 사용.

        수치형: 단순 임계값 비교 (필드별 정상 범위 없으므로 보수적 판단)
        코드형: HIGH/LOW/NORMAL 직접 매핑
        """
        # ─── concept_id는 RF2 DB 실존 검증 완료된 값만 ───
        HIGH_ID   = "75540009"   # High (qualifier value)
        LOW_ID    = "62482003"   # Low (qualifier value)
        NORMAL_ID = "17621005"   # Normal (qualifier value)

        if value is None:
            return None

        # 코드형 값 처리
        if isinstance(value, str):
            v_upper = value.upper()
            if any(kw in v_upper for kw in ["HIGH", "ELEVATED", "INCREASED"]):
                return HIGH_ID
            if any(kw in v_upper for kw in ["LOW", "DECREASED", "REDUCED"]):
                return LOW_ID
            if any(kw in v_upper for kw in ["NORMAL", "WNL", "WITHIN"]):
                return NORMAL_ID

        # IOP 수치형 처리 (mmHg 기준: 정상 10~20)
        if "IOP" in field_code.upper() and isinstance(value, (int, float)):
            if value > 25:
                return HIGH_ID
            if value < 8:
                return LOW_ID
            return NORMAL_ID

        # 일반 수치형: 부호로만 판단 (도메인별 정상 범위 미정의)
        if isinstance(value, (int, float)):
            if value > 0:
                return None  # 판단 불가 → 후조합 없음

        return None

    @staticmethod
    def _map_field_code_to_laterality(field_code: str) -> Optional[str]:
        """
        field_code 접미사로 Laterality concept_id를 결정한다.
        OD = 우측, OS = 좌측, OU = 양측
        concept_id는 RF2 DB 실존 검증 완료된 값만 사용.
        """
        # RF2 DB 실존 검증 완료 (2026-04-22)
        LATERALITY_MAP = {
            "_OD": "24028007",  # Right (qualifier value)
            "_OS": "7771000",   # Left  (qualifier value)
            "_OU": "51440002",  # Right and left (qualifier value)
            "_R_": "24028007",
            "_L_": "7771000",
        }
        for suffix, concept_id in LATERALITY_MAP.items():
            if suffix in field_code:
                return concept_id
        return None

    @staticmethod
    def _extract_attribute_from_scg(scg_expr: str) -> Optional[str]:
        """SCG 표현식에서 attribute concept_id를 추출한다. 예: '363713009 |Has interpretation|'"""
        import re
        # 패턴: ': {concept_id} |{term}| ='
        match = re.search(r":\s*(\d+)\s*\|", scg_expr)
        if match:
            return match.group(1)
        return None
