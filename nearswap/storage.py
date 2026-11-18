"""İlanları ve fotoğrafları diskte saklar; sunucu yeniden başlasa da veriler kalır.

ListingService'in kullandığı yardımcı bir kayıt katmanıdır; tasarım kalıplarından biri değildir.

Dosyalar (varsayılan klasör: data/, .env içinde NEARSWAP_DATA_DIR ile değiştirilebilir):
    listings.json     ilanlar, durum adıyla birlikte ("aktif", "rezerve" ...)
    photos.json       fotoğraf kimliği -> MIME türü
    photos/<kimlik>   fotoğrafın kendisi

Klasör ilk kayıtta oluşturulur; yalnızca okumak diske bir şey yazmaz.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from nearswap.models import Category, Listing
from nearswap.states import ActiveState, DraftState, ListingState, ReservedState, SoldState

# Kayıttaki durum adından durum nesnesini geri kurmak için. Geçiş kuralları burada değil,
# yalnızca states.py içinde; burası sadece kaydedilen adı sınıfa çevirir.
_STATE_CLASSES: tuple[type[ListingState], ...] = (DraftState, ActiveState, ReservedState, SoldState)
STATE_BY_NAME: dict[str, type[ListingState]] = {cls().name: cls for cls in _STATE_CLASSES}

_PHOTO_ID = re.compile(r"[0-9a-f]{12}")


def _listing_to_dict(listing: Listing) -> dict[str, Any]:
    return {
        "listing_id": listing.listing_id,
        "room_id": listing.room_id,
        "seller_id": listing.seller_id,
        "title": listing.title,
        "price": str(listing.price),
        "photos": list(listing.photos),
        "category": listing.category.value,
        "description": listing.description,
        "status": listing.status,
    }


def _listing_from_dict(item: dict[str, Any]) -> Listing:
    return Listing(
        listing_id=str(item["listing_id"]),
        room_id=str(item["room_id"]),
        seller_id=str(item["seller_id"]),
        title=str(item["title"]),
        price=Decimal(str(item["price"])),
        photos=tuple(str(p) for p in item["photos"]),
        category=Category(item["category"]),
        description=str(item.get("description", "")),
        state=STATE_BY_NAME[item["status"]](),
    )


class JsonFileStore:
    def __init__(self, directory: Path | str) -> None:
        self._dir = Path(directory)
        self._listings_file = self._dir / "listings.json"
        self._photo_index_file = self._dir / "photos.json"
        self._photos_dir = self._dir / "photos"
        self._lock = threading.Lock()  # FastAPI istekleri aynı anda yazmaya çalışabilir

    # --- İlanlar ------------------------------------------------------------------------

    def load_listings(self) -> dict[str, Listing]:
        """Kayıtlı ilanları yükler. Dosya yoksa ya da bozuksa boş başlar; bozuk tek kayıt atlanır."""
        raw = self._read_json(self._listings_file, [])
        listings: dict[str, Listing] = {}
        if not isinstance(raw, list):
            return listings
        for item in raw:
            try:
                listing = _listing_from_dict(item)
            except (KeyError, TypeError, ValueError, InvalidOperation):
                continue
            listings[listing.listing_id] = listing
        return listings

    def save_listings(self, listings: Iterable[Listing]) -> None:
        with self._lock:
            self._write_json(self._listings_file, [_listing_to_dict(l) for l in listings])

    # --- Fotoğraflar --------------------------------------------------------------------

    def save_photo(self, photo_id: str, data: bytes, mime_type: str) -> None:
        self._check_photo_id(photo_id)
        with self._lock:
            self._photos_dir.mkdir(parents=True, exist_ok=True)
            (self._photos_dir / photo_id).write_bytes(data)
            index = self._photo_index()
            index[photo_id] = mime_type
            self._write_json(self._photo_index_file, index)

    def load_photo(self, photo_id: str) -> tuple[bytes, str] | None:
        if not _PHOTO_ID.fullmatch(photo_id):  # "../" gibi yollarla klasör dışına çıkılmasın
            return None
        mime_type = self._photo_index().get(photo_id)
        path = self._photos_dir / photo_id
        if mime_type is None or not path.is_file():
            return None
        return path.read_bytes(), mime_type

    def delete_photo(self, photo_id: str) -> None:
        if not _PHOTO_ID.fullmatch(photo_id):
            return
        with self._lock:
            (self._photos_dir / photo_id).unlink(missing_ok=True)
            index = self._photo_index()
            if index.pop(photo_id, None) is not None:
                self._write_json(self._photo_index_file, index)

    # --- Yardımcılar --------------------------------------------------------------------

    def _photo_index(self) -> dict[str, str]:
        raw = self._read_json(self._photo_index_file, {})
        return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}

    @staticmethod
    def _check_photo_id(photo_id: str) -> None:
        if not _PHOTO_ID.fullmatch(photo_id):
            raise ValueError(f"Geçersiz fotoğraf kimliği: {photo_id!r}")

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
            return default

    def _write_json(self, path: Path, data: Any) -> None:
        """Önce geçici dosyaya yazar, sonra yerine koyar: yazma yarıda kesilirse eski dosya bozulmaz."""
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
