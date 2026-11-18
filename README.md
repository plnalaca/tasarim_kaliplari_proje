# NearSwap (EBLG443 Tasarım Kalıpları)

Yurt ve siteler için yapay zekâ destekli ikinci el pazar yeri. Python + FastAPI.
Ekip: Pelin ALACA, Handan VURAL. Ders: EBLG443, Dr. Ulaş Vural.

## Çalıştırma

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install -e ".[dev,ai]"
cp .env.example .env                      # Windows: copy .env.example .env
uvicorn nearswap.api:app --reload
```

Tarayıcıda **http://127.0.0.1:8000/docs** adresini açın. Bütün uç noktalar oradan denenebilir.

Varsayılan sağlayıcı `fake`: API anahtarı gerekmez, her fotoğrafa sabit bir taslak döner.
Gerçek yapay zekâ için `.env` içinde `NEARSWAP_AI_PROVIDER=openai` ya da `gemini` yapıp ilgili anahtarı girin.

```bash
pytest     # 55 test
mypy       # strict tip denetimi
```

## Dosyalar

```
nearswap/
├── models.py       Listing, Category, ListingDraft, ModerationResult, hatalar, turkish_lower
├── builder.py      Builder                  (Yaratımsal)
├── ai.py           Adapter                  (Yapısal)
├── states.py       State                    (Davranışsal)
├── moderation.py   Chain of Responsibility  (Davranışsal)
├── service.py      ListingService: dört kalıbı birbirine bağlar
└── api.py          FastAPI uç noktaları
tests/              her kalıp için ayrı dosya + uçtan uca API testi
```

## Kalıplar ve roller

| Kalıp | Rol | Sınıf |
|---|---|---|
| **Builder** | Product | `Listing` |
| | Builder | `ListingBuilder` |
| | ConcreteBuilder | `StandardListingBuilder` |
| | Director | `ListingDirector` (`from_form`, `from_ai_draft`) |
| **Adapter** | Target | `AIService` |
| | Adaptee | OpenAI SDK, Google Gen AI SDK |
| | Adapter | `OpenAIAdapter`, `GeminiAdapter` (+ test için `FakeAIAdapter`) |
| **State** | Context | `Listing` |
| | State | `ListingState` |
| | ConcreteState | `DraftState`, `ActiveState`, `ReservedState`, `SoldState` |
| **Chain of Responsibility** | Handler | `ModerationHandler` |
| | ConcreteHandler | `BannedWordsHandler`, `PriceSanityHandler`, `AIModerationHandler` |
| | Client | `ListingService` |

## Fotoğraftan ilan verme akışı

```
POST /listings/from-photo
  │
  ├─ AIService.draft_listing(photo)         Adapter      -> ListingDraft
  ├─ ListingDirector.from_ai_draft(...)     Builder      -> Listing (taslak)
  ├─ zincir.handle(listing)                 Chain        -> BannedWords → PriceSanity → AIModeration
  └─ listing.publish()                      State        -> aktif
```

## Uç noktalar

| Yöntem | Yol | Ne yapar |
|---|---|---|
| POST | `/ai/draft` | Fotoğraftan taslak önerir, ilan oluşturmaz |
| POST | `/listings/from-photo` | Fotoğraf + oda + satıcı ile ilan verir (başlık ve fiyat isteğe bağlı) |
| POST | `/listings` | Elle doldurulan formdan ilan verir |
| GET | `/rooms/{room_id}/listings` | Odadaki ilanlar |
| GET | `/listings/{id}` | Tek ilan |
| POST | `/listings/{id}/reserve` | Rezerve et |
| POST | `/listings/{id}/cancel-reservation` | Rezervasyonu iptal et |
| POST | `/listings/{id}/sold` | Satıldı olarak işaretle |
| GET | `/photos/{id}` | Yüklenen fotoğraf |

Hata kodları: eksik ya da hatalı ilan ve denetim reddi **422**, durumda izin verilmeyen işlem **409**, bulunamayan ilan **404**.

## Bilinen sınırlar

- Veriler bellekte tutulur, sunucu yeniden başlayınca silinir.
- Kullanıcı kaydı, oda üyeliği ve mesajlaşma yok. Oda yalnızca ilandaki `room_id` alanıdır.
- `OpenAIAdapter` ve `GeminiAdapter` sahte istemcilerle test edildi. Gerçek anahtarla bir kez denenmeli; model adları `.env` içinden değiştirilebilir.
