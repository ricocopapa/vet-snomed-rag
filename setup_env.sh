#!/bin/bash
# vet-snomed-rag 환경 세팅 스크립트
# 실행: bash setup_env.sh

set -e

echo "============================================"
echo " vet-snomed-rag 환경 세팅 시작"
echo "============================================"

# 1. Python 가상환경 생성 (디렉토리명: venv/ — 핸드오프 §1-3 표준)
echo "[1/4] Python 가상환경 생성..."
python3 -m venv venv
source venv/bin/activate

# 2. pip 업그레이드
echo "[2/4] pip 업그레이드..."
pip install --upgrade pip

# 3. 의존성 설치
echo "[3/4] 의존성 설치 (시간 소요: ~5분)..."
pip install -r requirements.txt

# 4. 데이터 심볼릭 링크 (원본 DB를 직접 참조)
echo "[4/4] 데이터 링크 설정..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"

# SNOMED DB 링크
SNOMED_DB="../../../05_Output_Workspace/EMR/snomed_ct_vet_reference.db"
if [ ! -L "${DATA_DIR}/snomed_ct_vet.db" ] && [ ! -f "${DATA_DIR}/snomed_ct_vet.db" ]; then
    ln -s "${SNOMED_DB}" "${DATA_DIR}/snomed_ct_vet.db"
    echo "  → snomed_ct_vet.db 링크 완료"
fi

# JSON 매핑 파일 링크
MAPPING_SRC="../../../05_Output_Workspace/EMR/VetSTT_Developer_Package/02_SNOMED_매핑"
for f in assessment_snomed_mapping.json plan_snomed_mapping.json snomed_post_coord_rules.json snomed_mapping_v2.json; do
    if [ ! -L "${DATA_DIR}/${f}" ] && [ ! -f "${DATA_DIR}/${f}" ]; then
        ln -s "${MAPPING_SRC}/${f}" "${DATA_DIR}/${f}" 2>/dev/null || true
    fi
done
echo "  → JSON 매핑 파일 링크 완료"

echo ""
echo "============================================"
echo " 세팅 완료!"
echo " 활성화: source venv/bin/activate"
echo " 실행:   python src/indexing/vectorize_snomed.py"
echo "============================================"
