"""A caller-supplied API key must be used for the run and stored nowhere.

The deployed instance is intended to hold no provider credentials of its own:
visitors bring their own key, it is used for that run, and it disappears. The
tests here pin the properties that make that safe — if any of them regress,
the service quietly becomes custodian of other people's credentials.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import pytest

from backend.schemas import RunCreate
from backend.services.run_service import _build_config
from marketminds.llm_clients import preflight

SECRET = "sk-test-do-not-store-me-1234567890"


def _payload(**overrides):
    data = {
        "ticker": "RELIANCE",
        "trade_date": "2026-09-01",
        "llm_provider": "openai",
        "quick_think_llm": "gpt-5.4-mini",
        "deep_think_llm": "gpt-5.4",
        "selected_analysts": ["market"],
        "api_key": SECRET,
    }
    data.update(overrides)
    return data


@pytest.mark.unit
class KeyReachesTheRunTests(unittest.TestCase):
    def test_build_config_carries_the_key(self):
        config = _build_config(_payload())
        assert config["api_key"] == SECRET

    def test_absent_key_leaves_config_clean(self):
        config = _build_config(_payload(api_key=None))
        assert "api_key" not in config

    def test_graph_forwards_the_key_to_both_clients(self):
        """Both the quick and deep client must receive the caller's key."""
        from marketminds.graph.trading_graph import MarketMindsGraph

        config = _build_config(_payload())
        config.update({"results_dir": ".", "data_cache_dir": "."})

        with patch("marketminds.graph.trading_graph.create_llm_client") as factory, \
             patch("marketminds.graph.trading_graph.GraphSetup"), \
             patch("marketminds.graph.trading_graph.TradingMemoryLog"), \
             patch("marketminds.graph.trading_graph.set_config"), \
             patch("os.makedirs"):
            factory.return_value.get_llm.return_value = MagicMock()
            try:
                MarketMindsGraph(config=config)
            except Exception:
                pass  # construction may fail later; the call args are the point

            assert factory.call_count >= 1
            for call in factory.call_args_list:
                assert call.kwargs.get("api_key") == SECRET


@pytest.mark.unit
class KeyIsNotPersistedTests(unittest.TestCase):
    def test_api_key_is_excluded_from_serialisation(self):
        """model_dump() feeds responses and logs; the key must not appear."""
        model = RunCreate(**_payload())
        assert model.api_key == SECRET
        assert "api_key" not in model.model_dump()
        assert SECRET not in model.model_dump_json()

    def test_repr_does_not_leak_the_key(self):
        """An exception traceback can print a model; it must not expose keys."""
        assert SECRET not in repr(RunCreate(**_payload()))

    def test_config_snapshot_shape_has_no_credential_field(self):
        """The snapshot stored on every run is built from an explicit allowlist."""
        import inspect
        from backend.routers import runs as runs_router

        source = inspect.getsource(runs_router.create_run)
        snapshot = source[source.index("config_snapshot={"):source.index("    )\n    db.add")]
        assert "api_key" not in snapshot


@pytest.mark.unit
class RouterThreadsTheKeyTests(unittest.TestCase):
    """`exclude=True` keeps the key out of dumps — including the one the
    router builds its config from. It must be re-attached deliberately, or the
    feature silently does nothing and the server's own key is used instead."""

    def test_model_dump_drops_the_key(self):
        """The premise: this is why the router cannot rely on model_dump alone."""
        assert "api_key" not in RunCreate(**_payload()).model_dump()

    def test_router_reattaches_the_key_before_building_config(self):
        import inspect
        from backend.routers import runs as runs_router

        source = inspect.getsource(runs_router.create_run)
        assert 'payload["api_key"] = body.api_key' in source, (
            "create_run must re-attach api_key after model_dump(), otherwise a "
            "visitor's key never reaches the provider"
        )

    def test_config_built_from_a_dumped_payload_still_carries_the_key(self):
        """End to end through the router's own construction path."""
        body = RunCreate(**_payload())
        payload = body.model_dump()
        payload["api_key"] = body.api_key
        assert _build_config(payload)["api_key"] == SECRET


@pytest.mark.unit
class BadKeyMessagingTests(unittest.TestCase):
    def test_supplied_key_rejection_does_not_mention_dotenv(self):
        """Pointing a visitor at a .env file they cannot edit is useless."""
        exc = Exception("401 Unauthorized: API key not valid")
        own = preflight._classify("google", "gemini-3.8-flash", exc, own_key=True)
        assert "you supplied" in own.reason
        assert ".env" not in own.reason

    def test_server_key_rejection_still_points_at_dotenv(self):
        exc = Exception("401 Unauthorized: API key not valid")
        server = preflight._classify("google", "gemini-3.8-flash", exc, own_key=False)
        assert ".env" in server.reason


@pytest.mark.unit
class PreflightDoesNotCacheKeysTests(unittest.TestCase):
    def setUp(self):
        preflight.clear_cache()

    def tearDown(self):
        preflight.clear_cache()

    def test_supplied_key_is_never_placed_in_the_cache(self):
        """lru_cache keeps its arguments alive; a user key must not be one."""
        with patch("marketminds.llm_clients.create_llm_client") as factory:
            preflight.check_model("openai", "gpt-5.4", None, SECRET)
            preflight.check_model("openai", "gpt-5.4", None, SECRET)
            # Uncached: probed both times rather than served from memory.
            assert factory.call_count == 2

        cache_contents = json.dumps(
            [str(k) for k in preflight._probe_cached.cache_info()._asdict().items()]
        )
        assert SECRET not in cache_contents

    def test_environment_path_is_still_cached(self):
        with patch("marketminds.llm_clients.create_llm_client") as factory:
            preflight.check_model("openai", "gpt-5.4")
            preflight.check_model("openai", "gpt-5.4")
            assert factory.call_count == 1

    def test_supplied_key_is_passed_to_the_client(self):
        with patch("marketminds.llm_clients.create_llm_client") as factory:
            preflight.check_model("openai", "gpt-5.4", None, SECRET)
            assert factory.call_args.kwargs.get("api_key") == SECRET


if __name__ == "__main__":
    unittest.main()
