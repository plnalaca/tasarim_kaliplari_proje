"""Adapter: OpenAIAdapter, GeminiAdapter, FakeAIAdapter, ortak yanıt çevirme ve sağlayıcı seçimi.

Gerçek SDK yerine, SDK'nın kullandığımız kısmıyla AYNI BİÇİMDE yanıt veren sahte istemciler
kullanılır. Testler ağa çıkmaz; adaptörün doğru çağrıyı yaptığını ve yanıtı doğru
çevirdiğini sınar.
"""

import json
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from nearswap.ai import (
    AIConfigurationError,
    AIService,
    FakeAIAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    create_ai_service,
    parse_draft,
    parse_moderation,
)
from nearswap.models import Category

JPEG = b"\xff\xd8\xff\xe0fake-jpeg"
PNG = b"\x89PNG\r\n\x1a\nfake-png"

DRAFT_JSON = json.dumps(
    {
        "title": "Çalışma masası",
        "category": "mobilya",
        "description": "Beyaz, çizik yok.",
        "suggested_price": 750,
    }
)


# --- Sahte OpenAI istemcisi -------------------------------------------------------


class _FakeOpenAIChat:
    def __init__(self, content: str | None) -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeOpenAIModerations:
    def __init__(self, flagged: bool, categories: dict[str, bool]) -> None:
        self.flagged = flagged
        self.categories = categories
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        result = SimpleNamespace(flagged=self.flagged, categories=self.categories)
        return SimpleNamespace(results=[result])


class FakeOpenAIClient:
    def __init__(
        self,
        content: str | None = DRAFT_JSON,
        flagged: bool = False,
        categories: dict[str, bool] | None = None,
    ) -> None:
        self.completions = _FakeOpenAIChat(content)
        self.chat = SimpleNamespace(completions=self.completions)
        self.moderations = _FakeOpenAIModerations(flagged, categories or {})


# --- Sahte Gemini istemcisi -------------------------------------------------------


class _FakeGeminiModels:
    def __init__(self, texts: list[str | None]) -> None:
        self._texts = texts
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(text=self._texts.pop(0))


class FakeGeminiClient:
    def __init__(self, *texts: str | None) -> None:
        self.models = _FakeGeminiModels(list(texts))


# --- Ortak ------------------------------------------------------------------------


def test_both_adapters_are_ai_services() -> None:
    assert isinstance(OpenAIAdapter(FakeOpenAIClient()), AIService)
    assert isinstance(GeminiAdapter(FakeGeminiClient()), AIService)


@pytest.mark.parametrize(
    "adapter",
    [
        lambda: OpenAIAdapter(FakeOpenAIClient(DRAFT_JSON)),
        lambda: GeminiAdapter(FakeGeminiClient(DRAFT_JSON)),
    ],
    ids=["openai", "gemini"],
)
def test_both_adapters_return_the_same_draft_for_the_same_answer(adapter: Any) -> None:
    draft = adapter().draft_listing(JPEG, "image/jpeg")

    assert draft.title == "Çalışma masası"
    assert draft.category is Category.FURNITURE
    assert draft.description == "Beyaz, çizik yok."
    assert draft.suggested_price == Decimal("750")


# --- OpenAIAdapter ----------------------------------------------------------------


def test_openai_draft_sends_photo_as_data_url_and_asks_for_json() -> None:
    client = FakeOpenAIClient()

    OpenAIAdapter(client, model="test-model").draft_listing(PNG, "image/png")

    call = client.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["response_format"] == {"type": "json_object"}
    image_part = call["messages"][0]["content"][1]
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")


def test_openai_moderate_approves_unflagged_text() -> None:
    client = FakeOpenAIClient(flagged=False)

    result = OpenAIAdapter(client).moderate("Masa lambası")

    assert result.approved
    assert result.checked_by == "OpenAIAdapter"
    assert client.moderations.calls[0]["input"] == "Masa lambası"


def test_openai_moderate_rejects_flagged_text_and_names_categories() -> None:
    client = FakeOpenAIClient(flagged=True, categories={"violence": True, "hate": False})

    result = OpenAIAdapter(client).moderate("...")

    assert not result.approved
    assert result.reason == "Uygunsuz içerik: violence"


# --- GeminiAdapter ----------------------------------------------------------------


def test_gemini_draft_sends_photo_bytes_with_mime_type() -> None:
    client = FakeGeminiClient(DRAFT_JSON)

    GeminiAdapter(client, model="test-model").draft_listing(PNG, "image/png")

    call = client.models.calls[0]
    assert call["model"] == "test-model"
    assert call["config"] == {
        "response_mime_type": "application/json",
        "thinking_config": {"thinking_level": "low"},
    }
    inline = call["contents"][0]["parts"][0]["inline_data"]
    assert inline == {"mime_type": "image/png", "data": PNG}


