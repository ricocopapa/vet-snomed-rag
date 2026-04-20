# C4 — Streamlit GIF 데모 제작 가이드

> 본 작업은 **실시간 화면 녹화가 필요**하므로 사용자가 직접 수행해야 합니다. 아래 단계대로 진행하면 약 60분 내 완료 가능합니다.

---

## 1. 사전 준비 (10분)

### 1-1. 환경 활성화
```bash
cd ~/claude-cowork/07_Projects/vet-snomed-rag
source venv/bin/activate
```

### 1-2. Streamlit 데모 실행
```bash
streamlit run app.py
# 기본 포트 8501 → 브라우저 자동 오픈
```

### 1-3. (선택) API 키 설정
- `GEMINI_API_KEY` (Primary): 반드시 설정 (Free Tier)
- `ANTHROPIC_API_KEY` (Optional): 설정 시 Claude Backend 스위칭 데모 가능

---

## 2. 녹화 도구 옵션 (macOS)

| 도구 | 난이도 | 특징 |
|---|---|---|
| **QuickTime Player** | ⭐ 쉬움 | 기본 탑재, 화면 일부 선택 가능, `.mov` 출력 |
| **Kap** (권장) | ⭐⭐ | 무료 오픈소스, GIF 직접 출력, FPS 조절 (https://getkap.co) |
| **LICEcap** | ⭐⭐ | GIF 특화, 저용량, Windows/macOS |
| **ffmpeg** | ⭐⭐⭐ | CLI, `.mov → .gif` 변환 스크립트 |

**추천: Kap** — 녹화 후 바로 GIF 저장, 15fps 이상 자동.

---

## 3. 녹화 시나리오 (3종 권장)

### 시나리오 1 — 한국어 쿼리 성공 (20초)
1. Streamlit 입력창에 **"고양이 범백혈구감소증 SNOMED 코드"** 입력
2. Enter → Top-5 결과 대기 (약 1초)
3. `339181000009108 Feline panleukopenia` Top-1 등장 강조
4. is-a 관계·Post-coord hint 영역까지 스크롤

### 시나리오 2 — T7 회귀 증명 "feline diabetes" (20초)
1. **"feline diabetes"** 입력
2. Before (회귀 전) 가정하지 말고, 현재 버전 Top-1 `73211009 Diabetes mellitus` 제시
3. 하단 "Before/After Regression" 섹션에서 11-쿼리 10/10 PASS 차트 확인

### 시나리오 3 — Backend 스위칭 (30초)
1. 사이드바에서 Backend: `Gemini` → 쿼리 실행 → latency 표시
2. 사이드바에서 Backend: `Claude` → 동일 쿼리 실행 → latency 비교
3. 양 backend 결과가 일관됨을 강조

---

## 4. 출력 스펙 (이력서·GitHub 용)

| 항목 | 권장값 |
|---|---|
| 해상도 | 1280 × 720 (또는 1440 × 900) |
| FPS | 15~20 fps |
| 길이 | 15~30초 (반복 루프 자연스럽게) |
| 파일 크기 | **< 10 MB** (GitHub README 임베드 한계) |
| 파일명 | `C4_demo_kr_query.gif`, `C4_demo_backend_switch.gif` |
| 저장 경로 | `graphify_out/portfolio/` |

---

## 5. 최적화 (용량 축소)

녹화 파일이 10 MB 초과 시:

```bash
# ffmpeg 설치 (brew install ffmpeg)
ffmpeg -i input.mov -vf "fps=15,scale=1000:-1:flags=lanczos,palettegen" palette.png
ffmpeg -i input.mov -i palette.png -lavfi "fps=15,scale=1000:-1:flags=lanczos [x]; [x][1:v] paletteuse" output.gif
```

또는 [gifski](https://gif.ski/) 사용 (brew install gifski):
```bash
gifski --fps 15 --width 1000 -o output.gif input.mov
```

---

## 6. README 반영

GIF 생성 후 README.md에 추가:

```markdown
## 데모 영상

![한국어 쿼리 데모](graphify_out/portfolio/C4_demo_kr_query.gif)

![Backend 스위칭](graphify_out/portfolio/C4_demo_backend_switch.gif)
```

LG careers 지원 시에는 docx 내 링크 또는 별도 URL(GitHub Pages, YouTube)로 공유 가능.

---

## 7. 대안 — 정적 스크린샷 시리즈

녹화가 부담스럽다면 이미 보유한 스크린샷 6종 사용:
- `docs/screenshots/01_query_feline_panleukopenia.png`
- `docs/screenshots/02_query_goyangi_dangnyo.png`
- `docs/screenshots/03_query_gae_chejangyeom.png`
- `docs/screenshots/04_query_pancreatitis_dog.png`
- `docs/screenshots/05_query_malui_jeyeopyeom.png`
- `docs/screenshots/06_query_canine_parvovirus.png`

**6장을 PPT로 이어붙여 1-page 스크린샷 콜라주**를 만드는 것도 대안 — matplotlib으로 자동 생성 가능 (요청 시 스크립트 제공).

---

## 문서 메타

- 작성일: 2026-04-20
- 용도: C4 GIF 데모 사용자 가이드 (화면 녹화 필요 작업)
- 대안 경로: 정적 스크린샷 콜라주 (요청 시 자동 생성)
