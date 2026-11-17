from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nearswap.domain.listing import Listing, ListingUpdate


class ListingState(ABC):
    """State arayüzü. Her ConcreteState, izin vermediği işlemde InvalidTransitionError fırlatır.

    Durum geçişi listing.transition_to(YeniDurum()) ile yapılır.
    `if listing.status == ...` yığınları yazılmaz; kalıbın amacı bu.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def publish(self, listing: Listing) -> None: ...

    @abstractmethod
    def reserve(self, listing: Listing) -> None: ...

    @abstractmethod
    def mark_sold(self, listing: Listing) -> None: ...

    @abstractmethod
    def cancel_reservation(self, listing: Listing) -> None: ...

    @abstractmethod
    def edit(self, listing: Listing, update: ListingUpdate) -> None: ...
