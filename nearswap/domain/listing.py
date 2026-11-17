"""İlan modeli.

Listing iki kalıpta rol alır:
- Builder kalıbında **Product**: doğrudan değil, ListingBuilder.build() ile oluşturulur.
- State kalıbında **Context**: durum işlemlerini o anki ListingState nesnesine devreder.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from nearswap.domain.category import Category

if TYPE_CHECKING:
    from nearswap.patterns.state.listing_state import ListingState


@dataclass(frozen=True)
class ListingUpdate:
    """edit() ile gönderilen değişiklikler. None bırakılan alan değişmez."""

    title: str | None = None
    price: Decimal | None = None
    description: str | None = None
    category: Category | None = None


class Listing:
    def __init__(
        self,
        *,
        listing_id: str,
        room_id: str,
        seller_id: str,
        title: str,
        price: Decimal,
        photos: tuple[str, ...],
        category: Category,
        description: str,
        state: ListingState,
    ) -> None:
        self.listing_id = listing_id
        self.room_id = room_id
        self.seller_id = seller_id
        self.title = title
        self.price = price
        self.photos = photos
        self.category = category
        self.description = description
        self._state = state

    # --- State: Context tarafı -------------------------------------------------

    @property
    def state(self) -> ListingState:
        return self._state

    def transition_to(self, state: ListingState) -> None:
        """Durumu değiştirir. Yalnızca ConcreteState sınıfları çağırmalı."""
        self._state = state

    def publish(self) -> None:
        self._state.publish(self)

    def reserve(self) -> None:
        self._state.reserve(self)

    def mark_sold(self) -> None:
        self._state.mark_sold(self)

    def cancel_reservation(self) -> None:
        self._state.cancel_reservation(self)

    def edit(self, update: ListingUpdate) -> None:
        self._state.edit(self, update)

    def apply_update(self, update: ListingUpdate) -> None:
        """Değişiklikleri uygular. Düzenlemeye izin veren ConcreteState çağırır."""
        if update.title is not None:
            self.title = update.title
        if update.price is not None:
            self.price = update.price
        if update.description is not None:
            self.description = update.description
        if update.category is not None:
            self.category = update.category

    def __repr__(self) -> str:
        return f"Listing(id={self.listing_id!r}, title={self.title!r}, state={self._state.name!r})"
