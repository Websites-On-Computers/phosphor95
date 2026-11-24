#!/usr/bin/env bash
# Fetch pinned third-party sources into .upstream/ (never executed, only read).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UP="$ROOT/.upstream"; mkdir -p "$UP"
fetch() { # name url commit
  local name=$1 url=$2 commit=$3 dir="$UP/$1"
  if [[ -d "$dir/.git" ]] && [[ "$(git -C "$dir" rev-parse HEAD)" == "$commit" ]]; then
    echo "  $name: up to date ($commit)"; return; fi
  rm -rf "$dir"; git init -q "$dir"
  git -C "$dir" fetch -q --depth 1 "$url" "$commit"
  git -C "$dir" -c advice.detachedHead=false checkout -q FETCH_HEAD
  echo "  $name: fetched $commit"
}
fetch w95       https://github.com/B00merang-Project/Windows-95.git 055abd7a3608afdcb2ef021732e07020f2b416b2
fetch chicago95 https://github.com/grassmunk/Chicago95.git          5da19b8b1e2a886ebf6628403023d5fac3acc3ee
