"""Generated wallpapers: digital rain on CRT glass.

Outputs (at [desktop] resolution in config/system.toml):
    phosphor95-rain-WxH.png    desktop: sparse rain, identity mark bottom-right
    phosphor95-login-WxH.png   login/lock: darker centre so the dialog reads
Deterministic (seeded), so rebuilds are stable.
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from p95 import VENDOR, hex_to_rgb, mix, resolution

KATAKANA = "ｦｧｨｩｪｫｬｭｮｯｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
DIGITS = "0123456789Z:.=*+-<>|"
CJK_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]


def _font(path, size, index=0):
    try:
        return ImageFont.truetype(str(path), size, index=index)
    except OSError:
        return None


def glyph_font(size):
    for p in CJK_CANDIDATES:
        if Path(p).exists():
            # index 5 in the Noto CJK collection = Noto Sans Mono CJK JP; fall back to 0
            for idx in (5, 0):
                f = _font(p, size, idx)
                if f:
                    return f, True
    return ImageFont.truetype(str(VENDOR / "fonts" / "VT323-Regular.ttf"), size), False


def rain_layer(w, h, cfg, rng, density, cell):
    """Return (rain RGB image, bright-heads RGB image) on black."""
    t = cfg["text"]
    font, has_kana = glyph_font(int(cell * 0.92))
    digit_font = ImageFont.truetype(str(VENDOR / "fonts" / "VT323-Regular.ttf"), int(cell * 1.05))
    rain = Image.new("RGB", (w, h), (0, 0, 0))
    heads = Image.new("RGB", (w, h), (0, 0, 0))
    cols = w // cell
    rows = h // cell + 1
    glyph_cache = {}

    def glyph(ch, colour, use_digit):
        key = (ch, colour, use_digit)
        if key not in glyph_cache:
            g = Image.new("RGB", (cell, cell), (0, 0, 0))
            d = ImageDraw.Draw(g)
            f = digit_font if use_digit or not has_kana else font
            bbox = d.textbbox((0, 0), ch, font=f)
            x = (cell - (bbox[2] - bbox[0])) // 2 - bbox[0]
            y = (cell - (bbox[3] - bbox[1])) // 2 - bbox[1]
            d.text((x, y), ch, font=f, fill=colour)
            if not use_digit:
                g = g.transpose(Image.FLIP_LEFT_RIGHT)   # mirrored, as in the film
            glyph_cache[key] = g
        return glyph_cache[key]

    ramp = [t["fg_faint"], t["fg_dim"], t["fg"]]
    for c in range(cols):
        if rng.random() > density:
            continue
        for _ in range(rng.choice((1, 1, 1, 2))):
            length = rng.randint(6, int(rows * 0.7))
            head = rng.randint(-2, rows + length // 2)
            for i in range(length):
                r = head - i
                if r < 0 or r >= rows:
                    continue
                k = i / max(1, length - 1)          # 0 at head, 1 at tail
                if i == 0:
                    colour = t["glow"]
                elif k < 0.15:
                    colour = mix(t["glow"], t["fg"], k / 0.15)
                else:
                    seg = min(2, int((1 - k) * 3))
                    colour = mix(ramp[max(0, seg - 1)], ramp[seg], 0.5)
                    colour = mix(colour, cfg["core"]["base"], k * 0.6)
                use_digit = rng.random() < 0.18
                ch = rng.choice(DIGITS if use_digit else KATAKANA)
                g = glyph(ch, hex_to_rgb(colour), use_digit)
                rain.paste(g, (c * cell, r * cell), ImageChops.lighter(g.convert("L"), Image.new("L", g.size, 0)))
                if i == 0:
                    heads.paste(g, (c * cell, r * cell))
    return rain, heads


def compose(w, h, cfg, *, seed, density, mark, centre_dark):
    rng = random.Random(seed)
    core, t, ident = cfg["core"], cfg["text"], cfg["identity"]
    scale = w / 1440
    cell = max(14, int(18 * scale))

    # glass: near-black with a faint green centre glow
    base = Image.new("RGB", (w, h), hex_to_rgb(core["base"]))
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse((-w * 0.2, -h * 0.35, w * 1.2, h * 1.35), fill=40)
    glow = glow.filter(ImageFilter.GaussianBlur(w / 6))
    base = Image.composite(Image.new("RGB", (w, h), hex_to_rgb(core["face"])), base, glow)

    rain, heads = rain_layer(w, h, cfg, rng, density, cell)
    if centre_dark:  # login: fade the rain out behind the centred dialog
        m = Image.new("L", (w, h), 255)
        ImageDraw.Draw(m).ellipse((w * 0.28, h * 0.18, w * 0.72, h * 0.86), fill=40)
        m = m.filter(ImageFilter.GaussianBlur(w / 14))
        rain = Image.composite(rain, Image.new("RGB", (w, h)), m)
        heads = Image.composite(heads, Image.new("RGB", (w, h)), m)
    if mark:  # keep the identity mark clean: no rain behind it
        m = Image.new("L", (w, h), 255)
        ImageDraw.Draw(m).rectangle((w * 0.70, h * 0.80, w, h * 0.97), fill=0)
        m = m.filter(ImageFilter.GaussianBlur(24 * scale))
        rain = Image.composite(rain, Image.new("RGB", (w, h)), m)
        heads = Image.composite(heads, Image.new("RGB", (w, h)), m)
    bloom = ImageChops.add(rain.filter(ImageFilter.GaussianBlur(3 * scale)),
                           heads.filter(ImageFilter.GaussianBlur(8 * scale)))
    img = ImageChops.lighter(base, ImageChops.add(rain, bloom))

    if mark:
        d = ImageDraw.Draw(img)
        big = ImageFont.truetype(str(VENDOR / "fonts" / "VT323-Regular.ttf"), int(64 * scale))
        small = ImageFont.truetype(str(VENDOR / "fonts" / "PxPlus_IBM_VGA_9x16.ttf"), int(16 * scale))
        name, tag = ident["name"], ident["tagline"]
        pad_r, pad_b = int(48 * scale), int(64 * scale)   # clear of the taskbar
        nb = d.textbbox((0, 0), name, font=big)
        tb = d.textbbox((0, 0), tag, font=small)
        x_name = w - pad_r - (nb[2] - nb[0])
        y_tag = h - pad_b - (tb[3] - tb[1])
        y_name = y_tag - (nb[3] - nb[1]) - int(14 * scale)
        layer = Image.new("RGB", (w, h))
        ld = ImageDraw.Draw(layer)
        ld.text((x_name - nb[0], y_name - nb[1]), name, font=big, fill=hex_to_rgb(t["glow"]))
        ld.text((w - pad_r - (tb[2] - tb[0]) - tb[0], y_tag - tb[1]), tag, font=small, fill=hex_to_rgb(t["fg_dim"]))
        # cursor block after the name
        cx = w - pad_r + int(8 * scale)
        ld.rectangle((cx, y_name + int(8 * scale), cx + int(18 * scale), y_name + (nb[3] - nb[1])), fill=hex_to_rgb(t["fg"]))
        img = ImageChops.lighter(img, ImageChops.add(layer, layer.filter(ImageFilter.GaussianBlur(6 * scale))))
        del d

    # scanlines on native device rows + vignette
    lines = Image.new("L", (w, h), 255)
    ld = ImageDraw.Draw(lines)
    step = max(2, round(2 * scale))
    for y in range(0, h, step):
        ld.line((0, y + step - 1, w, y + step - 1), fill=200)
    img = ImageChops.multiply(img, Image.merge("RGB", (lines, lines, lines)))
    vig = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vig).ellipse((-w * 0.15, -h * 0.2, w * 1.15, h * 1.2), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(w / 8))
    img = Image.composite(img, Image.new("RGB", (w, h), hex_to_rgb(core["void"])), vig)
    return img


def build(cfg, out: Path):
    for w, h in [resolution(cfg)]:
        compose(w, h, cfg, seed=1999, density=0.34, mark=True, centre_dark=False) \
            .save(out / f"phosphor95-rain-{w}x{h}.png", optimize=True)
        compose(w, h, cfg, seed=2199, density=0.42, mark=False, centre_dark=True) \
            .save(out / f"phosphor95-login-{w}x{h}.png", optimize=True)
