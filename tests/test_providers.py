from __future__ import annotations

from daily_video_factory.exceptions import ProviderFailed
from daily_video_factory.providers.base import Provider, ProviderChain
from daily_video_factory.providers.text import extract_json


class FakeProvider(Provider[str]):
    def __init__(self, name: str, available: bool, result: str | None = None) -> None:
        self.name = name
        self._available = available
        self.result = result

    def available(self) -> bool:
        return self._available


def test_extract_json_from_fence() -> None:
    assert extract_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_provider_chain_falls_through() -> None:
    providers = [FakeProvider("first", False), FakeProvider("second", True, "done")]
    result = ProviderChain(providers).run(
        "test", lambda provider: provider.result or (_ for _ in ()).throw(ProviderFailed("no"))
    )
    assert result.provider == "second"
    assert result.value == "done"
