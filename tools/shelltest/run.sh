#!/usr/bin/env bash
# Headless nested GNOME Shell screenshot harness for the Phosphor95 shell theme.
#   tools/shelltest/run.sh OUTDIR [app ...]
# Fully sandboxed: own D-Bus session, own XDG_DATA_HOME/XDG_CONFIG_HOME and dconf db,
# a virtual monitor at [desktop] resolution. Nothing touches the real session's settings.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$(realpath -m "${1:?usage: run.sh OUTDIR [app ...]}")"; shift
APPS=("$@")
SB="$(mktemp -d)"; trap 'rm -rf "$SB"' EXIT
mkdir -p "$OUT" "$SB"/{data/themes,data/gnome-shell/extensions,data/icons,config/fontconfig/conf.d,config/gtk-4.0,runtime}
rm -f "$OUT"/*.png "$OUT"/log.txt "$OUT"/DONE
ln -s "${XDG_DATA_HOME:-$HOME/.local/share}/fonts" "$SB/data/fonts"
cp "$ROOT/src/fonts/60-phosphor95.conf" "$SB/config/fontconfig/conf.d/"
cp -a "$ROOT/build/gtk/Phosphor95" "$SB/data/themes/Phosphor95"
cp -a "$ROOT/build/shell/Phosphor95/gnome-shell" "$SB/data/themes/Phosphor95/"
cp "$ROOT/build/gtk/user/gtk-4.0.css" "$SB/config/gtk-4.0/gtk.css"
cp -a "$ROOT/build/terminal/ghostty" "$SB/config/ghostty"   # so a test Ghostty looks like the real one
cp -a "$ROOT/build/icons/Phosphor95" "$ROOT/build/cursors/Phosphor95-Cursors" "$SB/data/icons/"
cp -a "$ROOT/build/shell/extensions/phosphor95-shell@terminal01" "$SB/data/gnome-shell/extensions/"
cp -a "$ROOT/tools/shelltest/p95-testkit@local" "$SB/data/gnome-shell/extensions/"
read -r UI_FONT MONO_FONT < <(python3 -I -c "import tomllib,sys;f=tomllib.load(open(sys.argv[1],'rb'))['fonts'];print(f\"{f['ui']} {f['ui_size']}\".replace(' ','_'), f\"{f['mono']} {f['mono_size']}\".replace(' ','_'))" "$ROOT/config/system.toml")
UI_FONT="${UI_FONT//_/ }"; MONO_FONT="${MONO_FONT//_/ }"
RES="$(python3 -I -c "import tomllib,sys;print(tomllib.load(open(sys.argv[1],'rb'))['desktop']['resolution'])" "$ROOT/config/system.toml")"
WALL="$ROOT/build/wallpaper/phosphor95-rain-$RES.png"
echo "user-db:p95test" > "$SB/dconf-profile"
chmod 700 "$SB/runtime"

cat > "$SB/inner.sh" <<INNER
set -u
export XDG_DATA_HOME="$SB/data" XDG_CONFIG_HOME="$SB/config" DCONF_PROFILE="$SB/dconf-profile"
export XDG_RUNTIME_DIR="$SB/runtime" P95_TEST_OUT="$OUT" P95_TEST_CSS="$SB/data/themes/Phosphor95/gnome-shell/gnome-shell.css"
export P95_TEST_WAIT=\${P95_TEST_WAIT:-6000}
unset WAYLAND_DISPLAY DISPLAY
w() { dconf write "\$1" "\$2"; }
w /org/gnome/shell/disable-user-extensions false
w /org/gnome/shell/enabled-extensions "['p95-testkit@local', 'phosphor95-shell@terminal01', 'window-list@gnome-shell-extensions.gcampax.github.com', 'apps-menu@gnome-shell-extensions.gcampax.github.com', 'system-monitor@gnome-shell-extensions.gcampax.github.com']"
w /org/gnome/shell/disabled-extensions "['ubuntu-dock@ubuntu.com', 'ding@rastersoft.com', 'snapd-prompting@canonical.com']"
w /org/gnome/shell/welcome-dialog-last-shown-version "'999'"
w /org/gnome/desktop/interface/gtk-theme "'Phosphor95'"
w /org/gnome/desktop/interface/icon-theme "'Phosphor95'"
w /org/gnome/desktop/interface/cursor-theme "'Phosphor95-Cursors'"
w /org/gnome/desktop/interface/color-scheme "'prefer-dark'"
w /org/gnome/desktop/interface/font-name "'$UI_FONT'"
w /org/gnome/desktop/interface/monospace-font-name "'$MONO_FONT'"
w /org/gnome/desktop/wm/preferences/button-layout "'appmenu:minimize,maximize,close'"
w /org/gnome/desktop/background/picture-uri "'file://$WALL'"
w /org/gnome/desktop/background/picture-uri-dark "'file://$WALL'"
w /org/gnome/desktop/screensaver/picture-uri "'file://$WALL'"
w /org/gnome/shell/extensions/window-list/grouping-mode "'never'"
gnome-shell --headless --virtual-monitor $RES --wayland-display=p95-test --mode=ubuntu > "$OUT/shell.log" 2>&1 &
SHELL_PID=\$!
for i in \$(seq 1 60); do [ -S "$SB/runtime/p95-test" ] && break; sleep 0.25; done
for app in ${APPS[@]+"${APPS[@]}"}; do WAYLAND_DISPLAY=p95-test GDK_BACKEND=wayland \$app >/dev/null 2>&1 & done
for i in \$(seq 1 240); do [ -e "$OUT/DONE" ] && break; kill -0 \$SHELL_PID 2>/dev/null || break; sleep 0.5; done
kill \$SHELL_PID 2>/dev/null; sleep 1; kill -9 \$SHELL_PID 2>/dev/null
INNER
# private session bus: use the system dbus-run-session, or a locally unpacked dbus-daemon .deb
# (Ubuntu 26.10 ships dbus-broker, which needs systemd to launch a bus)
DRS="$(command -v dbus-run-session || true)"
if [[ -z "$DRS" ]]; then
  L="$ROOT/.upstream/dbus/root/usr/bin"
  if [[ ! -x "$L/dbus-run-session" ]]; then
    mkdir -p "$ROOT/.upstream/dbus" && (cd "$ROOT/.upstream/dbus" && apt-get download dbus-daemon >/dev/null && dpkg-deb -x dbus-daemon_*.deb root)
  fi
  DRS="$L/dbus-run-session"
  export PATH="$L:$PATH"
fi
# the bus daemon (and the dconf-service it activates) must already see the sandbox env
export XDG_DATA_HOME="$SB/data" XDG_CONFIG_HOME="$SB/config" DCONF_PROFILE="$SB/dconf-profile" XDG_RUNTIME_DIR="$SB/runtime"
"$DRS" --dbus-daemon="$(dirname "$DRS")/dbus-daemon" --config-file=/usr/share/dbus-1/session.conf -- bash "$SB/inner.sh"
ls "$OUT"/*.png 2>/dev/null | wc -l | xargs echo "screenshots:"
[[ -e "$OUT/DONE" ]] || { echo "harness did not finish; see $OUT/shell.log and $OUT/log.txt"; exit 1; }
