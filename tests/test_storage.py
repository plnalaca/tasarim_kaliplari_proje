"""Kalıcılık: sunucu yeniden başlasa da ilanlar, durumları ve fotoğrafları kalmalı."""

from decimal import Decimal
from pathlib import Path

import pytest

from nearswap.ai import FakeAIAdapter
from nearswap.builder import ListingDirector, StandardListingBuilder
from nearswap.models import Category, ModerationRejectedError
from nearswap.moderation import build_default_chain
from nearswap.service import ListingService
from nearswap.states import DraftState, ReservedState
from nearswap.storage import STATE_BY_NAME, JsonFileStore

PHOTO = b"\x89PNG fake"


def _service(directory: Path) -> ListingService:
    """Her çağrı, sunucunun yeniden başlaması gibi sıfırdan bir servis kurar."""
    ai = FakeAIAdapter()
    return ListingService(
        ai, build_default_chain(ai), ListingDirector(StandardListingBuilder()), JsonFileStore(directory)
    )


def _create(service: ListingService, title: str = "Roman seti") -> str:
    listing = service.create_from_form(
        room_id="yurt-a",
        seller_id="pelin",
        title=title,
        price=Decimal("90"),
        category=Category.BOOKS,
        description="5 kitap.",
        photo_urls=["/photos/abc"],
    )
    return listing.listing_id


def test_listing_and_its_state_survive_a_restart(tmp_path: Path) -> None:
    first = _service(tmp_path)
    listing_id = _create(first)
    first.reserve(listing_id)

    restored = _service(tmp_path).get(listing_id)

    assert isinstance(restored.state, ReservedState)
    assert (restored.title, restored.price, restored.category) == ("Roman seti", Decimal("90"), Category.BOOKS)


def test_restored_listing_still_follows_state_rules(tmp_path: Path) -> None:
    first = _service(tmp_path)
    listing_id = _create(first)
    first.mark_sold(listing_id)

    restored = _service(tmp_path)

    with pytest.raises(Exception, match="satildi"):
        restored.reserve(listing_id)


def test_listing_order_is_kept(tmp_path: Path) -> None:
    first = _service(tmp_path)
    for title in ("Birinci", "İkinci", "Üçüncü"):
        _create(first, title)

    assert [l.title for l in _service(tmp_path).list_room("yurt-a")] == ["Birinci", "İkinci", "Üçüncü"]


def test_photo_survives_a_restart(tmp_path: Path) -> None:
    url = _service(tmp_path).save_photo(PHOTO, "image/png")

    assert _service(tmp_path).get_photo(url.rsplit("/", 1)[-1]) == (PHOTO, "image/png")


def test_photo_of_rejected_listing_is_not_kept_on_disk(tmp_path: Path) -> None:
    with pytest.raises(ModerationRejectedError):
        _service(tmp_path).create_from_photo(
            PHOTO, "image/png", room_id="yurt-a", seller_id="pelin", title="Satılık tabanca"
        )

    assert list((tmp_path / "photos").iterdir()) == []
    assert _service(tmp_path).list_room("yurt-a") == []


def test_corrupt_listings_file_starts_empty_instead_of_crashing(tmp_path: Path) -> None:
    (tmp_path / "listings.json").write_text("{ bozuk", encoding="utf-8")

    assert _service(tmp_path).list_room("yurt-a") == []


def test_broken_record_is_skipped_but_others_load(tmp_path: Path) -> None:
    service = _service(tmp_path)
    good_id = _create(service)
    path = tmp_path / "listings.json"
    path.write_text(path.read_text(encoding="utf-8")[:-2] + ', {"status": "bilinmiyor"}\n]', encoding="utf-8")

    assert [l.listing_id for l in _service(tmp_path).list_room("yurt-a")] == [good_id]


@pytest.mark.parametrize("photo_id", ["../listings.json", "abc", "ZZZZZZZZZZZZ"])
def test_invalid_photo_id_cannot_read_other_files(tmp_path: Path, photo_id: str) -> None:
    _create(_service(tmp_path))

    assert JsonFileStore(tmp_path).load_photo(photo_id) is None


def test_reading_does_not_create_the_data_folder(tmp_path: Path) -> None:
    folder = tmp_path / "data"
    JsonFileStore(folder).load_listings()

    assert not folder.exists()


def test_every_state_can_be_restored_by_name() -> None:
    assert set(STATE_BY_NAME) == {"taslak", "aktif", "rezerve", "satildi"}
    assert STATE_BY_NAME["taslak"] is DraftState
