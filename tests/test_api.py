"""Uçtan uca: HTTP isteğinden dört kalıbın birlikte çalışmasına kadar."""

import pytest
from fastapi.testclient import TestClient

from nearswap.ai import FakeAIAdapter
from nearswap.api import create_app
from nearswap.builder import ListingDirector, StandardListingBuilder
from nearswap.models import ListingDraft, ModerationResult
from nearswap.moderation import build_default_chain
from nearswap.service import ListingService

PHOTO = ("lamba.png", b"\x89PNG fake", "image/png")


@pytest.fixture
def ai() -> FakeAIAdapter:
    return FakeAIAdapter(flagged_words=frozenset({"kopya"}))


@pytest.fixture
def client(ai: FakeAIAdapter) -> TestClient:
    service = ListingService(ai, build_default_chain(ai), ListingDirector(StandardListingBuilder()))
    return TestClient(create_app(service))


def _form_listing(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "room_id": "yurt-a",
        "seller_id": "handan",
        "title": "Roman seti",
        "price": "90",
        "category": "kitap",
        "description": "5 kitap.",
        "photo_urls": ["https://ornek.com/kitap.jpg"],
    }
    body.update(overrides)
    return body


def test_ai_draft_suggestion(client: TestClient) -> None:
    response = client.post("/ai/draft", files={"photo": PHOTO})

    assert response.status_code == 200
    assert response.json()["title"] == "Çalışma lambası"


def test_full_flow_from_photo_to_sold(client: TestClient) -> None:
    created = client.post(
        "/listings/from-photo",
        files={"photo": PHOTO},
        data={"room_id": "yurt-a", "seller_id": "pelin", "price": "120"},
    )
    assert created.status_code == 201
    listing = created.json()
    assert listing["status"] == "aktif"
    assert listing["price"] == "120"
    assert listing["title"] == "Çalışma lambası"

    photo = client.get(listing["photos"][0])
    assert photo.content == PHOTO[1]
    assert photo.headers["content-type"] == "image/png"

    lid = listing["listing_id"]
    assert client.post(f"/listings/{lid}/reserve").json()["status"] == "rezerve"
    assert client.post(f"/listings/{lid}/cancel-reservation").json()["status"] == "aktif"
    assert client.post(f"/listings/{lid}/sold").json()["status"] == "satildi"

    again = client.post(f"/listings/{lid}/reserve")
    assert again.status_code == 409
    assert again.json()["error"] == "gecersiz_islem"


def test_form_listing_and_room_listing(client: TestClient) -> None:
    client.post("/listings", json=_form_listing())
    client.post("/listings", json=_form_listing(room_id="baska-yurt"))

    room = client.get("/rooms/yurt-a/listings").json()

    assert [l["title"] for l in room] == ["Roman seti"]


def test_invalid_listing_returns_all_problems(client: TestClient) -> None:
    response = client.post("/listings", json=_form_listing(title="", price="0", photo_urls=[]))

    assert response.status_code == 422
    assert response.json()["problems"] == [
        "Başlık boş olamaz.",
        "Fiyat sıfırdan büyük olmalı.",
        "En az bir fotoğraf eklenmeli.",
    ]


def test_banned_word_is_rejected_and_not_saved(client: TestClient, ai: FakeAIAdapter) -> None:
    response = client.post("/listings", json=_form_listing(description="Yanında tabanca kılıfı da var"))

    assert response.status_code == 422
    assert response.json()["checked_by"] == "BannedWordsHandler"
    assert ai.moderate_calls == []
    assert client.get("/rooms/yurt-a/listings").json() == []


def test_ai_rejection_from_photo_is_reported(client: TestClient) -> None:
    response = client.post(
        "/listings/from-photo",
        files={"photo": PHOTO},
        data={"room_id": "yurt-a", "seller_id": "pelin", "title": "Kopya saat"},
    )

    assert response.status_code == 422
    assert response.json()["checked_by"] == "AIModerationHandler"


def test_non_image_upload_is_rejected(client: TestClient) -> None:
    response = client.post("/ai/draft", files={"photo": ("notlar.txt", b"merhaba", "text/plain")})
    assert response.status_code == 415


def test_unknown_listing_returns_404(client: TestClient) -> None:
    assert client.get("/listings/yok").status_code == 404


class _BrokenAI(FakeAIAdapter):
    """Sağlayıcı geçici olarak yanıt vermiyormuş gibi davranır (ör. Gemini 503)."""

    def draft_listing(self, photo_bytes: bytes, mime_type: str) -> ListingDraft:
        raise RuntimeError("503 UNAVAILABLE")

    def moderate(self, text: str) -> ModerationResult:
        raise RuntimeError("503 UNAVAILABLE")


def test_ai_outage_returns_503_instead_of_crashing() -> None:
    ai = _BrokenAI()
    service = ListingService(ai, build_default_chain(ai), ListingDirector(StandardListingBuilder()))
    client = TestClient(create_app(service))

    assert client.post("/ai/draft", files={"photo": PHOTO}).status_code == 503
    assert client.post("/listings", json=_form_listing()).status_code == 503


