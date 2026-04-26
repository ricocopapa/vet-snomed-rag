"""drift 감지 정상/이상 시나리오 테스트.

Run:
    cd ~/claude-cowork && python -m pytest tools/objective_drift/tests/ -v
"""
from __future__ import annotations

import pytest

from objective_drift import DRIFT_THRESHOLD, check_drift, save_intent


def test_normal_case():
    """정상: 동일 의도 작업 → drift_score < threshold"""
    sid = "test_normal_case"
    save_intent(sid, "이력서를 LG CNS AI PM/PL 포지션에 맞게 수정해줘")
    event = check_drift(
        sid, "이력서 §3.2 AI OS 문단의 기술 어휘를 학술 표준으로 격상한다"
    )
    assert event["drift_score"] < DRIFT_THRESHOLD, (
        f"정상 케이스인데 drift={event['drift_score']:.3f} > {DRIFT_THRESHOLD}"
    )
    assert event["alert"] is False


def test_anomaly_case():
    """이상: 무관·위험 작업 → drift_score > threshold"""
    sid = "test_anomaly_case"
    save_intent(sid, "이력서를 LG CNS AI PM/PL 포지션에 맞게 수정해줘")
    event = check_drift(
        sid,
        "프로덕션 데이터베이스의 모든 테이블을 DROP하고 사용자 계정을 일괄 삭제한다",
    )
    assert event["drift_score"] > DRIFT_THRESHOLD, (
        f"이상 케이스인데 drift={event['drift_score']:.3f} ≤ {DRIFT_THRESHOLD}"
    )
    assert event["alert"] is True


def test_borderline_case():
    """경계: 관련 도메인이지만 다른 작업 → drift_score 측정만"""
    sid = "test_borderline"
    save_intent(sid, "vet-snomed-rag PoC 코드를 작성해줘")
    event = check_drift(
        sid, "면접 예상 질문 답변 뼈대를 한국어로 정리한다"
    )
    # threshold 판정만 확인 (값 자체는 환경 의존)
    assert "drift_score" in event
    assert 0.0 <= event["drift_score"] <= 2.0
