"""Chain of Responsibility kalıbı: yayın öncesi ilan denetimi (Guardrail).

Roller:
- Handler         -> ModerationHandler    (handler.py)
- ConcreteHandler -> BannedWordsHandler, PriceSanityHandler, AIModerationHandler  TODO(Handan)
- Client          -> nearswap.services.listing_publish_service.ListingPublishService

Ucuz kontroller önce, yapay zekâ kontrolü en sonda çalışır.
Bir halka reddederse zincir durur ve reddetme sebebi döner.
Web çatısının middleware zinciri bu kalıp olarak SAYILMAZ.
"""
