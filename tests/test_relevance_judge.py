"""G-3 RelevanceJudgeAgent 단위 테스트."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from src.retrieval.agentic.relevance_judge import (
    RelevanceJudgeAgent,
    RelevanceVerdict,
)


class TestBasicBehavior:
    def test_empty_answer_returns_fail(self):
        agent = RelevanceJudgeAgent()
        v = agent.judge("feline diabetes", "")
        assert v.verdict == "FAIL"
        assert v.method == "rule_based"
        assert "empty_answer" in v.missing_aspects

    def test_whitespace_only_answer_is_fail(self):
        agent = RelevanceJudgeAgent()
        v = agent.judge("feline diabetes", "   \n  ")
        assert v.verdict == "FAIL"


class TestGeminiSuccess:
    def test_pass_verdict_parsed(self):
        agent = RelevanceJudgeAgent()
        mock_response = MagicMock()
        mock_response.text = (
            '{"verdict":"PASS","confidence":0.9,"missing_aspects":[],"reasoning":"ok"}'
        )
        with patch("google.genai.Client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                mock_response
            )
            with patch.dict("os.environ", {"GOOGLE_API_KEY": "dummy"}):
                v = agent.judge(
                    "feline diabetes",
                    "Feline diabetes concept_id 73211009",
                    [{"concept_id": "73211009", "preferred_term": "Diabetes mellitus"}],
                )
        assert v.verdict == "PASS"
        assert v.confidence == 0.9
        assert v.method == "gemini"

    def test_partial_with_missing_aspects(self):
        agent = RelevanceJudgeAgent()
        mock_response = MagicMock()
        mock_response.text = '{"verdict":"PARTIAL","confidence":0.6,"missing_aspects":["treatment"],"reasoning":"치료 누락"}'
        with patch("google.genai.Client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                mock_response
            )
            with patch.dict("os.environ", {"GOOGLE_API_KEY": "dummy"}):
                v = agent.judge("당뇨 치료법", "Diabetes concept만 반환")
        assert v.verdict == "PARTIAL"
        assert "treatment" in v.missing_aspects


class TestFallback:
    def test_gemini_exception_falls_back_to_partial(self):
        agent = RelevanceJudgeAgent()
        with patch.object(
            agent, "_gemini_judge", side_effect=RuntimeError("503")
        ):
            v = agent.judge("feline diabetes", "some answer")
            assert v.verdict == "PARTIAL"
            assert v.confidence == 0.5
            assert v.method == "fallback"

    def test_json_parse_failure_falls_back(self):
        agent = RelevanceJudgeAgent()
        mock_response = MagicMock()
        mock_response.text = "not valid json {broken"
        with patch("google.genai.Client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                mock_response
            )
            with patch.dict("os.environ", {"GOOGLE_API_KEY": "dummy"}):
                v = agent.judge("q", "a")
        assert v.verdict == "PARTIAL"
        assert v.method == "fallback"

    def test_no_api_key_falls_back(self):
        agent = RelevanceJudgeAgent()
        import os
        # Clear env key in isolated scope
        with patch.dict(os.environ, {}, clear=True):
            v = agent.judge("q", "a")
        # Empty env may still trigger fallback branch
        assert v.verdict in ("PARTIAL", "FAIL")
