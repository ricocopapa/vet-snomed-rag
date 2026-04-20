"""
SNOMED VET RAG 파이프라인: 하이브리드 검색 + LLM 생성.

[흐름]
사용자 질문 (한국어/영어)
    → 한국어 질의 시 영어 번역 (Ollama 번역 레이어)
    → 하이브리드 검색 (Vector + SQL, 영어 쿼리)
    → [Step 0.7] SNOMED 쿼리 리포매팅 (--reformulator-backend 옵션으로 활성화)
    → 컨텍스트 조립 (검색 결과 + 관계 정보 + Post-coordination 패턴)
    → LLM 생성 (Claude API 또는 Ollama, 원본 한국어로 답변)
    → 구조화된 응답

[실행]
    python src/retrieval/rag_pipeline.py --query "고양이 범백혈구감소증 SNOMED 코드"
    python src/retrieval/rag_pipeline.py --interactive
    python src/retrieval/rag_pipeline.py --interactive --llm ollama
    python src/retrieval/rag_pipeline.py --interactive --llm ollama --ollama-model qwen2.5:7b
    python src/retrieval/rag_pipeline.py --interactive --llm claude --claude-model claude-sonnet-4-20250514
    python src/retrieval/rag_pipeline.py --query "feline diabetes" --reformulator-backend gemini --llm none

[환경변수]
    ANTHROPIC_API_KEY: Claude API 사용 시 필요
    GOOGLE_API_KEY: Gemini 리포매터 사용 시 필요 (--reformulator-backend gemini)
"""

import json
import re
import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Optional

# 프로젝트 내부 모듈
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.retrieval.hybrid_search import HybridSearchEngine, SearchResult
from src.retrieval.graph_rag import SNOMEDGraph, format_graph_context

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


# ─── Post-Coordination 패턴 로더 ────────────────────────

class PostCoordLoader:
    """Post-coordination 표현식 패턴을 로드한다."""

    def __init__(self):
        self.rules = {}
        self.mappings = {}
        self._load_rules()

    def _load_rules(self):
        """JSON 파일에서 Post-coordination 규칙을 로드."""
        rules_path = DATA_DIR / "snomed_post_coord_rules.json"
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                self.rules = json.load(f)
            print(f"[PostCoord] 규칙 로드: {len(self.rules)} entries")

        # Assessment 매핑
        assess_path = DATA_DIR / "assessment_snomed_mapping.json"
        if assess_path.exists():
            with open(assess_path, "r", encoding="utf-8") as f:
                self.mappings["assessment"] = json.load(f)
            print(f"[PostCoord] Assessment 매핑 로드")

        # Plan 매핑
        plan_path = DATA_DIR / "plan_snomed_mapping.json"
        if plan_path.exists():
            with open(plan_path, "r", encoding="utf-8") as f:
                self.mappings["plan"] = json.load(f)
            print(f"[PostCoord] Plan 매핑 로드")

    def find_patterns(self, concept_id: str) -> list[dict]:
        """특정 concept_id와 관련된 Post-coordination 패턴을 검색."""
        patterns = []
        if isinstance(self.rules, list):
            for rule in self.rules:
                if concept_id in json.dumps(rule):
                    patterns.append(rule)
        elif isinstance(self.rules, dict):
            for key, val in self.rules.items():
                if concept_id in str(val):
                    patterns.append({"key": key, "rule": val})
        return patterns[:5]  # 상위 5개만


# ─── 컨텍스트 빌더 ──────────────────────────────────────

def build_context(
    query: str,
    results: list[SearchResult],
    post_coord: Optional[PostCoordLoader] = None,
) -> str:
    """검색 결과를 LLM 프롬프트용 컨텍스트로 조립한다."""

    context_parts = []
    context_parts.append("=== SNOMED CT VET 검색 결과 ===\n")

    for i, r in enumerate(results[:7], 1):
        part = f"[{i}] {r.preferred_term}\n"
        part += f"    concept_id: {r.concept_id}\n"
        part += f"    FSN: {r.fsn}\n"
        part += f"    semantic_tag: {r.semantic_tag}\n"
        part += f"    source: {r.source} (INT=국제표준 / VET=수의학확장 / LOCAL=로컬)\n"
        part += f"    검색 점수: {r.score:.6f}"

        if r.vector_rank:
            part += f" | 의미검색 #{r.vector_rank}"
        if r.sql_rank:
            part += f" | 정확검색 #{r.sql_rank}"
        part += "\n"

        # 관계 정보
        if r.relationships:
            part += f"    관계:\n"
            for rel in r.relationships[:5]:
                direction = "→" if rel["source_id"] == r.concept_id else "←"
                other_term = rel["destination_term"] if direction == "→" else rel["source_term"]
                part += f"      {direction} [{rel['type_term']}] {other_term}\n"

        # Post-coordination 패턴
        if post_coord:
            patterns = post_coord.find_patterns(r.concept_id)
            if patterns:
                part += f"    Post-coordination 패턴:\n"
                for p in patterns[:2]:
                    part += f"      {json.dumps(p, ensure_ascii=False)[:200]}\n"

        context_parts.append(part)

    return "\n".join(context_parts)


