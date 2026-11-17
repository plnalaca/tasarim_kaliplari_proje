"""TODO(Handan): somut denetim halkaları

- BannedWordsHandler   : başlık ve açıklamada yasaklı kelime var mı?
- PriceSanityHandler   : fiyat kategoriye göre makul aralıkta mı?
- AIModerationHandler  : AIService.moderate() çağırır (Adapter ile birlikte çalışır). Zincirin SONUNDA.

Açık soru: Rehberdeki RequiredFieldsHandler, ListingBuilder.build() ile aynı işi yapıyor.
Ya zincirden çıkarılmalı ya da örneğin DuplicateListingHandler (aynı ilanın tekrar
paylaşılması) gibi farklı bir görev almalı.
"""
