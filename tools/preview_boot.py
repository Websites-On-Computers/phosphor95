#!/usr/bin/env python3
"""Simulate Plymouth (POST frame, logo frame) and GRUB screens from build/boot -> PNGs."""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from p95 import BUILD, VENDOR, hex_to_rgb, load_config, resolution  # noqa: E402

cfg = load_config()
out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
P = BUILD / "boot" / "plymouth" / "phosphor95"
G = BUILD / "boot" / "grub" / "phosphor95"
W, H = resolution(cfg)
src = (P / "phosphor95.script").read_text()
num = lambda k: int(re.search(rf"^{k} = (\d+);", src, re.M).group(1))
MX, MY, LH, N, MEM = num("MX"), num("MY"), num("LH"), num("POST_COUNT"), num("MEM_LINE")
bg = hex_to_rgb(cfg["core"]["base"])

post = Image.new("RGBA", (W, H), (*bg, 255))
for i in range(N):
    f = P / f"post-{i}.png"
    if f.exists():
        im = Image.open(f); post.alpha_composite(im, (MX, MY + i * LH))
lab = Image.open(P / "mem-label.png"); post.alpha_composite(lab, (MX, MY + MEM * LH))
x = MX + lab.width - 8
mem = re.search(r"^MEM_KB = (\d+);", src, re.M).group(1)
for k, ch in enumerate(mem):
    post.alpha_composite(Image.open(P / f"digit-{ch}.png"), (x + k * 9, MY + MEM * LH))
post.alpha_composite(Image.open(P / "mem-suffix.png"), (x + len(mem) * 9, MY + MEM * LH))
post.alpha_composite(Image.open(P / "scanlines.png"))
post.save(out / "plymouth-post.png")

logo = Image.new("RGBA", (W, H), (*bg, 255))
L = Image.open(P / "logo.png"); ly = int(H * 0.36 - L.height / 2)
logo.alpha_composite(L, ((W - L.width) // 2, ly))
fr = Image.open(P / "bar-frame.png"); bx, by = (W - fr.width) // 2, ly + L.height + 36
logo.alpha_composite(fr, (bx, by))
blk = Image.open(P / "bar-block.png")
for s in range(15):
    logo.alpha_composite(blk, (bx + 5 + s * num("SEG_W"), by + 4))
dl = Image.open(P / "dialog.png"); dx, dy = (W - dl.width) // 2, int(H * 0.62)
logo.alpha_composite(dl, (dx, dy))
for b in range(9):
    logo.alpha_composite(Image.open(P / "bullet.png"), (dx + 30 + b * 12, dy + 86))
logo.alpha_composite(Image.open(P / "scanlines.png"))
logo.save(out / "plymouth-logo.png")

g = Image.open(G / "background.png").convert("RGB")
d = ImageDraw.Draw(g)
vga = ImageFont.truetype(str(VENDOR / "fonts" / "PxPlus_IBM_VGA_9x16.ttf"), 16)
vt = ImageFont.truetype(str(VENDOR / "fonts" / "VT323-Regular.ttf"), 32)
t, sel, ident = cfg["text"], cfg["select"], cfg["identity"]
d.text(((W - d.textlength(ident["name"], font=vt)) // 2, int(H * .10)), ident["name"], font=vt, fill=t["glow"])
d.text(((W - d.textlength(ident["tagline"], font=vga)) // 2, int(H * .15)), ident["tagline"], font=vga, fill=t["fg_dim"])
entries = ["Ubuntu", "Advanced options for Ubuntu", "Memory test (memtest86+)", "UEFI Firmware Settings"]
x0, y0 = int(W * .12), int(H * .22)
for i, e in enumerate(entries):
    y = y0 + i * 30
    if i == 0:
        d.rectangle((x0, y, int(W * .88), y + 26), fill=sel["bg"])
    d.text((x0 + 10, y + 5), e, font=vga, fill=sel["fg"] if i == 0 else t["fg"])
bx0, by0, bw = int(W * .12), int(H * .68), int(W * .76)
d.rectangle((bx0, by0, bx0 + bw, by0 + 8), fill=cfg["core"]["face"])
d.rectangle((bx0, by0, bx0 + int(bw * .66), by0 + 8), fill=t["fg"])
msg = "BOOTING DEFAULT ENTRY IN 2 SECONDS ..."
d.text((bx0 + (bw - d.textlength(msg, font=vga)) // 2, int(H * .64)), msg, font=vga, fill=t["fg"])
g.save(out / "grub.png")
print("wrote plymouth-post.png plymouth-logo.png grub.png to", out)
