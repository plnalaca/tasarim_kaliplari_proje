# NearSwap Test Dokümanı

117 otomatik testin hepsi geçiyor ve kodun yüzde 99'unu çalıştırıyor (678 komuttan 668'i). Kod mypy strict modunda hatasız geçiyor.

## Çalıştırma

Sanal ortam etkinken proje klasöründe (kurulum için [KURULUM.md](KURULUM.md)):

```bash
pytest                              # bütün testler
pytest -v tests/test_states.py      # tek bir dosya, her testin adıyla
mypy                                # tip denetimi
```

Kapsam ölçümü için `pip install pytest-cov` kurulup şu komut çalıştırılır:

```bash
pytest --cov=nearswap --cov-report=term-missing
```

Testler gerçek yapay zekâ API'sine hiç istek atmaz ve kullanıcının `data/` klasörüne dokunmaz. Yapay zekâ gereken yerlerde `FakeAIAdapter` ya da gerçek SDK ile aynı biçimde yanıt veren sahte istemciler, kayıt testlerinde geçici klasörler kullanılır.

## Test dosyaları

| Dosya | Test | Neyi doğrular |
|---|---|---|
| `tests/test_ai.py` | 34 | İki adaptörün doğru isteği gönderip yanıtı ortak tiplere çevirmesi, bozuk yanıtlar, sağlayıcı seçimi, zaman aşımı ve yeniden deneme ayarları (Adapter) |
| `tests/test_states.py` | 18 | Geçiş tablosunun 16 hücresinin her biri, hata mesajı, arayüzün soyutluğu (State) |
| `tests/test_moderation.py` | 16 | Zincirin bağlanması ve ilk retle durması, her halka, Türkçe büyük harf, kelime sınırı, ucuz kontrol reddedince yapay zekânın çağrılmaması (Chain of Responsibility) |
| `tests/test_api.py` | 16 | Uçtan uca HTTP akışları, hata kodları (422, 409, 404, 415, 503), arayüz sayfası |
| `tests/test_storage.py` | 12 | Sunucu yeniden başladıktan sonra ilanların, durumların ve fotoğrafların geri gelmesi, bozuk dosyalar |
| `tests/test_models.py` | 11 | Arayüzlerin soyutluğu, `Listing`'in her işlemi duruma devretmesi, varsayılan durum davranışı |
| `tests/test_builder.py` | 10 | Eksik alanların birlikte bildirilmesi, iki Director senaryosu, kullanıcının taslağı düzeltmesi (Builder) |

## Kalıplara göre öne çıkan testler

| Kalıp | Test | Doğrulanan davranış |
|---|---|---|
| Builder | `test_build_collects_every_problem_at_once` | Eksik ilan oluşmaz; bütün sorunlar tek seferde bildirilir |
| Builder | `test_director_from_ai_draft_lets_user_fix_category_and_description` | Kullanıcının verdiği alanlar yapay zekâ taslağının yerine geçer |
| Adapter | `test_both_adapters_return_the_same_draft_for_the_same_answer` | İki sağlayıcı aynı yanıttan aynı `ListingDraft`'ı üretir |
| Adapter | `test_gemini_moderate_rejects_when_answer_is_unreadable` | Okunamayan denetim yanıtında ilan reddedilir |
| State | `test_transition_table` (16 durum) | Her durum yalnızca izin verdiği işlemi kabul eder, reddedilen işlem durumu değiştirmez |
| State | `test_restored_listing_still_follows_state_rules` | Diskten yüklenen satılmış ilan da rezerve edilemez |
| Chain of Responsibility | `test_default_chain_does_not_call_ai_when_banned_word_rejects` | Ucuz kontrol reddederse yapay zekâ çağrılmaz |
| Chain of Responsibility | `test_banned_word_inside_another_word_is_not_rejected` | "esrar" yasaklıyken "esrarengiz" geçer |

## Elle test senaryosu

Sunucu `fake` sağlayıcıyla çalışırken **http://127.0.0.1:8000/** adresinde:

| Adım | Beklenen sonuç | Kalıp |
|---|---|---|
| Fotoğraftan sekmesinde bir fotoğraf seç | Başlık, fiyat, kategori ve açıklama öneriyle dolar | Adapter |
| Kategoriyi değiştirip Yayınla'ya bas | İlan panoda seçilen kategoriyle, "Aktif" etiketiyle görünür | Builder, State |
| Elle sekmesinde fotoğraf eklemeden yayınla | "En az bir fotoğraf eklenmeli" uyarısı | Builder |
| Başlığa "Satılık tabanca" yazıp yayınla | İlan reddedilir, günlükte `BannedWordsHandler` yazar | Chain of Responsibility |
| Aktif ilanda Rezerve et, ardından Satıldı | Etiket önce "Rezerve", sonra "Satıldı" olur | State |
| Satılmış ilanda Rezerve et | "'satildi' durumundaki ilan için 'rezerve et' yapılamaz" hatası | State |
| Sunucuyu kapatıp yeniden aç | İlanlar aynı durumlarıyla geri gelir | (kalıcı kayıt) |
