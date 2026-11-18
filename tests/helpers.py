from decimal import Decimal

from nearswap.builder import StandardListingBuilder
from nearswap.models import Category, Listing


def make_listing(
    *,
    title: str = "Çalışma lambası",
    price: str = "150",
    description: str = "Az kullanılmış.",
) -> Listing:
    """Taslak durumunda geçerli bir ilan."""
    return (
        StandardListingBuilder()
        .set_owner("yurt-a", "pelin")
        .set_title(title)
        .set_price(Decimal(price))
        .add_photo("https://ornek.com/lamba.jpg")
        .set_category(Category.ELECTRONICS)
        .set_description(description)
        .build()
    )
