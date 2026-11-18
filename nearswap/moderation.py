"""Chain of Responsibility kalıbı: yayın öncesi ilan denetimi (Guardrail).

Roller:
    Handler          -> ModerationHandler
    ConcreteHandler  -> BannedWordsHandler, PriceSanityHandler, AIModerationHandler
    Client           -> service.ListingService

Ucuz kontroller önce, yapay zekâ kontrolü en sonda çalışır; böylece gereksiz API çağrısı
yapılmaz. Bir halka reddederse zincir durur ve reddetme sebebi döner. Yeni bir kontrol
eklemek için yeni bir ModerationHandler yazıp zincire bağlamak yeterli.

AIModerationHandler, yapay zekâya AIService (Adapter) üzerinden erişir.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from nearswap.ai import AIService
from nearswap.models import Listing, ModerationResult, turkish_lower

DEFAULT_BANNED_WORDS = frozenset(
    {"silah", "tabanca", "uyuşturucu", "esrar", "alkol", "sigara", "reçeteli", "sahte"}
)
DEFAULT_MAX_PRICE = Decimal("50000")


class ModerationHandler(ABC):
    def __init__(self) -> None:
        self._next: ModerationHandler | None = None

    def set_next(self, handler: ModerationHandler) -> ModerationHandler:
        """Sonraki halkayı bağlar ve onu döner: a.set_next(b).set_next(c)"""
        self._next = handler
        return handler

    @abstractmethod
    def handle(self, listing: Listing) -> ModerationResult:
        """Sorun bulursa ModerationResult.reject(...) döner, yoksa self._pass_to_next(listing)."""

    def _pass_to_next(self, listing: Listing) -> ModerationResult:
        if self._next is None:
            return ModerationResult.approve()
        return self._next.handle(listing)


def _listing_text(listing: Listing) -> str:
    return f"{listing.title}\n{listing.description}"


class BannedWordsHandler(ModerationHandler):
    def __init__(self, banned_words: frozenset[str] = DEFAULT_BANNED_WORDS) -> None:
        super().__init__()
        self._banned_words = sorted(turkish_lower(w) for w in banned_words)

    def handle(self, listing: Listing) -> ModerationResult:
        text = turkish_lower(_listing_text(listing))
        for word in self._banned_words:
            if word in text:
                return ModerationResult.reject(f"Yasaklı kelime: '{word}'", checked_by="BannedWordsHandler")
        return self._pass_to_next(listing)


class PriceSanityHandler(ModerationHandler):
    def __init__(self, max_price: Decimal = DEFAULT_MAX_PRICE) -> None:
        super().__init__()
        self._max_price = max_price

    def handle(self, listing: Listing) -> ModerationResult:
        if listing.price > self._max_price:
            return ModerationResult.reject(
                f"Fiyat makul aralığın dışında (en fazla {self._max_price} TL).",
                checked_by="PriceSanityHandler",
            )
        return self._pass_to_next(listing)


class AIModerationHandler(ModerationHandler):
    def __init__(self, ai: AIService) -> None:
        super().__init__()
        self._ai = ai

    def handle(self, listing: Listing) -> ModerationResult:
        result = self._ai.moderate(_listing_text(listing))
        if not result.approved:
            return ModerationResult.reject(
                result.reason or "Yapay zekâ denetimi ilanı onaylamadı.",
                checked_by="AIModerationHandler",
            )
        return self._pass_to_next(listing)


def build_default_chain(ai: AIService) -> ModerationHandler:
    """BannedWords -> PriceSanity -> AIModeration"""
    head = BannedWordsHandler()
    head.set_next(PriceSanityHandler()).set_next(AIModerationHandler(ai))
    return head
