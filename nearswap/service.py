"""İlan servisi: dört kalıbı birbirine bağlayan uygulama katmanı.

store (JsonFileStore) verilirse ilanlar ve fotoğraflar diske kaydedilir, sunucu yeniden başlasa da
kalır. Verilmezse (testlerde) her şey bellekte tutulur.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from nearswap.ai import AIService
from nearswap.builder import ListingDirector
from nearswap.models import (
    Category,
    Listing,
    ListingDraft,
    ListingNotFoundError,
    ModerationRejectedError,
    NearSwapError,
)
from nearswap.moderation import ModerationHandler
from nearswap.storage import JsonFileStore


class ListingService:
    def __init__(
        self,
        ai: AIService,
        moderation: ModerationHandler,
        director: ListingDirector,
        store: JsonFileStore | None = None,
    ) -> None:
        self._ai = ai
        self._moderation = moderation
        self._director = director
        self._store = store
        self._listings: dict[str, Listing] = store.load_listings() if store else {}
        self._photos: dict[str, tuple[bytes, str]] = {}  # yalnızca store yokken kullanılır

    # --- Fotoğraflar ---------------------------------------------------------------------

    def save_photo(self, photo: bytes, mime_type: str) -> str:
        photo_id = uuid.uuid4().hex[:12]
        if self._store:
            self._store.save_photo(photo_id, photo, mime_type)
        else:
            self._photos[photo_id] = (photo, mime_type)
        return f"/photos/{photo_id}"

    def get_photo(self, photo_id: str) -> tuple[bytes, str] | None:
        if self._store:
            return self._store.load_photo(photo_id)
        return self._photos.get(photo_id)

    def _discard_photo(self, photo_url: str) -> None:
        photo_id = photo_url.rsplit("/", 1)[-1]
        if self._store:
            self._store.delete_photo(photo_id)
        else:
            self._photos.pop(photo_id, None)

    def _persist(self) -> None:
        if self._store:
            self._store.save_listings(self._listings.values())

    # --- İlan verme ----------------------------------------------------------------------

    def suggest_draft(self, photo: bytes, mime_type: str) -> ListingDraft:
        return self._ai.draft_listing(photo, mime_type)

    def create_from_form(
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
        listing = self._director.from_form(
            room_id=room_id,
            seller_id=seller_id,
            title=title,
            price=price,
            category=category,
            description=description,
            photo_urls=photo_urls,
        )
        return self._publish(listing)

    def create_from_photo(
        self,
        photo: bytes,
        mime_type: str,
        *,
        room_id: str,
        seller_id: str,
        title: str | None = None,
        price: Decimal | None = None,
        category: Category | None = None,
        description: str | None = None,
    ) -> Listing:
        draft = self._ai.draft_listing(photo, mime_type)
        photo_url = self.save_photo(photo, mime_type)
        try:
            listing = self._director.from_ai_draft(
                draft,
                photo_url=photo_url,
                room_id=room_id,
                seller_id=seller_id,
                title=title,
                price=price,
                category=category,
                description=description,
            )
            return self._publish(listing)
        except NearSwapError:
            self._discard_photo(photo_url)
            raise

    def _publish(self, listing: Listing) -> Listing:
        result = self._moderation.handle(listing)
        if not result.approved:
            raise ModerationRejectedError(result)
        listing.publish()
        self._listings[listing.listing_id] = listing
        self._persist()
        return listing

    # --- Sorgular ve durum değişiklikleri ---------------------------------------------

    def get(self, listing_id: str) -> Listing:
        listing = self._listings.get(listing_id)
        if listing is None:
            raise ListingNotFoundError(listing_id)
        return listing

    def list_room(self, room_id: str) -> list[Listing]:
        return [l for l in self._listings.values() if l.room_id == room_id]

    def reserve(self, listing_id: str) -> Listing:
        listing = self.get(listing_id)
        listing.reserve()
        self._persist()
        return listing

    def mark_sold(self, listing_id: str) -> Listing:
        listing = self.get(listing_id)
        listing.mark_sold()
        self._persist()
        return listing

    def cancel_reservation(self, listing_id: str) -> Listing:
        listing = self.get(listing_id)
        listing.cancel_reservation()
        self._persist()
        return listing
