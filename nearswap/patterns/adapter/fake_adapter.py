from decimal import Decimal

from nearswap.domain.ai_types import ListingDraft, ModerationResult
from nearswap.domain.category import Category
from nearswap.domain.text import turkish_lower
from nearswap.patterns.adapter.ai_service import AIService

_DEFAULT_DRAFT = ListingDraft(
    title="Çalışma lambası",
    category=Category.ELECTRONICS,
    description="Az kullanılmış, sorunsuz çalışan masa lambası.",
    suggested_price=Decimal("150"),
)


class FakeAIAdapter(AIService):
    """Testler için AIService. Ağa çıkmaz, sabit yanıt döner ve çağrıları kaydeder.

    Kayıtlar sayesinde testlerde örneğin "ucuz kontrol reddettiyse yapay zekâ hiç
    çağrılmadı" gibi davranışlar doğrulanabilir.
    """

    def __init__(
        self,
        draft: ListingDraft = _DEFAULT_DRAFT,
        flagged_words: frozenset[str] = frozenset(),
    ) -> None:
        self._draft = draft
        self._flagged_words = frozenset(turkish_lower(w) for w in flagged_words)
        self.draft_calls = 0
        self.moderate_calls: list[str] = []

    def draft_listing(self, photo_bytes: bytes) -> ListingDraft:
        self.draft_calls += 1
        return self._draft

    def moderate(self, text: str) -> ModerationResult:
        self.moderate_calls.append(text)
        lowered = turkish_lower(text)
        for word in sorted(self._flagged_words):
            if word in lowered:
                return ModerationResult.reject(
                    f"Uygunsuz içerik: '{word}'", checked_by=type(self).__name__
                )
        return ModerationResult.approve(checked_by=type(self).__name__)
