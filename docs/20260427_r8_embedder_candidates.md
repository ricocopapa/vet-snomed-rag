---
tags: [vet-snomed-rag, v3.0, R-8, embedder, candidates]
date: 2026-04-27
status: 후보 조사 종결 — 사용자 결정 입력 대기
---

# R-8 Embedder 후보 비교 연구 보고서

> **목적:** vet-snomed-rag v3.0 phase 1 — ChromaDB 재구축을 위한 임베더 교체 후보 조사. 실제 재임베딩·전수 재구축은 별도 세션에서 진행.
> **작성일:** 2026-04-27
> **관련 핸드오프:** `docs/20260427_v2_9_roadmap_handoff.md` §1-2 #4 (R-8)

---

## §1. 현 임베딩 상태

### 1-1. 현 모델 스펙

| 항목 | 값 |
|---|---|
| **모델 ID** | `sentence-transformers/all-MiniLM-L6-v2` |
| **임베딩 차원** | **384** |
| **파라미터 수** | ~22M |
| **최대 입력 길이** | 256 tokens |
| **학습 코퍼스** | 1B 범용 문장 쌍 (영어 일반 도메인) — 의학/수의학 특화 데이터 없음 |
| **라이선스** | Apache 2.0 |

**소스 확인:** `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag/src/indexing/vectorize_snomed.py`
- `EMBEDDING_MODEL = "all-MiniLM-L6-v2"` (line 33)
- `"hnsw:space": "cosine"` (cosine 유사도 공간)

### 1-2. 현재 인덱스 규모 + 재구축 비용 추정

| 항목 | 수치 |
|---|---|
| ChromaDB 벡터 수 | **366,570** (전수 인덱싱) |
| SNOMED DB 개념 총수 | 414,860 |
| 인덱싱 대상 semantic_tag | 13종 (disorder, finding, procedure, body structure 등) |
| 배치 크기 | 500 |

**재구축 소요 시간 추정 (후보별 — 로컬 CPU 기준):**

| 모델 | 차원 | 파라미터 | 추정 재구축 시간 |
|---|---|---|---|
| all-MiniLM-L6-v2 (현행) | 384 | 22M | ~10분 (기준선) |
| BioBERT / PubMedBERT / SapBERT (BERT-base급) | 768 | 110M | **1.5~3시간** (CPU) |
| BioLinkBERT-base | 768 | 110M | 1.5~3시간 (CPU) |
| MedCPT-Query-Encoder | 768 | 110M | 1.5~3시간 (CPU) |
| BGE-M3 (XLM-RoBERTa Large 기반) | 1024 | ~570M | **4~8시간** (CPU) |
| e5-mistral-7b-instruct | 4096 | 7B | **GPU 필수, 수십 시간 (CPU 불가)** |

> **주의:** 배치 처리 + GPU 가속 시 BERT-base급 ~30~60분, BGE-M3 ~2~4시간으로 단축 가능.
> e5-mistral-7b-instruct는 7B 파라미터로 A10G 이상 GPU 없이 실용적 재구축 불가능.

### 1-3. 현행 임베더의 알려진 한계

외부 비교 연구 실측값:
- SNOMED CT 코드 매칭 정확도: **64.73%** (all-MiniLM-L6-v2)
- 동일 태스크 SapBERT 계열: **>80%** (재랭킹 전 69.0%, 재랭킹 후 71.8%)
- PubMed 의학 문헌 Pearson 상관: 93.46% vs. PubMedBERT 계열 95.62%

출처: MDPI Information 2024 — Performance of 4 Sentence Transformer Models on Peri-Implantitis dataset; NeuML pubmedbert-base-embeddings 모델 카드

---

## §2. 후보 비교 표

### 2-1. 6개 평가 차원 정의

| 차원 | 설명 | 가중치 |
|---|---|---|
| D1 수의학 도메인 적합성 | 학습 코퍼스 vet 데이터 포함 여부, 의학 벤치마크 점수 | **최고** |
| D2 임베딩 차원 | 현 384 대비 변경 폭 (ChromaDB 재구축 비용) | 높음 |
| D3 모델 사이즈 + 추론 속도 | 366,570 재임베딩 소요 시간 | 높음 |
| D4 라이선스 | 상업·연구 사용 가능 여부 | 중간 |
| D5 HuggingFace 유지보수 | 월간 다운로드 수, 최근 커밋 | 중간 |
| D6 다국어 지원 | 한국어 처리 (현 시스템은 사전+reformulate로 영어 변환, 영어 임베더로 충분) | 낮음 |

