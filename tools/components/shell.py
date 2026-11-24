"""GNOME Shell theme (user-theme extension) + phosphor95-shell companion extension."""
from p95 import SRC, render, render_tree

# Ubuntu's session loads Yaru; import its dark variant, then layer Phosphor on top.
BASE_IMPORT = '@import url("resource:///org/gnome/shell/theme/Yaru/gnome-shell-dark.css");\n'


def overrides(cfg) -> str:
    return render((SRC / "shell" / "phosphor.css.tmpl").read_text(), cfg)


def build(cfg, out):
    theme = out / "Phosphor95" / "gnome-shell"
    theme.mkdir(parents=True)
    (theme / "gnome-shell.css").write_text(BASE_IMPORT + overrides(cfg))
    render_tree(SRC / "shell" / "extension", out / "extensions", cfg)
