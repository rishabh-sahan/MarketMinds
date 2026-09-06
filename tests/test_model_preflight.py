"""Preflight model checks — turning provider errors into actionable messages."""

import unittest
from unittest.mock import patch

import pytest

from marketminds.llm_clients.preflight import (
    ModelCheck,
    _classify,
    check_model,
    context_window_from_error,
)


@pytest.mark.unit
class ClassifyTests(unittest.TestCase):
    """Each provider failure mode must produce a different, useful sentence."""

    def test_zero_quota_is_not_reported_as_retryable(self):
        """A free tier with `limit: 0` never succeeds, however long you wait."""
        exc = Exception(
            "429 RESOURCE_EXHAUSTED. Quota exceeded for metric: "
            "generate_content_free_tier_requests, limit: 0, model: gemini-3.1-pro. "
            "Please retry in 23.8s."
        )
        result = _classify("google", "gemini-3.1-pro-preview", exc)
        assert not result.ok
        assert not result.retryable, "a zero allocation must not invite retries"
        assert "not available on your google plan" in result.reason
        assert "Retrying will not help" in result.reason

    def test_retired_model_says_so(self):
        exc = Exception(
            "404 NOT_FOUND. This model models/gemini-2.5-flash is no longer "
            "available to new users."
        )
        result = _classify("google", "gemini-2.5-flash", exc)
        assert not result.ok
        assert "retired" in result.reason
        assert not result.retryable

    def test_unknown_model_suggests_checking_spelling(self):
        exc = Exception("404 NOT_FOUND. Model not found: gemini-9-turbo")
        result = _classify("google", "gemini-9-turbo", exc)
        assert not result.ok
        assert "does not recognise" in result.reason

    def test_bad_key_points_at_the_env_file(self):
        exc = Exception("401 Unauthorized: invalid api key supplied")
        result = _classify("openai", "gpt-5.4", exc)
        assert not result.ok
        assert ".env" in result.reason

    def test_genuine_rate_limit_is_marked_retryable(self):
        """A real rate limit differs from a zero allocation and may clear."""
        exc = Exception("429 Too Many Requests: rate limit exceeded, slow down")
        result = _classify("anthropic", "claude-opus-5", exc)
        assert not result.ok
        assert result.retryable

    def test_unrecognised_error_surfaces_provider_wording(self):
        """Never invent a diagnosis for an error we do not recognise."""
        exc = Exception("teapot malfunction 418")
        result = _classify("sarvam", "sarvam-105b", exc)
        assert not result.ok
        assert "teapot malfunction" in result.reason


@pytest.mark.unit
class ContextWindowTests(unittest.TestCase):
    def test_extracts_window_from_overflow_message(self):
        exc = Exception(
            "prompt_tokens (31315) + max_tokens (2048) = 33363 exceeds the model "
            "context window of 32000 tokens for sarvam-105b-conversations."
        )
        assert context_window_from_error(exc) == 32000

    def test_returns_none_when_absent(self):
        assert context_window_from_error(Exception("something else")) is None


@pytest.mark.unit
class CheckModelTests(unittest.TestCase):
    def setUp(self):
        check_model.cache_clear()

    def tearDown(self):
        check_model.cache_clear()

    def test_missing_model_rejected_without_a_network_call(self):
        for value in ("", "custom"):
            result = check_model("google", value)
            assert not result.ok
            assert "No model id" in result.reason

    def test_successful_probe_returns_ok(self):
        with patch("marketminds.llm_clients.create_llm_client") as factory:
            assert check_model("google", "gemini-3.8-flash").ok
            factory.assert_called_once()

    def test_result_is_cached_so_a_run_probes_once(self):
        with patch("marketminds.llm_clients.create_llm_client") as factory:
            check_model("google", "gemini-3.8-flash")
            check_model("google", "gemini-3.8-flash")
            check_model("google", "gemini-3.8-flash")
            assert factory.call_count == 1

    def test_modelcheck_is_falsey_when_not_ok(self):
        assert not bool(ModelCheck(False, "nope"))
        assert bool(ModelCheck(True))


if __name__ == "__main__":
    unittest.main()