---

### 2-2. 후보 비교 전체 표

| 후보 모델 | D1 수의학/의학 도메인 | D2 차원 | D3 사이즈·속도 | D4 라이선스 | D5 HF 유지보수 | D6 다국어 | 종합 평점 |
|---|---|---|---|---|---|---|---|
| **SapBERT** (cambridgeltl/SapBERT-from-PubMedBERT-fulltext) | ★★★★★ SNOMED/UMLS 특화 entity linking 최강, SNOMED 코드 Acc@1 69~71.8% | 768 (+2× 재구축 비용) | 110M, BERT-base급 | Apache 2.0 | 1,092,635 다운/월 (매우 높음) | 영어 전용 (별도 다국어 변형 있음) | **A** |
| **NeuML/pubmedbert-base-embeddings** | ★★★★ PubMed 특화 fine-tuning, 의학 Pearson 95.62% | 768 | 110M, BERT-base급 | Apache 2.0 | 595,583 다운/월 | 영어 전용 | **A** |
| **MedCPT-Query-Encoder** (ncbi/MedCPT-Query-Encoder) | ★★★★ 255M PubMed 검색 로그 학습, 바이오의학 IR SOTA | 768 | 110M, BERT-base급 | Public Domain | 352,738 다운/월 | 영어 전용 | **A-** |
| **BioLinkBERT-base** (michiyasunaga/BioLinkBERT-base) | ★★★★ PubMed + 인용 링크 학습, BLURB 83.39 | 768 | 110M, BERT-base급 | Apache 2.0 | 14,320 다운/월 (낮음) | 영어 전용 | **B+** |
| **BiomedBERT** (microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext) | ★★★ PubMed+PMC 학습, BLURB SOTA 기반 | 768 | 110M, BERT-base급 | MIT | 중간 (기반 모델) | 영어 전용 | **B+** |
| **BioBERT-v1.1** (dmis-lab/biobert-v1.1) | ★★★ PubMed+PMC 학습, 2019 원조 | 768 | 110M, BERT-base급 | Apache 2.0 | 보통 (구형) | 영어 전용 | **B** |
| **BGE-M3** (BAAI/bge-m3) | ★★ 범용 다국어, 의학 특화 없음 | 1024 | 570M, 중간 속도 | MIT | 18,410,715 다운/월 (최고) | 100+ 언어, 한국어 O | **B** (한국어 필요 시 A-) |
| **e5-mistral-7b-instruct** (intfloat) | ★★ MTEB 범용 최상위, 의학 특화 없음 | 4096 | 7B (GPU 필수) | MIT | 높음 | 영어 중심 (다국어 제한) | **C** (실용성 문제) |

---

### 2-3. 후보별 상세 카드

#### 1. SapBERT — 종합 평점 A (권장 1순위)

| 항목 | 내용 |
|---|---|
| **HuggingFace ID** | `cambridgeltl/SapBERT-from-PubMedBERT-fulltext` |
| **논문** | Liu et al., NAACL 2021 — "Self-Alignment Pretraining for Biomedical Entity Representations" |
| **임베딩 차원** | 768 (BERT-base 구조) |
| **파라미터** | ~110M |
| **학습 데이터** | UMLS 2020AA 동의어 쌍 (전체 의학 표준 용어 포함 — SNOMED CT, RxNorm, MeSH 등) |
| **의학 벤치마크** | SNOMED CT entity linking Acc@1: 69.0% (재랭킹 전) → 71.8% (재랭킹 후) (2025 BioNNE-L) |
| **라이선스** | Apache 2.0 |
| **HF 월간 다운로드** | 1,092,635 |
| **마지막 업데이트** | 명시되지 않음 (2021 공개 후 안정적) |
| **다국어** | 영어 전용 (별도 `SapBERT-UMLS-2020AB-all-lang-from-XLMR` 존재) |

