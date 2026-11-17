"""TODO(birlikte): ListingPublishService (Chain of Responsibility'de Client)

İlan verme akışı:
  1. AIService.draft_listing(photo)             -> ListingDraft        (Adapter)
  2. ListingDirector.from_ai_draft(...)         -> Listing, DraftState (Builder)
  3. moderation_chain.handle(listing)           -> ModerationResult    (Chain of Responsibility)
  4. onaylandıysa listing.publish()             -> ActiveState         (State)
  5. room.notify(NewListingEvent(...))          -> bildirimler         (Observer)

Bağımlılıklar (AIService, zincirin başı, Room) kurucu üzerinden dışarıdan verilir.
"""
