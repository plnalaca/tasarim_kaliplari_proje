"""Uçtan uca: HTTP isteğinden dört kalıbın birlikte çalışmasına kadar."""

import pytest
from fastapi.testclient import TestClient

from nearswap.ai import FakeAIAdapter
from nearswap.api import create_app
from nearswap.builder import ListingDirector, StandardListingBuilder
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
    response = client.post("/listings", json=_form_listing(description="Hediye olarak alkol de veririm"))

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
