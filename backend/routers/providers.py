"""Providers router — exposes supported LLM providers and model catalogs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import json
import os
import time
from typing import List
from urllib.request import Request, urlopen

from backend.schemas import ProviderListItem, ProviderModels, ModelOption

router = APIRouter(prefix="/api/providers", tags=["providers"])

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_OPENROUTER_CACHE_TTL_SEC = 6 * 60 * 60
_openrouter_cache = {"ts": 0.0, "models": []}

# Display names for providers
_DISPLAY_NAMES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google (Gemini)",
    "xai": "xAI (Grok)",
    "deepseek": "DeepSeek",
    "qwen": "Qwen (International)",
    "qwen-cn": "Qwen (China)",
    "glm": "GLM / Zhipu (International)",
    "glm-cn": "GLM / Zhipu (China)",
    "minimax": "MiniMax (Global)",
    "minimax-cn": "MiniMax (China)",
    "sarvam": "Sarvam AI (India)",
    "openrouter": "OpenRouter",
    "ollama": "Ollama (Local)",
}


@router.get("", response_model=list[ProviderListItem])
def list_providers():
    """List all supported LLM providers."""
    from marketminds.llm_clients.api_key_env import PROVIDER_API_KEY_ENV

    providers = []
    for name, env_var in PROVIDER_API_KEY_ENV.items():
        # Providers that need no key (local runtimes) count as always ready.
        has_key = True if env_var is None else bool(os.getenv(env_var, "").strip())
        providers.append(ProviderListItem(
            name=name,
            display_name=_DISPLAY_NAMES.get(name, name),
            requires_key=env_var is not None,
            env_var=env_var,
            has_key=has_key,
        ))
    return providers


def _fetch_openrouter_models() -> List[ModelOption]:
    """Fetch OpenRouter models list, with a simple in-memory cache."""
    now = time.time()
    if _openrouter_cache["models"] and (now - _openrouter_cache["ts"] < _OPENROUTER_CACHE_TTL_SEC):
        return _openrouter_cache["models"]

    headers = {"Accept": "application/json"}
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = Request(_OPENROUTER_MODELS_URL, headers=headers)
    try:
        with urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read())
    except Exception:
        return [ModelOption(label="Custom model ID", value="custom")]

    items = payload.get("data", []) if isinstance(payload, dict) else []
    options: List[ModelOption] = [ModelOption(label="Custom model ID", value="custom")]
    for item in items:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id") or item.get("name")
        name = item.get("name") or model_id
        if not model_id:
            continue
        label = f"{model_id} — {name}" if name and name != model_id else model_id
        options.append(ModelOption(label=label, value=model_id))

    _openrouter_cache["models"] = options
    _openrouter_cache["ts"] = now
    return options


@router.get("/{provider_name}/models", response_model=ProviderModels)
def get_provider_models(provider_name: str):
    """Get available models for a provider."""
    from marketminds.llm_clients.model_catalog import MODEL_OPTIONS

    provider = provider_name.lower()
    if provider == "openrouter":
        options = _fetch_openrouter_models()
        return ProviderModels(provider=provider, quick=options, deep=options)
    if provider not in MODEL_OPTIONS:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found")

    options = MODEL_OPTIONS[provider]
    return ProviderModels(
        provider=provider,
        quick=[ModelOption(label=label, value=value) for label, value in options.get("quick", [])],
        deep=[ModelOption(label=label, value=value) for label, value in options.get("deep", [])],
    )
