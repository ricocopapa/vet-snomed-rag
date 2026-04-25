"""G-4 RewriteLoopController 단위 테스트."""
from __future__ import annotations

from unittest.mock import patch

from src.retrieval.agentic.loop_controller import LoopDecision, RewriteLoopController
from src.retrieval.agentic.relevance_judge import RelevanceVerdict


class TestTerminationConditions:
    def test_pass_high_confidence_stops(self):
        ctrl = RewriteLoopController(max_iter=2, threshold=0.7)
        rel = RelevanceVerdict(verdict="PASS", confidence=0.9)
        d = ctrl.decide("orig", "orig", rel, iter_count=0, history=[])
        assert d.should_continue is False
        assert "PASS" in d.reason

    def test_max_iter_reached_stops(self):
        ctrl = RewriteLoopController(max_iter=2)
        rel = RelevanceVerdict(verdict="PARTIAL", confidence=0.5)
        d = ctrl.decide("orig", "cur", rel, iter_count=2, history=["orig", "cur"])
        assert d.should_continue is False
        assert "max_iter" in d.reason


class TestRewriteAttempt:
    def test_partial_triggers_rewrite_via_gemini_mock(self):
        ctrl = RewriteLoopController(max_iter=3)
        rel = RelevanceVerdict(
            verdict="PARTIAL",
            confidence=0.5,
            missing_aspects=["mechanism"],
        )
        with patch.object(
            ctrl, "_rewrite", return_value="feline diabetes mechanism and treatment"
        ):
            d = ctrl.decide(
                "feline diabetes", "feline diabetes", rel, iter_count=0, history=[]
            )
        assert d.should_continue is True
        assert d.new_query is not None
        assert "mechanism" in d.new_query

    def test_rewrite_failure_stops(self):
        ctrl = RewriteLoopController(max_iter=3)
        rel = RelevanceVerdict(verdict="FAIL", confidence=0.2)
        with patch.object(
            ctrl, "_rewrite", side_effect=RuntimeError("rewrite empty")
        ):
            d = ctrl.decide(
                "orig", "cur", rel, iter_count=0, history=[]
            )
        assert d.should_continue is False
        assert "rewrite 실패" in d.reason


class TestCycleDetection:
    def test_duplicate_new_query_triggers_cycle(self):
        ctrl = RewriteLoopController(max_iter=3, cycle_similarity_threshold=0.5)
        rel = RelevanceVerdict(verdict="PARTIAL", confidence=0.5)
        # rewrite가 history와 거의 동일한 문자열 반환
        with patch.object(ctrl, "_rewrite", return_value="feline diabetes code"):
            d = ctrl.decide(
                "feline diabetes code",
                "feline diabetes code",
                rel,
                iter_count=0,
                history=["feline diabetes code"],
            )
        assert d.should_continue is False
        assert "cycle" in d.reason.lower()
