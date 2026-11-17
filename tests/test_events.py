from nearswap.patterns.observer.events import ListingEvent, ListingSoldEvent, NewListingEvent


def test_events_share_common_base_and_get_timestamp() -> None:
    event = NewListingEvent(listing_id="l-1", room_id="r-1", seller_id="u-1", title="Lamba")
    sold = ListingSoldEvent(listing_id="l-1", room_id="r-1", seller_id="u-1")

    assert isinstance(event, ListingEvent)
    assert isinstance(sold, ListingEvent)
    assert event.occurred_at.tzinfo is not None