# ─── 한국어→영어 번역 레이어 ──────────────────────────────

_VET_DICT_CACHE: Optional[dict] = None


def _load_vet_dictionary() -> dict:
    """수의학 한국어→영어 용어 사전을 로드한다 (캐싱)."""
    global _VET_DICT_CACHE
    if _VET_DICT_CACHE is not None:
        return _VET_DICT_CACHE

    dict_path = DATA_DIR / "vet_term_dictionary_ko_en.json"
    flat_dict = {}
    if dict_path.exists():
        with open(dict_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for category, terms in raw.items():
            if category.startswith("_"):
                continue
            if isinstance(terms, dict):
                for ko, en in terms.items():
                    flat_dict[ko] = en
        # 긴 용어부터 치환하도록 길이 역순 정렬
        _VET_DICT_CACHE = dict(sorted(flat_dict.items(), key=lambda x: len(x[0]), reverse=True))
        print(f"[번역사전] {len(_VET_DICT_CACHE)}개 용어 로드 완료")
    else:
        _VET_DICT_CACHE = {}
    return _VET_DICT_CACHE


def _replace_with_dictionary(query: str) -> str:
    """사전 기반으로 한국어 용어를 영어로 치환한다."""
    vet_dict = _load_vet_dictionary()
    result = query
    for ko, en in vet_dict.items():
        if ko in result:
            result = result.replace(ko, en)
    return result


def _contains_korean(text: str) -> bool:
    """문자열에 한국어가 포함되어 있는지 판별한다."""
    return bool(re.search(r'[가-힣]', text))


# 검색 쿼리 메타 불용어: 의미 없는 상위 개념어 (embedding 오염·SQL 매칭 실패 원인)
# - SNOMED 메타 용어 + 일반 영어 관사/전치사/be동사/접속사 + 한국어 메타어
_QUERY_META_STOPWORDS = {
    "snomed", "sct", "snomed-ct", "code", "codes", "concept", "concepts",
    "id", "ids", "ct", "coding",
    "the", "a", "an", "of", "for", "to", "is", "and", "or",
    "in", "on", "at", "by", "with", "from", "as", "be", "are", "was", "were",
    "코드", "개념",
}


def preprocess_query(query: str) -> str:
    """검색 쿼리에서 메타 불용어를 제거한다.

    "feline panleukopenia SNOMED code" → "feline panleukopenia"
    이유: "SNOMED"/"code" 토큰이 embedding을 메타 방향으로 끌어당겨
    임상 개념 벡터 매칭을 방해하고, SQL LIKE에서도 0건을 유발한다.
    모든 토큰이 불용어이거나 결과가 공문자열이면 원본을 반환한다.
    """
    tokens = re.split(r'\s+', query.strip())
    content = [t for t in tokens if t and t.lower() not in _QUERY_META_STOPWORDS]
    cleaned = " ".join(content).strip()
    return cleaned if cleaned else query


def translate_query_to_english(query: str, model: str = "qwen2.5:14b") -> str:
    """한국어 질의를 영어 검색 쿼리로 번역한다.

    [수정 사유: 사전 치환 → LLM 번역 2단계 파이프라인으로 변경.
     수의학 전문 용어 오역 방지를 위해 사전 치환을 선행.]

    단계:
        1. 수의학 용어 사전으로 핵심 용어를 먼저 영어로 치환
        2. 한국어가 남아 있으면 Ollama LLM으로 나머지 번역
        3. 영어만 남으면 그대로 반환

    영어 질의는 번역 없이 그대로 반환한다.
    Ollama 미실행 등 오류 발생 시 사전 치환 결과를 반환한다.
    """
    if not _contains_korean(query):
        return query

    # Step 1: 사전 기반 치환
    dict_replaced = _replace_with_dictionary(query)

    # 사전 치환만으로 한국어가 모두 제거되었으면 바로 반환
    if not _contains_korean(dict_replaced):
        return dict_replaced

    # Step 2: 잔여 한국어가 있으면 Ollama LLM으로 번역
    try:
        import requests
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": (
                    "Translate the following veterinary/medical query into English. "
                    "Some terms are already in English — keep them as-is. "
                    "Return ONLY the English translation, nothing else. "
                    "Use standard SNOMED CT / veterinary medical terminology.\n\n"
                    f"Query: {dict_replaced}\n"
                    "English:"
                ),
                "stream": False,
            },
            timeout=30,
        )
        if response.status_code == 200:
            translated = response.json().get("response", "").strip()
            if translated and not _contains_korean(translated):
                return translated
    except Exception:
        pass

    # LLM 번역 실패 시 사전 치환 결과라도 반환
    return dict_replaced


