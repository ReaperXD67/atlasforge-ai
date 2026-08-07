from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

from ..exceptions import ProviderFailed, ProviderUnavailable
from ..logging import get_logger

T = TypeVar("T")


class Provider(ABC, Generic[T]):
    name: str

    @abstractmethod
    def available(self) -> bool:
        """Return whether required local configuration is present."""


@dataclass
class ProviderResult(Generic[T]):
    provider: str
    value: T


class ProviderChain(Generic[T]):
    def __init__(self, providers: Iterable[Provider[T]]) -> None:
        self.providers = list(providers)
        self.log = get_logger(component="provider_chain")

    def run(self, operation: str, invoke: Callable[[Provider[T]], T]) -> ProviderResult[T]:
        errors: list[str] = []
        for provider in self.providers:
            if not provider.available():
                errors.append(f"{provider.name}: unavailable")
                continue
            try:
                value = invoke(provider)
                self.log.info("provider_succeeded", operation=operation, provider=provider.name)
                return ProviderResult(provider=provider.name, value=value)
            except (ProviderUnavailable, ProviderFailed) as exc:
                errors.append(f"{provider.name}: {exc}")
                self.log.warning(
                    "provider_failed", operation=operation, provider=provider.name, error=str(exc)
                )
            except Exception as exc:  # provider boundaries intentionally isolate SDK failures
                errors.append(f"{provider.name}: {type(exc).__name__}: {exc}")
                self.log.exception(
                    "provider_unexpected_error",
                    operation=operation,
                    provider=provider.name,
                )
        raise ProviderFailed(f"All providers failed for {operation}: {' | '.join(errors)}")
