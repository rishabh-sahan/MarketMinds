"""Tests for the Sarvam AI provider wiring.

Sarvam's /v1 chat-completions endpoint is OpenAI-compatible and accepts
``Authorization: Bearer <key>`` alongside its native ``api-subscription-key``
header, so it routes through the shared OpenAIClient with no subclass.
These tests pin the wiring: factory routing, base URL, key handling, and
catalog/validator agreement.

Note: class references are resolved through the module object rather than
imported by name. ``tests/test_ollama_base_url.py`` calls
``importlib.reload`` on ``openai_client``, which rebinds its classes; an
import-time reference would go stale and break isinstance checks depending
on test order.
"""

from __future__ import annotations

import pytest

import tradingagents.llm_clients.openai_client as openai_client
from tradingagents.llm_clients.api_key_env import get_api_key_env
from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS, get_known_models
from tradingagents.llm_clients.validators import validate_model


@pytest.mark.unit
class TestSarvamWiring:
    def test_factory_routes_to_openai_compatible_client(self):
        client = create_llm_client(provider="sarvam", model="sarvam-105b")
        assert isinstance(client, openai_client.OpenAIClient)
        assert client.provider == "sarvam"

    def test_provider_name_is_case_insensitive(self):
        assert create_llm_client(provider="Sarvam", model="sarvam-105b").provider == "sarvam"

    def test_default_base_url(self):
        assert openai_client._PROVIDER_BASE_URL["sarvam"] == "https://api.sarvam.ai/v1"

    def test_api_key_env_registered(self):
        assert get_api_key_env("sarvam") == "SARVAM_API_KEY"

    def test_get_llm_uses_sarvam_endpoint_and_key(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "sk_test_placeholder")
        llm = openai_client.OpenAIClient("sarvam-105b", provider="sarvam").get_llm()
        assert isinstance(llm, openai_client.NormalizedChatOpenAI)
        assert str(llm.openai_api_base) == "https://api.sarvam.ai/v1"
        assert llm.openai_api_key.get_secret_value() == "sk_test_placeholder"

    def test_explicit_base_url_overrides_default(self, monkeypatch):
        """A caller-supplied base_url (corporate proxy/gateway) must win."""
        monkeypatch.setenv("SARVAM_API_KEY", "sk_test_placeholder")
        llm = openai_client.OpenAIClient(
            "sarvam-105b", base_url="https://proxy.internal/v1", provider="sarvam"
        ).get_llm()
        assert str(llm.openai_api_base) == "https://proxy.internal/v1"

    def test_missing_key_raises_actionable_error(self, monkeypatch):
        monkeypatch.delenv("SARVAM_API_KEY", raising=False)
        with pytest.raises(ValueError, match="SARVAM_API_KEY"):
            openai_client.OpenAIClient("sarvam-105b", provider="sarvam").get_llm()

    def test_sarvam_does_not_use_responses_api(self, monkeypatch):
        """Only native OpenAI opts into /v1/responses; Sarvam stays on
        chat-completions, so the flag must be left unset rather than
        forced True."""
        monkeypatch.setenv("SARVAM_API_KEY", "sk_test_placeholder")
        llm = openai_client.OpenAIClient("sarvam-105b", provider="sarvam").get_llm()
        assert getattr(llm, "use_responses_api", None) is not True


@pytest.mark.unit
class TestSarvamCatalog:
    def test_catalog_exposes_both_tiers(self):
        assert set(MODEL_OPTIONS["sarvam"]) == {"quick", "deep"}
        assert MODEL_OPTIONS["sarvam"]["quick"]
        assert MODEL_OPTIONS["sarvam"]["deep"]

    def test_flagship_is_the_deep_default(self):
        assert MODEL_OPTIONS["sarvam"]["deep"][0][1] == "sarvam-105b"

    @pytest.mark.parametrize("model", ["sarvam-105b", "sarvam-105b-conversations"])
    def test_catalog_models_pass_validation(self, model):
        assert validate_model("sarvam", model)
        assert model in get_known_models()["sarvam"]

    def test_unknown_model_is_rejected(self):
        assert not validate_model("sarvam", "not-a-real-sarvam-model")
