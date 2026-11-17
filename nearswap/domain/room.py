"""Oda: bir yurt, apartman ya da site için kurulan kapalı ilan alanı.

Observer kalıbında **ConcreteSubject** rolünü üstlenir. Odaya yeni ilan eklendiğinde ya da
odadaki bir ilan satıldığında olayı yayınlar; bildirimin nasıl gönderileceğini bilmez.

TODO(Handan): attach / detach / notify gövdeleri. Hazır olay kütüphanesi (blinker,
Django signals vb.) KULLANILMAYACAK; abone listesi ve döngü burada elle yazılacak.
"""

from nearswap.patterns.observer.events import ListingEvent
from nearswap.patterns.observer.listing_observer import ListingObserver
from nearswap.patterns.observer.publisher import ListingEventPublisher


class Room(ListingEventPublisher):
    def __init__(self, room_id: str, name: str, invite_code: str) -> None:
        self.room_id = room_id
        self.name = name
        self.invite_code = invite_code
        self.member_ids: set[str] = set()
        self._observers: list[ListingObserver] = []

    def attach(self, observer: ListingObserver) -> None:
        raise NotImplementedError("TODO(Handan)")

    def detach(self, observer: ListingObserver) -> None:
        raise NotImplementedError("TODO(Handan)")

    def notify(self, event: ListingEvent) -> None:
        raise NotImplementedError("TODO(Handan)")
