"""HTTP arayüzü (FastAPI) ve kullanıcı arayüzü sayfası.

Bu katman yalnızca ListingService'i çağırır; tasarım kalıpları çatıdan bağımsız modüllerdedir
(builder, ai, states, moderation). Servis, çatının bağımlılık enjeksiyonu yerine create_app()
içinde açıkça verilir; böylece testler kendi servislerini doğrudan geçebilir.

Çalıştırma:  uvicorn nearswap.api:app --reload
    http://127.0.0.1:8000/       kullanıcı arayüzü
    http://127.0.0.1:8000/docs   uç noktaların belgesi
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from nearswap.ai import create_ai_service
from nearswap.builder import ListingDirector, StandardListingBuilder
from nearswap.models import (
    Category,
    DraftNotFoundError,
    InvalidTransitionError,
    Listing,
    ListingNotFoundError,
    ListingValidationError,
    ModerationRejectedError,
    NearSwapError,
)
from nearswap.moderation import build_default_chain
from nearswap.service import ListingService, PreparedDraft
from nearswap.storage import JsonFileStore

MAX_PHOTO_BYTES = 5 * 1024 * 1024
INDEX_PAGE = Path(__file__).parent / "static" / "index.html"
logger = logging.getLogger("uvicorn.error")  # uvicorn'un Terminal çıktısına yazar


# --- İstek / yanıt şemaları ---------------------------------------------------------------


class ListingIn(BaseModel):
    room_id: str = Field(examples=["yurt-a-blok"])
    seller_id: str = Field(examples=["pelin"])
    title: str = Field(examples=["Çalışma lambası"])
    price: Decimal = Field(examples=["150"])
    category: Category
    description: str = ""
    photo_urls: list[str] = Field(default_factory=list, examples=[["https://ornek.com/lamba.jpg"]])


class ListingOut(BaseModel):
    listing_id: str
    room_id: str
    seller_id: str
    title: str
    price: Decimal
    category: Category
    description: str
    photos: list[str]
    status: str

    @classmethod
    def of(cls, listing: Listing) -> ListingOut:
        return cls(
            listing_id=listing.listing_id,
            room_id=listing.room_id,
            seller_id=listing.seller_id,
            title=listing.title,
            price=listing.price,
            category=listing.category,
            description=listing.description,
            photos=list(listing.photos),
            status=listing.status,
        )


class PhotoOut(BaseModel):
    url: str


class DraftOut(BaseModel):
    draft_id: str = Field(description="İlanı /listings/from-draft ile yayınlarken kullanılır")
    title: str
    category: Category
    description: str
    suggested_price: Decimal

    @classmethod
    def of(cls, prepared: PreparedDraft) -> DraftOut:
        draft = prepared.draft
        return cls(
            draft_id=prepared.draft_id,
            title=draft.title,
            category=draft.category,
            description=draft.description,
            suggested_price=draft.suggested_price,
        )


class DraftListingIn(BaseModel):
    draft_id: str
    room_id: str = Field(examples=["yurt-a-blok"])
    seller_id: str = Field(examples=["pelin"])
    title: str | None = None
    price: Decimal | None = None
    category: Category | None = None
    description: str | None = None


# --- Uygulama -----------------------------------------------------------------------------


def create_default_service() -> ListingService:
    load_dotenv()
    ai = create_ai_service()
    store = JsonFileStore(os.getenv("NEARSWAP_DATA_DIR") or "data")
    return ListingService(ai, build_default_chain(ai), ListingDirector(StandardListingBuilder()), store)


@contextmanager
def _ai_errors(task: str) -> Iterator[None]:
    """Yapay zekâ servisi hata verirse (ağ, kota, geçici yoğunluk, okunamayan yanıt) 503 döner.

    Alan hataları (NearSwapError) kendi eşlemeleriyle (422, 409, 404) dönmeye devam eder.
    Her işlemin süresi Terminal'e yazılır; yavaşlığın nerede olduğu buradan görülür.
    """
    started = time.perf_counter()
    try:
        yield
        logger.info("%s: %.1f sn", task, time.perf_counter() - started)
    except NearSwapError:
        logger.info("%s: %.1f sn (reddedildi)", task, time.perf_counter() - started)
        raise
    except Exception as exc:
        logger.exception("Yapay zekâ çağrısı başarısız oldu")
        raise HTTPException(
            status_code=503,
            detail=(
                "Yapay zekâ servisine şu an ulaşılamıyor ya da yanıtı okunamadı. "
                f"Biraz sonra tekrar deneyin. ({type(exc).__name__})"
            ),
        ) from exc


async def _read_photo(photo: UploadFile) -> tuple[bytes, str]:
    mime_type = photo.content_type or ""
    if not mime_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Yalnızca görsel dosyası yüklenebilir.")
    data = await photo.read()
    if not data:
        raise HTTPException(status_code=400, detail="Fotoğraf boş.")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Fotoğraf en fazla 5 MB olabilir.")
    return data, mime_type


def create_app(service: ListingService | None = None) -> FastAPI:
    svc = service or create_default_service()
    app = FastAPI(
        title="NearSwap",
        description="Yurt ve siteler için yapay zekâ destekli ikinci el pazar yeri (EBLG443).",
        version="1.0.0",
    )

    # --- Hata eşlemeleri -------------------------------------------------------------

    @app.exception_handler(ListingValidationError)
    async def _validation(_: Request, exc: ListingValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": "gecersiz_ilan", "problems": exc.problems})

    @app.exception_handler(ModerationRejectedError)
    async def _rejected(_: Request, exc: ModerationRejectedError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "denetim_reddi", "reason": exc.result.reason, "checked_by": exc.result.checked_by},
        )

    @app.exception_handler(InvalidTransitionError)
    async def _transition(_: Request, exc: InvalidTransitionError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": "gecersiz_islem", "detail": str(exc)})

    @app.exception_handler(DraftNotFoundError)
    async def _draft_missing(_: Request, exc: DraftNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": "taslak_bulunamadi", "detail": str(exc)})

    @app.exception_handler(ListingNotFoundError)
    async def _not_found(_: Request, exc: ListingNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": "bulunamadi", "detail": str(exc)})

    # --- Uç noktalar -----------------------------------------------------------------

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        """Kullanıcı arayüzü: ilan verme, oda panosu ve durum değiştirme tek sayfada."""
        return FileResponse(INDEX_PAGE, media_type="text/html")

    @app.post("/ai/draft", response_model=DraftOut, tags=["yapay zekâ"])
    async def suggest_draft(photo: Annotated[UploadFile, File()]) -> DraftOut:
        """Fotoğraftan ilan taslağı önerir ve saklar. İlan oluşturmaz.

        Dönen draft_id ile /listings/from-draft çağrılırsa yapay zekâ ikinci kez çağrılmaz.
        """
        data, mime_type = await _read_photo(photo)
        # Yapay zekâ çağrısı saniyeler sürebilir; ayrı iş parçacığında çalışır ki sunucu donmasın.
        with _ai_errors("Taslak önerisi"):
            prepared = await run_in_threadpool(svc.prepare_draft, data, mime_type)
        return DraftOut.of(prepared)

    @app.post("/listings/from-draft", response_model=ListingOut, status_code=201, tags=["ilanlar"])
    def create_from_draft(body: DraftListingIn) -> ListingOut:
        """/ai/draft ile üretilmiş taslaktan ilan verir; yapay zekâ yalnızca denetim için çağrılır.

        Başlık, fiyat, kategori ya da açıklama verilirse taslaktakinin yerine geçer.
        """
        with _ai_errors("Taslaktan ilan"):
            listing = svc.create_from_draft(
                body.draft_id,
                room_id=body.room_id,
                seller_id=body.seller_id,
                title=body.title or None,
                price=body.price,
                category=body.category,
                description=body.description or None,
            )
        return ListingOut.of(listing)

    @app.post("/listings/from-photo", response_model=ListingOut, status_code=201, tags=["ilanlar"])
    async def create_from_photo(
        photo: Annotated[UploadFile, File()],
        room_id: Annotated[str, Form()],
        seller_id: Annotated[str, Form()],
        title: Annotated[str | None, Form()] = None,
        price: Annotated[Decimal | None, Form()] = None,
        category: Annotated[Category | None, Form()] = None,
        description: Annotated[str | None, Form()] = None,
    ) -> ListingOut:
        """Fotoğraftan yapay zekâ taslağıyla ilan verir.

        Başlık, fiyat, kategori ya da açıklama verilirse taslaktakinin yerine geçer.
        """
        data, mime_type = await _read_photo(photo)
        with _ai_errors("Fotoğraftan ilan"):
            listing = await run_in_threadpool(
                svc.create_from_photo,
                data,
                mime_type,
                room_id=room_id,
                seller_id=seller_id,
                title=title or None,
                price=price,
                category=category,
                description=description or None,
            )
        return ListingOut.of(listing)

    @app.post("/listings", response_model=ListingOut, status_code=201, tags=["ilanlar"])
    def create_listing(body: ListingIn) -> ListingOut:
        """Elle doldurulan formdan ilan verir."""
        with _ai_errors("Formdan ilan"):  # denetim zincirinin son halkası yapay zekâyı çağırır
            listing = svc.create_from_form(
                room_id=body.room_id,
                seller_id=body.seller_id,
                title=body.title,
                price=body.price,
                category=body.category,
                description=body.description,
                photo_urls=body.photo_urls,
            )
        return ListingOut.of(listing)

    @app.get("/rooms/{room_id}/listings", response_model=list[ListingOut], tags=["ilanlar"])
    def list_room(room_id: str) -> list[ListingOut]:
        return [ListingOut.of(l) for l in svc.list_room(room_id)]

    @app.get("/listings/{listing_id}", response_model=ListingOut, tags=["ilanlar"])
    def get_listing(listing_id: str) -> ListingOut:
        return ListingOut.of(svc.get(listing_id))

    @app.post("/listings/{listing_id}/reserve", response_model=ListingOut, tags=["durum"])
    def reserve(listing_id: str) -> ListingOut:
        return ListingOut.of(svc.reserve(listing_id))

    @app.post("/listings/{listing_id}/cancel-reservation", response_model=ListingOut, tags=["durum"])
    def cancel_reservation(listing_id: str) -> ListingOut:
        return ListingOut.of(svc.cancel_reservation(listing_id))

    @app.post("/listings/{listing_id}/sold", response_model=ListingOut, tags=["durum"])
    def mark_sold(listing_id: str) -> ListingOut:
        return ListingOut.of(svc.mark_sold(listing_id))

    @app.post("/photos", response_model=PhotoOut, status_code=201, tags=["fotoğraflar"])
    async def upload_photo(photo: Annotated[UploadFile, File()]) -> PhotoOut:
        """Fotoğrafı yükler ve adresini döner. Elle ilan verirken photo_urls içinde kullanılır."""
        data, mime_type = await _read_photo(photo)
        return PhotoOut(url=svc.save_photo(data, mime_type))

    @app.get("/photos/{photo_id}", tags=["fotoğraflar"])
    def get_photo(photo_id: str) -> Response:
        found = svc.get_photo(photo_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı.")
        data, mime_type = found
        return Response(content=data, media_type=mime_type)

    return app


app = create_app()
