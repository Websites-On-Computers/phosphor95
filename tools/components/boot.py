"""Boot chain: Plymouth splash + GRUB menu.

Plymouth runs from the initramfs, where only Ubuntu's fonts exist, so all styled text is
pre-rendered here to PNGs with the IBM VGA pixel font. The script then only places sprites:
POST lines, a live memory counter built from digit sprites, logo, a segmented Win95 progress
bar, and a password dialog for encrypted disks.

The POST facts (CPU, RAM, disk) are read from *this* machine at build time.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from p95 import SRC, VENDOR, hex_to_rgb, mix, render, resolution

VGA = VENDOR / "fonts" / "PxPlus_IBM_VGA_9x16.ttf"
VT323 = VENDOR / "fonts" / "VT323-Regular.ttf"


# ----------------------------------------------------------------- helpers
def machine_facts():
    def read(p):
        try:
            return Path(p).read_text()
        except OSError:
            return ""
    cpu = re.search(r"model name\s*:\s*(.+)", read("/proc/cpuinfo"))
    cpu = re.sub(r"\((R|TM)\)|CPU\s+", "", cpu.group(1)).strip() if cpu else "UNKNOWN CPU"
    cpu = re.sub(r"\s+", " ", cpu)
    mem = re.search(r"MemTotal:\s*(\d+)", read("/proc/meminfo"))
    mem_kb = int(mem.group(1)) if mem else 0
    disk = "UNKNOWN"
    try:
        src = subprocess.run(["findmnt", "-no", "SOURCE", "/"], capture_output=True, text=True).stdout.strip()
        parent = subprocess.run(["lsblk", "-no", "PKNAME", src], capture_output=True, text=True).stdout.split()
        dev = "/dev/" + parent[0] if parent else src
        disk = subprocess.run(["lsblk", "-dno", "MODEL,SIZE", dev], capture_output=True, text=True).stdout.strip()
        disk = re.sub(r"\s+", " ", disk) or "UNKNOWN"
    except Exception:
        pass
    return {"cpu": cpu.upper(), "mem_kb": mem_kb, "disk": disk.upper()}


def text_img(text, colour, size=16, font=VGA, glow=None, pad=0):
    f = ImageFont.truetype(str(font), size)
    bbox = f.getbbox(text or " ")
    w = max(1, bbox[2]) + pad * 2
    h = max(size, bbox[3]) + pad * 2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad, pad), text, font=f, fill=(*hex_to_rgb(colour), 255))
    if glow:
        g = im.filter(ImageFilter.GaussianBlur(glow))
        im = Image.alpha_composite(g, im)
    return im


def spans_img(spans, size=16, pad=4, glow=2.0):
    """spans: [(text, colour), ...] rendered on one line (monospace)."""
    f = ImageFont.truetype(str(VGA), size)
    cw = f.getbbox("M")[2]
    total = sum(len(t) for t, _ in spans)
    im = Image.new("RGBA", (total * cw + pad * 2, size + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = pad
    for t, c in spans:
        d.text((x, pad), t, font=f, fill=(*hex_to_rgb(c), 255))
        x += len(t) * cw
    if glow:
        im = Image.alpha_composite(im.filter(ImageFilter.GaussianBlur(glow)), im)
    return im


def bevel_box(w, h, cfg, sunken=False, fill=None):
    c = cfg["core"]
    im = Image.new("RGBA", (w, h), (*hex_to_rgb(fill or c["face"]), 255))
    d = ImageDraw.Draw(im)
    tl, br = (c["shadow"], c["bevel_hi"]) if sunken else (c["bevel_hi"], c["void"])
    tl2, br2 = (c["void"], c["bevel_light"]) if sunken else (c["bevel_light"], c["shadow"])
    d.line((0, 0, w - 1, 0), fill=tl); d.line((0, 0, 0, h - 1), fill=tl)
    d.line((0, h - 1, w - 1, h - 1), fill=br); d.line((w - 1, 0, w - 1, h - 1), fill=br)
    d.line((1, 1, w - 2, 1), fill=tl2); d.line((1, 1, 1, h - 2), fill=tl2)
    d.line((1, h - 2, w - 2, h - 2), fill=br2); d.line((w - 2, 1, w - 2, h - 2), fill=br2)
    return im


# ----------------------------------------------------------------- plymouth
def build_plymouth(cfg, out: Path):
    t, c, ident = cfg["text"], cfg["core"], cfg["identity"]
    facts = machine_facts()
    W, H = resolution(cfg)
    out.mkdir(parents=True)
    year = __import__("datetime").date.today().year

    lines = [
        [(ident["bios"], t["glow"]), (f"   (C) 1995-{year} PHOSPHOR SYSTEMS", t["fg_dim"])],
        [(ident["name"], t["fg"])],
        [("", t["fg"])],
        [("CPU          : ", t["fg"]), (facts["cpu"][:60], t["glow"])],
        None,  # memory line: label + live counter + suffix (assembled by the script)
        [("FIXED DISK   : ", t["fg"]), (facts["disk"][:48], t["glow"]), ("  [ ", t["fg_dim"]), ("OK", t["glow"]), (" ]", t["fg_dim"])],
        [("DISPLAY      : ", t["fg"]), (f"PHOSPHOR P1 MONOCHROME  {W}x{H}", t["glow"])],
        [("KERNEL       : ", t["fg"]), (os.uname().release.upper(), t["glow"])],
        [("", t["fg"])],
        [("STARTING " + ident["name"] + " ...", t["fg_dim"])],
    ]
    n = 0
    for i, spans in enumerate(lines):
        if spans is None:
            spans_img([("MEMORY TEST  : ", t["fg"])]).save(out / "mem-label.png")
            spans_img([("K  [ ", t["fg_dim"]), ("OK", t["glow"]), (" ]", t["fg_dim"])]).save(out / "mem-suffix.png")
            mem_line = i
        else:
            spans_img(spans).save(out / f"post-{i}.png")
        n = i + 1
    for dgt in "0123456789":
        spans_img([(dgt, t["glow"])]).save(out / f"digit-{dgt}.png")

    # logo: big name with bloom + tagline
    name = text_img(ident["name"], t["glow"], size=96, font=VT323, glow=8, pad=16)
    tag = text_img(ident["tagline"], t["fg_dim"], size=16, glow=1.5, pad=4)
    logo = Image.new("RGBA", (max(name.width, tag.width), name.height + tag.height + 4), (0, 0, 0, 0))
    logo.alpha_composite(name, ((logo.width - name.width) // 2, 0))
    logo.alpha_composite(tag, ((logo.width - tag.width) // 2, name.height + 4))
    logo.save(out / "logo.png")

    # Win95 segmented progress bar
    seg_n, seg_w, seg_h, gap = 24, 14, 18, 3
    frame_w = seg_n * (seg_w + gap) + gap + 4
    bevel_box(frame_w, seg_h + 8, cfg, sunken=True, fill=c["base"]).save(out / "bar-frame.png")
    blk = Image.new("RGBA", (seg_w, seg_h), (*hex_to_rgb(t["fg"]), 255))
    ImageDraw.Draw(blk).line((0, 0, seg_w - 1, 0), fill=t["glow"])
    blk.save(out / "bar-block.png")

    # shutdown / reboot caption
    spans_img([("SHUTTING DOWN " + ident["name"] + " ...", t["fg"])]).save(out / "shutdown-title.png")

    # password dialog (Win95 caption + sunken field)
    dw, dh = 460, 150
    dlg = bevel_box(dw, dh, cfg)
    d = ImageDraw.Draw(dlg)
    d.rectangle((3, 3, dw - 4, 26), fill=cfg["title"]["active_bg"])
    cap = text_img("UNLOCK DISK", cfg["title"]["active_fg"], 16)
    dlg.alpha_composite(cap, (10, 6))
    lab = text_img("ENTER PASSPHRASE:", t["fg"], 16, glow=1.5, pad=2)
    dlg.alpha_composite(lab, (20, 46))
    field = bevel_box(dw - 40, 30, cfg, sunken=True, fill=c["base"])
    dlg.alpha_composite(field, (20, 76))
    hint = text_img("PRESS ENTER WHEN DONE", t["fg_faint"], 16, pad=2)
    dlg.alpha_composite(hint, (20, 116))
    dlg.save(out / "dialog.png")
    blt = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    ImageDraw.Draw(blt).rectangle((1, 1, 8, 8), fill=t["glow"])
    blt.save(out / "bullet.png")

    # full-screen scanline overlay (every 2nd device row, faint)
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sl)
    for y in range(1, H, 2):
        sd.line((0, y, W, y), fill=(0, 0, 0, 60))
    sl.save(out / "scanlines.png", optimize=True)

    bg = hex_to_rgb(c["base"])
    script = render((SRC / "boot" / "phosphor95.script.tmpl").read_text(), cfg)
    script = (script.replace("@POST_COUNT@", str(n)).replace("@MEM_LINE@", str(mem_line))
              .replace("@MEM_KB@", str(facts["mem_kb"])).replace("@SEG_N@", str(seg_n))
              .replace("@SEG_W@", str(seg_w + gap)).replace("@BG_R@", f"{bg[0] / 255:.3f}")
              .replace("@BG_G@", f"{bg[1] / 255:.3f}").replace("@BG_B@", f"{bg[2] / 255:.3f}"))
    (out / "phosphor95.script").write_text(script)
    (out / "phosphor95.plymouth").write_text(
        "[Plymouth Theme]\nName=Phosphor-95\nDescription=Green phosphor POST + Win95 progress bar\n"
        "ModuleName=script\n\n[script]\nImageDir=/usr/share/plymouth/themes/phosphor95\n"
        "ScriptFile=/usr/share/plymouth/themes/phosphor95/phosphor95.script\n")


# ----------------------------------------------------------------- grub
def grub_font(ttf: Path, size: int, out: Path) -> str | None:
    exe = shutil.which("grub-mkfont")
    if not exe:
        return None
    r = subprocess.run([exe, "-s", str(size), "-o", str(out), str(ttf)], capture_output=True, text=True)
    if r.returncode:
        print("           grub-mkfont failed:", r.stderr.strip()[:200])
        return None
    data = out.read_bytes()
    i = data.find(b"NAME")
    if i < 0:
        return None
    ln = int.from_bytes(data[i + 4:i + 8], "big")
    return data[i + 8:i + 8 + ln].rstrip(b"\0").decode()


def build_grub(cfg, out: Path):
    t, c, ident, sel = cfg["text"], cfg["core"], cfg["identity"], cfg["select"]
    W, H = resolution(cfg)
    out.mkdir(parents=True)
    f16 = grub_font(VGA, 16, out / "pxplus-16.pf2")
    f32 = grub_font(VT323, 32, out / "vt323-32.pf2")
    if not f16:
        print("           (grub-mkfont unavailable: GRUB theme will use GRUB's default font)")

    # background: BIOS-utility frame drawn at the same % geometry as theme.txt
    bg = Image.new("RGB", (W, H), hex_to_rgb(c["base"]))
    d = ImageDraw.Draw(bg)
    vga = ImageFont.truetype(str(VGA), 16)
    # scanlines (between caption and footer)
    for y in range(33, H - 35, 2):
        d.line((0, y, W, y), fill=mix(c["base"], c["void"], 0.5))
    # caption bar
    d.rectangle((0, 0, W, 31), fill=sel["bg"])
    cap = f"{ident['bios']}  -  BOOT SELECTION UTILITY"
    d.text(((W - vga.getlength(cap)) // 2, 8), cap, font=vga, fill=sel["fg"])
    # double-line frame around menu area: left 12%, top 22%, width 76%, height 36%
    x0, y0, x1, y1 = int(W * 0.12) - 14, int(H * 0.22) - 14, int(W * 0.88) + 14, int(H * 0.58) + 14
    for k, col in ((0, t["fg_dim"]), (4, t["fg_faint"])):
        d.rectangle((x0 + k, y0 + k, x1 - k, y1 - k), outline=col, width=2)
    title = f" {ident['name']} "
    tw = vga.getlength(title)
    d.rectangle((x0 + 24, y0 - 8, x0 + 24 + tw, y0 + 8), fill=c["base"])
    d.text((x0 + 24, y0 - 8), title, font=vga, fill=t["glow"])
    # footer key help
    d.rectangle((0, H - 34, W, H), fill=c["face"])
    d.line((0, H - 34, W, H - 34), fill=c["bevel_hi"])
    keys = "↑↓ : SELECT    ENTER : BOOT    E : EDIT ENTRY    C : COMMAND LINE"
    d.text(((W - vga.getlength(keys)) // 2, H - 25), keys, font=vga, fill=t["fg"])
    bg = bg.filter(ImageFilter.GaussianBlur(0.4))
    bg.save(out / "background.png")

    # selection highlight: solid 9-slice (inverted phosphor bar)
    for part in ("c", "n", "s", "e", "w", "ne", "nw", "se", "sw"):
        Image.new("RGB", (4, 4) if len(part) == 2 else (4, 4), hex_to_rgb(sel["bg"])).save(out / f"select_{part}.png")
    # countdown bar pixmaps
    Image.new("RGB", (4, 4), hex_to_rgb(c["face"])).save(out / "bar_c.png")
    Image.new("RGB", (4, 4), hex_to_rgb(t["fg"])).save(out / "hl_c.png")

    font_item = f16 or "Unifont Regular 16"
    font_big = f32 or font_item
    theme = f"""# Phosphor-95 GRUB theme (generated)