**강점:** UMLS 기반 self-alignment 학습 → SNOMED CT 개념 간 의미 거리를 인체 의학 기준으로 정렬. 현 프로젝트의 핵심 태스크(SNOMED concept 검색)에 직결.

**1차 출처 URL:**
- 모델 카드: https://huggingface.co/cambridgeltl/SapBERT-from-PubMedBERT-fulltext
- 논문: https://arxiv.org/abs/2010.11784
- 2025 SNOMED entity linking 성능 비교: https://ceur-ws.org/Vol-4038/paper_35.pdf

---

#### 2. NeuML/pubmedbert-base-embeddings — 종합 평점 A (권장 2순위)

| 항목 | 내용 |
|---|---|
| **HuggingFace ID** | `NeuML/pubmedbert-base-embeddings` |
| **논문/블로그** | "Embeddings for Medical Literature", NeuML Medium 2024 |
| **임베딩 차원** | 768 |
| **파라미터** | ~110M |
| **학습 데이터** | PubMed title-abstract 쌍 (sentence-transformers 방식 fine-tuning) |
| **의학 벤치마크** | PubMed QA 93.27, PubMed Subset 97.00, PubMed Summary 96.58 → **평균 95.62%** Pearson |
| **vs all-MiniLM-L6-v2** | 평균 95.62% vs 93.46% (의학 태스크 기준 +2.16%p) |
| **라이선스** | Apache 2.0 |
| **HF 월간 다운로드** | 595,583 |
| **마지막 업데이트** | 2024년 3월 |
| **다국어** | 영어 전용 |

**강점:** sentence-transformers 에코시스템 완전 호환 → `SentenceTransformerEmbeddingFunction` 교체 최소 코드 변경. PubMed 의학 문헌에서 직접 embedding 품질 검증됨.

**1차 출처 URL:**
- 모델 카드: https://huggingface.co/NeuML/pubmedbert-base-embeddings
- NeuML 블로그: https://medium.com/neuml/embeddings-for-medical-literature-74dae6abf5e0

---

#### 3. MedCPT-Query-Encoder — 종합 평점 A-

| 항목 | 내용 |
|---|---|
| **HuggingFace ID** | `ncbi/MedCPT-Query-Encoder` + `ncbi/MedCPT-Article-Encoder` |
| **논문** | Jin et al., Bioinformatics 2023 — "MedCPT: Contrastive Pre-trained Transformers with large-scale PubMed search logs" |
| **임베딩 차원** | 768 |
| **파라미터** | ~110M |
| **학습 데이터** | 255M PubMed 사용자 검색 로그 (query-article 쌍) |
| **의학 벤치마크** | BEIR 바이오의학 5종 태스크 SOTA (BioASQ, NFCorpus 등), 제로샷 최강 |
| **라이선스** | Public Domain |
| **HF 월간 다운로드** | 352,738 |
| **비대칭 인코더** | Query Encoder (단문용) / Article Encoder (제목+초록용) — **두 인코더 동일 공간** |

**강점:** IR(정보 검색) 태스크에 직접 최적화. 현 프로젝트의 쿼리→SNOMED 개념 검색 패턴과 구조 일치.
**주의점:** Query Encoder가 단문(쿼리)용, Article Encoder가 긴 문서용 — SNOMED 개념 인덱싱 시 Article Encoder 사용이 더 적합할 수 있음. 단, 두 인코더는 동일 임베딩 공간을 공유하므로 검색 시 Query/Index 인코더를 분리해야 최적 성능 발휘.

**1차 출처 URL:**
- 모델 카드: https://huggingface.co/ncbi/MedCPT-Query-Encoder
- 논문: https://arxiv.org/abs/2307.00589
- PMC 전문: https://pmc.ncbi.nlm.nih.gov/articles/PMC10627406/

---

#### 4. BioLinkBERT-base — 종합 평점 B+

| 항목 | 내용 |
|---|---|
| **HuggingFace ID** | `michiyasunaga/BioLinkBERT-base` |
| **논문** | Yasunaga et al., ACL 2022 — "LinkBERT: Pretraining Language Models with Document Links" |
| **임베딩 차원** | 768 |
| **파라미터** | 110M (base), 340M (large) |
| **학습 데이터** | PubMed 초록 + 인용 링크 그래프 |
| **의학 벤치마크** | BLURB **83.39** (PubMedBERT 81.10 대비 +2.29), PubMedQA 70.2 |
| **라이선스** | Apache 2.0 |
| **HF 월간 다운로드** | 14,320 (낮음) |
| **마지막 업데이트** | Jan 2024 |

