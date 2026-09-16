#!/usr/bin/env bash
# Install Grok CLI into the workenv platform prefix (not ~/.local or ~/.grok/bin).
#
# Usage:
#   grok-install.sh              # latest stable
#   grok-install.sh 1.0.30       # specific version
#
# The official installer honors GROK_BIN_DIR but still writes a
# `PATH=$HOME/.grok/bin` block into ~/.bashrc and may symlink into
# ~/.local/bin. This wrapper puts the binary in $WORKENV_PREFIX/bin
# (already on PATH via ~/.bashaux) and strips that bashrc block.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKENV_ROOT="${WORKENV_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
# shellcheck source=workenv-platform.sh
. "$SCRIPT_DIR/workenv-platform.sh"
PREFIX="${PREFIX:-$WORKENV_ROOT/$WORKENV_PLATFORM}"
mkdir -p "$PREFIX/bin"

# Official installer skips the ~/.local/bin symlink when BIN_DIR is on PATH.
export PATH="$PREFIX/bin:$PATH"
export GROK_BIN_DIR="$PREFIX/bin"

curl -fsSL https://x.ai/cli/install.sh | bash -s -- "$@"

# Official installer hardcodes PATH="$HOME/.grok/bin" into the shell rc
# even when GROK_BIN_DIR is set. workenv PATH already includes $PREFIX/bin.
strip_grok_bashrc_block() {
  local rc="$1"
  [ -f "$rc" ] || return 0
  grep -qs "grok installer" "$rc" || return 0
  local tmp="$rc.tmp.$$"
  awk '
    /# >>> grok installer >>>/ { skip=1; next }
    /# <<< grok installer <<</ { skip=0; next }
    !skip { print }
  ' "$rc" > "$tmp" && mv "$tmp" "$rc"
}

strip_grok_bashrc_block "$HOME/.bashrc"
strip_grok_bashrc_block "$HOME/.bash_profile"

# Drop the fallback ~/.local/bin shims; PREFIX/bin is the real install.
if [ -L "$HOME/.local/bin/grok" ]; then
  rm -f "$HOME/.local/bin/grok"
fi
if [ -L "$HOME/.local/bin/agent" ]; then
  rm -f "$HOME/.local/bin/agent"
fi

if [ -x "$PREFIX/bin/grok" ]; then
  echo "Grok installed to $PREFIX/bin/grok ($("$PREFIX/bin/grok" --version 2>/dev/null || echo ok))"
else
  echo "ERROR: grok missing after install at $PREFIX/bin/grok" >&2
  exit 1
fi
