from abc import ABC, abstractmethod

from nearswap.domain.ai_types import ListingDraft, ModerationResult


class AIService(ABC):
    """Target arayüzü: uygulamanın gördüğü tek yapay zekâ arayüzü."""

    @abstractmethod
    def draft_listing(self, photo_bytes: bytes) -> ListingDraft:
        """Ürün fotoğrafından ilan taslağı üretir."""

    @abstractmethod
    def moderate(self, text: str) -> ModerationResult:
        """İlan metninin yayına uygun olup olmadığını denetler."""
