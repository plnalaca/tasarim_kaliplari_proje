from collections.abc import Callable

import pytest

from nearswap.models import InvalidTransitionError, Listing
from nearswap.states import ListingState
from tests.helpers import make_listing

Action = Callable[[Listing], None]

PUBLISH: Action = Listing.publish
RESERVE: Action = Listing.reserve
SOLD: Action = Listing.mark_sold
CANCEL: Action = Listing.cancel_reservation

# Her durum için ilanı o duruma getiren işlem dizisi.
SETUP: dict[str, list[Action]] = {
    "taslak": [],
    "aktif": [PUBLISH],
    "rezerve": [PUBLISH, RESERVE],
    "satildi": [PUBLISH, SOLD],
}

# (başlangıç durumu, işlem, beklenen durum ya da None = hata)
TABLE: list[tuple[str, Action, str | None]] = [
    ("taslak", PUBLISH, "aktif"),
    ("taslak", RESERVE, None),
    ("taslak", SOLD, None),
    ("taslak", CANCEL, None),
    ("aktif", PUBLISH, None),
    ("aktif", RESERVE, "rezerve"),
    ("aktif", SOLD, "satildi"),
    ("aktif", CANCEL, None),
    ("rezerve", PUBLISH, None),
    ("rezerve", RESERVE, None),
    ("rezerve", SOLD, "satildi"),
    ("rezerve", CANCEL, "aktif"),
    ("satildi", PUBLISH, None),
    ("satildi", RESERVE, None),
    ("satildi", SOLD, None),
    ("satildi", CANCEL, None),
]


def _listing_in(status: str) -> Listing:
    listing = make_listing()
    for action in SETUP[status]:
        action(listing)
    assert listing.status == status
    return listing


@pytest.mark.parametrize(
    ("start", "action", "expected"),
    TABLE,
    ids=[f"{s}-{a.__name__}" for s, a, _ in TABLE],
)
def test_transition_table(start: str, action: Action, expected: str | None) -> None:
    listing = _listing_in(start)

    if expected is None:
        with pytest.raises(InvalidTransitionError):
            action(listing)
        assert listing.status == start
    else:
        action(listing)
        assert listing.status == expected


def test_error_message_names_state_and_action() -> None:
    listing = _listing_in("satildi")
    with pytest.raises(InvalidTransitionError, match="'satildi' durumundaki ilan için 'rezerve et'"):
        listing.reserve()


def test_state_interface_is_abstract() -> None:
    with pytest.raises(TypeError):
        ListingState()  # type: ignore[abstract]
