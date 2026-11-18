"""Testlerde ortak kullanılan yardımcılar."""

from __future__ import annotations

from decimal import Decimal

from nearswap.models import Category, Listing
from nearswap.states import DraftState, ListingState


class RecordingState(ListingState):
    """Context'in her işlemi o anki duruma devrettiğini sınamak için test durumu."""

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


def make_listing(state: ListingState | None = None, **overrides: object) -> Listing:
    """Builder'dan geçmeden doğrudan bir ilan kurar. Varsayılan durum: taslak.

    Builder'ın doğrulamasını sınayan testler bunu değil, StandardListingBuilder'ı kullanır.
    """
    fields: dict[str, object] = {
        "listing_id": "l-1",
        "room_id": "r-1",
        "seller_id": "u-1",
        "title": "Çalışma lambası",
        "price": Decimal("150"),
        "photos": ("https://example.com/lamba.jpg",),
        "category": Category.ELECTRONICS,
        "description": "Az kullanılmış.",
        "state": state or DraftState(),
    }
    fields.update(overrides)
    return Listing(**fields)  # type: ignore[arg-type]
