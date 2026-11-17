class NearSwapError(Exception):
    """Projedeki tüm alan hatalarının ortak atası."""


class InvalidTransitionError(NearSwapError):
    """İlanın mevcut durumunda izin verilmeyen bir işlem denendi (State)."""

    def __init__(self, state_name: str, action: str) -> None:
        super().__init__(f"'{state_name}' durumundaki ilan için '{action}' yapılamaz.")
        self.state_name = state_name
        self.action = action


class ListingValidationError(NearSwapError):
    """ListingBuilder.build() eksik ya da hatalı bir ilanı reddetti (Builder)."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("İlan oluşturulamadı: " + "; ".join(problems))
        self.problems = problems
