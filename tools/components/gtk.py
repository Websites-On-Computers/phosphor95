"""GTK theme 'Phosphor95': B00merang Windows-95 (GPL-3) recoloured to the phosphor palette.

The Win95 CSS uses literal greys. A plain hex->hex swap fails because one grey plays
several roles (#FFFFFF is both field fill and bevel highlight, #000000 is both text and
bevel shadow). So each colour is remapped *by the CSS property it appears in*:

    text      (color, caret)       dark -> fg       light -> select.fg   blue -> glow
    fill      (background*)        white -> base    grey  -> face ramp   blue -> select.bg
    edge      (border*, box-shadow) white -> bevel_hi grey -> bevel ramp  black -> void

Pixel-art assets get the same treatment with a spatial rule: pixels deep inside an
opaque shape (checkbox interior, check marks) are "content"; pixels on the rim are bevel.
"""
from __future__ import annotations

import colorsys
import re
import shutil

from PIL import Image, ImageFilter

from p95 import SRC, UPSTREAM, hex_to_rgb, luminance, mix, render

THEME = "Phosphor95"

COLOR_RE = re.compile(
    r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b"
    r"|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)"
    r"|\bwhite\b|\bblack\b"
)
DECL_RE = re.compile(r"([a-zA-Z-]+)(\s*:\s*)([^;{}]*)")
DEFINE_RE = re.compile(r"@define-color\s+([\w-]+)\s+([^;]+);")


# ------------------------------------------------------------------ role maps
def roles(cfg):
    c, t, s, st = cfg["core"], cfg["text"], cfg["select"], cfg["status"]
    pressed = mix(c["face"], c["shadow"], 0.5)
    return {
        "text": {"dark": t["fg"], "mid": t["fg_faint"], "light": s["fg"], "accent": t["glow"]},
        "fill": {
            "white": c["base"], "light": c["face_hover"], "face": c["face"],
            "mid": pressed, "dark": c["shadow"], "black": c["void"], "accent": s["bg"],
        },
        "edge": {
            "white": c["bevel_hi"], "light": c["bevel_light"], "mid": c["shadow"],
            "black": c["void"], "accent": t["fg"],
        },
        "status": {"warn": st["warn"], "error": st["error"], "ok": st["ok"]},
    }


def parse_color(tok: str):
    """-> (r, g, b, alpha|None)"""
    tok = tok.strip()
    if tok == "white":
        return 255, 255, 255, None
    if tok == "black":
        return 0, 0, 0, None
    if tok.startswith("#"):
        return (*hex_to_rgb(tok), None)
    nums = [float(x) for x in re.findall(r"[\d.]+", tok)]
    return int(nums[0]), int(nums[1]), int(nums[2]), (nums[3] if len(nums) > 3 else None)


def classify(rgb):
    """-> ('status', name) | ('accent',) | ('grey', luminance)"""
    r, g, b = (x / 255 for x in rgb)
    h, sat, v = colorsys.rgb_to_hsv(r, g, b)
    hue = h * 360
    if sat > 0.35 and v > 0.25:
        if 15 <= hue < 50:
            return ("status", "warn")
        if hue < 15 or hue >= 340:
            return ("status", "error")
        if 90 <= hue < 170:
            return ("status", "ok")
        return ("accent",)
    return ("grey", luminance(rgb))


def map_color(rgb, prop_kind, R):
    kind = classify(rgb)
    if kind[0] == "status":
        return R["status"][kind[1]]
    table = R[prop_kind]
    if kind[0] == "accent":
        return table["accent"]
    lum = kind[1]
    if prop_kind == "text":
        return table["dark"] if lum < 0.3 else table["mid"] if lum < 0.62 else table["light"]
    if prop_kind == "fill":
        if lum > 0.97: return table["white"]
        if lum > 0.8:  return table["light"]
        if lum > 0.7:  return table["face"]
        if lum > 0.55: return table["mid"]
        if lum > 0.3:  return table["dark"]
        return table["black"]
    # edge
    if lum > 0.9:  return table["white"]
    if lum > 0.55: return table["light"]
    if lum > 0.3:  return table["mid"]
    return table["black"]


def prop_kind(prop: str) -> str | None:
    p = prop.lower()
    if p in ("color", "caret-color", "-gtk-secondary-caret-color", "text-shadow", "-gtktextview-error-underline-color"):
        return "text"
    if p.startswith("background") or p == "-gtk-icon-shadow":
        return "fill"
    if p.startswith("border") or p.startswith("outline") or p == "box-shadow":
        return "edge"
    return None


def emit(hexcol: str, alpha):
    if alpha is None or alpha >= 0.999:
        return hexcol
    return "alpha(%s, %s)" % (hexcol, ("%.3f" % alpha).rstrip("0").rstrip("."))


