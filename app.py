"""
SNOMED VET RAG — Streamlit 데모 UI

[실행]
    streamlit run app.py

[환경변수]
    ANTHROPIC_API_KEY: Claude API 사용 시 (선택)
"""

import streamlit as st
import time
import sys
from pathlib import Path

# 프로젝트 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.retrieval.rag_pipeline import (
    SNOMEDRagPipeline,
    _contains_korean,
    translate_query_to_english,
    _load_vet_dictionary,
)


# ─── 페이지 설정 ──────────────────────────────────────

st.set_page_config(
    page_title="SNOMED VET RAG",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── 사이드바 ──────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ 설정")

    llm_backend = st.selectbox(
        "LLM 백엔드",
        options=["ollama", "none", "claude"],
        index=0,
        help="ollama: 로컬 무료 / claude: API 유료 / none: 검색만",
    )

    ollama_model = "gemma2:9b"
    claude_model = "claude-sonnet-4-20250514"

    if llm_backend == "ollama":
        ollama_model = st.text_input(
            "Ollama 모델명",
            value="gemma2:9b",
            help="ollama list로 설치된 모델 확인",
        )
    elif llm_backend == "claude":
        claude_model = st.text_input(
            "Claude 모델명",
            value="claude-sonnet-4-20250514",
        )

    top_k = st.slider("검색 결과 수 (Top-K)", 3, 20, 10)

    st.divider()

    st.subheader("📊 시스템 정보")
    st.markdown("""
    | 항목 | 값 |
    |------|-----|
    | Concepts | 414,860 |
    | Vectors | 366,570 |
    | Relationships | 1,379,816 |
    | 번역 사전 | 160+ terms |
    """)

    st.divider()

    st.subheader("💡 예시 질문")
    example_queries = [
        "고양이 범백혈구감소증의 SNOMED 코드는?",
        "개의 팔꿈치 이형성증 진단 코드를 알려줘",
        "말의 제엽염 진단 코드와 관련 해부학적 부위는?",
        "소의 바이러스성 설사 관련 SNOMED 개념을 찾아줘",
        "개 파보바이러스 백신 관련 SNOMED 코드를 검색해줘",
    ]
    for q in example_queries:
        if st.button(q, key=f"ex_{q[:10]}", use_container_width=True):
            st.session_state["input_query"] = q


# ─── 파이프라인 초기화 (캐싱) ──────────────────────────

@st.cache_resource
def load_pipeline(backend: str, o_model: str, c_model: str):
    """RAG 파이프라인을 초기화한다 (Streamlit 캐싱)."""
    return SNOMEDRagPipeline(
        llm_backend=backend,
        ollama_model=o_model,
        claude_model=c_model,
    )


# ─── 메인 UI ──────────────────────────────────────────

st.title("🩺 SNOMED VET RAG")
st.caption("수의학 SNOMED CT 온톨로지 기반 하이브리드 RAG 시스템")

# 파이프라인 로드
try:
    pipeline = load_pipeline(llm_backend, ollama_model, claude_model)
except Exception as e:
    st.error(f"파이프라인 초기화 실패: {e}")
    st.stop()

# 입력 영역
query = st.text_input(
    "질문을 입력하세요 (한국어/영어)",
    value=st.session_state.get("input_query", ""),
    placeholder="예: 고양이 범백혈구감소증의 SNOMED 코드는?",
    key="query_input",
)

col_search, col_clear = st.columns([1, 5])
with col_search:
    search_clicked = st.button("🔍 검색", type="primary", use_container_width=True)
with col_clear:
    if st.button("초기화"):
        st.session_state["input_query"] = ""
        st.rerun()

# 검색 실행
if search_clicked and query.strip():
    with st.spinner("검색 중..."):
        start_time = time.time()
        result = pipeline.query(query.strip(), top_k=top_k)
        elapsed = time.time() - start_time

    # ── 번역 정보 ──
    if result.get("translated_query"):
        st.info(f"🔄 **번역:** {query} → {result['translated_query']}")

    # ── LLM 답변 ──
    st.subheader("💬 답변")
    st.markdown(result["answer"])
    st.caption(f"LLM: {llm_backend} ({ollama_model if llm_backend == 'ollama' else claude_model if llm_backend == 'claude' else '-'}) · 소요시간: {elapsed:.1f}초")

    # ── 검색 결과 상세 ──
    st.subheader(f"🔎 검색 결과 ({len(result['search_results'])}건)")

    for i, r in enumerate(result["search_results"][:7], 1):
        with st.expander(f"[{i}] {r.preferred_term} — {r.semantic_tag}", expanded=(i <= 3)):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Concept ID:** `{r.concept_id}`")
                st.markdown(f"**FSN:** {r.fsn}")
                st.markdown(f"**Source:** {r.source}")
            with col2:
                st.markdown(f"**Score:** {r.score:.6f}")
                if r.vector_rank:
                    st.markdown(f"**Vector Rank:** #{r.vector_rank}")
                if r.sql_rank:
                    st.markdown(f"**SQL Rank:** #{r.sql_rank}")

            # 관계 정보
            if r.relationships:
                st.markdown("**관계:**")
                for rel in r.relationships[:5]:
                    direction = "→" if rel["source_id"] == r.concept_id else "←"
                    other_term = rel["destination_term"] if direction == "→" else rel["source_term"]
                    st.markdown(f"- {direction} **[{rel['type_term']}]** {other_term}")

    # ── 컨텍스트 (접기) ──
    with st.expander("📄 RAG 컨텍스트 (LLM에 전달된 원문)", expanded=False):
        st.code(result["context"], language="text")

elif search_clicked:
    st.warning("질문을 입력해주세요.")


# ─── 하단 정보 ──────────────────────────────────────────

st.divider()
st.caption(
    "SNOMED VET RAG · "
    "Hybrid Search (Vector + SQL + RRF) · "
    "한국어→영어 번역 레이어 (사전 + LLM) · "
    "SNOMED CT INT + VET Extension"
)
