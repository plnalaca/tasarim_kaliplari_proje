"""Chain of Responsibility: zincir mekanizması, somut halkalar ve varsayılan zincir."""

from decimal import Decimal

from nearswap.ai import FakeAIAdapter
from nearswap.models import Listing, ModerationResult
from nearswap.moderation import (
    AIModerationHandler,
    BannedWordsHandler,
    ModerationHandler,
    PriceSanityHandler,
    build_default_chain,
)
from tests.helpers import make_listing


class _AlwaysPass(ModerationHandler):
    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self._log = log

    def handle(self, listing: Listing) -> ModerationResult:
        self._log.append("pass")
        return self._pass_to_next(listing)


class _AlwaysReject(ModerationHandler):
    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self._log = log

    def handle(self, listing: Listing) -> ModerationResult:
        self._log.append("reject")
        return ModerationResult.reject("test", checked_by="_AlwaysReject")


def test_set_next_returns_the_next_handler_for_fluent_chaining() -> None:
    log: list[str] = []
    first, second = _AlwaysPass(log), _AlwaysPass(log)
    assert first.set_next(second) is second


def test_chain_approves_when_every_handler_passes() -> None:
    log: list[str] = []
    head = _AlwaysPass(log)
    head.set_next(_AlwaysPass(log)).set_next(_AlwaysPass(log))

    result = head.handle(make_listing())

    assert result.approved
    assert log == ["pass", "pass", "pass"]


def test_chain_stops_at_first_rejection() -> None:
    log: list[str] = []
    head = _AlwaysPass(log)
    head.set_next(_AlwaysReject(log)).set_next(_AlwaysPass(log))

    result = head.handle(make_listing())

    assert not result.approved
    assert result.checked_by == "_AlwaysReject"
    assert log == ["pass", "reject"]


# --- BannedWordsHandler -----------------------------------------------------------


def test_banned_word_in_title_is_rejected() -> None:
    result = BannedWordsHandler({"silah"}).handle(make_listing(title="Satılık silah kılıfı"))

    assert not result.approved
    assert result.reason == "Yasaklı kelime: 'silah'"
    assert result.checked_by == "BannedWordsHandler"


def test_banned_word_in_description_is_rejected() -> None:
    result = BannedWordsHandler({"silah"}).handle(make_listing(description="İçinde silah var."))

    assert not result.approved


def test_banned_word_matching_handles_turkish_capital_i() -> None:
    assert not BannedWordsHandler({"silah"}).handle(make_listing(title="SİLAH")).approved


def test_banned_word_inside_another_word_is_not_rejected() -> None:
    result = BannedWordsHandler({"esrar"}).handle(make_listing(title="Esrarengiz bir tablo"))

    assert result.approved


def test_clean_listing_passes_banned_words() -> None:
    assert BannedWordsHandler({"silah"}).handle(make_listing()).approved


# --- PriceSanityHandler -----------------------------------------------------------


def test_price_above_limit_is_rejected() -> None:
    result = PriceSanityHandler(Decimal("1000")).handle(make_listing(price=Decimal("1000.01")))

    assert not result.approved
    assert result.checked_by == "PriceSanityHandler"


def test_price_at_limit_passes() -> None:
    assert PriceSanityHandler(Decimal("1000")).handle(make_listing(price=Decimal("1000"))).approved


def test_default_price_limit_is_50000() -> None:
    handler = PriceSanityHandler()

    assert handler.handle(make_listing(price=Decimal("50000"))).approved
    assert not handler.handle(make_listing(price=Decimal("50001"))).approved


# --- AIModerationHandler ----------------------------------------------------------


def test_ai_handler_sends_title_and_description_to_ai_service() -> None:
    ai = FakeAIAdapter()

    AIModerationHandler(ai).handle(make_listing(title="Lamba", description="Sağlam."))

    assert ai.moderate_calls == ["Lamba\nSağlam."]


def test_ai_handler_rejects_when_ai_rejects() -> None:
    ai = FakeAIAdapter(flagged_words=frozenset({"kumar"}))

    result = AIModerationHandler(ai).handle(make_listing(description="Kumar masası"))

    assert not result.approved
    assert result.checked_by == "AIModerationHandler"
    assert result.reason == "Uygunsuz içerik: 'kumar'"


# --- Varsayılan zincir ------------------------------------------------------------


def test_default_chain_approves_clean_listing_after_calling_ai_once() -> None:
    ai = FakeAIAdapter()

    result = build_default_chain(ai).handle(make_listing())

    assert result.approved
    assert len(ai.moderate_calls) == 1


def test_default_chain_does_not_call_ai_when_banned_word_rejects() -> None:
    ai = FakeAIAdapter()

    result = build_default_chain(ai).handle(make_listing(title="Satılık tabanca"))

    assert result.checked_by == "BannedWordsHandler"
    assert ai.moderate_calls == []


def test_default_chain_does_not_call_ai_when_price_rejects() -> None:
    ai = FakeAIAdapter()

    result = build_default_chain(ai).handle(make_listing(price=Decimal("999999")))

    assert result.checked_by == "PriceSanityHandler"
    assert ai.moderate_calls == []