def test_ai_draft_that_cannot_be_read_returns_503() -> None:
    class _Unreadable(FakeAIAdapter):
        def draft_listing(self, photo_bytes: bytes, mime_type: str) -> ListingDraft:
            raise ValueError("Yanıt bir JSON nesnesi değil")

    ai = _Unreadable()
    service = ListingService(ai, build_default_chain(ai), ListingDirector(StandardListingBuilder()))
    response = TestClient(create_app(service)).post(
        "/listings/from-photo", files={"photo": PHOTO}, data={"room_id": "yurt-a", "seller_id": "pelin"}
    )

    assert response.status_code == 503


def test_home_page_serves_the_user_interface(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "NearSwap" in response.text


def test_from_photo_uses_category_and_description_chosen_by_user(client: TestClient) -> None:
    response = client.post(
        "/listings/from-photo",
        files={"photo": PHOTO},
        data={
            "room_id": "yurt-a",
            "seller_id": "pelin",
            "title": "Gri hırka",
            "category": "giyim",
            "description": "M beden, bir kez giyildi.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["title"], body["category"], body["description"]) == (
        "Gri hırka",
        "giyim",
        "M beden, bir kez giyildi.",
    )


def test_from_photo_rejects_unknown_category(client: TestClient) -> None:
    response = client.post(
        "/listings/from-photo",
        files={"photo": PHOTO},
        data={"room_id": "yurt-a", "seller_id": "pelin", "category": "uzay-gemisi"},
    )

    assert response.status_code == 422


def test_uploaded_photo_can_be_used_in_a_form_listing(client: TestClient) -> None:
    uploaded = client.post("/photos", files={"photo": PHOTO})
    assert uploaded.status_code == 201
    url = uploaded.json()["url"]

    created = client.post("/listings", json=_form_listing(photo_urls=[url]))

    assert created.status_code == 201
    assert client.get(created.json()["photos"][0]).content == PHOTO[1]


def test_photo_upload_rejects_non_images(client: TestClient) -> None:
    response = client.post("/photos", files={"photo": ("notlar.txt", b"merhaba", "text/plain")})
    assert response.status_code == 415


def test_ai_outage_message_names_the_error_type() -> None:
    ai = _BrokenAI()
    service = ListingService(ai, build_default_chain(ai), ListingDirector(StandardListingBuilder()))

    response = TestClient(create_app(service)).post("/ai/draft", files={"photo": PHOTO})

    assert "(RuntimeError)" in response.json()["detail"]


# --- Taslağın yeniden kullanılması: yayınlarken yapay zekâ ikinci kez çağrılmaz ---------------


def _draft_id(client: TestClient) -> str:
    response = client.post("/ai/draft", files={"photo": PHOTO})
    assert response.status_code == 200
    return str(response.json()["draft_id"])


def test_publishing_from_draft_calls_the_ai_draft_only_once(client: TestClient, ai: FakeAIAdapter) -> None:
    draft_id = _draft_id(client)

    response = client.post(
        "/listings/from-draft",
        json={"draft_id": draft_id, "room_id": "yurt-a", "seller_id": "pelin", "title": "Gri hırka", "category": "giyim"},
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["title"], body["category"], body["status"]) == ("Gri hırka", "giyim", "aktif")
    assert body["description"] == "Az kullanılmış, sorunsuz çalışan masa lambası."  # verilmeyen alan taslaktan
    assert len(ai.draft_calls) == 1  # yalnızca öneri sırasında
    assert len(ai.moderate_calls) == 1  # yayınlarken yalnızca denetim
    assert client.get(body["photos"][0]).content == PHOTO[1]


def test_draft_is_used_once(client: TestClient) -> None:
    draft_id = _draft_id(client)
    body = {"draft_id": draft_id, "room_id": "yurt-a", "seller_id": "pelin"}

    assert client.post("/listings/from-draft", json=body).status_code == 201
    again = client.post("/listings/from-draft", json=body)

    assert again.status_code == 404
    assert again.json()["error"] == "taslak_bulunamadi"


def test_rejected_draft_can_be_corrected_and_published(client: TestClient) -> None:
    draft_id = _draft_id(client)
    base = {"draft_id": draft_id, "room_id": "yurt-a", "seller_id": "pelin"}

    rejected = client.post("/listings/from-draft", json={**base, "title": "Satılık tabanca kılıfı"})
    fixed = client.post("/listings/from-draft", json={**base, "title": "Satılık masa lambası"})

    assert rejected.status_code == 422
    assert fixed.status_code == 201
    assert [l["title"] for l in client.get("/rooms/yurt-a/listings").json()] == ["Satılık masa lambası"]


def test_unknown_draft_returns_404(client: TestClient) -> None:
    response = client.post("/listings/from-draft", json={"draft_id": "yok", "room_id": "yurt-a", "seller_id": "pelin"})

    assert response.status_code == 404
    assert "Fotoğrafı yeniden seçin" in response.json()["detail"]


def test_only_the_latest_drafts_are_kept() -> None:
    from nearswap.service import MAX_PENDING_DRAFTS

    ai = FakeAIAdapter()
    service = ListingService(ai, build_default_chain(ai), ListingDirector(StandardListingBuilder()))
    first = service.prepare_draft(b"x", "image/png")
    for _ in range(MAX_PENDING_DRAFTS):
        service.prepare_draft(b"x", "image/png")

    with pytest.raises(Exception, match="Taslak bulunamadı"):
        service.create_from_draft(first.draft_id, room_id="yurt-a", seller_id="pelin")
