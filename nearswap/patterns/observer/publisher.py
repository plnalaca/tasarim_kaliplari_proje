from abc import ABC, abstractmethod

from nearswap.patterns.observer.events import ListingEvent
from nearswap.patterns.observer.listing_observer import ListingObserver


class ListingEventPublisher(ABC):
    """Subject arayüzü."""

    @abstractmethod
    def attach(self, observer: ListingObserver) -> None: ...

    @abstractmethod
    def detach(self, observer: ListingObserver) -> None: ...

    @abstractmethod
    def notify(self, event: ListingEvent) -> None: ...
