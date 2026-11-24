// TEST-ONLY. Runs inside a headless nested gnome-shell started by tools/shelltest/run.sh.
// Loads the Phosphor95 stylesheet, walks scripted scenes, saves a PNG per scene, writes DONE.
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

Gio._promisify(Shell.Screenshot.prototype, 'screenshot', 'screenshot_finish');
const sleep = ms => new Promise(r => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => { r(); return GLib.SOURCE_REMOVE; }));

let started = false;   // lock tests disable + re-enable this kit too: run the script once

export default class TestKit extends Extension {
    enable() {
        if (started) return;
        started = true;
        this._out = GLib.getenv('P95_TEST_OUT');
        const css = GLib.getenv('P95_TEST_CSS');
        if (css) {
            Main.setThemeStylesheet(css);
            Main.loadTheme();
        }
        this._run().catch(e => this._log(`FATAL ${e}\n${e.stack}`));
    }

    disable() {}

    _log(msg) {
        const f = Gio.File.new_for_path(`${this._out}/log.txt`);
        const s = f.append_to(Gio.FileCreateFlags.NONE, null);
        s.write_all(`${msg}\n`, null);
        s.close(null);
    }

    async _shot(name) {
        await sleep(450);
        const file = Gio.File.new_for_path(`${this._out}/${name}.png`);
        const stream = file.replace(null, false, Gio.FileCreateFlags.NONE, null);
        await new Shell.Screenshot().screenshot(false, stream);
        stream.close(null);
        this._log(`shot ${name}`);
    }

    async _scene(name, open, close) {
        try {
            await open();
            await this._shot(name);
        } catch (e) {
            this._log(`scene ${name} failed: ${e}`);
        }
        try { await close?.(); } catch (e) { this._log(`close ${name}: ${e}`); }
        await sleep(350);
    }

    _states() {
        const em = Main.extensionManager;
        const short = u => u.split('@')[0];
        return ['window-list@gnome-shell-extensions.gcampax.github.com',
            'apps-menu@gnome-shell-extensions.gcampax.github.com',
            'phosphor95-shell@terminal01']
            .map(u => `${short(u)}=${em.lookup(u)?.state}`).join(' ');
    }

    _dumpStart(tag) {
            const b = Main.panel.statusArea['apps-menu'];
            const dump = (a, d = 0) => {
                if (!a || d > 4) return;
                this._log(`${'  '.repeat(d)}${a.constructor.name}.${a.style_class ?? ''} w=${a.width} x_expand=${a.x_expand} needs=${a.needs_expand?.(0)}`);
                for (const c of a.get_children()) dump(c, d + 1);
            };
            this._log(`START tree (${tag}):`); dump(b?.container);
            const box = b?.container?.get_parent();
            this._log(`taskbar box children: ${box?.get_children().map(c => `${c.constructor.name}.${c.style_class ?? ''}:${c.width}:xe=${c.x_expand}`).join(' | ')}`);
    }

    _popLock() {
        const sm = Main.sessionMode;
        if (sm.currentMode === 'unlock-dialog') sm.popMode('unlock-dialog');
        else this._log(`  (mode is ${sm.currentMode}, stack ${JSON.stringify(sm._modeStack)})`);
    }

    _startDocked() {
        const b = Main.panel.statusArea['apps-menu'];
        const p = b?.container?.get_parent();
        return !b ? 'no-button' : p === Main.panel._leftBox ? 'top-bar' : 'taskbar';
    }

    async _step(name, fn) {
        this._log(`life ${name}: start`);
        await fn();
        await sleep(2500);   // retry docking runs every 400ms
        this._log(`life ${name}: ok  [${this._states()}] start=${this._startDocked()}`);
    }

    // Extension lifecycle: these are the paths that crashed the real session.
    async _lifecycle() {
        const em = Main.extensionManager;
        const WL = 'window-list@gnome-shell-extensions.gcampax.github.com';
        const AM = 'apps-menu@gnome-shell-extensions.gcampax.github.com';
        const P95 = 'phosphor95-shell@terminal01';
        this._dumpStart('initial');
        this._log(`life initial [${this._states()}] start=${this._startDocked()} order=${em._extensionOrder.map(u => u.split('@')[0]).join(',')}`);
        await this._step('lock (unlock-dialog session mode)', async () => {
            Main.sessionMode.pushMode('unlock-dialog');
            await sleep(2000);
            this._popLock();
        });
        await this._shot('09-after-lock');
        await this._step('disable+enable phosphor95-shell', async () => {
            await em.disableExtension(P95); await sleep(800); await em.enableExtension(P95);
        });
        await this._step('disable+enable window-list', async () => {
            await em.disableExtension(WL); await sleep(800); await em.enableExtension(WL);
        });
        await this._step('disable+enable apps-menu', async () => {
            await em.disableExtension(AM); await sleep(800); await em.enableExtension(AM);
        });
        await this._step('lock again', async () => {
            Main.sessionMode.pushMode('unlock-dialog');
            await sleep(1500);
            this._popLock();
        });
        this._dumpStart('after');
        await this._shot('10-after-lifecycle');
    }

    async _run() {
        await sleep(Number(GLib.getenv('P95_TEST_WAIT') ?? 6000));
        Main.overview.hide();
        await sleep(800);
        const sa = Main.panel.statusArea;
        await this._scene('01-desktop', async () => {});
        await this._scene('02-start-menu',
            async () => sa['apps-menu']?.menu.open(),
            async () => sa['apps-menu']?.menu.close());
        await this._scene('03-quick-settings',
            async () => sa.quickSettings.menu.open(),
            async () => sa.quickSettings.menu.close());
        await this._scene('04-calendar',
            async () => { Main.notify('TERMINAL-01', 'Uplink established. 3 local models online.'); await sleep(300); sa.dateMenu.menu.open(); },
            async () => sa.dateMenu.menu.close());
        await this._scene('05-notification',
            async () => { Main.notify('MODEL HOST', 'qwen2.5-7b loaded into memory (4.4 GB)'); await sleep(900); });
        await this._scene('06-run-dialog',
            async () => Main.openRunDialog(),
            async () => { for (const d of Main.layoutManager.modalDialogGroup.get_children()) d.close?.(); });
        await this._scene('07-overview',
            async () => { Main.overview.show(); await sleep(1200); },
            async () => { Main.overview.hide(); await sleep(800); });
        await this._scene('08-app-grid',
            async () => { Main.overview.showApps(); await sleep(1400); },
            async () => { Main.overview.hide(); await sleep(800); });
        if (GLib.getenv('P95_TEST_LIFECYCLE') !== '0')
            await this._lifecycle();
        this._log('DONE');
        GLib.file_set_contents(`${this._out}/DONE`, 'ok');
    }
}
