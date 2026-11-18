"""Chain of Responsibility kalıbı: yayın öncesi ilan denetimi (LLM literatüründeki Guardrail).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from decimal import Decimal

from nearswap.ai import AIService
from nearswap.models import Listing, ModerationResult, turkish_lower

DEFAULT_BANNED_WORDS: frozenset[str] = frozenset(
    {"silah", "tabanca", "uyuşturucu", "esrar", "sahte kimlik", "sahte rapor", "kaçak"}
)

DEFAULT_MAX_PRICE = Decimal("50000")


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


def _listing_text(listing: Listing) -> str:
    return f"{listing.title}\n{listing.description}"


class BannedWordsHandler(ModerationHandler):
    """Başlık ve açıklamada yasaklı kelime arar.

    Karşılaştırma turkish_lower ile yapılır ("SİLAH" da yakalanır). Kelimenin başına ve
    sonuna bakılır; böylece "esrar" yasaklıyken "esrarengiz bir tablo" reddedilmez.
    """

    def __init__(self, banned_words: Iterable[str] = DEFAULT_BANNED_WORDS) -> None:
        super().__init__()
        words = sorted({turkish_lower(w).strip() for w in banned_words if w.strip()})
        self._patterns = [(w, re.compile(rf"(?<!\w){re.escape(w)}(?!\w)")) for w in words]

    def handle(self, listing: Listing) -> ModerationResult:
        text = turkish_lower(_listing_text(listing))
        for word, pattern in self._patterns:
            if pattern.search(text):
                return ModerationResult.reject(
                    f"Yasaklı kelime: '{word}'", checked_by=type(self).__name__
                )
        return self._pass_to_next(listing)


class PriceSanityHandler(ModerationHandler):
    """Fiyatın makul olup olmadığını denetler.

    Fiyatın 0'dan büyük olmasını Builder zorunlu tutar; burada üst sınır denetlenir.
    Varsayılan üst sınır 50.000 TL.
    """

    def __init__(self, max_price: Decimal = DEFAULT_MAX_PRICE) -> None:
        super().__init__()
        self._max_price = max_price

    def handle(self, listing: Listing) -> ModerationResult:
        if listing.price > self._max_price:
            return ModerationResult.reject(
                f"Fiyat üst sınırı aşıyor ({self._max_price} TL)",
                checked_by=type(self).__name__,
            )
        return self._pass_to_next(listing)


class AIModerationHandler(ModerationHandler):
    """İlan metnini yapay zekâya denetletir. Zincirin SONUNDA durmalı.

    Yapay zekâya yalnızca AIService (Adapter'ın Target arayüzü) üzerinden erişir; hangi
    sağlayıcının kullanıldığını bilmez. Adapter ile Chain of Responsibility burada buluşur.
    """

    def __init__(self, ai: AIService) -> None:
        super().__init__()
        self._ai = ai

    def handle(self, listing: Listing) -> ModerationResult:
        result = self._ai.moderate(_listing_text(listing))
        if not result.approved:
            return ModerationResult.reject(
                result.reason or "Yapay zekâ denetimi onaylamadı",
                checked_by=type(self).__name__,
            )
        return self._pass_to_next(listing)


def build_default_chain(ai: AIService) -> ModerationHandler:
    """Varsayılan zinciri kurar ve başını döner."""
    head = BannedWordsHandler()
    head.set_next(PriceSanityHandler()).set_next(AIModerationHandler(ai))
    return head
