# NearSwap: Tasarım Kalıpları (EBLG443) Proje Rehberi

> Bu dosya, ekip arkadaşım **Handan VURAL** ve onun kullandığı yapay zekâ asistanı için hazırlandı. Amaç, projeyi hiç bilmeyen birinin bu dosyayı okuyarak ne yaptığımızı, hangi kararları neden aldığımızı ve kodu nasıl çalıştıracağımızı anlayabilmesi.
>
> Son güncelleme: 18 Kasım 2026. **Proje sadeleştirildi:** 4 kalıp, düz paket yapısı, FastAPI ile çalışan sistem. Observer çıkarıldı (bkz. bölüm 9).

---

## 1. Kısa özet

| Konu | Karar |
|---|---|
| Ders | EBLG443 Tasarım Kalıpları (Nişantaşı Üniversitesi), öğretim üyesi Dr. Ulaş Vural |
| Ekip | Pelin ALACA (20222022383), Handan VURAL (20222022396) |
| Proje | **NearSwap: Yurt ve Siteler İçin Yapay Zekâ Destekli İkinci El Pazar Yeri** |
| Dil | **Python 3.11+** (dönem boyunca değiştirilemez), arayüz **FastAPI** |
| Kalıplar | **Builder** (yaratımsal), **Adapter** (yapısal), **State** ve **Chain of Responsibility** (davranışsal) |
| Yapay zekâ özellikleri | 1) Fotoğraftan ilan taslağı üretme, 2) İlanı yayından önce otomatik denetleme |
| Ek puan hedefi | Bitirme projesiyle eşleşme (+%10) ve yapay zekâ kullanımı (+%10) |
| Kod durumu | **Çalışıyor.** Dört kalıp eksiksiz yazıldı, 55 test geçiyor, mypy strict temiz |

---

## 2. Projenin arka planı

NearSwap aslında Pelin'in **bitirme projesi** (danışman: Dr. Sibel Boran). Bitirme projesinde mobil uygulama Flutter + Firebase ile yapılıyor; bu ders için ayrı bir **Python çekirdeği** yazıyoruz. İki proje birbirinin kodunu kullanmıyor.

**Problem:** Yurtlarda ve sitelerde ikinci el eşyalar WhatsApp gruplarında satılıyor. Pelin'in yurdundaki satış grubunda 367 kişi var. Pelin bu kişilerden 20'siyle konuştu:

- Bazıları mesajları takip etmekte zorlandığını söyledi.
- Bazıları bir ürünün fiyatını öğrenmek için satıcıya özelden yazmak zorunda kaldığından şikâyet etti.
- Satıcılardan biri, mesajlar görünürlüğünü kaybettiği için aynı ürünü farklı zamanlarda tekrar paylaştığını söyledi.

Dolap ve Gardrops gibi uygulamalar kargo gerektiriyor ve komisyon alıyor; aynı binada yaşayanlar için mantıklı değil.

**Çözüm:** İlanlar bir **"oda"ya** (yurt, apartman, site) bağlı. Satıcı fotoğraf yükler, yapay zekâ ilan taslağı önerir, ilan yayından önce denetlenir. Alıcıyla kapıda buluşulur; kargo ve komisyon yoktur.

---

## 3. Dersin proje kuralları (hocanın metninden özet)

1. **En az dört farklı GoF kalıbı**, yaratımsal, yapısal ve davranışsal gruplardan **en az birer** kalıp.
2. Mimari, eşzamanlılık, olay güdümlü ve LLM/ajan kalıpları zorunlu değil.
3. Her kalıbın **katılımcı rolleri ayrı ve anlamlı adlandırılmış sınıflarla** karşılanır.
4. Arayüzler dilin açık mekanizmasıyla yazılır. Biz **`abc.ABC`** kullanıyoruz.
5. Dile gömülü karşılık (ör. Strategy yerine lambda) en fazla iki kalıp için kullanılabilir. **Biz hiç kullanmıyoruz.**
6. **Çerçevenin hazır sunduğu kalıplar sayılmaz** (Django signals, blinker, middleware, FastAPI `Depends`).
7. Her kalıp **gerçek bir tasarım problemini çözmeli**; sayıyı tamamlamak için eklenen kalıp sayılmaz.