def test_gemini_moderate_approves() -> None:
    client = FakeGeminiClient(json.dumps({"approved": True, "reason": ""}))

    result = GeminiAdapter(client).moderate("Masa lambası")

    assert result.approved
    assert result.checked_by == "GeminiAdapter"
    assert client.models.calls[0]["contents"].endswith("Masa lambası")


def test_gemini_moderate_rejects_with_reason() -> None:
    client = FakeGeminiClient(json.dumps({"approved": False, "reason": "Silah satışı"}))

    result = GeminiAdapter(client).moderate("...")

    assert not result.approved
    assert result.reason == "Silah satışı"


@pytest.mark.parametrize("raw", [None, "", "bu JSON değil", "[1, 2]"])
def test_gemini_moderate_rejects_when_answer_is_unreadable(raw: str | None) -> None:
    result = GeminiAdapter(FakeGeminiClient(raw)).moderate("...")

    assert not result.approved
    assert result.reason == "Yapay zekâ denetim yanıtı okunamadı"


# --- factory ----------------------------------------------------------------------


def test_factory_defaults_to_fake_adapter() -> None:
    assert isinstance(create_ai_service({}), FakeAIAdapter)


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(AIConfigurationError):
        create_ai_service({"NEARSWAP_AI_PROVIDER": "bilinmeyen"})


def test_factory_requires_api_key_for_real_provider() -> None:
    pytest.importorskip("google.genai")
    with pytest.raises(AIConfigurationError, match="GEMINI_API_KEY"):
        create_ai_service({"NEARSWAP_AI_PROVIDER": "gemini"})


# --- Ortak yanıt çevirme (parse_draft, parse_moderation) ------------------------------


def _draft_json(**fields: object) -> str:
    base: dict[str, object] = {
        "title": "Kitaplık",
        "category": "mobilya",
        "description": "Üç raflı.",
        "suggested_price": 400,
    }
    base.update(fields)
    return json.dumps(base)


def test_parse_draft_reads_all_fields() -> None:
    draft = parse_draft(_draft_json())

    assert (draft.title, draft.category, draft.suggested_price) == (
        "Kitaplık",
        Category.FURNITURE,
        Decimal("400"),
    )


def test_parse_draft_reads_json_inside_code_fence() -> None:
    assert parse_draft("```json\n" + _draft_json() + "\n```").title == "Kitaplık"


@pytest.mark.parametrize("category", ["araba", None, 42])
def test_unknown_category_becomes_other(category: object) -> None:
    assert parse_draft(_draft_json(category=category)).category is Category.OTHER


def test_category_is_matched_case_insensitively() -> None:
    assert parse_draft(_draft_json(category="Kitap")).category is Category.BOOKS


@pytest.mark.parametrize("price", ["bilmiyorum", None, -50, "NaN"])
def test_unreadable_or_negative_price_becomes_zero(price: object) -> None:
    assert parse_draft(_draft_json(suggested_price=price)).suggested_price == Decimal("0")


def test_price_is_rounded_to_whole_lira() -> None:
    assert parse_draft(_draft_json(suggested_price=199.6)).suggested_price == Decimal("200")


def test_title_is_cut_to_80_characters() -> None:
    assert len(parse_draft(_draft_json(title="a" * 120)).title) == 80


def test_unreadable_draft_raises() -> None:
    with pytest.raises(ValueError):
        parse_draft("bu JSON değil")


def test_moderation_without_explicit_true_is_rejected() -> None:
    result = parse_moderation(json.dumps({"approved": "evet"}), checked_by="x")

    assert not result.approved


# --- FakeAIAdapter ----------------------------------------------------------------


def test_fake_adapter_returns_configured_draft_and_records_calls() -> None:
    ai = FakeAIAdapter()

    draft = ai.draft_listing(b"photo", "image/jpeg")

    assert draft.title == "Çalışma lambası"
    assert ai.draft_calls == ["image/jpeg"]


def test_fake_adapter_rejects_flagged_words_case_insensitively() -> None:
    ai = FakeAIAdapter(flagged_words=frozenset({"silah"}))

    result = ai.moderate("Satılık SİLAH kılıfı")

    assert not result.approved
    assert result.checked_by == "FakeAIAdapter"
    assert ai.moderate_calls == ["Satılık SİLAH kılıfı"]


def test_fake_adapter_approves_clean_text() -> None:
    assert FakeAIAdapter(flagged_words=frozenset({"silah"})).moderate("Masa lambası").approved


