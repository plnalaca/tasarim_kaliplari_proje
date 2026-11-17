"""Adapter kalıbı: yapay zekâ servisleri.

Roller:
- Target  -> AIService         (ai_service.py)
- Adaptee -> OpenAI SDK, Gemini SDK (dış kütüphaneler)
- Adapter -> OpenAIAdapter, GeminiAdapter                    TODO(Handan)
- Test    -> FakeAIAdapter     (fake_adapter.py): ağa çıkmaz, testlerde kullanılır.

Kalıbın geçerli sayılması için en az İKİ gerçek uyarlayıcı olmalı.
İş mantığı SDK'ları hiçbir zaman doğrudan çağırmaz; her zaman AIService üzerinden gider.
"""