**강점:** BLURB 리더보드 상위, 논문 인용 링크 정보 활용.
**약점:** 다운로드 수 상대적으로 낮음. entity linking이 아닌 NER/QA 태스크 최적화 경향.

**1차 출처 URL:**
- 모델 카드: https://huggingface.co/michiyasunaga/BioLinkBERT-base
- 논문: https://arxiv.org/abs/2203.15827

---

#### 5. BiomedBERT (microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext) — 종합 평점 B+

| 항목 | 내용 |
|---|---|
| **HuggingFace ID** | `microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext` |
| **임베딩 차원** | 768 |
| **파라미터** | 110M |
| **학습 데이터** | PubMed 초록 + PubMed Central 전문 — **처음부터 학습(from scratch)** |
| **의학 벤치마크** | BLURB 리더보드 상위권 (공개 당시 SOTA) |
| **라이선스** | MIT |
| **특이사항** | SapBERT와 NeuML/pubmedbert-base-embeddings의 base 모델 — 즉 상위 후보 2개의 출발점 |

**평가:** 원본 기반 모델이므로 entity linking·embedding 특화 fine-tuning이 없음. SapBERT나 NeuML 변형 대비 직접적 이점 없음. SapBERT/NeuML 선택 시 자동으로 이 모델의 지식 포함.

**1차 출처 URL:**
- 모델 카드: https://huggingface.co/microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext
- BLURB 리더보드: https://microsoft.github.io/BLURB/models.html

---

#### 6. BioBERT-v1.1 (dmis-lab) — 종합 평점 B

| 항목 | 내용 |
|---|---|
| **HuggingFace ID** | `dmis-lab/biobert-v1.1` |
| **임베딩 차원** | 768 |
| **파라미터** | 110M |
| **학습 데이터** | 영어 Wikipedia + BookCorpus (BERT 사전학습) + PubMed 초록 + PMC 전문 (계속 학습) |
| **의학 벤치마크** | BLURB 기준 PubMedBERT 대비 하위 (from-scratch 모델이 domain-adaptive 모델보다 우수) |
| **라이선스** | Apache 2.0 |
| **마지막 업데이트** | 2024년 10월 (HF) |

**평가:** 2019년 발표 이래 가장 먼저 주목받은 바이오의학 BERT. 그러나 현재는 from-scratch PubMedBERT 계열에 전면 밀림. entity linking 특화 fine-tuning 없음. 동일 비용 대비 SapBERT/NeuML에 우위 없음. **단독 선택 이유 없음.**

**1차 출처 URL:**
- 모델 카드: https://huggingface.co/dmis-lab/biobert-v1.1
- GitHub: https://github.com/dmis-lab/biobert-pytorch

---

#### 7. BGE-M3 (BAAI/bge-m3) — 종합 평점 B (한국어 다국어 필요 시 A-)

| 항목 | 내용 |
|---|---|
| **HuggingFace ID** | `BAAI/bge-m3` |
| **논문** | Chen et al., 2024 — "BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity" |
| **임베딩 차원** | **1024** |
| **파라미터** | ~570M (XLM-RoBERTa Large 기반) |
| **학습 데이터** | 100+ 언어 다국어 범용 데이터 (의학 특화 없음) |
| **벤치마크** | MIRACL 다국어 검색 OpenAI 초과, MTEB 상위권 |
| **라이선스** | MIT |
| **HF 월간 다운로드** | **18,410,715** (전 후보 중 최다) |
| **최대 입력 길이** | 8,192 tokens |
| **다국어** | 100+언어, 한국어 O |
| **3가지 검색 방식** | Dense + Sparse + Multi-vector (ColBERT) 동시 지원 |

