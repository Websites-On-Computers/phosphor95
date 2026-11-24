"""Cursor theme 'Phosphor95-Cursors': Chicago95 Standard cursors, recoloured.

Works directly on compiled Xcursor files (no xcursorgen needed): parse each image chunk,
map pixel luminance onto void -> glow, write back. Symlink aliases are preserved.
Xcursor format: 'Xcur' header, TOC of (type, subtype, offset), image chunks of
36-byte header + width*height premultiplied ARGB32 (little-endian).
"""
from __future__ import annotations

import shutil
import struct

from p95 import UPSTREAM, ramp

IMAGE_TYPE = 0xFFFD0002
SOURCE = "Chicago95_Standard_Cursors"


def recolor_xcursor(data: bytes, lut) -> bytes:
    if data[:4] != b"Xcur":
        return data
    buf = bytearray(data)
    _, hsize, _, ntoc = struct.unpack_from("<4sIII", buf, 0)
    for i in range(ntoc):
        typ, _sub, pos = struct.unpack_from("<III", buf, hsize + i * 12)
        if typ != IMAGE_TYPE:
            continue
        chsize, ctype, _s, _v, w, h = struct.unpack_from("<IIIIII", buf, pos)
        if ctype != IMAGE_TYPE:
            continue
        px = pos + chsize
        for j in range(w * h):
            off = px + j * 4
            b, g, r, a = buf[off], buf[off + 1], buf[off + 2], buf[off + 3]
            if a == 0:
                continue
            # un-premultiply, take luminance, re-premultiply the mapped colour
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / a
            nr, ng, nb = lut[min(255, int(lum * 255))]
            buf[off] = nb * a // 255
            buf[off + 1] = ng * a // 255
            buf[off + 2] = nr * a // 255
    return bytes(buf)


def build(cfg, out):
    src = UPSTREAM / "chicago95" / "Cursors" / SOURCE
    if not src.exists():
        raise SystemExit("missing .upstream/chicago95 - run ./phosphor fetch")
    dst = out / "Phosphor95-Cursors"
    shutil.copytree(src, dst, symlinks=True, ignore=shutil.ignore_patterns("src"))
    t, c = cfg["text"], cfg["core"]
    lut = [ramp([c["void"], c["shadow"], t["fg_dim"], t["fg"], t["glow"]], i / 255) for i in range(256)]
    n = 0
    for f in (dst / "cursors").iterdir():
        if f.is_symlink() or not f.is_file():
            continue
        f.write_bytes(recolor_xcursor(f.read_bytes(), lut))
        n += 1
    (dst / "index.theme").write_text(
        "[Icon Theme]\nName=Phosphor95-Cursors\n"
        "Comment=Chicago95 Standard cursors recoloured for Phosphor-95 (GPL-3.0+)\nInherits=Adwaita\n")
    print(f"           recoloured {n} cursors")
