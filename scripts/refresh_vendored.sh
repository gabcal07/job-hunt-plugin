#!/usr/bin/env bash
# Refresh the vendored watermarks-remover copy and the skills derived from it
# (remove-ai-marks, clean-user-facing-text, humanizer).
# Usage: scripts/refresh_vendored.sh [COMMIT]   (default: the commit pinned in SOURCE.md)
set -euo pipefail

PLUGIN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$PLUGIN/vendor/watermarks-remover"
WM_URL="https://github.com/guillaumemeyer/watermarks-remover"
HUM_URL="https://github.com/blader/humanizer"

old="$(grep -oE 'commit [0-9a-f]{7,40}' "$VENDOR/SOURCE.md" | head -1 | cut -d' ' -f2)"
commit="${1:-$old}"
[ -n "$commit" ] || { echo "no commit given and none found in $VENDOR/SOURCE.md" >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "== watermarks-remover @ $commit"
git clone --quiet "$WM_URL" "$tmp/wm"
git -C "$tmp/wm" checkout --quiet "$commit"
new="$(git -C "$tmp/wm" rev-parse --short=7 HEAD)"

# rsync --delete drops files removed upstream; our own SOURCE.md and LICENSE files are excluded
mkdir -p "$VENDOR/service" "$VENDOR/config"
rsync -a --delete "$tmp/wm/service/" "$VENDOR/service/"
rsync -a --delete "$tmp/wm/config/" "$VENDOR/config/"
cp "$tmp/wm/LICENSE" "$VENDOR/LICENSE"

for s in remove-ai-marks clean-user-facing-text; do
  mkdir -p "$PLUGIN/skills/$s"
  rsync -a --delete --exclude LICENSE --exclude SOURCE.md "$tmp/wm/skills/$s/" "$PLUGIN/skills/$s/"
done

echo "== humanizer (shallow)"
git clone --quiet --depth 1 "$HUM_URL" "$tmp/hum"
hum="$(git -C "$tmp/hum" rev-parse --short=7 HEAD)"
mkdir -p "$PLUGIN/skills/humanizer"
cp "$tmp/hum/SKILL.md" "$tmp/hum/LICENSE" "$PLUGIN/skills/humanizer/"

# pin the new commit: every occurrence of the old sha (tree/<sha>/ URLs and "commit <sha>") and the copy date
today="$(date +%F)"
for f in "$VENDOR/SOURCE.md" "$PLUGIN/skills/remove-ai-marks/SOURCE.md" "$PLUGIN/skills/clean-user-facing-text/SOURCE.md"; do
  [ -f "$f" ] || continue
  sed -i.bak -E "s/$old/$new/g; s/Copied unmodified [0-9-]+/Copied unmodified $today/" "$f"
  rm -f "$f.bak"
done
# humanizer has no sha yet: drop any old ' at commit X' and append the new one
f="$PLUGIN/skills/humanizer/SOURCE.md"
if [ -f "$f" ]; then
  sed -i.bak -E "s/ at commit [0-9a-f]+//; s/Copied unmodified [0-9-]+\./Copied unmodified $today at commit $hum./" "$f"
  rm -f "$f.bak"
fi

find "$PLUGIN" -name __pycache__ -type d -prune -exec rm -rf {} +

echo "== done: watermarks-remover $old -> $new, humanizer $hum"
if git -C "$PLUGIN" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$PLUGIN" diff --stat -- vendor skills
else
  echo "(plugin is not a git repo: no diff stat available)"
fi
