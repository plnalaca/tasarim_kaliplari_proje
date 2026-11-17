"""State kalıbı: ilan durumu.

Roller:
- Context       -> nearswap.domain.listing.Listing
- State         -> ListingState    (listing_state.py)
- ConcreteState -> DraftState, ActiveState, ReservedState, SoldState    TODO(Pelin)

Geçiş tablosu (Hata = InvalidTransitionError):

| Durum   | publish | reserve  | mark_sold | cancel_reservation | edit   |
|---------|---------|----------|-----------|--------------------|--------|
| Taslak  | Aktif   | Hata     | Hata      | Hata               | İzinli |
| Aktif   | Hata    | Rezerve  | Satıldı   | Hata               | İzinli |
| Rezerve | Hata    | Hata     | Satıldı   | Aktif              | Hata   |
| Satıldı | Hata    | Hata     | Hata      | Hata               | Hata   |
"""
