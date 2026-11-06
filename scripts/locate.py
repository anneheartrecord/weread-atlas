#!/usr/bin/env python3
"""List Obsidian vaults and any 书脉 root already inside them.

Reads Obsidian's own vault registry (obsidian.json), so iCloud and other
deep vault paths are found without scanning the home folder. For each vault
it reports folders up to two levels deep that hold `.atlas/config.json`.

Output, one vault per block:
  库：<vault name>  <vault path>
    书脉：<root path>        (when a root exists)
"""
import argparse
import json
import os
import sys

REGISTRIES = [
    "~/Library/Application Support/obsidian/obsidian.json",  # macOS
    "~/.config/obsidian/obsidian.json",  # Linux
    "~/snap/obsidian/current/.config/obsidian/obsidian.json",  # Linux snap
    "~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json",  # Linux flatpak
    os.path.join(os.environ.get("APPDATA", ""), "obsidian", "obsidian.json") if os.environ.get("APPDATA") else "",  # Windows
]


def vaults_from_registry(registries=None):
    """Return [(name, path, last_opened_ms)] for every registered vault that still exists, newest first."""
    seen = {}
    for reg in registries if registries is not None else REGISTRIES:
        if not reg:
            continue
        path = os.path.expanduser(reg)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        for v in (data.get("vaults") or {}).values():
            p = v.get("path")
            if p and os.path.isdir(p) and p not in seen:
                seen[p] = v.get("ts") or 0
    return [(os.path.basename(p.rstrip("/\\")), p, ts) for p, ts in sorted(seen.items(), key=lambda x: -x[1])]


def roots_in(vault):
    """Folders up to two levels below the vault that already hold a 书脉 config."""
    found = []
    for depth1 in sorted(os.listdir(vault)):
        a = os.path.join(vault, depth1)
        if depth1.startswith(".") or not os.path.isdir(a):
            continue
        if os.path.isfile(os.path.join(a, ".atlas", "config.json")):
            found.append(a)
            continue
        try:
            children = sorted(os.listdir(a))
        except OSError:
            continue
        for depth2 in children:
            b = os.path.join(a, depth2)
            if not depth2.startswith(".") and os.path.isfile(os.path.join(b, ".atlas", "config.json")):
                found.append(b)
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description="列出 Obsidian 的库，以及库里已有的书脉根目录。")
    ap.parse_args(argv)
    vaults = vaults_from_registry()
    if not vaults:
        print("没找到 Obsidian 的库注册表。请让用户直接给出库的路径。")
        return 1
    for name, path, _ in vaults:
        print("库：%s  %s" % (name, path))
        for r in roots_in(path):
            print("  书脉：%s" % r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
