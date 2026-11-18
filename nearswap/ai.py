"""Adapter kalıbı: yapay zekâ servisleri.

Roller:
    Target   -> AIService
    Adaptee  -> OpenAI SDK istemcisi, Google Gen AI (Gemini) SDK istemcisi
    Adapter  -> OpenAIAdapter, GeminiAdapter
    (Test)   -> FakeAIAdapter: ağa çıkmaz, sabit yanıt döner

Uygulamanın geri kalanı yalnızca AIService'i görür. Sağlayıcının istek ve yanıt biçimi
Adapter'ın içinde kalır; Adapter yanıtı ListingDraft / ModerationResult'a dönüştürür.
SDK istemcisi Adapter'a dışarıdan verilir; böylece testlerde sahte istemci kullanılabilir.
"""

from __future__ import annotations

import base64
import json
import os
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Any

from nearswap.models import Category, ListingDraft, ModerationResult, turkish_lower

_CATEGORIES = ", ".join(c.value for c in Category)

DRAFT_PROMPT = (
    "Bu fotoğraftaki ürün bir yurtta ikinci el olarak satılacak. Türkçe bir ilan taslağı hazırla. "
    "Yalnızca şu anahtarları içeren bir JSON nesnesi döndür: "
    '"title" (en fazla 60 karakter), '
    f'"category" (şunlardan biri: {_CATEGORIES}), '
    '"description" (2-3 cümle, ürünün görünen durumunu anlat), '
    '"price" (Türk lirası cinsinden makul ikinci el fiyatı, sadece sayı).'
)

MODERATION_PROMPT = (
    "Bir yurt içi ikinci el pazar yerinde yayınlanacak ilan metnini denetle. "
    "Silah, uyuşturucu, alkol, tütün, reçeteli ilaç, sahte ürün, hakaret, cinsel içerik "
    "ya da dolandırıcılık varsa reddet. Yalnızca şu JSON nesnesini döndür: "
    '{"approved": true ya da false, "reason": "reddedildiyse kısa Türkçe sebep, değilse boş"}\n\n'
    "İlan metni:\n"
)


class AIService(ABC):
    """Target: uygulamanın gördüğü tek yapay zekâ arayüzü."""

    @abstractmethod
    def draft_listing(self, photo_bytes: bytes, mime_type: str = "image/jpeg") -> ListingDraft:
        """Ürün fotoğrafından ilan taslağı üretir."""

    @abstractmethod
    def moderate(self, text: str) -> ModerationResult:
        """İlan metninin yayına uygun olup olmadığını denetler."""


def parse_draft(data: dict[str, Any]) -> ListingDraft:
    """Modelin döndürdüğü JSON'u ListingDraft'a çevirir. Eksik ya da bozuk alanlara güvenli
    varsayılan verir; fiyat okunamazsa 0 olur ve kullanıcı fiyatı kendisi girmek zorunda kalır."""
    try:
        category = Category(turkish_lower(str(data.get("category", ""))).strip())
    except ValueError:
        category = Category.OTHER
    try:
        price = Decimal(str(data.get("price", "0"))).quantize(Decimal("1"))
    except InvalidOperation:
        price = Decimal("0")
    return ListingDraft(
        title=str(data.get("title", "")).strip()[:80] or "Başlıksız ürün",
        category=category,
        description=str(data.get("description", "")).strip(),
        suggested_price=max(price, Decimal("0")),
    )


def _load_json(text: str | None) -> dict[str, Any]:
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


