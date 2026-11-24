#!/usr/bin/env python3
"""Phosphor-95 build: python3 tools/build.py [component ...]  (default: all)"""
import importlib
import shutil
import sys
import time

sys.path.insert(0, __import__("os").path.dirname(__file__))
from p95 import BUILD, load_config  # noqa: E402

COMPONENTS = ["terminal", "gtk", "shell", "icons", "cursors", "wallpaper", "boot", "gdm"]


def main(argv):
    wanted = argv or COMPONENTS
    unknown = set(wanted) - set(COMPONENTS)
    if unknown:
        raise SystemExit(f"unknown component(s): {', '.join(sorted(unknown))}. choose from {COMPONENTS}")
    cfg = load_config()
    BUILD.mkdir(exist_ok=True)
    for name in COMPONENTS:
        if name not in wanted:
            continue
        t = time.time()
        out = BUILD / name
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        mod = importlib.import_module(f"components.{name}")
        mod.build(cfg, out)
        print(f"  [ OK ] {name:<10} {time.time() - t:5.1f}s  -> build/{name}")


if __name__ == "__main__":
    main(sys.argv[1:])
