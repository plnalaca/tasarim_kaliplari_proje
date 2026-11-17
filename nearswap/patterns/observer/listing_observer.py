from abc import ABC, abstractmethod

from nearswap.patterns.observer.events import ListingEvent


class ListingObserver(ABC):
    """Observer arayüzü."""

    @abstractmethod
    def update(self, event: ListingEvent) -> None: ...
