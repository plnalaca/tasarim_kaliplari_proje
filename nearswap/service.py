"""İlan servisi: dört kalıbı birbirine bağlayan uygulama katmanı.

Fotoğraftan ilan verme akışı:
    1. AIService.draft_listing(photo)       -> ListingDraft         (Adapter)
    2. ListingDirector.from_ai_draft(...)   -> Listing, taslak      (Builder)
    3. moderation.handle(listing)           -> ModerationResult     (Chain of Responsibility)
    4. listing.publish()                    -> aktif                (State)

Veriler bellekte tutulur; sunucu yeniden başlayınca silinir.
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


class ListingService:
    def __init__(self, ai: AIService, moderation: ModerationHandler, director: ListingDirector) -> None:
        self._ai = ai
        self._moderation = moderation
        self._director = director
        self._listings: dict[str, Listing] = {}
        self._photos: dict[str, tuple[bytes, str]] = {}

    # --- Fotoğraflar ---------------------------------------------------------------------

    def save_photo(self, photo: bytes, mime_type: str) -> str:
        photo_id = uuid.uuid4().hex[:12]
        self._photos[photo_id] = (photo, mime_type)
        return f"/photos/{photo_id}"

    def get_photo(self, photo_id: str) -> tuple[bytes, str] | None:
        return self._photos.get(photo_id)

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
    ) -> Listing:
        draft = self._ai.draft_listing(photo, mime_type)
        photo_url = self.save_photo(photo, mime_type)
        try:
            listing = self._director.from_ai_draft(
                draft, photo_url=photo_url, room_id=room_id, seller_id=seller_id, title=title, price=price
            )
            return self._publish(listing)
        except NearSwapError:
            self._photos.pop(photo_url.rsplit("/", 1)[-1], None)
            raise

    def _publish(self, listing: Listing) -> Listing:
        result = self._moderation.handle(listing)
        if not result.approved:
            raise ModerationRejectedError(result)
        listing.publish()
        self._listings[listing.listing_id] = listing
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
        return listing

    def mark_sold(self, listing_id: str) -> Listing:
        listing = self.get(listing_id)
        listing.mark_sold()
        return listing

    def cancel_reservation(self, listing_id: str) -> Listing:
        listing = self.get(listing_id)
        listing.cancel_reservation()
        return listing