title-text: ""
desktop-image: "background.png"
desktop-color: "{c['base']}"
terminal-font: "{font_item}"
terminal-left: "12%"
terminal-top: "22%"
terminal-width: "76%"
terminal-height: "36%"
terminal-border: "0"

+ boot_menu {{
  left = 12%
  top = 22%
  width = 76%
  height = 36%
  item_font = "{font_item}"
  selected_item_font = "{font_item}"
  item_color = "{t['fg']}"
  selected_item_color = "{sel['fg']}"
  item_height = 26
  item_padding = 10
  item_spacing = 4
  icon_width = 0
  icon_height = 0
  item_icon_space = 0
  selected_item_pixmap_style = "select_*.png"
  scrollbar = false
}}

+ label {{
  top = 10%
  left = 0
  width = 100%
  align = "center"
  text = "{ident['name']}"
  font = "{font_big}"
  color = "{t['glow']}"
}}
+ label {{
  top = 15%
  left = 0
  width = 100%
  align = "center"
  text = "{ident['tagline']}"
  font = "{font_item}"
  color = "{t['fg_dim']}"
}}

+ label {{
  id = "__timeout__"
  top = 64%
  left = 12%
  width = 76%
  align = "center"
  text = "BOOTING DEFAULT ENTRY IN %d SECONDS ..."
  font = "{font_item}"
  color = "{t['fg']}"
}}
+ progress_bar {{
  id = "__timeout__"
  left = 12%
  top = 68%
  width = 76%
  height = 8
  show_text = false
  bar_style = "bar_*.png"
  highlight_style = "hl_*.png"
}}
"""
    (out / "theme.txt").write_text(theme)


def build(cfg, out):
    build_plymouth(cfg, out / "plymouth" / "phosphor95")
    build_grub(cfg, out / "grub" / "phosphor95")
