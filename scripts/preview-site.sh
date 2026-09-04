#!/usr/bin/env sh
set -e
root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
src="$root/screenshots"
dst="$root/site/screenshots"

if [ ! -e "$dst" ]; then
  ln -s "$src" "$dst"
fi

echo "http://localhost:4173"
cd "$root/site"
npx --yes serve -p 4173 --no-clipboard
