"""Adapter kalıbı: yapay zekâ servisleri.
"""

from __future__ import annotations

import base64
import json
import os
from abc import ABC, abstractmethod
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from nearswap.models import Category, ListingDraft, ModerationResult, turkish_lower

# --- Target -----------------------------------------------------------------------


class AIService(ABC):
    """Target arayüzü: uygulamanın gördüğü tek yapay zekâ arayüzü."""

    @abstractmethod
    def draft_listing(self, photo_bytes: bytes, mime_type: str) -> ListingDraft:
        """Ürün fotoğrafından ilan taslağı üretir. mime_type örn. 'image/jpeg'."""

    @abstractmethod
    def moderate(self, text: str) -> ModerationResult:
        """İlan metninin yayına uygun olup olmadığını denetler."""


# --- Ortak istemler ve yanıt çevirme ----------------------------------------------------

_CATEGORY_VALUES = ", ".join(c.value for c in Category)

DRAFT_PROMPT = (
    "Bir yurt/site içi ikinci el pazar yeri için ilan taslağı hazırlıyorsun. "
    "Fotoğraftaki ürüne bakarak YALNIZCA şu alanları içeren bir JSON nesnesi döndür: "
    '{"title": str, "category": str, "description": str, "suggested_price": number}. '
    "title en fazla 80 karakterlik Türkçe bir başlık olsun. "
    f"category şu değerlerden biri olsun: {_CATEGORY_VALUES}. "
    "description ürünün görünen durumunu anlatan 1-2 Türkçe cümle olsun. "
    "suggested_price ikinci el için makul bir Türk lirası tutarı olsun; tahmin edemiyorsan 0 yaz."
)

MODERATION_PROMPT = (
    "Bir yurt/site içi ikinci el pazar yerinde yayınlanacak ilan metnini denetliyorsun. "
    "Yasa dışı ürün (silah, uyuşturucu, sahte belge vb.), hakaret, nefret söylemi, "
    "cinsel içerik ya da dolandırıcılık varsa ilanı reddet. "
    'YALNIZCA şu biçimde bir JSON nesnesi döndür: {"approved": bool, "reason": str}. '
    "Onaylıyorsan reason boş metin olsun, reddediyorsan kısa Türkçe sebep yaz.\n\nİlan metni:\n"
)


def _load_json_object(raw: str | None) -> dict[str, Any]:
    """Model yanıtından JSON nesnesini çıkarır. ```json kod bloğu içindeyse de okur."""
    if not raw:
        raise ValueError("Boş yanıt")
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Yanıt bir JSON nesnesi değil")
    return data


def _to_category(value: Any) -> Category:
    try:
        return Category(str(value).strip().lower())
    except ValueError:
        return Category.OTHER


def _to_price(value: Any) -> Decimal:
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")
    if not price.is_finite() or price < 0:
        return Decimal("0")
    return price.quantize(Decimal("1"))


def parse_draft(raw: str | None) -> ListingDraft:
    """Sağlayıcının JSON yanıtını ListingDraft'a çevirir.

    Bozuk ya da bilinmeyen kategori `diger`, okunamayan fiyat 0 olur. Fiyatın 0 olması,
    Builder'da kullanıcının fiyatı kendisinin girmesi gerektiği anlamına gelir.
    Yanıt hiç okunamıyorsa ValueError fırlatılır.
    """
    data = _load_json_object(raw)
    return ListingDraft(
        title=str(data.get("title") or "").strip()[:80],
        category=_to_category(data.get("category")),
        description=str(data.get("description") or "").strip(),
        suggested_price=_to_price(data.get("suggested_price")),
    )


