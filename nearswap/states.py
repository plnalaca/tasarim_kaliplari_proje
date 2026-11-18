"""State kalıbı: ilan durumu."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from nearswap.models import InvalidTransitionError

if TYPE_CHECKING:
    from nearswap.models import Listing


class ListingState(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    def publish(self, listing: Listing) -> None:
        raise InvalidTransitionError(self.name, "yayınla")

    def reserve(self, listing: Listing) -> None:
        raise InvalidTransitionError(self.name, "rezerve et")

    def mark_sold(self, listing: Listing) -> None:
        raise InvalidTransitionError(self.name, "satıldı olarak işaretle")

    def cancel_reservation(self, listing: Listing) -> None:
        raise InvalidTransitionError(self.name, "rezervasyonu iptal et")


class DraftState(ListingState):
    """Builder'ın oluşturduğu, henüz denetimden geçmemiş ilan."""

    @property
    def name(self) -> str:
        return "taslak"

    def publish(self, listing: Listing) -> None:
        listing.transition_to(ActiveState())


class ActiveState(ListingState):
    """Yayında, oda üyelerinin görebildiği ilan."""

    @property
    def name(self) -> str:
        return "aktif"

    def reserve(self, listing: Listing) -> None:
        listing.transition_to(ReservedState())

    def mark_sold(self, listing: Listing) -> None:
        listing.transition_to(SoldState())


class ReservedState(ListingState):
    """Bir alıcıyla anlaşılmış, buluşma bekleyen ilan."""

    @property
    def name(self) -> str:
        return "rezerve"

    def mark_sold(self, listing: Listing) -> None:
        listing.transition_to(SoldState())

    def cancel_reservation(self, listing: Listing) -> None:
        listing.transition_to(ActiveState())


class SoldState(ListingState):
    """Satışı tamamlanmış ilan. Hiçbir işleme izin vermez."""

    @property
    def name(self) -> str:
        return "satildi"