def recolor_css(css: str, cfg) -> str:
    R = roles(cfg)

    # 1. named colours: rebuild the @define-color block with semantic values
    c, t, s, st = cfg["core"], cfg["text"], cfg["select"], cfg["status"]
    named = {
        "theme_fg_color": t["fg"], "theme_text_color": t["fg"], "theme_bg_color": c["face"],
        "theme_base_color": c["base"], "theme_selected_bg_color": s["bg"],
        "theme_selected_fg_color": s["fg"], "insensitive_bg_color": c["face"],
        "insensitive_fg_color": t["fg_faint"], "insensitive_base_color": c["base"],
        "theme_unfocused_fg_color": t["fg_dim"], "theme_unfocused_text_color": t["fg_dim"],
        "theme_unfocused_bg_color": c["face"], "theme_unfocused_base_color": c["base"],
        "theme_unfocused_selected_bg_color": t["fg_dim"], "theme_unfocused_selected_fg_color": s["fg"],
        "unfocused_insensitive_color": t["fg_faint"], "borders": c["void"],
        "unfocused_borders": c["void"], "warning_color": st["warn"], "error_color": st["error"],
        "success_color": st["ok"], "wm_title": s["fg"], "wm_unfocused_title": t["fg_dim"],
        "wm_highlight": c["bevel_hi"], "wm_borders_edge": c["void"], "wm_bg_a": c["face"],
        "wm_bg_b": c["face"], "wm_shadow": "alpha(#000000, 0.35)", "wm_border": "alpha(#000000, 0.18)",
        "content_view_bg": c["base"], "link_color": t["glow"], "link_visited_color": t["fg_dim"],
    }

    def define(m):
        name, val = m.group(1), m.group(2)
        if name in named:
            return f"@define-color {name} {named[name]};"
        kind = "text" if ("fg" in name or "title" in name or "text" in name) else \
               "edge" if ("border" in name or "shadow" in name) else "fill"
        return f"@define-color {name} " + COLOR_RE.sub(lambda mm: emit(map_color(parse_color(mm.group())[:3], kind, R), parse_color(mm.group())[3]), val) + ";"

    css = DEFINE_RE.sub(define, css)

    # 2. literal colours inside declarations, mapped by property role
    def decl(m):
        prop, sep, val = m.groups()
        if prop.startswith("@") or prop == "define-color":
            return m.group(0)
        kind = prop_kind(prop)
        if kind is None or not COLOR_RE.search(val):
            return m.group(0)

        def col(mm):
            r, g, b, a = parse_color(mm.group())
            return emit(map_color((r, g, b), kind, R), a)

        return prop + sep + COLOR_RE.sub(col, val)

    out_lines = []
    for line in css.splitlines(keepends=True):
        out_lines.append(line if line.lstrip().startswith("@define-color") else DECL_RE.sub(decl, line))
    return "".join(out_lines)


# ------------------------------------------------------------------ PNG assets
def recolor_asset(path, cfg):
    c, t = cfg["core"], cfg["text"]
    im = Image.open(path).convert("RGBA")
    scale = 2 if "@2" in path.name else 1
    alpha = im.getchannel("A").point(lambda a: 255 if a > 40 else 0)
    depth = 2 * scale
    interior = alpha.filter(ImageFilter.MinFilter(2 * depth + 1)) if min(im.size) > 2 * depth + 2 else Image.new("L", im.size, 0)
    glyph = path.name.split(".")[0].split("@")[0] in ("arrow", "arrow-up", "arrow-down", "arrow-left", "arrow-right",
                                                       "close", "maximize", "minimize", "restore")
    insensitive = "insensitive" in path.name
    px, inn = im.load(), interior.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            lum = luminance((r, g, b))
            if glyph:                                   # black glyph on transparent
                new = t["fg_faint"] if insensitive else t["fg"]
            elif inn[x, y]:                             # content: field + marks
                new = (c["base"] if lum > 0.8 else (t["fg_faint"] if (insensitive or lum > 0.35) else t["fg"]))
            else:                                       # rim: Win95 bevel
                new = (c["bevel_hi"] if lum > 0.9 else c["bevel_light"] if lum > 0.7
                       else c["face"] if lum > 0.6 else c["shadow"] if lum > 0.3 else c["void"])
            px[x, y] = (*hex_to_rgb(new), a)
    im.save(path)


# --------------------------------------------------------------------- build
def build(cfg, out):
    src = UPSTREAM / "w95"
    if not src.exists():
        raise SystemExit("missing .upstream/w95 - run ./phosphor fetch")
    theme = out / THEME
    for d in ("gtk-3.0", "gtk-4.0"):
        shutil.copytree(src / d, theme / d)
        (theme / d / "thumbnail.png").unlink(missing_ok=True)
        css_path = theme / d / "gtk.css"
        css = recolor_css(css_path.read_text(), cfg)
        extra = SRC / "gtk" / f"phosphor-{d}.css.tmpl"
        if extra.exists():
            css += "\n/* ===== Phosphor-95 additions ===== */\n" + render(extra.read_text(), cfg)
        css_path.write_text(css)
        for png in (theme / d / "assets").glob("*.png"):
            recolor_asset(png, cfg)
    (theme / "index.theme").write_text(
        "[Desktop Entry]\nType=X-GNOME-Metatheme\nName=Phosphor95\n"
        "Comment=Win95 structure on a phosphor-green CRT. Based on B00merang Windows-95 (GPL-3).\n"
        "Encoding=UTF-8\n\n[X-GNOME-Metatheme]\nGtkTheme=Phosphor95\nMetacityTheme=Phosphor95\n"
        "IconTheme=Phosphor95\nCursorTheme=Phosphor95-Cursors\nButtonLayout=menu:minimize,maximize,close\n"
    )
    shutil.copy(src / "LICENSE", theme / "LICENSE")
    # user-level overrides for libadwaita apps (installed to ~/.config/gtk-4.0/gtk.css)
    user = out / "user"
    user.mkdir()
    (user / "gtk-4.0.css").write_text(render((SRC / "gtk" / "libadwaita.css.tmpl").read_text(), cfg))
