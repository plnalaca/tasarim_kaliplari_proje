"""Ortak alan modeli: ilan, kategori, yapay zekâ veri tipleri, hatalar ve Türkçe metin yardımcısı.

Listing iki kalıpta rol alır:
- Builder kalıbında **Product**: doğrudan değil, ListingBuilder.build() ile oluşturulur.
- State kalıbında **Context**: durum işlemlerini o anki ListingState nesnesine devreder.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nearswap.states import ListingState


class Category(StrEnum):
    ELECTRONICS = "elektronik"
    FURNITURE = "mobilya"
    BOOKS = "kitap"
    CLOTHING = "giyim"
    KITCHEN = "mutfak"
    OTHER = "diger"


# --- Yapay zekâ servisleriyle taşınan, sağlayıcıdan bağımsız veri tipleri ----------------


@dataclass(frozen=True)
class ListingDraft:
    """AIService.draft_listing() çıktısı: fotoğraftan önerilen ilan taslağı."""

    title: str
    category: Category
    description: str
    suggested_price: Decimal


@dataclass(frozen=True)
class ModerationResult:
    """Bir denetimin sonucu. Hem AIService.moderate() hem de denetim zinciri döner."""

    approved: bool
    reason: str | None = None
    checked_by: str | None = None

    @classmethod
    def approve(cls, checked_by: str | None = None) -> ModerationResult:
        return cls(approved=True, checked_by=checked_by)

    @classmethod
    def reject(cls, reason: str, checked_by: str) -> ModerationResult:
        return cls(approved=False, reason=reason, checked_by=checked_by)


# --- Hatalar ------------------------------------------------------------------------------


class NearSwapError(Exception):
    """Projedeki tüm alan hatalarının ortak atası."""


class ListingValidationError(NearSwapError):
    """ListingBuilder.build() eksik ya da hatalı bir ilanı reddetti."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("İlan oluşturulamadı: " + " ".join(problems))
        self.problems = problems


class InvalidTransitionError(NearSwapError):
    """İlanın mevcut durumunda izin verilmeyen bir işlem denendi."""

    def __init__(self, state_name: str, action: str) -> None:
        super().__init__(f"'{state_name}' durumundaki ilan için '{action}' yapılamaz.")
        self.state_name = state_name
        self.action = action


class ModerationRejectedError(NearSwapError):
    """İlan denetim zincirinden geçemedi."""

    def __init__(self, result: ModerationResult) -> None:
        super().__init__(result.reason or "İlan denetimden geçemedi.")
        self.result = result


class ListingNotFoundError(NearSwapError):
    def __init__(self, listing_id: str) -> None:
        super().__init__(f"'{listing_id}' numaralı ilan bulunamadı.")


# --- Metin yardımcısı ---------------------------------------------------------------------

_TR_UPPER_TO_LOWER = str.maketrans({"İ": "i", "I": "ı"})


def turkish_lower(text: str) -> str:
    """Türkçeye uygun küçük harf. Python'un lower()/casefold() işlevleri İ ve I'yı yanlış çevirir:
    "SİLAH".casefold() sonucu "silah" değildir."""
    return text.translate(_TR_UPPER_TO_LOWER).lower()


# --- İlan ---------------------------------------------------------------------------------


class Listing:
    """İlan.

    - Builder kalıbında **Product**: doğrudan değil, ListingBuilder.build() ile oluşturulur.
    - State kalıbında **Context**: durum işlemlerini o anki ListingState nesnesine devreder.
    """

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

    @property
    def state(self) -> ListingState:
        return self._state

    @property
    def status(self) -> str:
        return self._state.name

    def transition_to(self, state: ListingState) -> None:
        """Durumu değiştirir. Yalnızca ConcreteState sınıfları çağırır."""
        self._state = state

    def publish(self) -> None:
        self._state.publish(self)

    def reserve(self) -> None:
        self._state.reserve(self)

    def mark_sold(self) -> None:
        self._state.mark_sold(self)

    def cancel_reservation(self) -> None:
        self._state.cancel_reservation(self)

    def __repr__(self) -> str:
        return f"Listing(id={self.listing_id!r}, title={self.title!r}, status={self.status!r})"
