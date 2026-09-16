#!/usr/bin/env bash
# Install Claude Code into the workenv platform prefix (not ~/.local).
#
# Usage:
#   claude-install.sh              # latest stable
#   claude-install.sh 2.1.267      # specific version
#
# The official native installer always lands in ~/.local/{bin,share/claude}.
# Copy the binary into $WORKENV_PREFIX so it is on PATH via ~/.bashaux
# (workenv does not put ~/.local/bin on PATH).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKENV_ROOT="${WORKENV_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
# shellcheck source=workenv-platform.sh
. "$SCRIPT_DIR/workenv-platform.sh"
PREFIX="${PREFIX:-$WORKENV_ROOT/$WORKENV_PLATFORM}"
mkdir -p "$PREFIX/bin" "$PREFIX/share/claude/versions"

export PATH="$PREFIX/bin:$PATH"

curl -fsSL https://claude.ai/install.sh | bash -s -- "$@"

src=""
if [ -e "$HOME/.local/bin/claude" ]; then
  src="$(readlink -f "$HOME/.local/bin/claude")"
fi
if [ -z "$src" ] || [ ! -x "$src" ]; then
  echo "ERROR: claude installer did not produce ~/.local/bin/claude" >&2
  exit 1
fi

ver="$(basename "$src")"
# Version names are like "2.1.267"; fall back if the installer used another layout.
if [ -z "$ver" ] || [ "$ver" = "claude" ]; then
  ver="$("$src" --version 2>/dev/null | awk '{print $NF; exit}')"
  ver="${ver:-current}"
fi

cp -f "$src" "$PREFIX/share/claude/versions/$ver"
chmod +x "$PREFIX/share/claude/versions/$ver"
ln -sfn "$PREFIX/share/claude/versions/$ver" "$PREFIX/bin/claude"

# Prefer the prefix launcher; leave ~/.local/share/claude for `claude update`.
rm -f "$HOME/.local/bin/claude"

echo "Claude installed to $PREFIX/bin/claude ($ver)"
