"""
anonymize_hyangnam_pdf.py
=========================
향남메디동물병원 Chart_Data.PDF → PHI 마스킹 후 data/synthetic_scenarios_pdf/ 에 저장.

목적:
  v2.2 Stage 1 (텍스트 PDF) 테스트 fixture 생성. 원본 PDF는 보호자명/주소/전화/
  환자명/수의사명 등 PHI를 포함하므로 공개 repo에 커밋할 수 없다. PyMuPDF 의
  redact_annot + apply_redactions API 로 PHI 영역만 텍스트 치환하여 원본 레이아웃을
  보존한 익명화 PDF 를 생성한다.

실행:
  .venv/bin/python scripts/anonymize_hyangnam_pdf.py

요구 사항:
  - pymupdf>=1.24.0 (별도 설치, 런타임 의존성 아님)
  - 원본 향남 PDF 디렉토리: ~/Downloads/향남동물병원_extract/향남동물병원/

대상 케이스 (v2.2 Stage 1 샘플 3건):
  - 10053_이미정_뭉뭉이            → hyangnam_anon_01_ophthalmology.pdf
  - 10024_양정희_구름              → hyangnam_anon_02_dermatology.pdf
  - 10146_김수민_티즈              → hyangnam_anon_03_gastrointestinal.pdf

마스킹 규칙 (대체 문자열은 ASCII 로 — Helv 폰트가 CJK 를 렌더링하지 못함):
  Client 이름   → Owner_A / Owner_B / Owner_C
  Client No     → 90001 / 90002 / 90003
  Address       → [REDACTED]
  Tel           → 000-0000-0000
  Patient 이름  → Pet_A / Pet_B / Pet_C
  Sign (수의사) → Vet_X

주의:
  - 익명화된 PDF 만 data/synthetic_scenarios_pdf/ 에 커밋.
  - 원본 PDF 는 ~/Downloads/ 에 그대로 보존 (repo 외부).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("pymupdf 가 필요합니다. .venv/bin/pip install 'pymupdf>=1.24.0'")

# ── 경로 상수 ──────────────────────────────────────────────────────────────
SRC_ROOT = Path.home() / "Downloads" / "향남동물병원_extract" / "향남동물병원"
DST_DIR  = Path(__file__).resolve().parent.parent / "data" / "synthetic_scenarios_pdf"

# ── 케이스 매핑 ────────────────────────────────────────────────────────────
# (원본 폴더명, 출력 파일명, 보호자 대체명, 환자 대체명, 대체 Client No)
CASES: list[dict[str, Any]] = [
    {
        "src_folder": "10053_이미정_뭉뭉이",
        "dst_name":   "hyangnam_anon_01_ophthalmology.pdf",
        "replacements": {
            "이미정": "Owner_A",
            "뭉뭉이": "Pet_A",
            "10053":  "90001",
            "화성시 향남읍 하길로9 부영1102동 302호": "[REDACTED]",
            "010-9519-9537": "000-0000-0000",
            "이근용": "Vet_X",
            "이현정": "Vet_X",
        },
    },
    {
        "src_folder": "10024_양정희_구름",
        "dst_name":   "hyangnam_anon_02_dermatology.pdf",
        "replacements": {
            "양정희": "Owner_B",
            # 환자명 '구름' 은 흔한 명사와 충돌 가능 — 본 샘플 진료 내역에 '구름' 재등장이
            # 없어 안전 (육안 검증). Patient 필드 외 '구름' 도 치환됨.
            "구름":   "Pet_B",
            "10024":  "90002",
            "부영3단지 301동 304호": "[REDACTED]",
            "010-2416-9785": "000-0000-0000",
            "이근용": "Vet_X",
        },
    },
    {
        "src_folder": "10146_김수민_티즈",
        "dst_name":   "hyangnam_anon_03_gastrointestinal.pdf",
        "replacements": {
            "김수민": "Owner_C",
            "티즈":   "Pet_C",
            "10146":  "90003",
            "화성시 향남읍 부영9단지 905동 1203호": "[REDACTED]",
            "010-8388-1481": "000-0000-0000",
            "이근용": "Vet_X",
            "이현정": "Vet_X",
        },
    },
]


def anonymize_pdf(src_pdf: Path, dst_pdf: Path, replacements: dict[str, str]) -> dict[str, Any]:
    """Redact PHI substrings in src_pdf and write dst_pdf.

    redact_annot 는 해당 영역을 지우고 같은 사각형 위에 대체 텍스트를 렌더링한다.
    원본 폰트/위치가 보존되는 것은 아니지만, 페이지 레이아웃은 유지된다.

    Returns: {"pages": int, "redactions": int}
    """
    doc = fitz.open(src_pdf)
    total_redactions = 0

    for page in doc:
        for needle, replacement in replacements.items():
            if not needle:
                continue
            # search_for 는 대상 문자열의 모든 출현 위치 rect 목록을 반환
            for rect in page.search_for(needle):
                # redact_annot: 해당 rect 내 텍스트를 제거하고 대체 텍스트로 덮어쓰기
                page.add_redact_annot(
                    rect,
                    text=replacement,
                    fontname="helv",      # 영문/숫자는 helvetica. 한글 대체는 아래 주석 참조.
                    fontsize=8,
                    fill=(1, 1, 1),       # 흰 배경
                    text_color=(0, 0, 0),
                )
                total_redactions += 1
        # apply_redactions 는 페이지 단위로 적용
        page.apply_redactions()

    dst_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dst_pdf, garbage=4, deflate=True)
    doc.close()
    return {"pages": len(fitz.open(dst_pdf)), "redactions": total_redactions}


def main() -> int:
    if not SRC_ROOT.exists():
        print(f"ERROR: 원본 디렉토리 없음: {SRC_ROOT}")
        return 1

    DST_DIR.mkdir(parents=True, exist_ok=True)

    print(f"source root: {SRC_ROOT}")
    print(f"dest dir:    {DST_DIR}\n")

    ok = 0
    for case in CASES:
        src_pdf = SRC_ROOT / case["src_folder"] / "Chart_Data.PDF"
        dst_pdf = DST_DIR / case["dst_name"]
        if not src_pdf.exists():
            print(f"  SKIP (not found): {src_pdf}")
            continue
        try:
            info = anonymize_pdf(src_pdf, dst_pdf, case["replacements"])
            print(f"  OK  {dst_pdf.name}  pages={info['pages']} redactions={info['redactions']}")
            ok += 1
        except Exception as e:
            print(f"  FAIL {dst_pdf.name}: {e}")

    print(f"\ndone: {ok}/{len(CASES)}")
    return 0 if ok == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
