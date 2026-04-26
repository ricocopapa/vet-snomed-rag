---
tags: [readme, vet-snomed-rag, v2.2, roadmap, release-notes]
date: 2026-04-23
summary: README.md v2.1→v2.2 Roadmap 반영 + Supported Input Formats 신규 섹션 추가 작업 완료 리포트
---

# README v2.2 업데이트 리포트

**작업 일자**: 2026-04-23  
**대상 파일**: `/Users/wondongmin/claude-cowork/07_Projects/vet-snomed-rag/README.md`  
**부속 파일**: `RELEASE_NOTES_v2.1.md`  
**커밋**: 0건 (Task 범위 외)

---

## §1 신규 섹션 위치 + 라인 번호

| 섹션 | 라인 | 위치 설명 |
|---|---|---|
| 목차 — `[Supported Input Formats]` 추가 | 29 | 기존 `[데모]` 항목 바로 아래 |
| 목차 — `[v2.2 Roadmap]` 추가 | 35 | 기존 `[로드맵]` 항목 바로 아래 |
| `## Supported Input Formats` 섹션 신설 | 458 | `Streamlit 데모 UI` 스크린샷 표 바로 뒤 (데모 섹션 끝) |
| `## v2.2 Roadmap` 섹션 신설 | 631 | 기존 `## 로드맵` 섹션 바로 뒤 (v2.1 완료 체크리스트 직후) |

**What's New 헤더 업데이트:**
- `## What's New in v2.0 (2026-04-22)` → `## What's New in v2.1 (2026-04-23)` (라인 41)
- 리드 배지 수치: Precision 0.938/Recall 0.737 → **0.891/0.772** (v2.1 실측값, 라인 13)

**로드맵 v2.1 상태 업데이트:**
- `- [ ] v2.1 (계획)` → `- [x] v2.1 (2026-04-23)` (라인 621, 완료 체크 4항목)

---

## §2 v2.2 로드맵 6건 링크 검증

| # | URL | README 인용 라인 | RELEASE_NOTES 인용 라인 |
|---|---|---|---|
| #1 | https://github.com/ricocopapa/vet-snomed-rag/issues/1 | 635 | 106 |
| #2 | https://github.com/ricocopapa/vet-snomed-rag/issues/2 | 636 | 107 |
| #3 | https://github.com/ricocopapa/vet-snomed-rag/issues/3 | 637 | 108 |
| #4 | https://github.com/ricocopapa/vet-snomed-rag/issues/4 | 638 | 109 |
| #5 | https://github.com/ricocopapa/vet-snomed-rag/issues/5 | 639 | 110 |
| #6 | https://github.com/ricocopapa/vet-snomed-rag/issues/6 | 466·467·470·640·642 | 111 |

**판정**: 6건 전수 README + RELEASE_NOTES 양쪽 인용 확인. #6은 Supported Input Formats 표(2행) + 주석(1행) + v2.2 Roadmap(1행) + PDF 배경 설명(1행) 총 5회 등장 — 모두 정당한 문맥.

---

## §3 grep 검증 결과

| 검증 항목 | 결과 | 세부 |
|---|---|---|
| `#1~#6` Issue 링크 6건 전수 | PASS | issues/1~6 각 1건 이상 README 내 존재 |
| PDF 미지원 `❌` 표기 | PASS | 라인 466·467 (표 내) + 라인 642 (주석 내) |
| `Supported Input Formats` 섹션 존재 | PASS | 라인 458 (헤더) + 라인 29 (목차) |
| `v2.2 Roadmap` 섹션 존재 | PASS | 라인 631 (헤더) + 라인 35 (목차) |
| 모호 문구 (`곧 지원` / `soon` / `upcoming`) | PASS | 0건 |
| 커밋·push | PASS (0건) | `git status` 확인: M README.md, M RELEASE_NOTES_v2.1.md (unstaged) |
| Supported Input Formats 표 5행 | PASS | Text / Audio / PDF-text / PDF-scan / Image |

---

## §4 문서 내 충돌 여부 확인

| 수치 | 출처 | README 표기 | 충돌 여부 |
|---|---|---|---|
| SNOMED Match 0.889 | RELEASE_NOTES_v2.1.md Headline | 라인 12, 47, 622, 636 | 없음 |
| Precision 0.891 | RELEASE_NOTES_v2.1.md 메트릭 표 | 라인 13 | 없음 |
| Recall 0.772 | RELEASE_NOTES_v2.1.md 메트릭 표 | 라인 13 | 없음 |
| pytest 85/86 PASS | RELEASE_NOTES_v2.1.md Repo Stats | 라인 13 (v2.0 문맥으로 표기) | 없음 (v2.0 수치, 정당) |
| v2.1 완료 기능 4건 | RELEASE_NOTES_v2.1.md What's Changed | 로드맵 [x] 체크리스트 | 없음 |

**기존 v1.0 수치 보존 확인**: PASS 6/10 → 10/10 (라인 13), latency -14.7% (라인 482) — 변경 없음.

---

## [Self-Verification]

- [x] README.md "Supported Input Formats" 섹션 존재 + 5행 표 (text / audio / PDF-text / PDF-scan / image) — 라인 458~471
- [x] README.md "v2.2 Roadmap" 섹션에 Issue #1~#6 전수 링크 — 라인 631~642
- [x] PDF 미지원(❌) 현 상태 명시 — 라인 466·467·642
- [x] 목차에 신규 섹션 2개 추가 — 라인 29, 35
- [x] RELEASE_NOTES_v2.1.md v2.2 로드맵 5건→6건 교체 — 라인 104~111
- [x] 리포트 §1~§4 작성 완료
- [x] 커밋·push 0건 확인
- [x] "곧 지원" 등 모호 문구 0건
- [x] v2.1 headline 수치(0.889 / 0.891 / 0.772) README와 RELEASE_NOTES 일치
