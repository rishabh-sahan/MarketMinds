import unittest

import pytest

from cli.utils import normalize_ticker_symbol
from marketminds.agents.utils.agent_utils import build_instrument_context
from marketminds.dataflows.india import (
    NotAnIndianTickerError,
    benchmark_for,
    format_inr,
    resolve_ticker,
    split_suffix,
)


@pytest.mark.unit
class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_preserves_exchange_suffix(self):
        self.assertEqual(normalize_ticker_symbol(" reliance.ns "), "RELIANCE.NS")

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context("RELIANCE.NS")
        self.assertIn("RELIANCE.NS", context)
        self.assertIn("exchange suffix", context)

    def test_build_instrument_context_names_exchange_and_index(self):
        nse = build_instrument_context("INFY.NS")
        self.assertIn("NSE", nse)
        self.assertIn("Nifty 50", nse)

        bse = build_instrument_context("RELIANCE.BO")
        self.assertIn("BSE", bse)
        self.assertIn("Sensex", bse)

    def test_build_instrument_context_requires_rupees(self):
        context = build_instrument_context("TCS.NS")
        self.assertIn("rupees", context)
        self.assertIn("₹", context)


@pytest.mark.unit
class SuffixTests(unittest.TestCase):
    def test_split_suffix_indian(self):
        self.assertEqual(split_suffix("RELIANCE.NS"), ("RELIANCE", ".NS"))
        self.assertEqual(split_suffix("reliance.bo"), ("RELIANCE", ".BO"))

    def test_split_suffix_bare(self):
        self.assertEqual(split_suffix("INFY"), ("INFY", None))

    def test_split_suffix_foreign(self):
        self.assertEqual(split_suffix("7203.T"), ("7203", ".T"))

    def test_benchmark_follows_exchange(self):
        """NSE listings are measured against the Nifty 50, BSE against the Sensex."""
        self.assertEqual(benchmark_for("RELIANCE.NS"), "^NSEI")
        self.assertEqual(benchmark_for("RELIANCE.BO"), "^BSESN")
        # A bare name resolves to NSE, so it takes the Nifty 50.
        self.assertEqual(benchmark_for("INFY"), "^NSEI")


@pytest.mark.unit
class ResolveTickerTests(unittest.TestCase):
    """Resolution rules that hold without touching the network."""

    def test_foreign_suffix_rejected_by_market_name(self):
        for symbol, market in [("7203.T", "Tokyo"), ("0700.HK", "Hong Kong"), ("VOD.L", "London")]:
            with self.assertRaises(NotAnIndianTickerError) as ctx:
                resolve_ticker(symbol)
            self.assertIn(market, str(ctx.exception))

    def test_bse_scrip_code_rejected_with_guidance(self):
        with self.assertRaises(NotAnIndianTickerError) as ctx:
            resolve_ticker("500325")
        self.assertIn("scrip code", str(ctx.exception))

    def test_empty_input_rejected(self):
        with self.assertRaises(NotAnIndianTickerError):
            resolve_ticker("   ")


@pytest.mark.unit
class RupeeFormattingTests(unittest.TestCase):
    def test_lakh_crore_grouping(self):
        """Indian grouping puts the last three digits together, then pairs."""
        self.assertEqual(format_inr(1234567.5), "₹12,34,567.50")
        self.assertEqual(format_inr(999), "₹999.00")
        self.assertEqual(format_inr(100000), "₹1,00,000.00")

    def test_negative_sign_precedes_symbol(self):
        self.assertEqual(format_inr(-45678.9), "-₹45,678.90")


if __name__ == "__main__":
    unittest.main()