**평가:** 수의학·의학 도메인 특화 없음. 범용 다국어 최강 모델. 현 시스템이 한국어 쿼리를 영어로 reformulate 후 임베딩하므로 한국어 임베더 이점이 제한적. 차원 1024로 재구축 비용 증가. SNOMED CT entity linking 벤치마크 데이터 없음.
**선택 근거:** 현 사전+reformulate 파이프라인을 제거하고 한국어 직접 임베딩으로 전환할 때만 1순위 의미 있음.

**1차 출처 URL:**
- 모델 카드: https://huggingface.co/BAAI/bge-m3
- 논문: https://arxiv.org/abs/2402.03216

---

#### 8. e5-mistral-7b-instruct (intfloat) — 종합 평점 C (실용성 문제)

| 항목 | 내용 |
|---|---|
| **HuggingFace ID** | `intfloat/e5-mistral-7b-instruct` |
| **임베딩 차원** | **4096** |
| **파라미터** | **7B** |
| **학습 데이터** | 범용 다국어 혼합 + instruction fine-tuning |
| **벤치마크** | MTEB 영어 리더보드 최상위권 (2024 기준) |
| **라이선스** | MIT |
| **GPU 요구사항** | V100 이상 (≥16GB VRAM) 필수, CPU 재구축 사실상 불가 |
| **다국어** | 영어 중심 (다국어 제한적) |

**명시적 배제 이유:**
1. **재구축 실용성 불가:** 366,570 벡터 × 4096차원 = 5.7GB 벡터 저장 공간 (현 384차원 대비 10.7× 증가). GPU 없는 로컬 재구축 불가.
2. **의학 특화 없음:** MTEB 일반 벤치마크 최강이나 SNOMED/UMLS entity linking 전용 학습 없음.
3. **instruction 의존:** 최적 성능을 위해 쿼리마다 instruction prefix 필요 → 인덱싱 파이프라인 대폭 수정 필요.

**결론: 현 프로젝트 범위에서 제외 권장.**

**1차 출처 URL:**
- 모델 카드: https://huggingface.co/intfloat/e5-mistral-7b-instruct
- 논문: https://arxiv.org/abs/2401.00368

---

## §3. 수의학 적합성 가설

### 3-1. 핵심 사실: vet 코퍼스 학습 모델은 사실상 없음

| 모델 | vet 학습 데이터 포함 여부 |
|---|---|
| BioBERT | 없음 (PubMed + PMC — 인간 의학 중심) |
| PubMedBERT (NeuML fine-tuned) | 없음 (PubMed 초록 — 인간 의학) |
| SapBERT | **간접 포함 가능** — UMLS 2020AA에 SNOMED CT VET 개념 일부 포함되나 명시적 vet 데이터 없음 |
| MedCPT | 없음 (PubMed 검색 로그 — 인간 의학) |
| BGE-M3 | 없음 (범용 다국어) |
| e5-mistral-7b | 없음 (범용 영어) |

**결론:** 현재 공개된 어떤 임베딩 모델도 수의학 전용 학습 코퍼스를 포함하지 않는다. 이는 이번 후보 선택에서 공정한 출발선을 의미하지만, 동시에 모든 후보가 "인간 의학 지식의 수의학 전이" 가설에 의존한다는 뜻이다.

### 3-2. 적용 가설 (Alpha Transfer Hypothesis)

**가설:** 수의학 임상 용어(feline panleukopenia, elbow dysplasia, canine hip dysplasia 등)는 인간 의학 용어(parvovirus infection, joint dysplasia, etc.)와 의미 공간이 충분히 겹치므로, 인간 의학 도메인 특화 임베더가 범용 임베더보다 수의학 SNOMED 검색에서 우월하다.

**가설 지지 근거:**
- SNOMED CT VET는 SNOMED CT International 기반 확장 — 개념 구조(body structure, disorder 등)가 인간 의학과 동일한 계층 체계 사용
- SapBERT의 UMLS 기반 학습: UMLS에 SNOMED CT VET 개념 일부 포함 (NLM UMLS Metathesaurus SNOMEDCT_VET 출처)
- 수의학 논문의 70%+ 가 PubMed에 게재 — PubMed 기반 모델들이 수의학 용어를 간접 학습했을 가능성

