"""İlan servisi: dört kalıbı birbirine bağlayan uygulama katmanı.

store (JsonFileStore) verilirse ilanlar ve fotoğraflar diske kaydedilir, sunucu yeniden başlasa da
kalır. Verilmezse (testlerde) her şey bellekte tutulur.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal

from nearswap.ai import AIService
from nearswap.builder import ListingDirector
from nearswap.models import (
    Category,
    DraftNotFoundError,
    Listing,
    ListingDraft,
    ListingNotFoundError,
    ModerationRejectedError,
    NearSwapError,
)
from nearswap.moderation import ModerationHandler
from nearswap.storage import JsonFileStore


MAX_PENDING_DRAFTS = 50
"""Yayınlanmayı bekleyen en fazla taslak sayısı; daha eskileri unutulur."""


@dataclass(frozen=True)
class PreparedDraft:
    """Fotoğraftan üretilmiş ve yayınlanmayı bekleyen taslak."""

    draft_id: str
    draft: ListingDraft


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
        # Fotoğraf seçilirken üretilen taslaklar: yayınlarken yapay zekâ ikinci kez çağrılmaz.
        self._drafts: OrderedDict[str, tuple[bytes, str, ListingDraft]] = OrderedDict()
        self._drafts_lock = threading.Lock()

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

    def prepare_draft(self, photo: bytes, mime_type: str) -> PreparedDraft:
        """Fotoğraftan taslak üretir ve yayınlanana kadar saklar."""
        draft = self._ai.draft_listing(photo, mime_type)
        draft_id = uuid.uuid4().hex
        with self._drafts_lock:
            self._drafts[draft_id] = (photo, mime_type, draft)
            while len(self._drafts) > MAX_PENDING_DRAFTS:
                self._drafts.popitem(last=False)
        return PreparedDraft(draft_id, draft)

    def create_from_draft(
        self,
        draft_id: str,
        *,
        room_id: str,
        seller_id: str,
        title: str | None = None,
        price: Decimal | None = None,
        category: Category | None = None,
        description: str | None = None,
    ) -> Listing:
        """Daha önce üretilmiş taslaktan ilan verir; yapay zekâ yalnızca denetim için çağrılır.

        İlan reddedilirse taslak saklanmaya devam eder; kullanıcı düzeltip yeniden deneyebilir.
        """
        with self._drafts_lock:
            entry = self._drafts.get(draft_id)
        if entry is None:
            raise DraftNotFoundError(draft_id)
        photo, mime_type, draft = entry
        listing = self._publish_draft(
            draft,
            photo,
            mime_type,
            room_id=room_id,
            seller_id=seller_id,
            title=title,
            price=price,
            category=category,
            description=description,
        )
        with self._drafts_lock:
            self._drafts.pop(draft_id, None)
        return listing

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
        if title and price is not None and category is not None:
            # Kullanıcı ilanın zorunlu alanlarını kendisi girdi (örneğin taslak önerisi yapay zekâ
            # yoğun olduğu için gelmedi): taslak istemeye gerek yok, form yoluyla kurulur.
            photo_url = self.save_photo(photo, mime_type)
            try:
                return self.create_from_form(
                    room_id=room_id,
                    seller_id=seller_id,
                    title=title,
                    price=price,
                    category=category,
                    description=description or "",
                    photo_urls=[photo_url],
                )
            except NearSwapError:
                self._discard_photo(photo_url)
                raise
        draft = self._ai.draft_listing(photo, mime_type)
        return self._publish_draft(
            draft,
            photo,
            mime_type,
            room_id=room_id,
            seller_id=seller_id,
            title=title,
            price=price,
            category=category,
            description=description,
        )

    def _publish_draft(
        self,
        draft: ListingDraft,
        photo: bytes,
        mime_type: str,
        *,
        room_id: str,
        seller_id: str,
        title: str | None,
        price: Decimal | None,
        category: Category | None,
        description: str | None,
    ) -> Listing:
        """Taslaktan ilanı kurar (Builder), denetler (Chain) ve yayınlar (State).
        İlan reddedilirse kaydedilen fotoğraf silinir."""
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
