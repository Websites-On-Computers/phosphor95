"""Phosphor-95 shared helpers: config loading, colour math, template rendering.

Templates use {{ section.key }} with optional filters:
    {{ core.fg }}               -> #33ff66
    {{ core.fg | nohash }}      -> 33ff66
    {{ core.fg | rgb }}         -> 51, 255, 102
    {{ core.fg | rgbf }}        -> 0.200, 1.000, 0.400   (GLSL)
    {{ core.fg | sgr }}         -> 38;2;51;255;102       (ANSI escape)
    {{ core.fg | alpha 0.5 }}   -> rgba(51, 255, 102, 0.5)
    {{ core.fg | mix core.face 0.3 }} -> hex 30% of the way from fg to face
    {{ identity.name | lower }} / | upper
Lookup searches palette.toml then system.toml (sections are disjoint).
"""
from __future__ import annotations

import colorsys
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
BUILD = ROOT / "build"
SRC = ROOT / "src"
VENDOR = ROOT / "vendor"
UPSTREAM = ROOT / ".upstream"   # fetched third-party sources (git clones)


def load_config() -> dict:
    cfg: dict = {}
    for name in ("palette.toml", "system.toml"):
        with open(CONFIG / name, "rb") as fh:
            for section, values in tomllib.load(fh).items():
                if section in cfg:
                    raise SystemExit(f"duplicate config section [{section}]")
                cfg[section] = values
    return cfg


def resolution(cfg) -> tuple[int, int]:
    """[desktop] resolution = "WxH" -> (W, H)"""
    w, h = cfg["desktop"]["resolution"].lower().split("x")
    return int(w), int(h)


# ---------------------------------------------------------------- colour math
def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb[:3])


def mix(a: str, b: str, t: float) -> str:
    """t=0 -> a, t=1 -> b"""
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return rgb_to_hex([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])


def luminance(rgb) -> float:
    r, g, b = rgb[:3]
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def ramp(stops: list[str], t: float) -> tuple[int, int, int]:
    """Piecewise-linear colour ramp; t in [0,1]."""
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    i = min(int(t * n), n - 1)
    local = t * n - i
    a, b = hex_to_rgb(stops[i]), hex_to_rgb(stops[i + 1])
    return tuple(round(a[k] + (b[k] - a[k]) * local) for k in range(3))


def phosphor_ramp(cfg) -> list[str]:
    """Dark -> bright green ramp used for icon/image tinting."""
    c, t = cfg["core"], cfg["text"]
    return [c["void"], c["shadow"], c["face"], t["fg_faint"], t["fg_dim"], t["fg"], t["glow"]]


# ------------------------------------------------------------------ templating
_TOKEN = re.compile(r"\{\{\s*(.+?)\s*\}\}")


def lookup(cfg: dict, dotted: str):
    section, _, key = dotted.partition(".")
    try:
        return cfg[section][key]
    except KeyError:
        raise KeyError(f"unknown config key '{dotted}'") from None


def _apply(cfg, value, filt: str):
    parts = filt.split()
    name, args = parts[0], parts[1:]
    if name == "nohash":
        return str(value).lstrip("#")
    if name == "rgb":
        return "%d, %d, %d" % hex_to_rgb(value)
    if name == "sgr":   # 24-bit ANSI fg parameter list: 38;2;R;G;B
        return "38;2;%d;%d;%d" % hex_to_rgb(value)
    if name == "rgbf":
        return "%.3f, %.3f, %.3f" % tuple(c / 255 for c in hex_to_rgb(value))
    if name == "alpha":
        return "rgba(%d, %d, %d, %s)" % (*hex_to_rgb(value), args[0])
    if name == "mix":
        return mix(value, lookup(cfg, args[0]) if "." in args[0] else args[0], float(args[1]))
    if name == "upper":
        return str(value).upper()
    if name == "lower":
        return str(value).lower()
    if name == "argb":  # GRUB/Plymouth style 0xRRGGBB
        return "0x" + str(value).lstrip("#")
    raise ValueError(f"unknown filter '{name}'")


def render(text: str, cfg: dict) -> str:
    def sub(m):
        expr = m.group(1)
        chunks = [c.strip() for c in expr.split("|")]
        value = lookup(cfg, chunks[0])
        for f in chunks[1:]:
            value = _apply(cfg, value, f)
        return str(value)

    return _TOKEN.sub(sub, text)


def render_tree(src: Path, dst: Path, cfg: dict) -> list[Path]:
    """Copy src -> dst; files ending in .tmpl are rendered and lose the suffix."""
    out = []
    for f in sorted(src.rglob("*")):
        if f.is_dir():
            continue
        rel = f.relative_to(src)
        if f.suffix == ".tmpl":
            target = dst / rel.with_suffix("")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render(f.read_text(), cfg))
        else:
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f.read_bytes())
        target.chmod(f.stat().st_mode & 0o777)
        out.append(target)
    return out
