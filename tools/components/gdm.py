"""GDM login theme: copy of Ubuntu's Yaru shell gresource with Phosphor overrides appended
to every stylesheet, plus the login wallpaper. Installed via update-alternatives (revertible)."""
import shutil
import subprocess
import tempfile
from pathlib import Path

from p95 import BUILD, render, resolution
from components.shell import overrides

SOURCE = Path("/usr/share/gnome-shell/theme/Yaru/gnome-shell-theme.gresource")
PREFIX = "/org/gnome/shell/theme"


def build(cfg, out):
    if not SOURCE.exists():
        print("           skipped: no Yaru gresource on this system")
        return
    compiler = shutil.which("glib-compile-resources")
    if not compiler:
        print("           skipped: glib-compile-resources missing (apt: libglib2.0-dev-bin)")
        return
    w, h = resolution(cfg)
    wall = BUILD / "wallpaper" / f"phosphor95-login-{w}x{h}.png"
    if not wall.exists():
        raise SystemExit("build wallpaper first")
    listing = subprocess.run(["gresource", "list", str(SOURCE)], capture_output=True, text=True, check=True).stdout.split()
    extra = overrides(cfg) + render(
        "\n/* GDM: login wallpaper */\n"
        "#lockDialogGroup, .login-dialog { background: {{ core.base }} url(\"resource://" + PREFIX +
        "/phosphor95-login.png\"); background-size: cover; background-position: center; }\n", cfg)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        files = []
        for res in listing:
            data = subprocess.run(["gresource", "extract", str(SOURCE), res], capture_output=True, check=True).stdout
            rel = res[len(PREFIX) + 1:] if res.startswith(PREFIX + "/") else res.lstrip("/")
            dst = tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if res.endswith(".css") and "pad-osd" not in res and "high-contrast" not in res:
                data = data + ("\n/* ===== Phosphor-95 ===== */\n" + extra).encode()
            dst.write_bytes(data)
            files.append(rel)
        shutil.copy(wall, tmp / "phosphor95-login.png")
        files.append("phosphor95-login.png")
        xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<gresources>", f'  <gresource prefix="{PREFIX}">']
        xml += [f"    <file>{f}</file>" for f in files]
        xml += ["  </gresource>", "</gresources>"]
        (tmp / "theme.gresource.xml").write_text("\n".join(xml))
        subprocess.run([compiler, "--sourcedir", str(tmp), "--target", str(out / "phosphor95-gdm.gresource"),
                        str(tmp / "theme.gresource.xml")], check=True)
    print(f"           {len(files)} resources -> phosphor95-gdm.gresource")
