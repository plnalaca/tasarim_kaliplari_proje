from decimal import Decimal

from nearswap.ai import FakeAIAdapter
from nearswap.models import Listing, ModerationResult, turkish_lower
from nearswap.moderation import (
    AIModerationHandler,
    BannedWordsHandler,
    ModerationHandler,
    PriceSanityHandler,
    build_default_chain,
)
from tests.helpers import make_listing


def test_clean_listing_passes_whole_chain_and_reaches_ai() -> None:
    ai = FakeAIAdapter()

    result = build_default_chain(ai).handle(make_listing())

    assert result.approved
    assert ai.moderate_calls == ["Çalışma lambası\nAz kullanılmış."]


def test_banned_word_stops_chain_before_ai_is_called() -> None:
    ai = FakeAIAdapter()

    result = build_default_chain(ai).handle(make_listing(description="Yanında SİGARA kutusu da var"))

    assert not result.approved
    assert result.checked_by == "BannedWordsHandler"
    assert ai.moderate_calls == []


def test_price_sanity_stops_chain_before_ai_is_called() -> None:
    ai = FakeAIAdapter()

    result = build_default_chain(ai).handle(make_listing(price="999999"))

    assert result.checked_by == "PriceSanityHandler"
    assert ai.moderate_calls == []


def test_ai_rejection_is_reported_by_ai_handler() -> None:
    ai = FakeAIAdapter(flagged_words=frozenset({"kopya"}))

    result = build_default_chain(ai).handle(make_listing(description="Orijinal değil, kopya saat"))

    assert not result.approved
    assert result.checked_by == "AIModerationHandler"
    assert result.reason == "Uygunsuz içerik: 'kopya'"


def test_new_handler_can_be_added_without_changing_others() -> None:
    class OnlyRoomA(ModerationHandler):
        def handle(self, listing: Listing) -> ModerationResult:
            if listing.room_id != "yurt-a":
                return ModerationResult.reject("Yanlış oda", checked_by="OnlyRoomA")
            return self._pass_to_next(listing)

    head = OnlyRoomA()
    head.set_next(BannedWordsHandler()).set_next(PriceSanityHandler(Decimal("100")))

    assert head.handle(make_listing(price="150")).checked_by == "PriceSanityHandler"


def test_set_next_returns_next_handler() -> None:
    first, second = BannedWordsHandler(), AIModerationHandler(FakeAIAdapter())
    assert first.set_next(second) is second


def test_turkish_lower() -> None:
    assert turkish_lower("SİLAH") == "silah"
    assert turkish_lower("IŞIK") == "ışık"
