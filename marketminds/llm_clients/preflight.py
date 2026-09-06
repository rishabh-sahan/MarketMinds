"""Check that a model is actually callable before a run commits to it.

A MarketMinds run takes minutes and spends real quota. Discovering that the
chosen model is retired, restricted to a paid tier, or misspelled *after* the
analyst team has started is expensive and confusing — the failure surfaces as
a provider stack trace partway through the pipeline.

This module makes one minimal request up front and turns whatever comes back
into a plain sentence. The provider's own errors are not usable as-is:

- Gemini answers a paid-tier-only model with ``429 RESOURCE_EXHAUSTED`` and
  "Please retry in 23s", when the real quota is ``limit: 0`` and no amount of
  waiting will help.
- Gemini answers a retired model with ``404 ... no longer available to new
  users``, buried in a JSON blob.
- Sarvam answers an oversized prompt with a context-window figure that
  contradicts what its own model list advertises.

Results are cached for the process: a run resolves the same two models many
times, and the check costs a network round-trip.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# Deliberately tiny: this is a reachability probe, not a generation.
_PROBE_PROMPT = "hi"


@dataclass(frozen=True)
class ModelCheck:
    """Outcome of probing one provider/model pair."""

    ok: bool
    reason: str = ""
    # True when retrying later could plausibly succeed (a real rate limit),
    # as opposed to a permanent block (retired model, wrong tier, bad key).
    retryable: bool = False

    def __bool__(self) -> bool:
        return self.ok


def _classify(provider: str, model: str, exc: Exception) -> ModelCheck:
    """Turn a provider exception into an actionable sentence."""
    msg = str(exc)
    low = msg.lower()

    # A zero quota is not a rate limit, however it is dressed up.
    if "limit: 0" in low or "limit:0" in low:
        return ModelCheck(
            False,
            f"'{model}' is not available on your {provider} plan — the free tier "
            f"allocates it zero quota. Pick a non-Pro model, or enable billing. "
            f"Retrying will not help despite what the provider's message says.",
        )

    if "no longer available" in low:
        return ModelCheck(
            False,
            f"'{model}' has been retired by {provider} and is no longer available "
            f"to new users. Choose a current model from the dropdown.",
        )

    if "not found" in low or "404" in low:
        return ModelCheck(
            False,
            f"{provider} does not recognise the model '{model}'. Check the spelling, "
            f"or pick one from the dropdown.",
        )

    if "api key" in low or "unauthenticated" in low or "401" in low or "invalid_api_key" in low:
        return ModelCheck(
            False,
            f"{provider} rejected the API key. Check the matching *_API_KEY entry in "
            f".env and restart the backend after changing it.",
        )

    if "429" in low or "resource_exhausted" in low or "rate limit" in low:
        return ModelCheck(
            False,
            f"{provider} is rate-limiting this key for '{model}'. This one may clear "
            f"on its own — wait a minute and try again.",
            retryable=True,
        )

    # Anything unrecognised: surface the provider's own words rather than
    # inventing a diagnosis.
    return ModelCheck(False, f"{provider} rejected '{model}': {msg[:240]}")


@lru_cache(maxsize=64)
def check_model(provider: str, model: str, backend_url: Optional[str] = None) -> ModelCheck:
    """Probe one model, returning whether it is usable and why not if it isn't.

    Cached, so the repeated checks a single run performs cost one round-trip.
    """
    if not model or model == "custom":
        return ModelCheck(
            False,
            "No model id was supplied. Pick a model, or enter one when choosing "
            "'Custom model ID'.",
        )

    try:
        from marketminds.llm_clients import create_llm_client

        llm = create_llm_client(provider=provider, model=model, base_url=backend_url).get_llm()
        llm.invoke(_PROBE_PROMPT)
        return ModelCheck(True)
    except Exception as exc:
        result = _classify(provider, model, exc)
        logger.info("Preflight rejected %s/%s: %s", provider, model, result.reason)
        return result


def context_window_from_error(exc: Exception) -> Optional[int]:
    """Extract a context-window size from a provider's overflow message.

    Providers that reject an oversized prompt usually name the true limit,
    which is the most reliable source for it — model listings can be stale.
    """
    match = re.search(r"context window of (\d+) tokens", str(exc))
    return int(match.group(1)) if match else None


def clear_cache() -> None:
    """Forget cached results — used when credentials change mid-process."""
    check_model.cache_clear()
