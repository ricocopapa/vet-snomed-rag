"""UMLS REST API 클라이언트 — v2.5 Tier B 외부 도구.

NLM UMLS Terminology Services REST API 통합.

[엔드포인트]
- Base: https://uts-ws.nlm.nih.gov/rest
- 인증: ?apiKey={UMLS_API_KEY} (쿼리 파라미터)
- 라이선스: UMLS Affiliate License (한국 회원국 무료)

[제공 메서드]
- search(query, top_k) → CUI 후보 목록
- get_concept(cui) → name + semantic_types
- get_cross_walks(cui, sources) → {source: [codes]}
- search_with_cross_walks(query) → 합산본 (RAG context 합류용)

[안전장치]
- UMLS_API_KEY env 미설정 시 enabled=False (호출 0)
- 401 → enabled=False 영구 (잘못된 키)
- 429 / 5xx / timeout → 빈 결과 graceful fallback
- LRU+TTL cache 24h (재호출 latency·rate limit 보호)

[설계서] docs/20260425_v2_5_tier_b_external_tools_design_v1.md §3-3
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from src.tools._cache import TTLCache

logger = logging.getLogger(__name__)

UMLS_BASE = "https://uts-ws.nlm.nih.gov/rest"
DEFAULT_TIMEOUT = 3.0
DEFAULT_TOP_K = 5
DEFAULT_SOURCES = ["ICD10CM", "MSH", "SNOMEDCT_US", "SNOMEDCT_VET"]


class UMLSClient:
    """UMLS REST API 클라이언트.

    Args:
        api_key: 명시 키. None이면 env UMLS_API_KEY에서 로드.
        timeout: 요청 타임아웃 (초).
        cache: 외부 주입 cache. None이면 자체 TTLCache 생성.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        cache: Optional[TTLCache] = None,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("UMLS_API_KEY", "")
        self.timeout = timeout
        self.cache = cache or TTLCache(max_size=1000, ttl_seconds=86400)
        self._enabled = bool(self.api_key)
        if not self._enabled:
            logger.info("UMLSClient: UMLS_API_KEY 미설정 → 자동 비활성")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _get(self, path: str, params: Optional[dict] = None) -> Optional[dict]:
        """공통 GET. 모든 실패 → None (graceful)."""
        if not self._enabled:
            return None
        params = dict(params or {})
        params["apiKey"] = self.api_key
        url = f"{UMLS_BASE}{path}"
        try:
            r = requests.get(url, params=params, timeout=self.timeout)
        except requests.Timeout:
            logger.warning("UMLS timeout %.1fs path=%s", self.timeout, path)
            return None
        except requests.RequestException as e:
            logger.warning("UMLS request failure path=%s err=%s", path, e)
            return None

        if r.status_code == 401:
            logger.warning("UMLS 401 인증 실패 — 키 확인 필요. 클라이언트 비활성화.")
            self._enabled = False
            return None
        if r.status_code == 429:
            logger.warning("UMLS 429 rate limit hit path=%s", path)
            return None
        if r.status_code >= 500:
            logger.warning("UMLS %d 서버 오류 path=%s", r.status_code, path)
            return None
        if r.status_code >= 400:
            logger.warning("UMLS %d client 오류 path=%s", r.status_code, path)
            return None

        try:
            return r.json()
        except ValueError:
            logger.warning("UMLS 응답 JSON 파싱 실패 path=%s", path)
            return None

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
        """자연어 검색 → CUI 후보 목록.

        Returns:
            [{"cui": "C0011849", "name": "...", "source": "umls"}, ...]
        """
        if not self._enabled or not query.strip():
            return []
        cache_key = f"search:{query}:{top_k}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        data = self._get(
            "/search/current",
            params={"string": query, "pageSize": top_k},
        )
        if not data:
            return []
        raw_results = data.get("result", {}).get("results", []) or []
        normalized = [
            {"cui": r.get("ui", ""), "name": r.get("name", ""), "source": "umls"}
            for r in raw_results
            if r.get("ui") and r.get("ui") != "NONE"
        ]
        self.cache.set(cache_key, normalized)
        return normalized

    def get_concept(self, cui: str) -> Optional[dict]:
        """CUI 메타데이터 (name + semantic types)."""
        if not self._enabled or not cui:
            return None
        cache_key = f"concept:{cui}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        data = self._get(f"/content/current/CUI/{cui}")
        if not data:
            return None
        result = data.get("result")
        if not result:
            return None
        normalized = {
            "cui": result.get("ui", cui),
            "name": result.get("name", ""),
            "semantic_types": [
                st.get("name", "") for st in (result.get("semanticTypes") or [])
            ],
            "source": "umls",
        }
        self.cache.set(cache_key, normalized)
        return normalized

    def get_cross_walks(
        self,
        cui: str,
        sources: Optional[list[str]] = None,
    ) -> dict[str, list[str]]:
        """CUI → 다른 코드 체계 cross-walk."""
        if not self._enabled or not cui:
            return {}
        sources = sources or DEFAULT_SOURCES
        cache_key = f"xwalk:{cui}:{','.join(sorted(sources))}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        data = self._get(
            f"/content/current/CUI/{cui}/atoms",
            params={"sabs": ",".join(sources)},
        )
        if not data:
            return {}
        atoms = data.get("result") or []
        if not isinstance(atoms, list):
            return {}
        xwalks: dict[str, list[str]] = {}
        for atom in atoms:
            if not isinstance(atom, dict):
                continue
            sab = atom.get("rootSource", "")
            code = atom.get("code", "")
            if "/" in code:
                code = code.rsplit("/", 1)[-1]
            if not sab or not code:
                continue
            xwalks.setdefault(sab, []).append(code)
        deduped = {sab: sorted(set(codes)) for sab, codes in xwalks.items()}
        self.cache.set(cache_key, deduped)
        return deduped

    def search_with_cross_walks(
        self,
        query: str,
        top_k: int = 1,
        sources: Optional[list[str]] = None,
    ) -> list[dict]:
        """검색 + 상위 결과 cross-walk 합본 (RAG context 합류용)."""
        results = self.search(query, top_k=top_k)
        enriched = []
        for r in results:
            cui = r.get("cui", "")
            entry = dict(r)
            if cui:
                concept = self.get_concept(cui)
                if concept:
                    entry["semantic_types"] = concept.get("semantic_types", [])
                entry["cross_walks"] = self.get_cross_walks(cui, sources=sources)
            enriched.append(entry)
        return enriched
