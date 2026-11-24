#!/usr/bin/env bash
# Phosphor-95: system-level steps (need sudo). Run from a normal terminal:
#   sudo ./scripts/install-system.sh packages
#   sudo ./scripts/install-system.sh boot      # Plymouth + GRUB (after ./phosphor build)
#   sudo ./scripts/install-system.sh gdm       # login screen      (after ./phosphor build)
#   sudo ./scripts/install-system.sh shell     # make zsh the login shell
#   sudo ./scripts/install-system.sh all
#   sudo ./scripts/install-system.sh uninstall # revert Plymouth, GRUB, GDM
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $EUID -eq 0 ]] || { echo "Run with sudo." >&2; exit 1; }
REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo root)}"
STAMP="$(date +%Y%m%d-%H%M%S)"
SYSBAK="$ROOT/backups/system"
mkdir -p "$SYSBAK"

PACKAGES=(
  # GNOME shell theming + official, version-matched extensions
  gnome-shell-extension-user-theme gnome-shell-extension-window-list
  gnome-shell-extension-apps-menu gnome-shell-extension-system-monitor gnome-tweaks
  # terminal stack
  ghostty zsh zsh-autosuggestions zsh-syntax-highlighting starship fastfetch btop cmatrix
  # build tooling
  imagemagick librsvg2-bin python3-pil libglib2.0-dev-bin unzip fonts-noto-cjk git
  # preview / test tools
  gtk-3-examples gtk-4-examples
  # boot
  plymouth-label plymouth-themes
)

do_packages() {
  apt-get update
  apt-get install -y "${PACKAGES[@]}"
}

backup_file() { # copy a system file into backups/system once per run
  local f="$1"; [[ -e "$f" ]] || return 0
  local dest="$SYSBAK/$STAMP$(echo "$f")"
  mkdir -p "$(dirname "$dest")"; cp -a "$f" "$dest"
  echo "  backed up $f"
}

do_boot() {
  local B="$ROOT/build/boot"
  [[ -d "$B/plymouth/phosphor95" && -d "$B/grub/phosphor95" ]] || { echo "Run ./phosphor build first." >&2; exit 1; }
  echo "== Plymouth"
  backup_file /etc/alternatives/default.plymouth
  rm -rf /usr/share/plymouth/themes/phosphor95
  cp -r "$B/plymouth/phosphor95" /usr/share/plymouth/themes/phosphor95
  update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth \
    /usr/share/plymouth/themes/phosphor95/phosphor95.plymouth 200
  update-alternatives --set default.plymouth /usr/share/plymouth/themes/phosphor95/phosphor95.plymouth
  echo "== GRUB"
  backup_file /etc/default/grub
  rm -rf /boot/grub/themes/phosphor95
  mkdir -p /boot/grub/themes
  cp -r "$B/grub/phosphor95" /boot/grub/themes/phosphor95
  # managed block in /etc/default/grub
  sed -i '/^# >>> phosphor95 >>>/,/^# <<< phosphor95 <<</d' /etc/default/grub
  sed -i -E 's/^(GRUB_TIMEOUT_STYLE=|GRUB_TIMEOUT=|GRUB_THEME=|GRUB_GFXMODE=|GRUB_GFXPAYLOAD_LINUX=|GRUB_TERMINAL_OUTPUT=)/#p95# \1/' /etc/default/grub
  local res; res="$(python3 -I -c "import tomllib,sys;print(tomllib.load(open(sys.argv[1],'rb'))['desktop']['resolution'])" "$ROOT/config/system.toml")"
  cat >> /etc/default/grub <<GRUBCFG
# >>> phosphor95 >>>
GRUB_TIMEOUT_STYLE=menu
GRUB_TIMEOUT=3
GRUB_GFXMODE=$res,auto
GRUB_THEME=/boot/grub/themes/phosphor95/theme.txt
GRUB_GFXPAYLOAD_LINUX=keep
# <<< phosphor95 <<<
GRUBCFG
  update-grub
  update-initramfs -u
}

do_gdm() {
  local G="$ROOT/build/gdm/phosphor95-gdm.gresource"
  [[ -f "$G" ]] || { echo "Run ./phosphor build first." >&2; exit 1; }
  install -Dm644 "$G" /usr/share/gnome-shell/theme/Phosphor95/gnome-shell-theme.gresource
  update-alternatives --install /usr/share/gnome-shell/gdm-theme.gresource gdm-theme.gresource \
    /usr/share/gnome-shell/theme/Phosphor95/gnome-shell-theme.gresource 5
  update-alternatives --set gdm-theme.gresource /usr/share/gnome-shell/theme/Phosphor95/gnome-shell-theme.gresource
  echo "GDM theme set. It shows on next logout/reboot."
}

do_uninstall() {
  echo "== Plymouth -> distro default"
  update-alternatives --remove default.plymouth /usr/share/plymouth/themes/phosphor95/phosphor95.plymouth 2>/dev/null || true
  update-alternatives --auto default.plymouth || true
  rm -rf /usr/share/plymouth/themes/phosphor95
  echo "== GRUB -> previous settings"
  sed -i '/^# >>> phosphor95 >>>/,/^# <<< phosphor95 <<</d' /etc/default/grub
  sed -i -E 's/^#p95# //' /etc/default/grub
  rm -rf /boot/grub/themes/phosphor95
  update-grub
  echo "== GDM -> Yaru"
  update-alternatives --remove gdm-theme.gresource /usr/share/gnome-shell/theme/Phosphor95/gnome-shell-theme.gresource 2>/dev/null || true
  update-alternatives --auto gdm-theme.gresource || true
  rm -rf /usr/share/gnome-shell/theme/Phosphor95
  update-initramfs -u
  echo "System parts reverted. (Login shell unchanged: chsh -s /bin/bash $REAL_USER to revert.)"
}

do_shell() {
  chsh -s /usr/bin/zsh "$REAL_USER" && echo "Login shell for $REAL_USER -> zsh (takes effect next login)."
}

[[ $# -gt 0 ]] || { sed -n '2,9p' "$0"; exit 1; }
for step in "$@"; do
  case "$step" in
    packages)  do_packages ;;
    boot)      do_boot ;;
    gdm)       do_gdm ;;
    shell)     do_shell ;;
    all)       do_packages; do_boot; do_gdm; do_shell ;;
    uninstall) do_uninstall ;;
    *) sed -n '2,9p' "$0"; exit 1 ;;
  esac
done
