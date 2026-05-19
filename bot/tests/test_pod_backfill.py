from bot.services.pod_backfill import normalize_colors, strip_cdn_dims


def test_normalize_colors_wubrg_order():
    assert normalize_colors("RW") == "WR"
    assert normalize_colors("GB") == "BG"
    assert normalize_colors("GBw") == "BGw"
    assert normalize_colors("WUBRG") == "WUBRG"
    assert normalize_colors("URb") == "URb"


def test_strip_cdn_dims_removes_only_width_height():
    url = "https://media.discordapp.net/x.png?ex=abc&hm=def&format=webp&quality=lossless&width=550&height=198"
    cleaned = strip_cdn_dims(url)
    assert "width=" not in cleaned
    assert "height=" not in cleaned
    assert "ex=abc" in cleaned
    assert "hm=def" in cleaned
    assert "format=webp" in cleaned
    assert "quality=lossless" in cleaned


def test_strip_cdn_dims_idempotent_on_clean_url():
    url = "https://media.discordapp.net/x.png?ex=abc&hm=def"
    assert strip_cdn_dims(url) == url
