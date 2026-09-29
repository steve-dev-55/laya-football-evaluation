#!/usr/bin/env python3
"""Crée la release GitHub v0.2.0-real-integration avec notes + artefacts.

Usage : python3 scripts/create_release.py   (depuis le dépôt d'étude)
Le token est lu depuis l'URL du remote (jamais écrit dans un fichier).
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = "steve-dev-55/laya-football-evaluation"
TAG = "v0.2.0-real-integration"
NOTES = Path("docs/release_notes_v0.2.0.md")


def git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def main() -> int:
    token = git("remote", "get-url", "origin").split("steve-dev-55:")[1].split("@")[0]
    head = git("rev-parse", "HEAD")

    # 1) tag annoté
    tags = git("tag", "-l", TAG)
    if not tags:
        git("tag", "-a", TAG, "-m",
            "SDK Laya réel intégré — checkpoint épinglé, écarts A3, pilot réel")
        git("push", "origin", TAG)
        print(f"tag {TAG} poussé")

    # 2) release
    notes = NOTES.read_text(encoding="utf-8")
    body = {
        "tag_name": TAG,
        "target_commitish": head,
        "name": "v0.2.0-real-integration — SDK Laya réel intégré (checkpoint épinglé)",
        "body": notes,
        "make_latest": "true",
    }
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            rel = json.loads(resp.read())
        print(f"release créée: id={rel['id']} html_url={rel['html_url']}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        print(f"ÉCHEC {e.code}: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
