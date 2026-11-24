# NearSwap Kurulum Dokümanı

Sistem, Python 3.11 ya da daha yeni bir sürümle beş adımda kurulup çalıştırılır. Varsayılan ayarlarla API anahtarı gerekmez.

## Gereksinimler

- Python 3.11 ya da daha yeni (`python3 --version` ile kontrol edilir)
- Git
- İsteğe bağlı: gerçek yapay zekâ için bir Gemini ya da OpenAI API anahtarı

## Adımlar

1. Depoyu klonlayın ve klasöre girin:

   ```bash
   git clone https://github.com/plnalaca/tasarim_kaliplari_proje.git
   cd tasarim_kaliplari_proje
   ```

2. Sanal ortamı oluşturup etkinleştirin:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   ```

3. Bağımlılıkları kurun:

   ```bash
   pip install -e ".[dev,ai]"
   ```

4. Yapılandırma dosyasını oluşturun:

   ```bash
   cp .env.example .env               # Windows: copy .env.example .env
   ```

5. Sunucuyu başlatın:

   ```bash
   uvicorn nearswap.api:app
   ```

Sunucu açılınca iki adres kullanılır:

- **http://127.0.0.1:8000/**: kullanıcı arayüzü (ilan verme, oda panosu, durum değiştirme, "Ne oldu?" günlüğü)
- **http://127.0.0.1:8000/docs**: bütün uç noktaların etkileşimli belgesi

## Yapılandırma (`.env`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `NEARSWAP_AI_PROVIDER` | `fake` | `fake` (anahtarsız, sabit taslak), `gemini` ya da `openai` |
| `GEMINI_API_KEY` | | Gemini kullanılırken gerekli |
| `OPENAI_API_KEY` | | OpenAI kullanılırken gerekli |
| `NEARSWAP_GEMINI_MODEL` | `gemini-3.8-flash` | Gemini model adı |
| `NEARSWAP_GEMINI_THINKING` | `low` | Gemini'nin düşünme düzeyi: `low`, `medium` ya da `high`; boş bırakılırsa modelin varsayılanı |
| `NEARSWAP_GEMINI_FALLBACK_MODELS` | `gemini-3.1-flash-lite` | Ana model yoğunken sırayla denenen yedek modeller (virgülle ayrılır); boş bırakılırsa yedek kullanılmaz |
| `NEARSWAP_OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model adı |
| `NEARSWAP_DATA_DIR` | `data` | İlanların ve fotoğrafların saklandığı klasör |

`.env` dosyası ve `data/` klasörü git'e eklenmez. Sağlayıcı değiştirildikten sonra sunucu yeniden başlatılmalıdır.

Seçili yapay zekâ sağlayıcısını sunucu açmadan denemek için:

```bash
python scripts/try_ai.py urun_fotografi.jpg
```

Betik, fotoğraftan çıkarılan taslağı ve iki örnek metnin denetim sonucunu yazdırır.

## Sık karşılaşılan durumlar

| Belirti | Sebep ve çözüm |
|---|---|
| `pip install` sırasında sürüm hatası | Python 3.11'den eski. Daha yeni bir Python kurup sanal ortamı yeniden oluşturun. |
| Ana adreste `{"detail":"Not Found"}` | Eski bir sürüm çalışıyor. Depoyu güncelleyip sunucuyu yeniden başlatın. |
| `address already in use` | 8000 portu dolu. `uvicorn nearswap.api:app --port 8001` ile başka port kullanın. |
| Sunucu açılırken `GEMINI_API_KEY tanımlı değil` | Gemini seçili ama anahtar yok. Anahtarı `.env`'e yazın ya da sağlayıcıyı `fake` yapın. |
| Arayüzde 503 hatası | Yapay zekâ servisine ulaşılamıyor (örneğin geçici yoğunluk). Sistem isteği bir kez tekrar dener, ardından yedek modele (`gemini-3.1-flash-lite`) geçer; sorun sürerse biraz sonra tekrar deneyin. Sebep, sunucunun çalıştığı terminale yazılır. |
| Yayınlama yavaş | Sunucunun terminalinde her yapay zekâ işleminin süresi yazar (örneğin `Taslaktan ilan: 2.3 sn`). Süre uzunsa `NEARSWAP_GEMINI_THINKING=low` olduğundan emin olun. |
| İlanları sıfırlamak | `data/` klasörünü silip sunucuyu yeniden başlatın. |
