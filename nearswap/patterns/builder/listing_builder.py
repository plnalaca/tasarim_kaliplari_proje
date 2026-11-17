from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Self

from nearswap.domain.category import Category
from nearswap.domain.listing import Listing


class ListingBuilder(ABC):
    """Builder arayüzü. İlanı adım adım kurar; doğrulama tek yerde, build() içinde yapılır.

    build() yalnızca yapısal kuralları denetler (fiyat > 0, en az bir fotoğraf, kategori
    geçerli, zorunlu alanlar dolu). İçerik politikası (yasaklı kelime, yapay zekâ denetimi)
    denetim zincirinin işidir.
    """

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
        """Geçerli bir Listing döner ya da ListingValidationError fırlatır."""