def parse_moderation(raw: str | None, checked_by: str) -> ModerationResult:
    """{"approved": bool, "reason": str} yanıtını çevirir.

    Yanıt okunamazsa ilan reddedilir: denetim belirsizse güvenli taraf seçilir.
    """
    try:
        data = _load_json_object(raw)
    except ValueError:
        return ModerationResult.reject("Yapay zekâ denetim yanıtı okunamadı", checked_by)
    if data.get("approved") is True:
        return ModerationResult.approve(checked_by=checked_by)
    reason = str(data.get("reason") or "").strip() or "Yapay zekâ denetimi onaylamadı"
    return ModerationResult.reject(reason, checked_by)


# --- Adapter: OpenAI --------------------------------------------------------------

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_MODERATION_MODEL = "omni-moderation-latest"


def _flagged_categories(categories: Any) -> list[str]:
    """Moderations yanıtındaki işaretli kategori adlarını toplar."""
    if hasattr(categories, "model_dump"):
        values = categories.model_dump()
    elif isinstance(categories, dict):
        values = categories
    else:
        values = vars(categories)
    return sorted(name for name, flagged in values.items() if flagged is True)


class OpenAIAdapter(AIService):
    """OpenAI SDK'sını AIService'e uyarlar.

    Taslak için Chat Completions (görsel girdi, JSON yanıt), denetim için Moderations API.
    """

    def __init__(
        self,
        client: Any,
        model: str = DEFAULT_OPENAI_MODEL,
        moderation_model: str = DEFAULT_OPENAI_MODERATION_MODEL,
    ) -> None:
        self._client = client
        self._model = model
        self._moderation_model = moderation_model

    def draft_listing(self, photo_bytes: bytes, mime_type: str) -> ListingDraft:
        encoded = base64.b64encode(photo_bytes).decode("ascii")
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": DRAFT_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                        },
                    ],
                }
            ],
        )
        return parse_draft(response.choices[0].message.content)

    def moderate(self, text: str) -> ModerationResult:
        response = self._client.moderations.create(model=self._moderation_model, input=text)
        result = response.results[0]
        if not result.flagged:
            return ModerationResult.approve(checked_by=type(self).__name__)
        categories = _flagged_categories(result.categories)
        reason = "Uygunsuz içerik"
        if categories:
            reason += ": " + ", ".join(categories)
        return ModerationResult.reject(reason, checked_by=type(self).__name__)


# --- Adapter: Gemini --------------------------------------------------------------

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"

_GEMINI_JSON_CONFIG = {"response_mime_type": "application/json"}


class GeminiAdapter(AIService):
    """Google Gen AI SDK'sını AIService'e uyarlar.

    Gemini'de ayrı bir denetim API'si yoktur; ikisi için de generate_content çağrılır.
    Denetim yanıtı okunamazsa ilan reddedilir (güvenli taraf).
    """

    def __init__(self, client: Any, model: str = DEFAULT_GEMINI_MODEL) -> None:
        self._client = client
        self._model = model

    def draft_listing(self, photo_bytes: bytes, mime_type: str) -> ListingDraft:
        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {"mime_type": mime_type, "data": photo_bytes}},
                        {"text": DRAFT_PROMPT},
                    ],
                }
            ],
            config=_GEMINI_JSON_CONFIG,
        )
        return parse_draft(response.text)

    def moderate(self, text: str) -> ModerationResult:
        response = self._client.models.generate_content(
            model=self._model,
            contents=MODERATION_PROMPT + text,
            config=_GEMINI_JSON_CONFIG,
        )
        # Gemini'nin kendi güvenlik filtresi yanıtı engellerse text boş gelir;
        # parse_moderation bu durumda ilanı reddeder.
        return parse_moderation(response.text, checked_by=type(self).__name__)


# --- Test için -------------------------------------------------------------------

_DEFAULT_FAKE_DRAFT = ListingDraft(
    title="Çalışma lambası",
    category=Category.ELECTRONICS,
    description="Az kullanılmış, sorunsuz çalışan masa lambası.",
    suggested_price=Decimal("150"),
)


