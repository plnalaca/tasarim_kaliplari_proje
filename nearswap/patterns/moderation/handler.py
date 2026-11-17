from __future__ import annotations

from abc import ABC, abstractmethod

from nearswap.domain.ai_types import ModerationResult
from nearswap.domain.listing import Listing


class ModerationHandler(ABC):
    """Handler arayüzü.

    Her ConcreteHandler handle() içinde kendi kontrolünü yapar:
    - sorun bulursa ModerationResult.reject(...) döner (zincir durur),
    - sorun yoksa self._pass_to_next(listing) döner.
    """

    def __init__(self) -> None:
        self._next: ModerationHandler | None = None

    def set_next(self, handler: ModerationHandler) -> ModerationHandler:
        """Sonraki halkayı bağlar ve onu döner: a.set_next(b).set_next(c)"""
        self._next = handler
        return handler

    @abstractmethod
    def handle(self, listing: Listing) -> ModerationResult: ...

    def _pass_to_next(self, listing: Listing) -> ModerationResult:
        if self._next is None:
            return ModerationResult.approve()
        return self._next.handle(listing)
