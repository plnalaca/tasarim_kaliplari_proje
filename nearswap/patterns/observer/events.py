from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, kw_only=True)
class ListingEvent:
    """Gözlemcilere iletilen tüm olayların ortak atası."""

    listing_id: str
    room_id: str
    occurred_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, kw_only=True)
class NewListingEvent(ListingEvent):
    """Odada yeni bir ilan yayına çıktı."""

    seller_id: str
    title: str


@dataclass(frozen=True, kw_only=True)
class ListingSoldEvent(ListingEvent):
    """Odadaki bir ilan satıldı olarak işaretlendi."""

    seller_id: str