class FakeAIAdapter(AIService):
    """Testler ve demo için AIService. Ağa çıkmaz, sabit yanıt döner ve çağrıları kaydeder.

    Kayıtlar sayesinde testlerde "ucuz kontrol reddettiyse yapay zekâ hiç çağrılmadı" gibi
    davranışlar doğrulanabilir.
    """

    def __init__(
        self,
        draft: ListingDraft = _DEFAULT_FAKE_DRAFT,
        flagged_words: frozenset[str] = frozenset(),
    ) -> None:
        self._draft = draft
        self._flagged_words = frozenset(turkish_lower(w) for w in flagged_words)
        self.draft_calls: list[str] = []
        self.moderate_calls: list[str] = []

    def draft_listing(self, photo_bytes: bytes, mime_type: str) -> ListingDraft:
        self.draft_calls.append(mime_type)
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


# --- Sağlayıcı seçimi -------------------------------------------------------------


class AIConfigurationError(Exception):
    """Sağlayıcı adı geçersiz ya da gereken API anahtarı yok."""


def _require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise AIConfigurationError(f"{name} tanımlı değil. Anahtarı .env dosyasına yazın.")
    return value


AI_TIMEOUT_SECONDS = 30
"""Tek bir deneme bu sürede yanıt almazsa kesilir; sayfa sonsuza kadar beklemez."""

AI_RETRY_ATTEMPTS = 3
"""Sağlayıcının geçici hatalarında (yoğunluk 503, kota 429 vb.) ilk istek dahil en fazla deneme sayısı.
Denemeler arasında 2 ve 4 saniye beklenir. Hepsi başarısız olursa API 503 döner."""

_RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]


def create_ai_service(env: Mapping[str, str] | None = None) -> AIService:
    """Ortam değişkenlerine göre doğru uyarlayıcıyı kurar.

    NEARSWAP_AI_PROVIDER = fake | openai | gemini (varsayılan fake)
    OPENAI_API_KEY / GEMINI_API_KEY, isteğe bağlı NEARSWAP_OPENAI_MODEL / NEARSWAP_GEMINI_MODEL

    SDK'lar yalnızca burada, ilgili sağlayıcı seçildiğinde içe aktarılır; testler ve `fake`
    için openai / google-genai paketlerinin kurulu olması gerekmez.
    """
    env = os.environ if env is None else env
    provider = env.get("NEARSWAP_AI_PROVIDER", "fake").strip().lower()

    if provider == "fake":
        return FakeAIAdapter()

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(
            api_key=_require(env, "OPENAI_API_KEY"),
            timeout=AI_TIMEOUT_SECONDS,
            max_retries=AI_RETRY_ATTEMPTS - 1,  # OpenAI SDK geçici hataları kendisi tekrar dener
        )
        return OpenAIAdapter(client, model=env.get("NEARSWAP_OPENAI_MODEL") or DEFAULT_OPENAI_MODEL)

    if provider == "gemini":
        from google import genai

        gemini_client = genai.Client(
            api_key=_require(env, "GEMINI_API_KEY"),
            http_options={
                "timeout": AI_TIMEOUT_SECONDS * 1000,  # milisaniye
                # SDK varsayılan olarak hiç tekrar denemez; Google'ın geçici yoğunluk hatalarında
                # (503 UNAVAILABLE) isteği birkaç saniye arayla tekrarlıyoruz.
                "retry_options": {
                    "attempts": AI_RETRY_ATTEMPTS,
                    "initial_delay": 2.0,
                    "max_delay": 8.0,
                    "http_status_codes": _RETRYABLE_STATUS_CODES,
                },
            },
        )
        return GeminiAdapter(gemini_client, model=env.get("NEARSWAP_GEMINI_MODEL") or DEFAULT_GEMINI_MODEL)

    raise AIConfigurationError(
        f"Bilinmeyen NEARSWAP_AI_PROVIDER: {provider!r}. Geçerli değerler: fake, openai, gemini."
    )
