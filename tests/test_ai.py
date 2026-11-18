"""Adapter testleri. Gerçek SDK yerine aynı biçimde yanıt veren sahte istemciler kullanılır;
böylece her uyarlayıcının sağlayıcı yanıtını doğru dönüştürdüğü ağa çıkmadan sınanır."""

import json
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from nearswap.ai import (
    AIService,
    FakeAIAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    create_ai_service,
    parse_draft,
)
from nearswap.models import Category

DRAFT_JSON = json.dumps(
    {"title": "Masa lambası", "category": "Elektronik", "description": "Çalışıyor.", "price": "149.6"}
)


# --- Sahte SDK istemcileri ----------------------------------------------------------------


class _Categories:
    def __init__(self, **hits: bool) -> None:
        self._hits = hits

    def model_dump(self) -> dict[str, bool]:
        return self._hits


class FakeOpenAIClient:
    def __init__(self, content: str, flagged: bool = False, **categories: bool) -> None:
        self.requests: list[dict[str, Any]] = []
        completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
        moderation = SimpleNamespace(
            results=[SimpleNamespace(flagged=flagged, categories=_Categories(**categories))]
        )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._record(completion)))
        self.moderations = SimpleNamespace(create=self._record(moderation))

    def _record(self, response: object) -> Any:
        def create(**kwargs: Any) -> object:
            self.requests.append(kwargs)
            return response

        return create


class FakeGeminiClient:
    def __init__(self, text: str) -> None:
        self.requests: list[dict[str, Any]] = []
        self.models = SimpleNamespace(generate_content=self._generate)
        self._text = text

    def _generate(self, **kwargs: Any) -> object:
        self.requests.append(kwargs)
        return SimpleNamespace(text=self._text)


# --- Testler ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "adapter",
    [OpenAIAdapter(FakeOpenAIClient(DRAFT_JSON)), GeminiAdapter(FakeGeminiClient(DRAFT_JSON)), FakeAIAdapter()],
    ids=["openai", "gemini", "fake"],
)
def test_every_adapter_is_an_ai_service(adapter: AIService) -> None:
    assert isinstance(adapter, AIService)


@pytest.mark.parametrize("make", [OpenAIAdapter, GeminiAdapter], ids=["openai", "gemini"])
def test_adapters_convert_provider_response_to_same_draft(make: Any) -> None:
    client = FakeOpenAIClient(DRAFT_JSON) if make is OpenAIAdapter else FakeGeminiClient(DRAFT_JSON)

    draft = make(client).draft_listing(b"\x89PNG", "image/png")

    assert draft.title == "Masa lambası"
    assert draft.category is Category.ELECTRONICS
    assert draft.suggested_price == Decimal("150")


def test_openai_adapter_sends_photo_as_data_url() -> None:
    client = FakeOpenAIClient(DRAFT_JSON)
    OpenAIAdapter(client).draft_listing(b"abc", "image/png")

    image_part = client.requests[0]["messages"][0]["content"][1]
    assert image_part["image_url"]["url"] == "data:image/png;base64,YWJj"


def test_openai_moderation_lists_flagged_categories() -> None:
    client = FakeOpenAIClient("{}", flagged=True, violence=True, harassment=False)

    result = OpenAIAdapter(client).moderate("metin")

    assert not result.approved
    assert result.reason == "Uygunsuz içerik tespit edildi: violence"


def test_openai_moderation_approves_unflagged() -> None:
    assert OpenAIAdapter(FakeOpenAIClient("{}")).moderate("metin").approved


def test_gemini_moderation_reads_json_verdict() -> None:
    rejected = GeminiAdapter(FakeGeminiClient('{"approved": false, "reason": "Alkol satışı"}')).moderate("x")
    approved = GeminiAdapter(FakeGeminiClient('{"approved": true, "reason": ""}')).moderate("x")

    assert (rejected.approved, rejected.reason) == (False, "Alkol satışı")
    assert approved.approved


def test_gemini_moderation_fails_closed_on_unreadable_answer() -> None:
    result = GeminiAdapter(FakeGeminiClient("bu JSON değil")).moderate("x")

    assert not result.approved
    assert result.checked_by == "GeminiAdapter"


def test_parse_draft_falls_back_on_bad_fields() -> None:
    draft = parse_draft({"category": "uzay gemisi", "price": "bilmiyorum"})

    assert draft.title == "Başlıksız ürün"
    assert draft.category is Category.OTHER
    assert draft.suggested_price == Decimal("0")


def test_create_ai_service_defaults_to_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEARSWAP_AI_PROVIDER", raising=False)
    assert isinstance(create_ai_service(), FakeAIAdapter)


def test_create_ai_service_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError):
        create_ai_service("claude")
