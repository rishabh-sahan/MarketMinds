"""How the decision-log store reaches the graph.

The web app swaps the markdown decision log for a database-backed one. The
obvious way to do that — put the object in the ``config`` dict — is wrong, and
wrong in a way that is invisible until a run actually starts:
``MarketMindsGraph.__init__`` hands its config to ``set_config``, which
deep-copies it. A live store holds a SQLAlchemy session factory, which holds
module references, and ``deepcopy`` raises ``TypeError: cannot pickle 'module'
object``. Every run then fails during construction, before a single agent runs.

These tests pin the arrangement that avoids it: the store is a constructor
parameter, and whatever ends up in ``config`` stays copyable.
"""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

from backend.database import SessionLocal
from backend.services.db_memory import DatabaseMemoryLog
from backend.services.run_service import _build_config
from marketminds.dataflows.config import set_config


def _payload(**overrides) -> dict:
    payload = {
        "llm_provider": "openai",
        "deep_think_llm": "gpt-5.4",
        "quick_think_llm": "gpt-5.4-mini",
        "max_debate_rounds": 1,
        "max_risk_discuss_rounds": 1,
        "output_language": "English",
    }
    payload.update(overrides)
    return payload


@pytest.mark.unit
class TestStoreIsNotCopyable:
    """Why the store cannot travel in `config`."""

    def test_database_memory_log_cannot_be_deep_copied(self):
        log = DatabaseMemoryLog(SessionLocal, user_id="user-1")

        with pytest.raises(TypeError):
            deepcopy(log)

    def test_a_config_carrying_the_store_breaks_set_config(self):
        """The exact failure this arrangement exists to prevent."""
        config = _build_config(_payload())
        config["memory_log"] = DatabaseMemoryLog(SessionLocal, user_id="user-1")

        with pytest.raises(TypeError):
            set_config(config)


@pytest.mark.unit
class TestRunConfigStaysCopyable:
    """What the backend actually builds must survive the graph's deep copy."""

    def test_web_run_config_survives_set_config(self):
        # Mirrors what _run_analysis assembles before constructing the graph.
        config = {**_build_config(_payload()), "save_state_logs": False}

        set_config(config)  # must not raise

    def test_config_with_a_caller_api_key_survives(self):
        config = {**_build_config(_payload(api_key="sk-test")), "save_state_logs": False}

        set_config(config)


@pytest.mark.unit
class TestGraphAcceptsTheStore:
    def _build_graph(self, **kwargs):
        from marketminds.graph.trading_graph import MarketMindsGraph

        config = _build_config(_payload())
        config.update({"results_dir": ".", "data_cache_dir": "."})

        # set_config is deliberately NOT patched: it is the thing that broke,
        # so patching it would hide exactly the regression under test.
        with patch("marketminds.graph.trading_graph.create_llm_client") as factory, \
             patch("marketminds.graph.trading_graph.GraphSetup"), \
             patch("os.makedirs"):
            factory.return_value.get_llm.return_value = MagicMock()
            return MarketMindsGraph(config=config, **kwargs)

    def test_injected_store_is_used(self):
        log = DatabaseMemoryLog(SessionLocal, user_id="user-1")

        graph = self._build_graph(memory_log=log)

        assert graph.memory_log is log

    def test_default_is_the_markdown_log(self):
        """The CLI and local runs must keep the file-backed log."""
        from marketminds.agents.utils.memory import TradingMemoryLog

        graph = self._build_graph()

        assert isinstance(graph.memory_log, TradingMemoryLog)