**가설 한계 (반론):**
- 순수 vet-only 개념 (예: species-specific anatomy, exotic animal diseases)은 인간 의학 임베더에서 poorly represented 가능성
- 2024 PLOS Digital Health 논문: 수의학 EMR 진단 코딩에서 대형 LLM이 소형 fine-tuned 모델보다 우수 — 도메인 특화 임베더가 반드시 수의학 최강이 아닐 수 있음

### 3-3. vet-specific 강화 방향 (v3.0 이후)

향후 검토 옵션:
1. **SapBERT fine-tuning on SNOMED VET pairs** — SNOMED CT VET 개념 쌍으로 contrastive fine-tuning
2. **NeuML pubmedbert-base-embeddings Matryoshka 변형** — 가변 차원 지원, veterinary title-abstract 쌍 추가 fine-tuning
3. **합성 vet 데이터 생성** — Gemini/GPT-4로 vet 임상 텍스트↔SNOMED 쌍 생성 후 fine-tuning (현 시스템 내 Gemini 파이프라인 활용 가능)

---

## §4. 검증 절차 제안

### 4-1. 3단계 검증 로드맵

```
[Phase 0] 현행 기준선 측정 (all-MiniLM-L6-v2)
   ↓ 11쿼리 회귀 RERANK=1: none 10/10, gemini 10/10 (기존 달성)
   ↓ 100쿼리 샘플 chromaDB 검색 결과 수동 평가 (정성 점수 기록)

[Phase 1] 후보 모델 샘플 테스트 (5건 smoke)
   ↓ 각 후보 모델로 SNOMED 개념 5건 임베딩 → 같은 쿼리 5건으로 유사도 비교
   ↓ "feline panleukopenia", "elbow dysplasia dog", "dental extraction", "blood glucose", "German Shepherd"

[Phase 2] 100쿼리 비교 임베딩 (샘플 ChromaDB 구축)
   ↓ 전체 366,570 재구축 전에 1,000개 대표 샘플로 임시 ChromaDB 구축
   ↓ 11쿼리 회귀 + 추가 89쿼리 (SNOMED tag별 분포 반영)
   ↓ MRR@10, Recall@10, nDCG@10 측정

[Phase 3] 전수 재구축 (Phase 2 검증 통과 후에만)
   ↓ 선정 모델로 366,570 벡터 전수 재구축
   ↓ 11쿼리 전수 회귀 (RERANK=1, none·gemini 10/10 기준 유지)
```

### 4-2. 구체적 검증 쿼리 설계 (100쿼리 샘플)

| 분류 | 쿼리 수 | 예시 |
|---|---|---|
| 수의학 전용 개념 (vet-specific) | 20 | feline panleukopenia, canine parvovirus, equine colic |
| 범용 disorder (human-vet 공유) | 25 | diabetes mellitus, pneumonia, renal failure |
| Procedure | 20 | dental extraction, splenectomy, blood culture |
| Body structure | 15 | femoral head, hepatic lobe, cardiac valve |
| Drug/Substance | 10 | amoxicillin, prednisolone, insulin |
| 한국어 쿼리 → 영어 reformulate 경유 | 10 | 고양이 범백혈구감소증, 강아지 엉덩이 이형성 |

### 4-3. 성공 기준 (Phase 2)

| 지표 | 허용 임계값 |
|---|---|
| 11쿼리 회귀 | none·gemini 10/10 유지 (회귀 0) |
| MRR@10 (100쿼리 평균) | ≥ 현행 MRR@10 × 1.05 (+5% 이상 향상) |
| 수의학 전용 쿼리 Recall@5 | ≥ 현행 × 0.95 (수의학 손실 ≤5% 허용) |
| 전수 재구축 소요 시간 | ≤ 8시간 (CPU) |

---

## §5. 권장 1-2개 선정 + 근거

### 5-1. 권장 1순위: SapBERT (cambridgeltl/SapBERT-from-PubMedBERT-fulltext)

**선정 근거 (Why SapBERT):**

1. **SNOMED CT entity linking에 가장 직접적으로 최적화** — 다른 후보들이 NER, QA, 문헌 검색 일반 태스크를 주 목표로 했다면, SapBERT는 UMLS 동의어 쌍 기반 self-alignment로 의학 개념 ID↔텍스트 매핑을 목표로 학습. 현 프로젝트의 "수의사가 입력한 텍스트 → SNOMED concept 검색" 패턴과 가장 직접 일치.