class OpenAIAdapter(AIService):
    """Adaptee: openai.OpenAI istemcisi (Chat Completions + Moderations API)."""

    def __init__(
        self,
        client: Any,
        model: str = "gpt-4o-mini",
        moderation_model: str = "omni-moderation-latest",
    ) -> None:
        self._client = client
        self._model = model
        self._moderation_model = moderation_model

    def draft_listing(self, photo_bytes: bytes, mime_type: str = "image/jpeg") -> ListingDraft:
        image_url = f"data:{mime_type};base64,{base64.b64encode(photo_bytes).decode()}"
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": DRAFT_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
        )
        return parse_draft(_load_json(response.choices[0].message.content))

    def moderate(self, text: str) -> ModerationResult:
        response = self._client.moderations.create(model=self._moderation_model, input=text)
        result = response.results[0]
        if not result.flagged:
            return ModerationResult.approve()
        flagged = [name for name, hit in result.categories.model_dump().items() if hit]
        reason = "Uygunsuz içerik tespit edildi"
        if flagged:
            reason += ": " + ", ".join(flagged)
        return ModerationResult.reject(reason, checked_by="OpenAIAdapter")


class GeminiAdapter(AIService):
    """Adaptee: google.genai.Client istemcisi (generate_content)."""

    def __init__(self, client: Any, model: str = "gemini-2.5-flash") -> None:
        self._client = client
        self._model = model

    def draft_listing(self, photo_bytes: bytes, mime_type: str = "image/jpeg") -> ListingDraft:
        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": DRAFT_PROMPT},
                        {"inline_data": {"mime_type": mime_type, "data": photo_bytes}},
                    ],
                }
            ],
            config={"response_mime_type": "application/json"},
        )
        return parse_draft(_load_json(response.text))

    def moderate(self, text: str) -> ModerationResult:
        response = self._client.models.generate_content(
            model=self._model,
            contents=MODERATION_PROMPT + text,
            config={"response_mime_type": "application/json"},
        )
        data = _load_json(response.text)
        approved = data.get("approved")
        if approved is True:
            return ModerationResult.approve()
        # Yanıt okunamazsa güvenli tarafta kal: ilanı yayınlama.
        reason = str(data.get("reason") or "").strip() or "Yapay zekâ denetimi ilanı onaylamadı."
        return ModerationResult.reject(reason, checked_by="GeminiAdapter")


_DEFAULT_DRAFT = ListingDraft(
    title="Çalışma lambası",
    category=Category.ELECTRONICS,
    description="Az kullanılmış, sorunsuz çalışan masa lambası.",
    suggested_price=Decimal("150"),
)


class FakeAIAdapter(AIService):
    """Testler ve API anahtarı olmadan deneme için. Ağa çıkmaz, çağrıları kaydeder."""

    def __init__(
        self,
        draft: ListingDraft = _DEFAULT_DRAFT,
        flagged_words: frozenset[str] = frozenset(),
    ) -> None:
        self._draft = draft
        self._flagged_words = frozenset(turkish_lower(w) for w in flagged_words)
        self.draft_calls = 0
        self.moderate_calls: list[str] = []

    def draft_listing(self, photo_bytes: bytes, mime_type: str = "image/jpeg") -> ListingDraft:
        self.draft_calls += 1
        return self._draft

    def moderate(self, text: str) -> ModerationResult:
        self.moderate_calls.append(text)
        lowered = turkish_lower(text)
        for word in sorted(self._flagged_words):
            if word in lowered:
                return ModerationResult.reject(f"Uygunsuz içerik: '{word}'", checked_by="FakeAIAdapter")
        return ModerationResult.approve()


def create_ai_service(provider: str | None = None) -> AIService:
    """Ortam değişkenine göre uyarlayıcı seçer: NEARSWAP_AI_PROVIDER = fake | openai | gemini."""
    provider = (provider or os.getenv("NEARSWAP_AI_PROVIDER") or "fake").strip().lower()
    if provider == "openai":
        from openai import OpenAI  # OPENAI_API_KEY ortam değişkeninden okunur

        return OpenAIAdapter(OpenAI(), model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    if provider == "gemini":
        from google import genai

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        return GeminiAdapter(client, model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    if provider == "fake":
        return FakeAIAdapter()
    raise ValueError(f"Bilinmeyen yapay zekâ sağlayıcısı: {provider!r} (fake, openai ya da gemini)")
