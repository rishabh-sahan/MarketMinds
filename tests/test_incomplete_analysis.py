"""An incomplete run must fail loudly rather than report a default rating.

Regression cover for a live failure: a HAL.NS run finished as "completed" with
a Hold rating while the Research Manager, Portfolio Manager, three risk
analysts and three of four analysts had all produced nothing. The rating came
from `parse_rating`'s fallback, not from any analysis, and the phantom Hold was
then written into the decision log that later runs read as prior experience.
"""

import unittest
from unittest.mock import MagicMock

import pytest

from marketminds.agents.utils.memory import TradingMemoryLog
from marketminds.agents.utils.rating import parse_rating
from marketminds.graph.trading_graph import IncompleteAnalysisError, MarketMindsGraph


def _graph_stub():
    g = MagicMock(spec=MarketMindsGraph)
    g._REQUIRED_SECTIONS = MarketMindsGraph._REQUIRED_SECTIONS
    g._ANALYST_SECTIONS = MarketMindsGraph._ANALYST_SECTIONS
    return g


def _complete_state():
    return {
        "market_report": "m" * 400,
        "sentiment_report": "s" * 400,
        "news_report": "n" * 400,
        "fundamentals_report": "f" * 400,
        "investment_plan": "plan",
        "trader_investment_plan": "proposal",
        "final_trade_decision": "**Rating**: Buy\n\nthesis",
        "investment_debate_state": {
            "bull_history": "Bull Researcher: a real argument",
            "bear_history": "Bear Researcher: a real argument",
            "judge_decision": "verdict",
        },
        "risk_debate_state": {
            "aggressive_history": "\nAggressive Analyst: a real argument",
            "conservative_history": "\nConservative Analyst: a real argument",
            "neutral_history": "\nNeutral Analyst: a real argument",
            "judge_decision": "verdict",
        },
    }


@pytest.mark.unit
class IncompleteRunTests(unittest.TestCase):
    def test_complete_run_passes(self):
        MarketMindsGraph._assert_analysis_complete(_graph_stub(), _complete_state())

    def test_missing_decision_raises(self):
        state = _complete_state()
        state["final_trade_decision"] = ""
        with self.assertRaises(IncompleteAnalysisError) as ctx:
            MarketMindsGraph._assert_analysis_complete(_graph_stub(), state)
        assert "no decision" in str(ctx.exception)

    def test_whitespace_only_decision_raises(self):
        state = _complete_state()
        state["final_trade_decision"] = "   \n  "
        with self.assertRaises(IncompleteAnalysisError):
            MarketMindsGraph._assert_analysis_complete(_graph_stub(), state)

    def test_label_only_risk_history_counts_as_empty(self):
        """'\\nAggressive Analyst: ' with nothing after it is not an argument."""
        state = _complete_state()
        state["final_trade_decision"] = ""
        state["risk_debate_state"]["aggressive_history"] = "\nAggressive Analyst: "
        with self.assertRaises(IncompleteAnalysisError) as ctx:
            MarketMindsGraph._assert_analysis_complete(_graph_stub(), state)
        assert "aggressive_history" in str(ctx.exception)

    def test_error_names_every_empty_section(self):
        state = _complete_state()
        state.update({
            "final_trade_decision": "",
            "investment_plan": "",
            "news_report": "",
        })
        with self.assertRaises(IncompleteAnalysisError) as ctx:
            MarketMindsGraph._assert_analysis_complete(_graph_stub(), state)
        message = str(ctx.exception)
        assert "Research Manager" in message
        assert "News Analyst" in message
        assert "Portfolio Manager" in message

    def test_absent_analyst_is_not_reported_missing(self):
        """A team that excluded an analyst must not be flagged for its absence."""
        state = _complete_state()
        del state["news_report"]
        MarketMindsGraph._assert_analysis_complete(_graph_stub(), state)

    def test_empty_sections_without_a_missing_decision_do_not_raise(self):
        """A rating exists, so the run stands; the gaps are logged, not fatal."""
        state = _complete_state()
        state["sentiment_report"] = ""
        MarketMindsGraph._assert_analysis_complete(_graph_stub(), state)


@pytest.mark.unit
class PhantomRatingTests(unittest.TestCase):
    def test_parse_rating_still_defaults_for_prose(self):
        """The fallback is fine for real prose that omits an explicit label."""
        assert parse_rating("the case is finely balanced") == "Hold"

    def test_empty_decision_is_never_logged(self, ):
        """An empty decision must not become a Hold entry in the decision log."""
        import tempfile
        import pathlib

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "mem.md"
            log = TradingMemoryLog({"memory_log_path": str(path)})

            log.store_decision("HAL.NS", "2026-09-07", "")
            log.store_decision("HAL.NS", "2026-09-07", "   \n ")
            assert log.load_entries() == [], "empty decisions must not be recorded"

            log.store_decision("HAL.NS", "2026-09-07", "**Rating**: Buy\n\nreal thesis")
            entries = log.load_entries()
            assert len(entries) == 1
            assert entries[0]["rating"] == "Buy"


if __name__ == "__main__":
    unittest.main()
