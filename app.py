"""
SNOMED VET RAG — Streamlit 데모 UI (v2.0)

[실행]
    streamlit run app.py

[환경변수]
    ANTHROPIC_API_KEY: Claude API 사용 시 (선택)

[탭 구조]
    탭 1 — Search:            SNOMED VET 하이브리드 검색 (v1.0 기능 유지)
    탭 2 — Clinical Encoding: 텍스트/음성 → SOAP + SNOMED JSONL 인코딩 (v2.0 신규)
"""

import json
import os
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
    page_title="SNOMED VET RAG v2.0",
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

st.title("🩺 SNOMED VET RAG v2.0")
st.caption("수의학 SNOMED CT 온톨로지 기반 하이브리드 RAG 시스템 + E2E 임상 인코딩")

# ─── 탭 구성 ─────────────────────────────────────────────
tab_search, tab_encoding = st.tabs(["🔍 Search", "🏥 Clinical Encoding"])


# ══════════════════════════════════════════════════════════
# 탭 1: Search (v1.0 기능 완전 보존)
# ══════════════════════════════════════════════════════════
with tab_search:

    # 파이프라인 로드
    try:
        pipeline = load_pipeline(llm_backend, ollama_model, claude_model)
    except Exception as e:
        st.error(f"파이프라인 초기화 실패: {e}")
        pipeline = None

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
    if search_clicked and query.strip() and pipeline is not None:
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

    elif search_clicked and not query.strip():
        st.warning("질문을 입력해주세요.")
    elif search_clicked and pipeline is None:
        st.error("파이프라인 초기화 실패 — 사이드바 설정을 확인하세요.")


