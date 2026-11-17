"""TODO(Pelin): ListingDirector

İki farklı kurma senaryosu (hocaya karşı Builder savunması için şart):
- from_ai_draft(draft: ListingDraft, photo_url, room_id, seller_id) -> Listing
    Yapay zekâ taslağından başlar; kullanıcı düzeltmeleri sonra uygulanır.
- from_manual_input(...) -> Listing
    Kullanıcının elle doldurduğu formdan kurar.
"""