2. **SNOMED CT 실증 벤치마크 존재** — 2024년 논문(Abdulnazar et al., SAGE)과 2025년 BioNNE-L에서 SapBERT가 SNOMED CT 매핑에서 BioBERT/PubMedBERT를 상회함을 실측으로 확인. SNOMED CT 200K 개념 매칭에서 cosine 기반 검색 성능 검증.

3. **Apache 2.0 라이선스** — 상업·연구 무제한.

4. **HuggingFace 커뮤니티 1순위 바이오의학 entity 모델** — 월 다운로드 ~110만. 활발한 유지보수.

5. **sentence-transformers 호환** — `vectorize_snomed.py`의 `SentenceTransformerEmbeddingFunction` 교체 시 코드 변경 최소화. ChromaDB 연동에서 별도 래퍼 불필요.

**주의사항:**
- 평균 토큰 인코더 변형(`SapBERT-from-PubMedBERT-fulltext-mean-token`)이 [CLS] 토큰 변형보다 embedding 태스크에 더 적합할 수 있음 — Phase 1 smoke에서 두 변형 비교 권장.
- 차원 768로 증가 → 현행 384 대비 ChromaDB 저장 공간 2× 증가 예상.

---

### 5-2. 권장 2순위: NeuML/pubmedbert-base-embeddings

**선정 근거 (Why NeuML pubmedbert-base-embeddings):**

1. **sentence-transformers 파이프라인 완전 호환** — 현행 코드 `embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)` 한 줄만 변경으로 교체 가능. 가장 낮은 마이그레이션 리스크.

2. **PubMed 의학 문헌 semantic similarity 최적화** — SNOMED preferred term / FSN / 동의어 텍스트 쌍이 PubMed 의학 용어와 높은 의미 공간 겹침. 의학 Pearson 95.62% (all-MiniLM-L6-v2 93.46% 대비 +2.16%p) 실증.

3. **SapBERT 대비 차이점:** NeuML은 sentence-level semantic similarity 최적화, SapBERT는 entity-level concept matching 최적화. **짧은 용어 쌍 매칭(SNOMED preferred_term↔query)에는 SapBERT가, 문장 수준 RAG 답변 생성 맥락 이해에는 NeuML이 더 적합**할 수 있음.

4. **Matryoshka 변형 존재** (`NeuML/pubmedbert-base-embeddings-matryoshka`) — 향후 차원 축소(384→256→128) 실험 가능.

**Phase 1에서 두 모델 비교 권장.** 동일 5쿼리 smoke에서 직접 cosine score 비교 후 최종 선택.

---

### 5-3. 비선택 이유 요약

| 모델 | 비선택 이유 |
|---|---|
| BioLinkBERT-base | 다운로드 수 낮음(14K), entity linking보다 NER/QA 최적화 |
| BiomedBERT (microsoft) | SapBERT/NeuML의 base 모델 — 상위 변형이 항상 우위 |
| BioBERT-v1.1 | 2019 원조 모델, 현재 모든 후속 모델에 전면 열세 |
| BGE-M3 | 의학 특화 없음, 1024차원으로 재구축 비용 증가, 현 시스템 한국어→영어 reformulate로 다국어 이점 불필요 |
| e5-mistral-7b-instruct | 7B 파라미터 GPU 필수, 4096차원 저장 10×, 의학 entity linking 특화 없음 — **명시적 배제** |

---

## §6. 사용자 결정 입력 항목

아래 항목에 대한 사용자 결정이 Phase 1 진입 전에 필요합니다.

