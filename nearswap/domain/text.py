"""Türkçe metin yardımcıları.

Python'un lower()/casefold() işlevleri Türkçe İ/I harflerini doğru çevirmez:
"SİLAH".casefold() -> "si̇lah" (i + birleşik nokta), "IŞIK".lower() -> "işik".
Bu yüzden yasaklı kelime gibi metin karşılaştırmalarında turkish_lower kullanılmalı.
"""

_TR_UPPER_TO_LOWER = str.maketrans({"İ": "i", "I": "ı"})


def turkish_lower(text: str) -> str:
    return text.translate(_TR_UPPER_TO_LOWER).lower()
