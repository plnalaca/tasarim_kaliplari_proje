from enum import StrEnum


class Category(StrEnum):
    """Geçerli ilan kategorileri."""

    ELECTRONICS = "elektronik"
    FURNITURE = "mobilya"
    BOOKS = "kitap"
    CLOTHING = "giyim"
    KITCHEN = "mutfak"
    OTHER = "diger"
