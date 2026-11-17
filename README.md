# NearSwap (EBLG443 Tasarım Kalıpları)

Yurt ve siteler için yapay zekâ destekli ikinci el pazar yerinin **Python çekirdeği**.
Ekip: Pelin ALACA, Handan VURAL. Ders: EBLG443, Dr. Ulaş Vural.

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # gerçek AI uyarlayıcıları için: pip install -e ".[dev,ai]"
cp .env.example .env               # anahtarları .env içine yazın
```

## Komutlar

```bash
pytest          # testler
mypy            # tip denetimi (strict)
```

Bir değişikliği göndermeden önce ikisi de temiz geçmeli.

## Klasör yapısı

```
nearswap/
├── domain/        Listing, Room, User, Category, ortak veri tipleri, hatalar
├── patterns/
│   ├── builder/     Builder                  (Yaratımsal)
│   ├── adapter/     Adapter                  (Yapısal)
│   ├── state/       State                    (Davranışsal)
│   ├── observer/    Observer                 (Davranışsal)
│   └── moderation/  Chain of Responsibility  (Davranışsal)
├── services/      Kalıpları birbirine bağlayan akışlar (ilan verme)
└── api/           (isteğe bağlı) FastAPI ya da komut satırı
tests/             pytest testleri
```

Her kalıp klasörünün `__init__.py` dosyasında rollerin hangi sınıflarla karşılandığı yazıyor.

## Kalıp rolleri ve durum

| Kalıp | Arayüz (hazır) | Somut sınıflar | Kim |
|---|---|---|---|
| Builder | `ListingBuilder` | `StandardListingBuilder`, `ListingDirector` | Pelin |
| State | `ListingState` | `DraftState`, `ActiveState`, `ReservedState`, `SoldState` | Pelin |
| Adapter | `AIService` | `OpenAIAdapter`, `GeminiAdapter` (+ hazır `FakeAIAdapter`) | Handan |
| Observer | `ListingEventPublisher`, `ListingObserver` | `Room`, `InAppNotifier`, `EmailNotifier`, `ActivityLogObserver` | Handan |
| Chain of Resp. | `ModerationHandler` | `BannedWordsHandler`, `PriceSanityHandler`, `AIModerationHandler` | Handan |
| İlan verme akışı | | `ListingPublishService` | Birlikte |

Yapılacaklar kodda `TODO(Pelin)`, `TODO(Handan)` ve `TODO(birlikte)` ile işaretli.

## İskelette alınan kararlar

Rehber dosyasında açık kalan noktalar için şimdilik şu kararlar uygulandı. Gerekirse değiştirilir.

1. **`DraftState` eklendi.** Builder'ın oluşturduğu ilan önce Taslak durumunda olur, denetimden geçince `publish()` ile Aktif'e geçer. Geçiş tablosu `patterns/state/__init__.py` içinde.
2. **Fiyat `Decimal` tipinde.** Para hesaplarında `float` yuvarlama hatası yapar.
3. **Observer'da Subject `Room`.** `Listing` zaten Product ve Context rollerini taşıyor.
4. **Builder ile zincirin görevi ayrıldı.** `build()` yapısal kuralları denetler, zincir içerik politikasını. `RequiredFieldsHandler` bu yüzden iskelete konmadı (bkz. `patterns/moderation/handlers.py`).
5. **Türkçe metin karşılaştırması için `turkish_lower` kullanılmalı.** Python'un `lower()` ve `casefold()` işlevleri İ/I harflerini yanlış çevirir.

## Kurallar (özet)

- Arayüzler `abc.ABC` ile yazılır. Her rol ayrı ve anlamlı adlandırılmış bir sınıftır.
- Lambda gibi dile gömülü kısayollar kalıp yerine kullanılmaz.
- blinker, Django signals, middleware, FastAPI `Depends` gibi hazır yapılar kalıp yerine kullanılmaz.
- Yapay zekâya her zaman `AIService` üzerinden erişilir. Testler `FakeAIAdapter` kullanır, gerçek API'ye istek atmaz.
- API anahtarları koda yazılmaz, `.env` dosyasından okunur.
