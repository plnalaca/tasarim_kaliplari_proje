from nearswap.domain.text import turkish_lower


def test_turkish_lower_handles_dotted_and_dotless_i() -> None:
    assert turkish_lower("SİLAH") == "silah"
    assert turkish_lower("IŞIK") == "ışık"
    assert turkish_lower("Çalışma Lambası") == "çalışma lambası"
