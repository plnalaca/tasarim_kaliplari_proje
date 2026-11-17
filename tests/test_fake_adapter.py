from nearswap.patterns.adapter.ai_service import AIService
from nearswap.patterns.adapter.fake_adapter import FakeAIAdapter


def test_fake_adapter_is_an_ai_service() -> None:
    assert isinstance(FakeAIAdapter(), AIService)


def test_draft_listing_returns_configured_draft_and_counts_calls() -> None:
    ai = FakeAIAdapter()

    draft = ai.draft_listing(b"fake-photo")

    assert draft.title == "Çalışma lambası"
    assert ai.draft_calls == 1


def test_moderate_rejects_flagged_words_case_insensitively() -> None:
    ai = FakeAIAdapter(flagged_words=frozenset({"silah"}))

    result = ai.moderate("Satılık SİLAH kılıfı")

    assert not result.approved
    assert result.checked_by == "FakeAIAdapter"
    assert ai.moderate_calls == ["Satılık SİLAH kılıfı"]


def test_moderate_approves_clean_text() -> None:
    assert FakeAIAdapter(flagged_words=frozenset({"silah"})).moderate("Masa lambası").approved