**Ek puanlar:** Bitirme projesiyle eşleşme +%10 (Handan'a da uygulanıp uygulanmayacağı hocaya sorulacak). Yapay zekâ modellerini ve gereken kalıpları kullanma +%10.

---

## 4. Sistemin yaptıkları

- Fotoğraftan yapay zekâ ile ilan taslağı önerme (başlık, kategori, açıklama, fiyat)
- Fotoğraftan ya da elle doldurulan formdan ilan verme
- İlanı yayından önce denetleme (yasaklı kelime, makul fiyat, yapay zekâ denetimi)
- İlanı rezerve etme, rezervasyonu iptal etme, satıldı olarak işaretleme
- Bir odadaki ilanları listeleme

**Kapsam dışı (sadeleştirme):** kullanıcı kaydı, oda üyeliği, mesajlaşma, bildirimler, kalıcı veritabanı. Veriler bellekte tutulur.

---

## 5. Kalıplar

| Kalıp | Grup | Dosya | Neyi çözüyor |
|---|---|---|---|
| **Builder** | Yaratımsal | `builder.py` | İlan farklı kaynaklardan adım adım doluyor; eksik ilan hiç oluşmamalı. |
| **Adapter** | Yapısal | `ai.py` | OpenAI ve Gemini farklı biçimlerde çağrılıyor; uygulama tek arayüz görmeli. |
| **State** | Davranışsal | `states.py` | İlanın durumuna göre izin verilen işlemler değişiyor. |
| **Chain of Responsibility** | Davranışsal | `moderation.py` | İlan yayından önce sıralı denetimlerden geçmeli; yenisi kolay eklenmeli. |

Chain of Responsibility, LLM literatüründeki **Guardrail** fikrine karşılık geliyor.

### 5.1 Builder (`builder.py`)

| Rol | Sınıf |
|---|---|
| Product | `Listing` (`models.py`) |
| Builder | `ListingBuilder(ABC)` |
| ConcreteBuilder | `StandardListingBuilder` |
| Director | `ListingDirector` |

- `build()` yalnızca **yapısal kuralları** denetler: oda ve satıcı var mı, başlık boş değil ve en fazla 80 karakter mi, fiyat > 0 mı, en az bir fotoğraf var mı, kategori seçili mi. **Bütün eksikleri birlikte** toplar ve tek bir `ListingValidationError(problems)` fırlatır. Geçerliyse ilanı **taslak** durumunda oluşturur ve kendini sıfırlar.
- `ListingDirector` iki kurma sırası sunar:
  - `from_form(...)`: kullanıcının elle doldurduğu formdan.
  - `from_ai_draft(draft, ...)`: yapay zekâ taslağından başlar; kullanıcı başlık ya da fiyat verdiyse onları kullanır. Yapay zekâ fiyat çıkaramazsa (0), kullanıcının fiyat girmesi zorunlu olur.

**Hocaya savunma:** "Python'da `dataclass` varken Builder'a gerek yok" itirazına cevabımız: ilan tek seferde değil, iki farklı kaynaktan ve iki farklı sırayla kuruluyor; doğrulama tek yerde. Bunu iki Director senaryosu ve testleri kodda gösteriyor.

### 5.2 Adapter (`ai.py`)

| Rol | Sınıf |
|---|---|
| Target | `AIService(ABC)`: `draft_listing(photo_bytes, mime_type) -> ListingDraft`, `moderate(text) -> ModerationResult` |
| Adaptee | `openai.OpenAI` istemcisi, `google.genai.Client` istemcisi |
| Adapter | `OpenAIAdapter`, `GeminiAdapter` |
| (Test) | `FakeAIAdapter`: ağa çıkmaz, sabit taslak döner, çağrıları kaydeder |

- **OpenAIAdapter:** taslak için Chat Completions (görsel, JSON yanıt), denetim için Moderations API.
- **GeminiAdapter:** ikisi için de `generate_content` (JSON yanıt). Denetim yanıtı okunamazsa ilanı **reddeder** (güvenli taraf).
- İki sağlayıcının yanıtı ortak `parse_draft()` ile `ListingDraft`'a çevrilir; bozuk kategori `diger`, okunamayan fiyat `0` olur.
- SDK istemcisi Adapter'a dışarıdan verilir; testler aynı biçimde yanıt veren **sahte istemcilerle** iki uyarlayıcıyı da ağa çıkmadan sınar.
- Sağlayıcı `.env` içindeki `NEARSWAP_AI_PROVIDER` (`fake` | `openai` | `gemini`) ile seçilir. Model adları da `.env`'den değiştirilebilir.

**İki gerçek uyarlayıcı şartı karşılandı.** Gerçek API anahtarıyla henüz denenmedi; teslimden önce bir kez denenmeli.

### 5.3 State (`states.py`)

| Durum | `publish()` | `reserve()` | `mark_sold()` | `cancel_reservation()` |
|---|---|---|---|---|
| Taslak | Aktif'e geçer | Hata | Hata | Hata |
| Aktif | Hata | Rezerve'ye geçer | Satıldı'ya geçer | Hata |
| Rezerve | Hata | Hata | Satıldı'ya geçer | Aktif'e döner |
| Satıldı | Hata | Hata | Hata | Hata |

| Rol | Sınıf |
|---|---|
| Context | `Listing` |
| State | `ListingState(ABC)` |
| ConcreteState | `DraftState`, `ActiveState`, `ReservedState`, `SoldState` |

- GoF'taki gibi `ListingState` her işlem için varsayılan davranışı tanımlar (`InvalidTransitionError`); her durum yalnızca izin verdiği işlemleri ezer. Kodda `if listing.status == ...` yok.
- Geçiş durumun içinde `listing.transition_to(ActiveState())` ile yapılır.
- Tablonun 16 hücresinin hepsi testli (`tests/test_states.py`).
- Sadeleştirme gereği **düzenleme (`edit`) işlemi çıkarıldı.**

### 5.4 Chain of Responsibility (`moderation.py`)

| Rol | Sınıf |
|---|---|
| Handler | `ModerationHandler(ABC)`: `set_next(handler)`, `handle(listing)`, `_pass_to_next(listing)` |
| ConcreteHandler | `BannedWordsHandler` → `PriceSanityHandler` → `AIModerationHandler` |
| Client | `ListingService` |

- Ucuz kontroller önce, yapay zekâ en sonda; ucuz kontrol reddederse API hiç çağrılmaz (testli).
- `AIModerationHandler`, yapay zekâya `AIService` (Adapter) üzerinden erişir. İki kalıp burada birlikte çalışır.
- Yasaklı kelime karşılaştırması **`turkish_lower`** ile yapılır (Python'un `lower()` işlevi İ/I'yı yanlış çevirir).
- Varsayılan fiyat üst sınırı 50.000 TL.
- `RequiredFieldsHandler` yok, çünkü bu kontrolü `build()` yapıyor.

---

## 6. Akış ve dosya yapısı

```
POST /listings/from-photo
  ├─ AIService.draft_listing(photo)        Adapter  -> ListingDraft
  ├─ ListingDirector.from_ai_draft(...)    Builder  -> Listing (taslak)
  ├─ zincir.handle(listing)                Chain    -> BannedWords → PriceSanity → AIModeration
  └─ listing.publish()                     State    -> aktif
```

Bu akışı `service.py` içindeki `ListingService` yürütür. Reddedilen ilan kaydedilmez.

```
nearswap/                  # depo kökü
├── pyproject.toml
├── README.md              # kurulum, uç noktalar, rol tablosu
├── .env.example
├── nearswap/
│   ├── models.py          # Listing, Category, ListingDraft, ModerationResult, hatalar, turkish_lower
│   ├── builder.py         # Builder
│   ├── ai.py              # Adapter
│   ├── states.py          # State
│   ├── moderation.py      # Chain of Responsibility
│   ├── service.py         # ListingService
│   └── api.py             # FastAPI
└── tests/                 # test_builder, test_ai, test_states, test_moderation, test_api
```

---

## 7. Çalıştırma ve teknik kurallar

```bash
pip install -e ".[dev,ai]"
cp .env.example .env
uvicorn nearswap.api:app --reload      # http://127.0.0.1:8000/docs
pytest                                  # 55 test
mypy                                    # strict
```

- Bir değişikliği göndermeden önce `pytest` ve `mypy` temiz geçmeli.
- Testler gerçek API'ye istek atmaz; `FakeAIAdapter` ya da sahte SDK istemcisi kullanılır.
- Para tutarları `Decimal`. API anahtarları yalnızca `.env` içinde.
- FastAPI yalnızca dış katman: servis `create_app(service)` ile verilir, `Depends` kullanılmaz.
- HTTP hata kodları: geçersiz ilan ve denetim reddi 422, izin verilmeyen durum işlemi 409, bulunamayan ilan 404.

---

## 8. İş bölümü (rapor ve sunum için)

Kod tamamlandı. Kalan işler için öneri:

| Kişi | Görev |
|---|---|
| Pelin | Builder ve State bölümlerinin rapordaki anlatımı ve sınıf diyagramları |
| Handan | Adapter ve Chain of Responsibility bölümlerinin anlatımı; gerçek OpenAI ve Gemini anahtarıyla deneme |
| Birlikte | Sunum, canlı demo (`/docs` üzerinden fotoğraftan ilan → rezerve → satıldı), hocaya sorulacakların takibi |

---

## 9. Açık sorular ve dikkat edilecekler

1. **Öneri dokümanından sapma (önemli):** Teslim ettiğimiz öneride 5 kalıp (Observer dahil) ve "odasındaki yeni ilanlar için bildirim alır" gereksinimi vardı. Observer ve bildirimler sadeleştirme için çıkarıldı. Kural en az dört kalıp istediği için geçerli, ama **hocaya haber verilmeli**. Gerekirse Observer geri eklenebilir: `Room` (Subject) yeni ilanda ve satışta olay yayınlar, `InAppNotifier` gibi gözlemciler dinler.
2. **Handan'ın ek puanı:** Bitirme projesi ek puanı ikimize de uygulanacak mı? Hocaya sorulacak.
3. **Çalışan yazılım beklentisi:** FastAPI ve `/docs` sayfası üzerinden demo yeterli mi? Hocaya sorulacak.
4. **Gerçek yapay zekâ denemesi:** İki uyarlayıcı gerçek anahtarla bir kez denenmeli.

---

## 10. Bu dosyayı okuyan yapay zekâ asistanı için notlar

- Dil **Python**. Başka dil önerme.
- Mevcut arayüzleri (`ListingBuilder`, `AIService`, `ListingState`, `ModerationHandler`) değiştirmeden önce kullanıcıya sor; diğer ekip üyesinin kodu bunlara dayanıyor.
- Kalıp sayısını tamamlamak için gereksiz kalıp ekleme.
- Her kalıp rolü ayrı, anlamlı adlandırılmış bir sınıf olmalı; arayüzler `abc.ABC` ile.
- Lambda gibi dile gömülü kısayolları ve Django signals, blinker, middleware, FastAPI `Depends` gibi hazır yapıları kalıp yerine kullanma.
- Yapay zekâ çağrıları her zaman `AIService` üzerinden. SDK'yı iş mantığında doğrudan çağırma.
- Para için `Decimal`, Türkçe metin karşılaştırması için `turkish_lower`.
- Her yeni sınıf için pytest testi ekle; mypy strict'ten geçmeli.
- Emin olmadığın ders kuralları için tahmin yürütme, kullanıcıya sor.
