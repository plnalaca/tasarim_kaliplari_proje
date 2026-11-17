"""Listing (State Context) işlemleri o anki duruma devrediyor mu?"""

from decimal import Decimal

from nearswap.domain.listing import ListingUpdate
from tests.helpers import RecordingState, make_listing


def test_listing_delegates_every_action_to_current_state() -> None:
    state = RecordingState()
    listing = make_listing(state)

    listing.publish()
    listing.reserve()
    listing.cancel_reservation()
    listing.mark_sold()
    listing.edit(ListingUpdate(title="Yeni başlık"))

    assert state.calls == ["publish", "reserve", "cancel_reservation", "mark_sold", "edit"]


def test_transition_to_changes_the_state_that_receives_calls() -> None:
    first, second = RecordingState(), RecordingState()
    listing = make_listing(first)

    listing.transition_to(second)
    listing.reserve()

    assert first.calls == []
    assert second.calls == ["reserve"]


def test_apply_update_changes_only_given_fields() -> None:
    listing = make_listing(RecordingState())

    listing.apply_update(ListingUpdate(price=Decimal("120")))

    assert listing.price == Decimal("120")
    assert listing.title == "Çalışma lambası"
