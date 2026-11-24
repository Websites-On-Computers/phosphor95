#!/usr/bin/env bash
# Phosphor-95: user-level install (no sudo). Idempotent; re-run after every build.
#   ./scripts/install-user.sh            install everything
#   ./scripts/install-user.sh terminal   just one part: fonts|themes|icons|wallpaper|terminal|shell|settings
# Every gsettings key we touch has its previous value recorded once in
# backups/gsettings-revert.txt; every file we overwrite is copied to backups/files/<stamp>/.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
B="$ROOT/build"
STAMP="$(date +%Y%m%d-%H%M%S)"
BAK="$ROOT/backups"; mkdir -p "$BAK"
REVERT="$BAK/gsettings-revert.txt"; touch "$REVERT"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
cfgval() { python3 -I -c "import tomllib,sys;d=tomllib.load(open('$ROOT/config/'+sys.argv[1],'rb'));print(d[sys.argv[2]][sys.argv[3]])" "$@"; }

say()  { printf '\e[38;2;51;255;102m[ P95 ]\e[0m %s\n' "$*"; }
warn() { printf '\e[38;2;255;176;0m[ P95 ]\e[0m %s\n' "$*" >&2; }

[[ -d "$B" ]] || { warn "no build/ - run ./phosphor build first"; exit 1; }

# copy a file into place, backing up anything different that was there before
place() { # src dst [mode]
  local src="$1" dst="$2" mode="${3:-644}"
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" && ! -L "$dst" ]] && ! cmp -s "$src" "$dst"; then
    if ! grep -q "generated, edit src/\|Phosphor-95" "$dst" 2>/dev/null; then
      local keep="$BAK/files/$STAMP${dst#"$HOME"}"
      mkdir -p "$(dirname "$keep")"; cp -a "$dst" "$keep"; warn "backed up existing ${dst/#$HOME/~}"
    fi
  fi
  install -m "$mode" "$src" "$dst"
}
place_dir() { # src dst  (replace directory wholesale; it is ours)
  rm -rf "$2"; mkdir -p "$(dirname "$2")"; cp -a "$1" "$2"
}

gset() { # schema key value  (records the original once)
  local schema="$1" key="$2" val="$3"
  if ! gsettings list-keys "$schema" 2>/dev/null | grep -qx "$key"; then
    warn "skip $schema $key (schema/key not available)"; return 0; fi
  if ! grep -q "^$schema $key " "$REVERT"; then
    printf '%s %s %s\n' "$schema" "$key" "$(gsettings get "$schema" "$key")" >> "$REVERT"
  fi
  gsettings set "$schema" "$key" "$val" || warn "could not set $schema $key"
}

