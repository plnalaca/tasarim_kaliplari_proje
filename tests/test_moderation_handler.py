"""ModerationHandler temel mekanizması: bağlama, iletme, zincirin durması."""

from nearswap.domain.ai_types import ModerationResult
from nearswap.domain.listing import Listing
from nearswap.patterns.moderation.handler import ModerationHandler
from tests.helpers import RecordingState, make_listing


class _AlwaysPass(ModerationHandler):
    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self._log = log

    def handle(self, listing: Listing) -> ModerationResult:
        self._log.append("pass")
        return self._pass_to_next(listing)


class _AlwaysReject(ModerationHandler):
    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self._log = log

    def handle(self, listing: Listing) -> ModerationResult:
        self._log.append("reject")
        return ModerationResult.reject("test", checked_by="_AlwaysReject")


def test_set_next_returns_the_next_handler_for_fluent_chaining() -> None:
    log: list[str] = []
    first, second = _AlwaysPass(log), _AlwaysPass(log)
    assert first.set_next(second) is second


def test_chain_approves_when_every_handler_passes() -> None:
    log: list[str] = []
    head = _AlwaysPass(log)
    head.set_next(_AlwaysPass(log)).set_next(_AlwaysPass(log))

    result = head.handle(make_listing(RecordingState()))

    assert result.approved
    assert log == ["pass", "pass", "pass"]


def test_chain_stops_at_first_rejection() -> None:
    log: list[str] = []
    head = _AlwaysPass(log)
    head.set_next(_AlwaysReject(log)).set_next(_AlwaysPass(log))

    result = head.handle(make_listing(RecordingState()))

    assert not result.approved
    assert result.checked_by == "_AlwaysReject"
    assert log == ["pass", "reject"]
