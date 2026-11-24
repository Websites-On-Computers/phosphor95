"""Terminal stack: ghostty + CRT shader, zsh, starship, fastfetch, btop, helper scripts."""
from p95 import SRC, render_tree

SCREEN_W = 18  # inner width of the monitor glass in the fastfetch logo


def logo(cfg) -> str:
    name = cfg["identity"]["name"][:SCREEN_W - 2]
    rows = [
        ">_",
        "",
        "░▒▓█ ▓▒░ █▓▒░",
        "▒░  ▓█▓  ░▒▓",
        "",
        name,
    ]
    glass = [f"$2 {r:<{SCREEN_W - 1}}$1" for r in rows]
    w = SCREEN_W + 2
    lines = [
        "$1╔" + "═" * (w + 2) + "╗",
        "$1║ ┌" + "─" * SCREEN_W + "┐ ║",
        *[f"$1║ │{g}│ ║" for g in glass],
        "$1║ └" + "─" * SCREEN_W + "┘ ║",
        "$1║ " + "$3▪$1" + " " * (w - 2) + "$3●$1 ║",
        "$1╚" + "═" * ((w + 2) // 2 - 2) + "╤══╤" + "═" * ((w + 2) - (w + 2) // 2 - 2) + "╝",
        " " * ((w + 4) // 2 - 5) + "▄▄▄█▄▄█▄▄▄",
    ]
    return "\n".join(lines) + "\n"


def build(cfg, out):
    render_tree(SRC / "terminal", out, cfg)
    (out / "fastfetch" / "logo.txt").write_text(logo(cfg))
