"""Gerçek yapay zekâ sağlayıcısını elle denemek için betik (testlerin parçası değil).

Kullanım:
    python scripts/try_ai.py yol/urun_fotografi.jpg

Sağlayıcı ve anahtar .env dosyasından okunur (NEARSWAP_AI_PROVIDER, GEMINI_API_KEY ...).
Betik yalnızca AIService arayüzünü kullanır; hangi sağlayıcının seçildiğini bilmez.
"""

import mimetypes
import sys
from pathlib import Path

from dotenv import load_dotenv

from nearswap.ai import create_ai_service

CLEAN_TEXT = "Çalışma lambası\nAz kullanılmış, sorunsuz çalışan masa lambası."
BAD_TEXT = "Ruhsatsız tabanca ve fişek\nAcil satılık, kimseye sormadan elden teslim."


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Kullanım: python scripts/try_ai.py <fotoğraf yolu>")

    load_dotenv()
    ai = create_ai_service()
    print(f"Sağlayıcı: {type(ai).__name__}\n")

    photo = Path(sys.argv[1])
    mime_type = mimetypes.guess_type(photo.name)[0] or "image/jpeg"
    if photo.suffix.lower() in (".heic", ".heif"):
        mime_type = "image/heic"
    draft = ai.draft_listing(photo.read_bytes(), mime_type)
    print("1) Fotoğraftan ilan taslağı")
    print(f"   Başlık   : {draft.title}")
    print(f"   Kategori : {draft.category.value}")
    print(f"   Açıklama : {draft.description}")
    print(f"   Fiyat    : {draft.suggested_price} TL\n")

    for label, text in (("2) Temiz ilan", CLEAN_TEXT), ("3) Uygunsuz ilan", BAD_TEXT)):
        result = ai.moderate(text)
        verdict = "ONAYLANDI" if result.approved else f"REDDEDİLDİ ({result.reason})"
        print(f"{label}: {verdict}")


if __name__ == "__main__":
    main()