def test_factory_gives_real_providers_a_timeout_and_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sağlayıcı yanıt vermezse istek sonsuza kadar beklememeli."""
    pytest.importorskip("google.genai")
    from nearswap.ai import AI_RETRY_ATTEMPTS, AI_TIMEOUT_SECONDS

    gemini = create_ai_service({"NEARSWAP_AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-anahtar"})
    assert isinstance(gemini, GeminiAdapter)
    http_options = gemini._client._api_client._http_options
    assert http_options.timeout == AI_TIMEOUT_SECONDS * 1000
    assert http_options.retry_options is not None
    assert http_options.retry_options.attempts == AI_RETRY_ATTEMPTS
    assert 503 in (http_options.retry_options.http_status_codes or [])

    pytest.importorskip("openai")
    openai_service = create_ai_service({"NEARSWAP_AI_PROVIDER": "openai", "OPENAI_API_KEY": "test-anahtar"})
    assert isinstance(openai_service, OpenAIAdapter)
    assert openai_service._client.timeout == AI_TIMEOUT_SECONDS
    assert openai_service._client.max_retries == AI_RETRY_ATTEMPTS - 1


def test_gemini_moderation_also_uses_low_thinking() -> None:
    client = FakeGeminiClient(json.dumps({"approved": True, "reason": ""}))

    GeminiAdapter(client).moderate("Masa lambası")

    assert client.models.calls[0]["config"]["thinking_config"] == {"thinking_level": "low"}


def test_gemini_thinking_level_can_be_left_to_the_model() -> None:
    """Düşünme düzeyi ayarı olmayan bir modele geçilirse ayar hiç gönderilmez."""
    client = FakeGeminiClient(DRAFT_JSON)

    GeminiAdapter(client, thinking_level=None).draft_listing(PNG, "image/png")

    assert "thinking_config" not in client.models.calls[0]["config"]


def test_factory_reads_gemini_thinking_level_from_env() -> None:
    pytest.importorskip("google.genai")
    env = {"NEARSWAP_AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test", "NEARSWAP_GEMINI_THINKING": "medium"}

    service = create_ai_service(env)

    assert isinstance(service, GeminiAdapter)
    assert service._config["thinking_config"] == {"thinking_level": "medium"}
    assert "thinking_config" not in create_ai_service({**env, "NEARSWAP_GEMINI_THINKING": ""})._config  # type: ignore[attr-defined]


# --- Gemini: yoğun ana modelden yedek modele geçiş ----------------------------------------


class _Overloaded(Exception):
    """Gemini SDK'nın 503 UNAVAILABLE hatasının yerine."""


class _FlakyGeminiModels:
    """Belirtilen modeller hata verir, diğerleri yanıt döner."""

    def __init__(self, failing: set[str], text: str) -> None:
        self._failing = failing
        self._text = text
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if kwargs["model"] in self._failing:
            raise _Overloaded(f"{kwargs['model']} is currently experiencing high demand")
        return SimpleNamespace(text=self._text)


def _flaky_client(failing: set[str], text: str = DRAFT_JSON) -> Any:
    return SimpleNamespace(models=_FlakyGeminiModels(failing, text))


def test_gemini_falls_back_when_main_model_is_overloaded() -> None:
    client = _flaky_client({"ana"})
    adapter = GeminiAdapter(client, model="ana", fallback_models=["yedek"])

    draft = adapter.draft_listing(JPEG, "image/jpeg")

    assert draft.title == "Çalışma masası"
    assert [c["model"] for c in client.models.calls] == ["ana", "yedek"]
    # Yedek modele düşünme düzeyi gönderilmez; her model kendi varsayılanıyla çalışır.
    assert "thinking_config" in client.models.calls[0]["config"]
    assert "thinking_config" not in client.models.calls[1]["config"]


def test_gemini_moderation_also_falls_back() -> None:
    client = _flaky_client({"ana"}, json.dumps({"approved": True, "reason": ""}))

    result = GeminiAdapter(client, model="ana", fallback_models=["yedek"]).moderate("Masa lambası")

    assert result.approved
    assert [c["model"] for c in client.models.calls] == ["ana", "yedek"]


def test_gemini_raises_main_model_error_when_every_model_fails() -> None:
    client = _flaky_client({"ana", "yedek"})

    with pytest.raises(_Overloaded, match="ana is currently"):
        GeminiAdapter(client, model="ana", fallback_models=["yedek"]).draft_listing(JPEG, "image/jpeg")


def test_gemini_does_not_use_fallback_when_main_model_answers() -> None:
    client = _flaky_client(set())

    GeminiAdapter(client, model="ana", fallback_models=["yedek"]).draft_listing(JPEG, "image/jpeg")

    assert [c["model"] for c in client.models.calls] == ["ana"]


def test_factory_sets_default_fallback_and_allows_turning_it_off() -> None:
    pytest.importorskip("google.genai")
    from nearswap.ai import DEFAULT_GEMINI_FALLBACK_MODELS

    env = {"NEARSWAP_AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test"}
    default = create_ai_service(env)
    off = create_ai_service({**env, "NEARSWAP_GEMINI_FALLBACK_MODELS": ""})

    assert isinstance(default, GeminiAdapter) and isinstance(off, GeminiAdapter)
    assert default._models == ["gemini-3.8-flash", *DEFAULT_GEMINI_FALLBACK_MODELS]
    assert off._models == ["gemini-3.8-flash"]
