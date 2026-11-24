"""Icon theme 'Phosphor95': Chicago95 (GPL-3) re-tinted to a monochrome phosphor ramp.

PNG: luminance -> ramp lookup (alpha kept). SVG: every colour literal remapped the same
way. *-symbolic icons are left alone because GTK/Shell recolour them at runtime.
The ramp has a faint green floor, not black, so Win95's black outlines stay visible
on the dark desktop.
"""
from __future__ import annotations

import re
import shutil

from PIL import Image

from p95 import UPSTREAM, hex_to_rgb, luminance, ramp, rgb_to_hex

NAMED = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "blue": "#0000ff",
         "yellow": "#ffff00", "green": "#008000", "gray": "#808080", "grey": "#808080",
         "silver": "#c0c0c0", "navy": "#000080", "teal": "#008080", "maroon": "#800000",
         "olive": "#808000", "purple": "#800080", "lime": "#00ff00", "aqua": "#00ffff",
         "fuchsia": "#ff00ff"}
SVG_COLOR = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)"
                       r"|(?<=[\"':;\s])(?:" + "|".join(NAMED) + r")(?=[\"';\s])")


def stops(cfg):
    t = cfg["text"]
    return ["#04170a", t["fg_faint"], t["fg_dim"], t["fg"], t["glow"]]


def tint_png(path, lut):
    try:
        im = Image.open(path)
    except Exception:          # a few upstream "png"s are really SVG or corrupt: leave as-is
        return
    if im.mode not in ("RGBA", "LA", "P", "RGB", "L"):
        return
    im = im.convert("RGBA")
    a = im.getchannel("A")
    L = im.convert("L")
    r, g, b = (L.point([x[i] for x in lut]) for i in range(3))
    Image.merge("RGBA", (r, g, b, a)).save(path, optimize=True)


def tint_svg(path, st):
    text = path.read_text(errors="replace")

    def sub(m):
        tok = m.group(0)
        if tok.startswith("rgb("):
            rgb = tuple(int(x) for x in re.findall(r"\d+", tok))
        else:
            rgb = hex_to_rgb(NAMED.get(tok.lower(), tok))
        return rgb_to_hex(ramp(st, luminance(rgb)))

    path.write_text(SVG_COLOR.sub(sub, text))


def build(cfg, out):
    src = UPSTREAM / "chicago95" / "Icons" / "Chicago95"
    if not src.exists():
        raise SystemExit("missing .upstream/chicago95 - run ./phosphor fetch")
    dst = out / "Phosphor95"
    shutil.copytree(src, dst, symlinks=True, ignore=shutil.ignore_patterns("*.html", "icon-theme.cache", "*.old"))
    st = stops(cfg)
    lut = [ramp(st, i / 255) for i in range(256)]
    n_png = n_svg = 0
    for f in dst.rglob("*"):
        if f.is_symlink() or not f.is_file() or "symbolic" in f.name:
            continue
        if f.suffix == ".png":
            tint_png(f, lut); n_png += 1
        elif f.suffix == ".svg":
            tint_svg(f, st); n_svg += 1
    idx = (dst / "index.theme").read_text()
    idx = re.sub(r"^Name=.*$", "Name=Phosphor95", idx, count=1, flags=re.M)
    idx = re.sub(r"^Comment=.*$", "Comment=Chicago95 icons re-tinted for a phosphor-green CRT (GPL-3).", idx, count=1, flags=re.M)
    idx = re.sub(r"^Inherits=.*$\n?", "", idx, flags=re.M)
    idx = idx.replace("[Icon Theme]\n", "[Icon Theme]\nInherits=Adwaita,hicolor\n", 1)
    (dst / "index.theme").write_text(idx)
    (dst / "UPSTREAM-LICENSE").write_text(
        "Derived from Chicago95 by grassmunk (https://github.com/grassmunk/Chicago95),\n"
        "licensed GPL-3.0+/MIT per its README. Recoloured by Phosphor-95.\n")
    print(f"           tinted {n_png} png, {n_svg} svg")
