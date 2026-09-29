from __future__ import annotations

import json
import os
import re
from abc import abstractmethod
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from ..exceptions import ProviderFailed
from .base import Provider


def extract_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
        if not match:
            raise ProviderFailed("Model response did not contain a JSON object") from None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ProviderFailed(f"Model returned malformed JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ProviderFailed("Model response JSON must be an object")
    return value


class TextProvider(Provider[dict[str, Any]]):
    @abstractmethod
    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], temperature: float = 0.6
    ) -> dict[str, Any]:
        pass


class OpenRouterTextProvider(TextProvider):
    name = "openrouter"

    def __init__(self, model: str, timeout_seconds: int = 120) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds

    def available(self) -> bool:
        return bool(os.getenv("OPENROUTER_API_KEY"))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, ProviderFailed)),
        reraise=True,
    )
    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], temperature: float = 0.6
    ) -> dict[str, Any]:
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/ReaperXD67/atlasforge-ai",
                "X-OpenRouter-Title": "AtlasForge AI",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "daily_video", "strict": True, "schema": schema},
                },
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise ProviderFailed(
                f"OpenRouter returned HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderFailed("OpenRouter returned an unexpected response") from exc
        return extract_json(content)


class GeminiTextProvider(TextProvider):
    name = "gemini"

    def __init__(self, model: str, timeout_seconds: int = 120) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds

    def available(self) -> bool:
        return bool(os.getenv("GOOGLE_API_KEY"))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, ProviderFailed)),
        reraise=True,
    )
    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], temperature: float = 0.6
    ) -> dict[str, Any]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        response = httpx.post(
            url,
            headers={"x-goog-api-key": os.environ["GOOGLE_API_KEY"]},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "responseMimeType": "application/json",
                    "responseJsonSchema": schema,
                },
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise ProviderFailed(
                f"Gemini returned HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderFailed("Gemini returned an unexpected response") from exc
        return extract_json(text)


class OllamaTextProvider(TextProvider):
    name = "ollama"

    def __init__(self, model: str, timeout_seconds: int = 300) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")

    def available(self) -> bool:
        try:
            return httpx.get(f"{self.base_url}/api/tags", timeout=2).status_code == 200
        except httpx.HTTPError:
            return False

    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], temperature: float = 0.6
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "format": schema,
                "options": {"temperature": temperature, "num_ctx": 8192},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise ProviderFailed(f"Ollama returned HTTP {response.status_code}")
        try:
            return extract_json(response.json()["message"]["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderFailed("Ollama returned an unexpected response") from exc