# ─── LLM 생성기 ─────────────────────────────────────────

SYSTEM_PROMPT = """당신은 수의학 SNOMED CT 전문가입니다.
사용자의 질문에 대해 검색된 SNOMED CT 개념 정보를 기반으로 정확하게 답변합니다.

응답 규칙:
1. 검색 결과에 있는 concept_id와 FSN을 정확히 인용한다.
2. 검색 결과에 없는 정보를 만들어내지 않는다.
3. INT(국제표준), VET(수의학확장), LOCAL(로컬) 소스를 구분하여 표기한다.
4. 관련 관계(is-a, finding_site 등)가 있으면 함께 설명한다.
5. Post-coordination이 필요한 경우 SCG 문법으로 표현식을 제시한다.
6. 한국어로 답변한다.
"""


def generate_with_claude(query: str, context: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Claude API로 답변을 생성한다."""
    try:
        import anthropic
        client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수 필요

        message = client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"질문: {query}\n\n{context}\n\n위 검색 결과를 기반으로 질문에 답변해주세요."
            }],
        )
        return message.content[0].text
    except ImportError:
        return "[ERROR] anthropic 패키지가 설치되지 않았습니다. pip install anthropic"
    except Exception as e:
        return f"[ERROR] Claude API 호출 실패: {e}"


OLLAMA_PROMPT_TEMPLATE = """You are a veterinary SNOMED CT expert. Answer the question based ONLY on the search results below.
Write your answer in Korean (한국어). Do NOT use Chinese. SNOMED terms (concept_id, FSN, preferred_term) should remain in English.

=== Search Results ===
{context}

=== Rules ===
1. Cite concept_id, FSN, preferred_term from the search results.
2. Do NOT fabricate information not in the search results.
3. Label sources: INT(international), VET(veterinary extension), LOCAL(local).
4. Explain relationships (is-a, finding_site, etc.) if present.
5. Write the explanation in Korean. Do NOT switch to Chinese.

Question: {query}

Answer in Korean:"""


def _clean_ollama_response(text: str) -> str:
    """Ollama 응답에서 특수 토큰, 메타 코멘트, 중국어 혼입, 반복 패턴을 제거한다."""
    # 특수 토큰이 반복되는 지점 이후를 잘라냄 (유효 답변만 보존)
    repeat_match = re.search(r'(<\|[a-z_]+\|>)\s*\1', text)
    if repeat_match:
        text = text[:repeat_match.start()]
    # 개별 특수 토큰 제거
    text = re.sub(r'<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>', '', text)
    text = re.sub(r'<\|[a-z_]+\|>', '', text)
    # 모델의 자기 수정 메타 코멘트 제거 (예: "Oh, it seems...", "Let me correct...")
    text = re.sub(
        r'(Oh,?\s*(it seems|I\'ve|I have|let me)|Let me correct|Let me provide|'
        r'I apologize|Sorry,? (let me|I)|Wait,?\s*(let me|I))[^\n]*\.?',
        '', text, flags=re.IGNORECASE
    )
    # 이모지 제거
    text = re.sub(r'[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f900-\U0001f9ff]', '', text)
    # 중국어 문장 제거 (한국어·영어·숫자·기호만 보존)
    cleaned_lines = []
    for line in text.split('\n'):
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', line))
        korean_chars = len(re.findall(r'[가-힣]', line))
        english_chars = len(re.findall(r'[a-zA-Z]', line))
        total_meaningful = chinese_chars + korean_chars + english_chars
        if total_meaningful > 0 and chinese_chars / total_meaningful > 0.5:
            continue  # 중국어가 과반인 라인 스킵
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    # 연속 공백/줄바꿈 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def generate_with_ollama(query: str, context: str, model: str = "llama3.2") -> str:
    """Ollama 로컬 LLM으로 답변을 생성한다."""
    try:
        import requests
        prompt = OLLAMA_PROMPT_TEMPLATE.format(context=context, query=query)
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 1024,
                    "repeat_penalty": 1.3,
                    "temperature": 0.3,
                },
            },
            timeout=120,
        )
        if response.status_code == 200:
            raw = response.json().get("response", "[빈 응답]")
            return _clean_ollama_response(raw)
        return f"[ERROR] Ollama 응답 코드: {response.status_code}"
    except ImportError:
        return "[ERROR] requests 패키지가 필요합니다. pip install requests"
    except Exception as e:
        return f"[ERROR] Ollama 호출 실패: {e}\n  → Ollama가 실행 중인지 확인: ollama serve"


def generate_without_llm(query: str, context: str, results: list[SearchResult]) -> str:
    """LLM 없이 검색 결과만 구조화하여 반환 (fallback)."""
    output = [f"[검색 결과] \"{query}\"\n"]

    for i, r in enumerate(results[:5], 1):
        output.append(f"{i}. {r.preferred_term}")
        output.append(f"   - concept_id: {r.concept_id}")
        output.append(f"   - FSN: {r.fsn}")
        output.append(f"   - 카테고리: {r.semantic_tag}")
        output.append(f"   - 소스: {r.source}")
        if r.relationships:
            for rel in r.relationships[:3]:
                direction = "→" if rel["source_id"] == r.concept_id else "←"
                other = rel["destination_term"] if direction == "→" else rel["source_term"]
                output.append(f"   - {rel['type_term']}: {other}")
        output.append("")

    return "\n".join(output)


# ─── RAG 파이프라인 ──────────────────────────────────────

class SNOMEDRagPipeline:
    """SNOMED VET RAG 전체 파이프라인."""

    def __init__(
        self,
        llm_backend: str = "none",
        ollama_model: str = "llama3.2",
        claude_model: str = "claude-sonnet-4-20250514",
        reformulator_backend: str = "none",
    ):
        """
        Args:
            llm_backend: "claude" / "ollama" / "none"
            ollama_model: Ollama 모델명 (기본: llama3.2)
            claude_model: Claude 모델명 (기본: claude-sonnet-4-20250514)
            reformulator_backend: "none" / "gemini" / "claude" (Step 0.7 쿼리 리포매터)
        """
        print("=" * 60)
        print(" SNOMED VET RAG Pipeline 초기화")
        print(f" LLM Backend: {llm_backend}")
        if llm_backend == "ollama":
            print(f" Ollama Model: {ollama_model}")
        elif llm_backend == "claude":
            print(f" Claude Model: {claude_model}")
        print(f" Reformulator Backend: {reformulator_backend}")
        print("=" * 60)

        self.engine = HybridSearchEngine()
        self.post_coord = PostCoordLoader()
        self.snomed_graph = SNOMEDGraph()
        self.llm_backend = llm_backend
        self.ollama_model = ollama_model
        self.claude_model = claude_model
        self.reformulator_backend = reformulator_backend

        # Step 0.7 리포매터 초기화
        self.reformulator = None
        if reformulator_backend != "none":
            from src.retrieval.query_reformulator import get_reformulator
            self.reformulator = get_reformulator(reformulator_backend)
            print(f"[Reformulator] {reformulator_backend} 백엔드 초기화 완료")

    def query(self, question: str, top_k: int = 10) -> dict:
        """RAG 질의를 실행한다.

        Returns:
            {
                "question": str,
                "translated_query": str | None,
                "reformulation": dict | None,
                "search_results": list[SearchResult],
                "context": str,
                "answer": str,
            }
        """
        # Step 0: 한국어 질의 → 영어 번역 (DB가 영어 전용이므로)
        translated_query = None
        search_query = question
        if _contains_korean(question) and self.llm_backend == "ollama":
            translated_query = translate_query_to_english(question, model=self.ollama_model)
            if translated_query != question:
                search_query = translated_query
                print(f"  [번역] {question} → {translated_query}")

        # Step 0.5: 메타 불용어 제거 (SNOMED/code 등 검색 방해 토큰)
        english_query = preprocess_query(search_query)
        if english_query != search_query:
            print(f"  [전처리] '{search_query}' → '{english_query}'")

        # Step 0.7: SNOMED 쿼리 리포매팅 (reformulator_backend != "none" 시 활성화)
        # 한국어 번역+불용어제거 후 영어 쿼리에 대해 리포매팅 적용
        reformulation_info = None
        final_search_query = english_query
        if self.reformulator is not None:
            reformulation = self.reformulator.reformulate(english_query)
            if reformulation.confidence >= 0.5:
                final_search_query = reformulation.reformulated
            reformulation_info = asdict(reformulation)
            print(
                f"  [Reformulate-{self.reformulator_backend}] "
                f"{english_query} → {final_search_query} "
                f"(conf={reformulation.confidence:.2f})"
            )

        # Step 1: 하이브리드 검색 (리포매팅된 쿼리 사용)
        results = self.engine.search(final_search_query, top_k=top_k)

        # Step 2: 컨텍스트 조립 (기존 검색 결과)
        context = build_context(question, results, self.post_coord)

        # Step 2.5: GraphRAG 컨텍스트 확장 (상위 3개 결과에 대해 그래프 탐색)
        graph_contexts = []
        for r in results[:3]:
            try:
                gctx = self.snomed_graph.explore(
                    r.concept_id,
                    hierarchy_depth=3,
                    clinical_hops=2,
                    max_clinical_neighbors=10,
                    max_children=3,
                )
                graph_contexts.append(gctx)
            except Exception:
                pass

        graph_context_text = format_graph_context(graph_contexts, max_per_concept=3)
        if graph_context_text:
            context = context + "\n" + graph_context_text

        # Step 3: LLM 생성 (원본 한국어 질문으로 답변 생성)
        if self.llm_backend == "claude":
            answer = generate_with_claude(question, context, model=self.claude_model)
        elif self.llm_backend == "ollama":
            answer = generate_with_ollama(question, context, model=self.ollama_model)
        else:
            answer = generate_without_llm(question, context, results)

        return {
            "question": question,
            "translated_query": translated_query,
            "reformulation": reformulation_info,
            "search_results": results,
            "context": context,
            "answer": answer,
        }

    def print_answer(self, result: dict):
        """RAG 결과를 포맷팅하여 출력."""
        print(f"\n{'═' * 60}")
        print(f"  Q: {result['question']}")
        if result.get("translated_query"):
            print(f"  → Search Query: {result['translated_query']}")
        print(f"{'═' * 60}")
        print(f"\n{result['answer']}")
        print(f"\n{'─' * 60}")
        print(f"  검색된 개념: {len(result['search_results'])}건")
        print(f"  GraphRAG: 상위 3개 개념 × 2-hop 탐색 적용")
        if self.llm_backend == "ollama":
            print(f"  LLM: {self.llm_backend} ({self.ollama_model})")
        elif self.llm_backend == "claude":
            print(f"  LLM: {self.llm_backend} ({self.claude_model})")
        else:
            print(f"  LLM: {self.llm_backend}")
        print(f"{'─' * 60}")

    def close(self):
        self.engine.close()


# ─── CLI ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SNOMED VET RAG 파이프라인")
    parser.add_argument("--query", "-q", type=str, help="질의")
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--llm", type=str, default="none",
                        choices=["claude", "ollama", "none"],
                        help="LLM 백엔드 (기본: none)")
    parser.add_argument("--ollama-model", type=str, default="llama3.2",
                        help="Ollama 모델명 (기본: llama3.2)")
    parser.add_argument("--claude-model", type=str, default="claude-sonnet-4-20250514",
                        help="Claude 모델명 (기본: claude-sonnet-4-20250514)")
    parser.add_argument("--top-k", "-k", type=int, default=10)
    parser.add_argument("--reformulator-backend", type=str, default="none",
                        choices=["none", "gemini", "claude"],
                        help="쿼리 리포매터 백엔드 (기본: none). gemini=Gemini 2.5 Flash, claude=Claude Sonnet 4.6")
    args = parser.parse_args()

    pipeline = SNOMEDRagPipeline(
        llm_backend=args.llm,
        ollama_model=args.ollama_model,
        claude_model=args.claude_model,
        reformulator_backend=args.reformulator_backend,
    )

    if args.interactive:
        print("\n[인터랙티브 모드] 'q' 입력 시 종료\n")
        while True:
            question = input("\n질문> ").strip()
            if question.lower() in ("q", "quit", "exit"):
                break
            if not question:
                continue
            result = pipeline.query(question, top_k=args.top_k)
            pipeline.print_answer(result)

    elif args.query:
        result = pipeline.query(args.query, top_k=args.top_k)
        pipeline.print_answer(result)

    else:
        # 데모 질의
        demos = [
            "고양이 범백혈구감소증의 SNOMED 코드는?",
            "개의 팔꿈치 이형성증 진단과 관련 처치 코드를 알려줘",
            "소의 바이러스성 설사 관련 SNOMED 개념을 찾아줘",
        ]
        for q in demos:
            result = pipeline.query(q, top_k=5)
            pipeline.print_answer(result)

    pipeline.close()


if __name__ == "__main__":
    main()
