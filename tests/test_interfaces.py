"""Her kalıbın arayüzü gerçekten soyut mu? (abc.ABC ile tanımlanma kuralı)"""

import pytest

from nearswap.patterns.adapter.ai_service import AIService
from nearswap.patterns.builder.listing_builder import ListingBuilder
from nearswap.patterns.moderation.handler import ModerationHandler
from nearswap.patterns.observer.listing_observer import ListingObserver
from nearswap.patterns.observer.publisher import ListingEventPublisher
from nearswap.patterns.state.listing_state import ListingState

INTERFACES = [
    ListingBuilder,
    AIService,
    ListingState,
    ListingEventPublisher,
    ListingObserver,
    ModerationHandler,
]


@pytest.mark.parametrize("interface", INTERFACES, ids=lambda c: c.__name__)
def test_interface_cannot_be_instantiated(interface: type) -> None:
    with pytest.raises(TypeError):
        interface()