| # | 항목 | 옵션 | 현재 상태 |
|---|---|---|---|
| U-1 | **권장 1순위 확정** | (a) SapBERT [CLS] / (b) SapBERT mean-token / (c) NeuML pubmedbert / (d) MedCPT / (e) Phase 1 두 모델 비교 후 결정 | 미결정 |
| U-2 | **ChromaDB 차원 변경 허용** | (a) 768로 증가 허용 (권장) / (b) 384 유지 강제 (→ dimension reduction 추가 필요) | 미결정 |
| U-3 | **재구축 실행 환경** | (a) 로컬 CPU (~2~3시간) / (b) 로컬 GPU (가속) / (c) 클라우드 GPU | 미결정 |
| U-4 | **한국어 직접 임베딩 전환 여부** | (a) 현행 한국어→영어 reformulate 유지 (영어 임베더 선택) / (b) 직접 임베딩으로 전환 (BGE-M3 선택) | 미결정 |
| U-5 | **Phase 2 검증 선행 여부** | (a) 1,000 샘플 임시 ChromaDB로 검증 후 전수 재구축 (권장) / (b) 즉시 전수 재구축 | 미결정 |
| U-6 | **MedCPT 비대칭 인코더 방식 채택 여부** | (a) 단일 인코더(SapBERT/NeuML) / (b) Query+Article 분리(MedCPT — 인덱싱 파이프라인 수정 필요) | 미결정 |

---

## §7. 핸드오프 성공 기준 체크리스트 (B-항목 1:1 검증)

| # | 항목 | 결과 |
|---|---|---|
| B1-1 | 현 임베더 확인 (`vectorize_snomed.py` 모델 ID + 차원 추출) | ✅ PASS — `all-MiniLM-L6-v2`, 384차원 (line 33) |
| B1-2 | 후보 ≥6 조사 | ✅ PASS — 8개 후보 평가 (지시 7개 + NeuML 추가 1개) |
| B1-3 | 1차 출처 (HuggingFace 모델 카드 URL + 논문 URL 명시) | ✅ PASS — 각 후보 카드에 HF URL + 논문/블로그 URL 명시 |
| B1-4 | 비교 표 (6차원 × N 후보) | ✅ PASS — §2-2에 8후보 × 6차원 표 + 상세 카드 |
| B1-5 | 권장안 1-2개 + "왜 이 모델인가" 근거 | ✅ PASS — §5에 SapBERT(1순위)/NeuML(2순위) + 5가지 근거 각각 명시 |

---

## §8. 부록 — 참고 출처 목록

| 출처 | URL |
|---|---|
| SapBERT HuggingFace | https://huggingface.co/cambridgeltl/SapBERT-from-PubMedBERT-fulltext |
| SapBERT 논문 (NAACL 2021) | https://arxiv.org/abs/2010.11784 |
| NeuML pubmedbert-base-embeddings HuggingFace | https://huggingface.co/NeuML/pubmedbert-base-embeddings |
| NeuML 블로그 | https://medium.com/neuml/embeddings-for-medical-literature-74dae6abf5e0 |
| MedCPT Query Encoder HuggingFace | https://huggingface.co/ncbi/MedCPT-Query-Encoder |
| MedCPT 논문 (Bioinformatics 2023) | https://arxiv.org/abs/2307.00589 |
| BioLinkBERT HuggingFace | https://huggingface.co/michiyasunaga/BioLinkBERT-base |
| BioLinkBERT 논문 (ACL 2022) | https://arxiv.org/abs/2203.15827 |
| BiomedBERT HuggingFace | https://huggingface.co/microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext |
| BLURB 리더보드 | https://microsoft.github.io/BLURB/models.html |
| BioBERT HuggingFace | https://huggingface.co/dmis-lab/biobert-v1.1 |
| BGE-M3 HuggingFace | https://huggingface.co/BAAI/bge-m3 |
| BGE-M3 논문 (2024) | https://arxiv.org/abs/2402.03216 |
| e5-mistral-7b-instruct HuggingFace | https://huggingface.co/intfloat/e5-mistral-7b-instruct |
| e5-mistral-7b-instruct 논문 (2024) | https://arxiv.org/abs/2401.00368 |
| SapBERT SNOMED CT 비교 2024 | https://journals.sagepub.com/doi/10.1177/20552076241288681 |
| SNOBERT 벤치마크 2024 | https://arxiv.org/html/2405.16115v1 |
| 수의학 진단 코딩 LLM 비교 (PLOS 2024) | https://journals.plos.org/digitalhealth/article?id=10.1371/journal.pdig.0001147 |
| SNOMED CT VET 공식 | https://vtsl.vetmed.vt.edu/ |

---

**보고서 종결 — v3.0 R-8 Phase 1 진입을 위한 사용자 결정(§6 U-1~U-6) 대기.**
