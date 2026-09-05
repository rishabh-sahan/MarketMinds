"""Tests for the Reddit OAuth path.

Reddit blocks all unauthenticated API traffic (403 on every User-Agent),
so the fetcher must authenticate or skip cleanly rather than issuing
requests that are guaranteed to fail.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import marketminds.dataflows.reddit as reddit


@pytest.fixture(autouse=True)
def _clear_token_cache():
    reddit._token_cache = (None, 0.0)
    yield
    reddit._token_cache = (None, 0.0)


@pytest.mark.unit
class TestCredentialHandling:
    def test_missing_credentials_makes_no_requests(self, monkeypatch):
        """Without credentials, fail fast — don't fire 23 doomed requests."""
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)

        with patch.object(reddit, "urlopen") as mock_open:
            out = reddit.fetch_reddit_posts("AAPL")

        mock_open.assert_not_called()
        assert "reddit unavailable" in out.lower()
        assert "REDDIT_CLIENT_ID" in out

    def test_partial_credentials_treated_as_missing(self, monkeypatch):
        monkeypatch.setenv("REDDIT_CLIENT_ID", "id-only")
        monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
        assert reddit._get_access_token() is None


@pytest.mark.unit
class TestTokenFlow:
    def _token_response(self, body: dict):
        class _Resp:
            def read(self_inner):
                return json.dumps(body).encode()
            def __enter__(self_inner):
                return self_inner
            def __exit__(self_inner, *a):
                return False
        return _Resp()

    def test_token_is_requested_and_cached(self, monkeypatch):
        monkeypatch.setenv("REDDIT_CLIENT_ID", "cid")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "csec")

        with patch.object(reddit, "urlopen") as mock_open:
            mock_open.return_value = self._token_response(
                {"access_token": "tok-123", "expires_in": 86400}
            )
            first = reddit._get_access_token()
            second = reddit._get_access_token()

        assert first == "tok-123" and second == "tok-123"
        # Second call must be served from cache, not a second HTTP round trip.
        assert mock_open.call_count == 1

    def test_token_request_uses_basic_auth_and_client_credentials(self, monkeypatch):
        monkeypatch.setenv("REDDIT_CLIENT_ID", "cid")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "csec")

        with patch.object(reddit, "urlopen") as mock_open:
            mock_open.return_value = self._token_response({"access_token": "t", "expires_in": 60})
            reddit._get_access_token()

        req = mock_open.call_args[0][0]
        assert req.full_url == "https://www.reddit.com/api/v1/access_token"
        assert req.get_header("Authorization").startswith("Basic ")
        assert b"grant_type=client_credentials" in req.data

    def test_auth_failure_degrades_to_placeholder(self, monkeypatch):
        monkeypatch.setenv("REDDIT_CLIENT_ID", "cid")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "bad")

        from urllib.error import HTTPError
        with patch.object(reddit, "urlopen", side_effect=HTTPError(
            "u", 401, "Unauthorized", None, None
        )):
            out = reddit.fetch_reddit_posts("AAPL")

        assert "reddit unavailable" in out.lower()


@pytest.mark.unit
class TestAuthenticatedFetch:
    def test_requests_go_to_oauth_host_with_bearer(self, monkeypatch):
        monkeypatch.setenv("REDDIT_CLIENT_ID", "cid")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "csec")
        monkeypatch.setattr(reddit, "_token_cache", ("tok-abc", 9e12))

        captured = []

        class _Resp:
            def read(self):
                return json.dumps({"data": {"children": []}}).encode()
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            captured.append(req)
            return _Resp()

        with patch.object(reddit, "urlopen", side_effect=fake_urlopen):
            reddit.fetch_reddit_posts("AAPL", subreddits=["stocks"], inter_request_delay=0)

        assert len(captured) == 1
        assert captured[0].full_url.startswith("https://oauth.reddit.com/r/stocks/search")
        assert captured[0].get_header("Authorization") == "Bearer tok-abc"
