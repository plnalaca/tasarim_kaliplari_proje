"""Observer kalıbı: bildirimler.

Roller:
- Subject          -> ListingEventPublisher    (publisher.py)
- ConcreteSubject  -> nearswap.domain.room.Room                         TODO(Handan)
- Observer         -> ListingObserver          (listing_observer.py)
- ConcreteObserver -> InAppNotifier, EmailNotifier, ActivityLogObserver TODO(Handan)

Hazır olay kütüphaneleri (blinker, Django signals) kalıp olarak SAYILMAZ, kullanılmayacak.
"""
