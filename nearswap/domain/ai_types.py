"""Yapay zekâ servisleriyle uygulama arasında taşınan, sağlayıcıdan bağımsız veri tipleri.

Adapter'lar sağlayıcıya özgü yanıtları bu tiplere dönüştürür. Uygulamanın geri kalanı
yalnızca bu tipleri görür.
"""

from dataclasses import dataclass
from decimal import Decimal

from nearswap.domain.category import Category


@dataclass(frozen=True)
class ListingDraft:
    """AIService.draft_listing() çıktısı: fotoğraftan önerilen ilan taslağı."""

    title: str
    category: Category
    description: str
    suggested_price: Decimal


@dataclass(frozen=True)
class ModerationResult:
    """Bir denetimin sonucu. Hem AIService.moderate() hem de denetim zinciri kullanır."""

    approved: bool
    reason: str | None = None
    checked_by: str | None = None

    @classmethod
    def approve(cls, checked_by: str | None = None) -> "ModerationResult":
        return cls(approved=True, checked_by=checked_by)

    @classmethod
    def reject(cls, reason: str, checked_by: str) -> "ModerationResult":
        return cls(approved=False, reason=reason, checked_by=checked_by)
