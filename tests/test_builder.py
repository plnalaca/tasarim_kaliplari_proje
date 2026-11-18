from decimal import Decimal

import pytest

from nearswap.builder import ListingBuilder, ListingDirector, StandardListingBuilder
from nearswap.models import Category, ListingDraft, ListingValidationError
from nearswap.states import DraftState
from tests.helpers import make_listing

DRAFT = ListingDraft(
    title="Kahve makinesi",
    category=Category.KITCHEN,
    description="Filtre kahve makinesi, çalışıyor.",
    suggested_price=Decimal("400"),
)


def test_builder_interface_is_abstract() -> None:
    with pytest.raises(TypeError):
        ListingBuilder()  # type: ignore[abstract]


def test_build_creates_listing_in_draft_state() -> None:
    listing = make_listing()

    assert isinstance(listing.state, DraftState)
    assert listing.title == "Çalışma lambası"
    assert listing.price == Decimal("150")
    assert len(listing.listing_id) == 8


def test_build_collects_every_problem_at_once() -> None:
    with pytest.raises(ListingValidationError) as exc:
        StandardListingBuilder().set_title("  ").set_price(Decimal("0")).build()

    assert exc.value.problems == [
        "İlanın odası ve satıcısı belirtilmeli.",
        "Başlık boş olamaz.",
        "Fiyat sıfırdan büyük olmalı.",
        "En az bir fotoğraf eklenmeli.",
        "Kategori seçilmeli.",
    ]


def test_build_rejects_too_long_title() -> None:
    with pytest.raises(ListingValidationError) as exc:
        make_listing(title="x" * 81)
    assert exc.value.problems == ["Başlık en fazla 80 karakter olabilir."]


def test_builder_resets_after_build() -> None:
    builder = StandardListingBuilder()
    builder.set_owner("r", "u").set_title("A").set_price(Decimal("1")).add_photo("p").set_category(
        Category.OTHER
    ).build()

    with pytest.raises(ListingValidationError):
        builder.build()


def test_director_from_form() -> None:
    listing = ListingDirector(StandardListingBuilder()).from_form(
        room_id="yurt-a",
        seller_id="handan",
        title="Roman seti",
        price=Decimal("90"),
        category=Category.BOOKS,
        description="5 kitap.",
        photo_urls=["a.jpg", "b.jpg"],
    )

    assert listing.photos == ("a.jpg", "b.jpg")
    assert listing.category is Category.BOOKS


def test_director_from_ai_draft_uses_draft_fields() -> None:
    listing = ListingDirector(StandardListingBuilder()).from_ai_draft(
        DRAFT, photo_url="/photos/1", room_id="yurt-a", seller_id="pelin"
    )

    assert listing.title == "Kahve makinesi"
    assert listing.price == Decimal("400")
    assert listing.category is Category.KITCHEN
    assert listing.photos == ("/photos/1",)


def test_director_from_ai_draft_lets_user_override_title_and_price() -> None:
    listing = ListingDirector(StandardListingBuilder()).from_ai_draft(
        DRAFT,
        photo_url="/photos/1",
        room_id="yurt-a",
        seller_id="pelin",
        title="Philips kahve makinesi",
        price=Decimal("350"),
    )

    assert listing.title == "Philips kahve makinesi"
    assert listing.price == Decimal("350")
    assert listing.description == DRAFT.description


def test_director_from_ai_draft_with_zero_price_requires_user_price() -> None:
    zero = ListingDraft(title="Sandalye", category=Category.FURNITURE, description="", suggested_price=Decimal("0"))

    with pytest.raises(ListingValidationError) as exc:
        ListingDirector(StandardListingBuilder()).from_ai_draft(
            zero, photo_url="/photos/1", room_id="yurt-a", seller_id="pelin"
        )
    assert exc.value.problems == ["Fiyat sıfırdan büyük olmalı."]
