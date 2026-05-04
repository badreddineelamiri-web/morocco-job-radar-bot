"""AI provider adapters used by the Facebook post writer.

All secrets are read from environment variables. The bot tries providers in the
configured order and falls back to the local Arabic template if all providers
fail.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)
REQUEST_TIMEOUT = 45


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _provider_order(task: str = "facebook") -> list[str]:
    forced_provider = os.getenv("AI_PROVIDER", "auto").strip().lower()
    if forced_provider and forced_provider != "auto":
        return [forced_provider]

    env_name = f"AI_TASK_{task.upper()}_PROVIDER_ORDER"
    order = os.getenv(env_name) or os.getenv("AI_FINAL_PROVIDER_ORDER", "")
    return _split_csv(order) or ["openai"]


def _models_for(provider: str) -> list[str]:
    provider_upper = provider.upper()
    default_model = os.getenv(f"{provider_upper}_MODEL", "").strip()
    models = _split_csv(os.getenv(f"{provider_upper}_MODELS", ""))
    if default_model and default_model not in models:
        models.insert(0, default_model)

    try:
        max_models = int(os.getenv("AI_MAX_MODELS_PER_PROVIDER", "0"))
    except ValueError:
        max_models = 0
    if max_models > 0:
        models = models[:max_models]
    return models


def _chat_payload(model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    return {
        "model": model,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }


def _extract_openai_compatible(data: dict[str, Any]) -> str:
    return str(data["choices"][0]["message"]["content"])


def _call_openai_compatible(
    *,
    provider: str,
    endpoint: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    extra_headers: dict[str, str] | None = None,
) -> str:
    if not api_key:
        raise RuntimeError(f"{provider.upper()} API key is missing")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    response = requests.post(
        endpoint,
        headers=headers,
        json=_chat_payload(model, system_prompt, user_prompt),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    LOGGER.info("AI provider succeeded: %s (%s)", provider, model)
    return _extract_openai_compatible(response.json())


def _call_gemini(model: str, system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        json={
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "responseMimeType": "application/json",
            },
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    LOGGER.info("AI provider succeeded: gemini (%s)", model)
    return str(response.json()["candidates"][0]["content"]["parts"][0]["text"])


def _call_cohere(model: str, system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("COHERE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is missing")

    response = requests.post(
        "https://api.cohere.com/v2/chat",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    LOGGER.info("AI provider succeeded: cohere (%s)", model)
    content = data.get("message", {}).get("content", [])
    if content and isinstance(content, list):
        return str(content[0].get("text", ""))
    return str(data)


def _call_huggingface(model: str, system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("HUGGINGFACE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("HUGGINGFACE_API_KEY is missing")

    response = requests.post(
        f"https://api-inference.huggingface.co/models/{model}",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "inputs": f"{system_prompt}\n\n{user_prompt}",
            "parameters": {"temperature": 0.4, "return_full_text": False},
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    LOGGER.info("AI provider succeeded: huggingface (%s)", model)
    if isinstance(data, list) and data:
        return str(data[0].get("generated_text", data[0]))
    return str(data)


def _call_provider(provider: str, model: str, system_prompt: str, user_prompt: str) -> str:
    if provider == "gemini":
        return _call_gemini(model, system_prompt, user_prompt)
    if provider == "cohere":
        return _call_cohere(model, system_prompt, user_prompt)
    if provider == "huggingface":
        return _call_huggingface(model, system_prompt, user_prompt)
    if provider == "openai":
        return _call_openai_compatible(
            provider=provider,
            endpoint="https://api.openai.com/v1/chat/completions",
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    if provider == "groq":
        return _call_openai_compatible(
            provider=provider,
            endpoint="https://api.groq.com/openai/v1/chat/completions",
            api_key=os.getenv("GROQ_API_KEY", "").strip(),
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    if provider == "mistral":
        return _call_openai_compatible(
            provider=provider,
            endpoint="https://api.mistral.ai/v1/chat/completions",
            api_key=os.getenv("MISTRAL_API_KEY", "").strip(),
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    if provider == "nvidia":
        return _call_openai_compatible(
            provider=provider,
            endpoint="https://integrate.api.nvidia.com/v1/chat/completions",
            api_key=os.getenv("NVIDIA_API_KEY", "").strip(),
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    if provider == "together":
        return _call_openai_compatible(
            provider=provider,
            endpoint="https://api.together.xyz/v1/chat/completions",
            api_key=os.getenv("TOGETHER_API_KEY", "").strip(),
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    if provider == "openrouter":
        return _call_openai_compatible(
            provider=provider,
            endpoint="https://openrouter.ai/api/v1/chat/completions",
            api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            extra_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://github.com/"),
                "X-Title": os.getenv("OPENROUTER_APP_NAME", "Morocco Job Radar Bot"),
            },
        )
    raise RuntimeError(f"Unsupported AI provider: {provider}")


def generate_json_text(system_prompt: str, user_prompt: str, task: str = "facebook") -> str | None:
    for provider in _provider_order(task):
        models = _models_for(provider)
        if not models:
            LOGGER.info("AI provider skipped, no models configured: %s", provider)
            continue
        for model in models:
            try:
                return _call_provider(provider, model, system_prompt, user_prompt)
            except Exception as exc:
                LOGGER.warning("AI provider failed: %s (%s): %s", provider, model, exc)
    return None