# ══════════════════════════════════════════════════════════
# 탭 2: Clinical Encoding (v2.0 신규)
# ══════════════════════════════════════════════════════════
with tab_encoding:

    st.subheader("🏥 Clinical Encoding")
    st.caption(
        "텍스트 또는 음성 파일 → STT → SOAP 구조화 → SNOMED 자동 태깅 → JSONL 다운로드\n"
        "기본 설정: reformulator=gemini, rerank=False (M2 최적)"
    )

    # ── ClinicalEncoder 초기화 (캐싱) ─────────────────────────────────

    @st.cache_resource
    def load_clinical_encoder(dry_run: bool, reformulator: str, enable_rerank: bool):
        """ClinicalEncoder 초기화 (Streamlit 캐싱)."""
        from src.pipeline.e2e import ClinicalEncoder, ClinicalEncoderConfig
        config = ClinicalEncoderConfig(
            dry_run=dry_run,
            reformulator_backend=reformulator,
            enable_rerank=enable_rerank,
        )
        return ClinicalEncoder(config=config)

    # ── 입력 모드 선택 ─────────────────────────────────────────────────
    enc_col1, enc_col2 = st.columns([1, 1])
    with enc_col1:
        input_mode = st.radio(
            "입력 방식",
            options=[
                "텍스트 입력",
                "오디오 파일 업로드",
                "PDF 업로드 (v2.2)",
                "이미지 업로드 (v2.2 Vision)",
            ],
            index=0,
            horizontal=True,
        )
    with enc_col2:
        enc_dry_run = st.checkbox(
            "dry-run (API 미호출, mock 응답)",
            value=not bool(os.environ.get("ANTHROPIC_API_KEY")),
            help="ANTHROPIC_API_KEY 미설정 시 자동 체크",
        )

    # ── 입력 영역 ──────────────────────────────────────────────────────
    enc_text_input = ""
    enc_audio_path = None

    if input_mode == "텍스트 입력":
        enc_text_input = st.text_area(
            "임상 텍스트 입력",
            value="안압이 오른쪽 28, 왼쪽 14로 측정됐습니다. 우안 고안압으로 판단되어 녹내장 약물 시작합니다.",
            height=120,
            placeholder="수의사 발화 텍스트를 입력하세요...",
            key="enc_text",
        )
    elif input_mode == "오디오 파일 업로드":
        uploaded_file = st.file_uploader(
            "오디오 파일 업로드 (m4a / wav / mp3 / mp4)",
            type=["m4a", "wav", "mp3", "mp4"],
            key="enc_audio",
        )
        if uploaded_file is not None:
            import tempfile
            suffix = Path(uploaded_file.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.read())
                enc_audio_path = tmp.name
            st.success(f"업로드 완료: {uploaded_file.name}")
    elif input_mode == "PDF 업로드 (v2.2)":
        # v2.2 Stage 1+2 — 텍스트 레이어 PDF + OCR fallback
        uploaded_pdf = st.file_uploader(
            "진료 기록 PDF 업로드 (텍스트 레이어 또는 스캔 자동 감지)",
            type=["pdf"],
            key="enc_pdf",
            help="v2.2 Stage 1+2: text_layer 우선, 없으면 tesseract OCR(kor+eng) fallback.",
        )
        if uploaded_pdf is not None:
            import tempfile
            from src.pipeline.pdf_reader import read_pdf
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_pdf.read())
                pdf_tmp_path = tmp.name
            try:
                with st.spinner("PDF 분석 중... (text_layer 우선, 필요시 OCR)"):
                    pdf_info = read_pdf(pdf_tmp_path, enable_ocr=True)
                enc_text_input = pdf_info["text"]
                st.success(
                    f"PDF 파싱 완료: {uploaded_pdf.name} "
                    f"(pages={pdf_info['pages']}, chars={len(enc_text_input)}, "
                    f"source={pdf_info['source']})"
                )
                with st.expander("📄 추출된 텍스트 미리보기", expanded=False):
                    st.code(enc_text_input, language="text")
            except Exception as e:
                st.error(f"PDF 파싱 실패: {e}")

    else:
        # v2.2 Stage 3 — 이미지 업로드 (Gemini Vision)
        uploaded_image = st.file_uploader(
            "진료 기록 이미지 업로드 (jpg / png / jpeg / webp)",
            type=["jpg", "jpeg", "png", "webp"],
            key="enc_image",
            help="v2.2 Stage 3: Gemini 2.5 Flash Vision 으로 이미지 → 진료 텍스트 추출.",
        )
        if uploaded_image is not None:
            import tempfile
            from src.pipeline.vision_reader import read_image
            suffix = Path(uploaded_image.name).suffix or ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_image.read())
                img_tmp_path = tmp.name
            st.image(img_tmp_path, caption=uploaded_image.name, width=300)
            try:
                with st.spinner("Gemini Vision 으로 이미지 분석 중..."):
                    vision_info = read_image(img_tmp_path, dry_run=enc_dry_run)
                enc_text_input = vision_info["text"]
                st.success(
                    f"Vision 추출 완료: {uploaded_image.name} "
                    f"(chars={len(enc_text_input)}, model={vision_info['model']}, "
                    f"latency={vision_info['latency_ms']}ms, "
                    f"cost=${vision_info['cost_usd']:.6f})"
                )
                with st.expander("🖼️ Vision 추출 텍스트 미리보기", expanded=False):
                    st.code(enc_text_input, language="text")
            except Exception as e:
                st.error(f"Vision 추출 실패: {e}")

    # ── Encode 버튼 ────────────────────────────────────────────────────
    encode_clicked = st.button("⚡ Encode", type="primary", use_container_width=False)

    if encode_clicked:
        # 입력 유효성 확인
        if input_mode == "텍스트 입력" and not enc_text_input.strip():
            st.warning("텍스트를 입력해주세요.")
        elif input_mode == "오디오 파일 업로드" and enc_audio_path is None:
            st.warning("오디오 파일을 업로드해주세요.")
        elif input_mode == "PDF 업로드 (v2.2)" and not enc_text_input.strip():
            st.warning("PDF 를 업로드해주세요. (텍스트 레이어 또는 스캔 자동 감지)")
        elif input_mode == "이미지 업로드 (v2.2 Vision)" and not enc_text_input.strip():
            st.warning("이미지를 업로드해주세요.")
        else:
            # ClinicalEncoder 로드
            try:
                encoder = load_clinical_encoder(
                    dry_run=enc_dry_run,
                    reformulator="gemini",
                    enable_rerank=False,
                )
            except Exception as e:
                st.error(f"ClinicalEncoder 초기화 실패: {e}")
                encoder = None

            if encoder is not None:
                with st.spinner("임상 데이터 인코딩 중... (SOAP 추출 + SNOMED 태깅)"):
                    enc_start = time.time()
                    try:
                        if input_mode == "오디오 파일 업로드":
                            record = encoder.encode(enc_audio_path, input_type="audio")
                        else:
                            # 텍스트 입력 또는 PDF 업로드 (v2.2) — 모두 텍스트 경로
                            record = encoder.encode(enc_text_input.strip(), input_type="text")
                        enc_elapsed = time.time() - enc_start
                        st.success(f"인코딩 완료 — {enc_elapsed:.1f}초 소요")
                    except Exception as e:
                        st.error(f"인코딩 실패: {e}")
                        record = None

                if record is not None:
                    # ── 결과 표시 ──────────────────────────────────────

                    # 에러 알림
                    if record.get("errors"):
                        st.warning("⚠️ 일부 단계 오류 발생:")
                        for err in record["errors"]:
                            st.markdown(f"- `{err}`")

                    # encounter_id / timestamp
                    meta_col1, meta_col2 = st.columns(2)
                    with meta_col1:
                        st.markdown(f"**encounter_id:** `{record.get('encounter_id')}`")
                    with meta_col2:
                        st.markdown(f"**timestamp:** `{record.get('timestamp')}`")

                    # latency 분해
                    latency = record.get("latency_ms", {})
                    st.markdown(
                        f"**Latency:** STT={latency.get('stt', 0):.0f}ms · "
                        f"SOAP={latency.get('soap', 0):.0f}ms · "
                        f"SNOMED={latency.get('snomed', 0):.0f}ms · "
                        f"**Total={latency.get('total', 0):.0f}ms**"
                    )

                    # SOAP 구조
                    st.subheader("📋 SOAP 구조")
                    soap = record.get("soap", {})
                    soap_col1, soap_col2 = st.columns(2)
                    with soap_col1:
                        st.markdown(f"**S (Subjective):** {soap.get('subjective') or '—'}")
                        st.markdown(f"**O (Objective):** {soap.get('objective') or '—'}")
                    with soap_col2:
                        st.markdown(f"**A (Assessment):** {soap.get('assessment') or '—'}")
                        st.markdown(f"**P (Plan):** {soap.get('plan') or '—'}")

                    # 도메인 + 필드
                    domains = record.get("domains", [])
                    fields = record.get("fields", [])
                    st.markdown(f"**탐지 도메인:** {', '.join(domains) if domains else '—'}")
                    st.markdown(f"**추출 필드:** {len(fields)}개")

                    if fields:
                        with st.expander(f"필드 상세 ({len(fields)}개)", expanded=True):
                            for f in fields:
                                st.markdown(
                                    f"- `{f.get('field_code')}` = **{f.get('value')}** "
                                    f"[{f.get('validation', 'PASS')}]"
                                )

                    # SNOMED 태깅
                    snomed_tagging = record.get("snomed_tagging", [])
                    mapped = [t for t in snomed_tagging if t.get("concept_id") != "UNMAPPED"]
                    st.markdown(f"**SNOMED 태깅:** {len(mapped)}/{len(snomed_tagging)}개 매핑 성공")

                    if snomed_tagging:
                        with st.expander(f"SNOMED 태깅 상세 ({len(snomed_tagging)}개)", expanded=True):
                            for t in snomed_tagging:
                                cid = t.get("concept_id", "UNMAPPED")
                                term = t.get("preferred_term", "")
                                tag = t.get("semantic_tag", "")
                                conf = t.get("confidence", 0.0)
                                if cid == "UNMAPPED":
                                    st.markdown(f"- `{t.get('field_code')}` → ⚠️ **UNMAPPED**")
                                else:
                                    st.markdown(
                                        f"- `{t.get('field_code')}` → `{cid}` | {term} "
                                        f"({tag}) conf={conf:.3f}"
                                    )
                                    if t.get("post_coordination"):
                                        st.markdown(f"  SCG: `{t['post_coordination']}`")

                    # JSON 전문 뷰
                    with st.expander("📄 JSONL 레코드 전문 (§7.1)", expanded=False):
                        st.code(
                            json.dumps(record, ensure_ascii=False, indent=2),
                            language="json",
                        )

                    # 다운로드 버튼
                    jsonl_str = json.dumps(record, ensure_ascii=False) + "\n"
                    st.download_button(
                        label="⬇️ Download JSONL",
                        data=jsonl_str.encode("utf-8"),
                        file_name=f"encounter_{record.get('encounter_id', 'unknown')[:8]}.jsonl",
                        mime="application/jsonl",
                    )


# ─── 하단 정보 ──────────────────────────────────────────

st.divider()
st.caption(
    "SNOMED VET RAG v2.0 · "
    "Hybrid Search (Vector + SQL + RRF) · "
    "E2E Clinical Encoding (STT → SOAP → SNOMED) · "
    "SNOMED CT INT + VET Extension"
)
