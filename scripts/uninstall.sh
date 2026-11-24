#!/usr/bin/env bash
# Phosphor-95: undo the user-level install. (System parts: sudo ./scripts/install-system.sh uninstall)
#   - restores every gsettings key recorded in backups/gsettings-revert.txt
#   - re-enables the Ubuntu dock, disables the extensions we turned on
#   - removes installed theme files; restores the newest backup of any config we replaced
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAK="$ROOT/backups"; REVERT="$BAK/gsettings-revert.txt"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"; CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
say() { printf '[ P95 ] %s\n' "$*"; }

if [[ -f "$REVERT" ]]; then
  say "restoring gsettings"
  while read -r schema key value; do
    gsettings set "$schema" "$key" "$value" 2>/dev/null || say "  could not restore $schema $key"
  done < "$REVERT"
  mv "$REVERT" "$REVERT.restored-$(date +%s)"
fi
dconf reset -f /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/p95-term/ || true
dconf reset -f /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/p95-term2/ || true
dconf reset -f /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/p95-matrix/ || true

say "extensions"
gnome-extensions disable phosphor95-shell@terminal01 2>/dev/null || true
for e in user-theme window-list apps-menu system-monitor; do
  gnome-extensions disable "$e@gnome-shell-extensions.gcampax.github.com" 2>/dev/null || true
done
gnome-extensions enable ubuntu-dock@ubuntu.com 2>/dev/null || true
gnome-extensions enable ding@rastersoft.com 2>/dev/null || true

say "removing installed files"
rm -rf "$DATA/themes/Phosphor95" "$DATA/icons/Phosphor95" "$DATA/icons/Phosphor95-Cursors" \
       "$HOME/.icons/Phosphor95-Cursors" "$DATA/backgrounds/phosphor95" "$DATA/fonts/phosphor95" \
       "$DATA/gnome-shell/extensions/phosphor95-shell@terminal01" "$CONF/fontconfig/conf.d/60-phosphor95.conf"
fc-cache -f >/dev/null 2>&1 || true

# generated configs: remove if ours, then restore the newest backup if one exists
for f in "$CONF/gtk-4.0/gtk.css" "$CONF/ghostty/config" "$CONF/ghostty/shaders/phosphor-crt.glsl" \
         "$CONF/starship.toml" "$CONF/fastfetch/config.jsonc" "$CONF/fastfetch/logo.txt" \
         "$CONF/btop/themes/phosphor95.theme" "$HOME/.zshrc" "$CONF/xdg-terminals.list" \
         "$HOME/.local/bin/p95-boot" "$HOME/.local/bin/crt" "$HOME/.local/bin/matrix"; do
  [[ -e "$f" ]] || continue
  if grep -qE "Phosphor-95|phosphor95|ghostty.desktop" "$f" 2>/dev/null || [[ "$f" == *"/.local/bin/"* ]]; then
    rm -f "$f"
    rel="${f#"$HOME"}"
    newest="$(ls -d "$BAK"/files/*"$rel" 2>/dev/null | sort | tail -1 || true)"
    if [[ -n "$newest" ]]; then cp -a "$newest" "$f"; say "  restored ${f/#$HOME/~} from backup"; fi
  fi
done
[[ -f "$CONF/btop/btop.conf" ]] && sed -i 's|^color_theme = "phosphor95"|color_theme = "Default"|' "$CONF/btop/btop.conf"
say "done. Log out and back in to fully return to stock Ubuntu."