do_fonts() {
  say "fonts"
  mkdir -p "$DATA/fonts/phosphor95"
  cp "$ROOT"/vendor/fonts/*.{ttf,otf} "$DATA/fonts/phosphor95/"
  place "$ROOT/src/fonts/60-phosphor95.conf" "$CONF/fontconfig/conf.d/60-phosphor95.conf"
  fc-cache -f "$DATA/fonts" >/dev/null
}

do_themes() {
  say "GTK + Shell theme -> ${DATA/#$HOME/~}/themes/Phosphor95"
  place_dir "$B/gtk/Phosphor95" "$DATA/themes/Phosphor95"
  cp -a "$B/shell/Phosphor95/gnome-shell" "$DATA/themes/Phosphor95/gnome-shell"
  place "$B/gtk/user/gtk-4.0.css" "$CONF/gtk-4.0/gtk.css"
}

do_icons() {
  say "icons + cursors"
  place_dir "$B/icons/Phosphor95" "$DATA/icons/Phosphor95"
  place_dir "$B/cursors/Phosphor95-Cursors" "$DATA/icons/Phosphor95-Cursors"
  gtk-update-icon-cache -q -f "$DATA/icons/Phosphor95" 2>/dev/null || true
  # Xwayland/legacy apps look in ~/.icons
  mkdir -p "$HOME/.icons"; ln -sfn "$DATA/icons/Phosphor95-Cursors" "$HOME/.icons/Phosphor95-Cursors"
}

do_wallpaper() {
  say "wallpapers -> ${DATA/#$HOME/~}/backgrounds/phosphor95"
  place_dir "$B/wallpaper" "$DATA/backgrounds/phosphor95"
}

do_terminal() {
  say "terminal: ghostty, zsh, starship, fastfetch, btop, helpers"
  local T="$B/terminal"
  place "$T/ghostty/config" "$CONF/ghostty/config"
  place "$T/ghostty/shaders/phosphor-crt.glsl" "$CONF/ghostty/shaders/phosphor-crt.glsl"
  place "$T/starship/starship.toml" "$CONF/starship.toml"
  place "$T/fastfetch/config.jsonc" "$CONF/fastfetch/config.jsonc"
  place "$T/fastfetch/logo.txt" "$CONF/fastfetch/logo.txt"
  place "$T/btop/themes/phosphor95.theme" "$CONF/btop/themes/phosphor95.theme"
  if [[ -f "$CONF/btop/btop.conf" ]]; then
    sed -i 's|^color_theme = .*|color_theme = "phosphor95"|; s|^theme_background = .*|theme_background = True|' "$CONF/btop/btop.conf"
  else
    printf 'color_theme = "phosphor95"\ntheme_background = True\nrounded_corners = False\n' > "$CONF/btop/btop.conf"
  fi
  place "$T/zsh/zshrc" "$HOME/.zshrc"
  for f in "$T"/bin/*; do place "$f" "$HOME/.local/bin/$(basename "$f")" 755; done
  # crt default from config/system.toml
  if [[ "$(cfgval system.toml desktop crt)" == "False" ]]; then "$HOME/.local/bin/crt" off >/dev/null; fi
  # default terminal for xdg-terminal-exec (GNOME / Nautilus "Open in Terminal")
  if [[ -f /usr/share/applications/com.mitchellh.ghostty.desktop ]]; then
    printf 'com.mitchellh.ghostty.desktop\n' > "$CONF/xdg-terminals.list"
  fi
}

do_shell() {
  say "GNOME Shell extension: phosphor95-shell"
  place_dir "$B/shell/extensions/phosphor95-shell@terminal01" \
            "$DATA/gnome-shell/extensions/phosphor95-shell@terminal01"
}

ext_on()  { gnome-extensions enable  "$1" 2>/dev/null && say "  + $1" || warn "  could not enable $1 (installed? may need re-login)"; }
ext_off() { gnome-extensions disable "$1" 2>/dev/null && say "  - $1" || true; }

do_settings() {
  say "GNOME settings (originals recorded in backups/gsettings-revert.txt)"
  local ui; ui="$(cfgval system.toml fonts ui) $(cfgval system.toml fonts ui_size)"
  local mono; mono="$(cfgval system.toml fonts mono) $(cfgval system.toml fonts mono_size)"
  local I=org.gnome.desktop.interface
  gset $I gtk-theme 'Phosphor95'
  gset $I icon-theme 'Phosphor95'
  gset $I cursor-theme 'Phosphor95-Cursors'
  gset $I cursor-size 24
  gset $I color-scheme 'prefer-dark'
  gset $I accent-color 'green'
  gset $I font-name "$ui"
  gset $I document-font-name "$ui"
  gset $I monospace-font-name "$mono"
  gset $I enable-animations true
  gset org.gnome.desktop.wm.preferences titlebar-font "$(cfgval system.toml fonts ui) Bold $(cfgval system.toml fonts ui_size)"
  gset org.gnome.desktop.wm.preferences button-layout 'appmenu:minimize,maximize,close'

  local wall="file://$DATA/backgrounds/phosphor95/phosphor95-rain-$(cfgval system.toml desktop resolution).png"
  local base; base="$(cfgval palette.toml core base)"
  for s in org.gnome.desktop.background org.gnome.desktop.screensaver; do
    gset $s picture-uri "$wall"
    gset $s picture-options 'zoom'
    gset $s primary-color "$base"
  done
  gset org.gnome.desktop.background picture-uri-dark "$wall"

  # extensions
  ext_off ubuntu-dock@ubuntu.com
  ext_off ding@rastersoft.com          # desktop icons would sit on top of the rain
  for e in user-theme window-list apps-menu system-monitor; do
    ext_on "$e@gnome-shell-extensions.gcampax.github.com"
  done
  ext_on phosphor95-shell@terminal01
  gset org.gnome.shell.extensions.user-theme name 'Phosphor95'
  gset org.gnome.shell.extensions.window-list grouping-mode 'never'
  gset org.gnome.shell.extensions.window-list show-on-all-monitors false
  gset org.gnome.shell.extensions.window-list display-all-workspaces false
  gset org.gnome.shell.extensions.window-list embed-previews false

  # keyboard: Ctrl+Alt+T / Super+Return -> ghostty, Ctrl+Alt+M -> matrix screensaver
  if command -v ghostty >/dev/null; then
    local MK=org.gnome.settings-daemon.plugins.media-keys
    local P=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings
    gset $MK terminal "[]"
    gset $MK custom-keybindings "['$P/p95-term/', '$P/p95-term2/', '$P/p95-matrix/']"
    local CK=org.gnome.settings-daemon.plugins.media-keys.custom-keybinding
    gsettings set $CK:$P/p95-term/   name 'Phosphor terminal';  gsettings set $CK:$P/p95-term/   command 'ghostty'; gsettings set $CK:$P/p95-term/   binding '<Primary><Alt>t'
    gsettings set $CK:$P/p95-term2/  name 'Phosphor terminal 2';gsettings set $CK:$P/p95-term2/  command 'ghostty'; gsettings set $CK:$P/p95-term2/  binding '<Super>Return'
    gsettings set $CK:$P/p95-matrix/ name 'Matrix screensaver'; gsettings set $CK:$P/p95-matrix/ command 'ghostty --fullscreen=true --custom-shader-animation=true -e matrix'; gsettings set $CK:$P/p95-matrix/ binding '<Primary><Alt>m'
  fi
}

parts=("${@:-fonts themes icons wallpaper terminal shell settings}")
for p in ${parts[@]}; do
  case "$p" in
    fonts|themes|icons|wallpaper|terminal|shell|settings) "do_$p" ;;
    *) warn "unknown part '$p'"; exit 1 ;;
  esac
done
say "done. Log out and back in once so GNOME Shell loads the new theme + extensions."
