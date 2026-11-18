"""Builder kalıbı: ilan oluşturma.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Self

from nearswap.models import Category, Listing, ListingDraft, ListingValidationError
from nearswap.states import DraftState

MAX_TITLE_LENGTH = 80


class ListingBuilder(ABC):
    @abstractmethod
    def reset(self) -> Self: ...

    @abstractmethod
    def set_owner(self, room_id: str, seller_id: str) -> Self: ...

    @abstractmethod
    def set_title(self, title: str) -> Self: ...

    @abstractmethod
    def set_price(self, price: Decimal) -> Self: ...

    @abstractmethod
    def add_photo(self, url: str) -> Self: ...

    @abstractmethod
    def set_category(self, category: Category) -> Self: ...

    @abstractmethod
    def set_description(self, description: str) -> Self: ...

    @abstractmethod
    def build(self) -> Listing:
        """Taslak durumunda geçerli bir Listing döner ya da ListingValidationError fırlatır."""


class StandardListingBuilder(ListingBuilder):
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> Self:
        self._room_id: str | None = None
        self._seller_id: str | None = None
        self._title: str | None = None
        self._price: Decimal | None = None
        self._photos: list[str] = []
        self._category: Category | None = None
        self._description = ""
        return self

    def set_owner(self, room_id: str, seller_id: str) -> Self:
        self._room_id = room_id.strip()
        self._seller_id = seller_id.strip()
        return self

    def set_title(self, title: str) -> Self:
        self._title = title.strip()
        return self

    def set_price(self, price: Decimal) -> Self:
        self._price = price
        return self

    def add_photo(self, url: str) -> Self:
        self._photos.append(url)
        return self

    def set_category(self, category: Category) -> Self:
        self._category = category
        return self

    def set_description(self, description: str) -> Self:
        self._description = description.strip()
        return self

    def build(self) -> Listing:
        room_id, seller_id = self._room_id, self._seller_id
        title, price, category = self._title, self._price, self._category

        problems: list[str] = []
        if not room_id or not seller_id:
            problems.append("İlanın odası ve satıcısı belirtilmeli.")
        if not title:
            problems.append("Başlık boş olamaz.")
        elif len(title) > MAX_TITLE_LENGTH:
            problems.append(f"Başlık en fazla {MAX_TITLE_LENGTH} karakter olabilir.")
        if price is None:
            problems.append("Fiyat girilmeli.")
        elif price <= 0:
            problems.append("Fiyat sıfırdan büyük olmalı.")
        if not self._photos:
            problems.append("En az bir fotoğraf eklenmeli.")
        if category is None:
            problems.append("Kategori seçilmeli.")

        if problems or not room_id or not seller_id or not title or price is None or category is None:
            raise ListingValidationError(problems)

        listing = Listing(
            listing_id=uuid.uuid4().hex[:8],
            room_id=room_id,
            seller_id=seller_id,
            title=title,
            price=price,
            photos=tuple(self._photos),
            category=category,
            description=self._description,
            state=DraftState(),
        )
        self.reset()
        return listing


class ListingDirector:
    """İki kurma senaryosu sunar: kullanıcı formundan ve yapay zekâ taslağından."""

    def __init__(self, builder: ListingBuilder) -> None:
        self._builder = builder

    def from_form(
        self,
        *,
        room_id: str,
        seller_id: str,
        title: str,
        price: Decimal,
        category: Category,
        description: str,
        photo_urls: list[str],
    ) -> Listing:
        """Kullanıcının elle doldurduğu formdan ilan kurar."""
        builder = (
            self._builder.reset()
            .set_owner(room_id, seller_id)
            .set_title(title)
            .set_price(price)
            .set_category(category)
            .set_description(description)
        )
        for url in photo_urls:
            builder.add_photo(url)
        return builder.build()

    def from_ai_draft(
        self,
        draft: ListingDraft,
        *,
        photo_url: str,
        room_id: str,
        seller_id: str,
        title: str | None = None,
        price: Decimal | None = None,
        category: Category | None = None,
        description: str | None = None,
    ) -> Listing:
        """Yapay zekâ taslağından başlar; kullanıcının verdiği her alan taslaktakinin yerine geçer.

        Yapay zekâ kategoriyi ya da açıklamayı yanlış tahmin edebilir; kullanıcı bunları da
        düzeltebilir. Verilmeyen (None) alanlar taslaktan alınır.
        """
        return (
            self._builder.reset()
            .set_owner(room_id, seller_id)
            .add_photo(photo_url)
            .set_category(category if category is not None else draft.category)
            .set_description(description if description is not None else draft.description)
            .set_title(title if title else draft.title)
            .set_price(price if price is not None else draft.suggested_price)
            .build()
        )
