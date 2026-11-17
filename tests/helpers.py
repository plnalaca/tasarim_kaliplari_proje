"""Testlerde ortak kullanılan yardımcılar."""

from __future__ import annotations

from decimal import Decimal

from nearswap.domain.category import Category
from nearswap.domain.listing import Listing, ListingUpdate
from nearswap.patterns.state.listing_state import ListingState


class RecordingState(ListingState):
    """Gerçek ConcreteState'ler yazılana kadar Context'in devrini sınamak için test durumu."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return "recording"

    def publish(self, listing: Listing) -> None:
        self.calls.append("publish")

    def reserve(self, listing: Listing) -> None:
        self.calls.append("reserve")

    def mark_sold(self, listing: Listing) -> None:
        self.calls.append("mark_sold")

    def cancel_reservation(self, listing: Listing) -> None:
        self.calls.append("cancel_reservation")

    def edit(self, listing: Listing, update: ListingUpdate) -> None:
        self.calls.append("edit")
        listing.apply_update(update)


def make_listing(state: ListingState, **overrides: object) -> Listing:
    fields: dict[str, object] = {
        "listing_id": "l-1",
        "room_id": "r-1",
        "seller_id": "u-1",
        "title": "Çalışma lambası",
        "price": Decimal("150"),
        "photos": ("https://example.com/lamba.jpg",),
        "category": Category.ELECTRONICS,
        "description": "Az kullanılmış.",
        "state": state,
    }
    fields.update(overrides)
    return Listing(**fields)  # type: ignore[arg-type]
