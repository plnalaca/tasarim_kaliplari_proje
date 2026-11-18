"""Ortak model, arayüzlerin soyutluğu ve State Context'in devri."""

import pytest

from nearswap.ai import AIService
from nearswap.builder import ListingBuilder
from nearswap.models import InvalidTransitionError, Listing, turkish_lower
from nearswap.moderation import ModerationHandler
from nearswap.states import ListingState
from tests.helpers import RecordingState, make_listing


@pytest.mark.parametrize(
    "interface",
    [ListingBuilder, AIService, ListingState, ModerationHandler],
    ids=lambda c: c.__name__,
)
def test_interface_cannot_be_instantiated(interface: type) -> None:
    with pytest.raises(TypeError):
        interface()


def test_turkish_lower_handles_dotted_and_dotless_i() -> None:
    assert turkish_lower("SİLAH") == "silah"
    assert turkish_lower("IŞIK") == "ışık"
    assert turkish_lower("Çalışma Lambası") == "çalışma lambası"


def test_listing_delegates_every_action_to_current_state() -> None:
    state = RecordingState()
    listing = make_listing(state)

    listing.publish()
    listing.reserve()
    listing.cancel_reservation()
    listing.mark_sold()

    assert state.calls == ["publish", "reserve", "cancel_reservation", "mark_sold"]


def test_transition_to_changes_the_state_that_receives_calls() -> None:
    first, second = RecordingState(), RecordingState()
    listing = make_listing(first)

    listing.transition_to(second)
    listing.reserve()

    assert first.calls == []
    assert second.calls == ["reserve"]


class _NothingAllowed(ListingState):
    @property
    def name(self) -> str:
        return "kapalı"


# Hata mesajı kullanıcıya (API 409 yanıtında) gösterildiği için işlem adı Türkçe.
ACTION_LABELS = {
    "publish": "yayınla",
    "reserve": "rezerve et",
    "mark_sold": "satıldı olarak işaretle",
    "cancel_reservation": "rezervasyonu iptal et",
}


@pytest.mark.parametrize("action", list(ACTION_LABELS))
def test_state_default_behaviour_is_invalid_transition(action: str) -> None:
    listing: Listing = make_listing(_NothingAllowed())

    with pytest.raises(InvalidTransitionError) as error:
        getattr(listing, action)()

    assert error.value.action == ACTION_LABELS[action]
    assert error.value.state_name == "kapalı"
