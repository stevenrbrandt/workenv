#!/usr/bin/env bash
# Bootstrap workenv: arch-specific Python (with _ctypes), optional Vim/clangd,
# then run install.py for shell/vim/git/ssh config.
#
# Usage:
#   ./install.sh
#   ./install.sh --force-python
#   ./install.sh --skip-vim
#   ./install.sh --skip-python
#   PY_VER=3.13.14 PYTHON_OPTIMIZE=0 ./install.sh
#
# Layout:
#   $WORKENV_ROOT/bin              portable scripts (this repo)
#   $WORKENV_ROOT/py               portable Python modules
#   $WORKENV_ROOT/$(uname -m)/     arch-specific toolchain (python, vim, clangd, libs)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WORKENV_ROOT="$ROOT"
ARCH="$(uname -m)"
export PREFIX="${PREFIX:-$ROOT/$ARCH}"

FORCE_PYTHON=0
SKIP_PYTHON=0
SKIP_VIM=0
SKIP_DOTFILES=0

for arg in "$@"; do
  case "$arg" in
    --force-python) FORCE_PYTHON=1 ;;
    --skip-python)  SKIP_PYTHON=1 ;;
    --skip-vim)     SKIP_VIM=1 ;;
    --skip-dotfiles) SKIP_DOTFILES=1 ;;
    --help|-h)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

log() { printf '==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

chmod +x "$ROOT/bin/mk-python.sh" "$ROOT/bin/mk-vim.sh" 2>/dev/null || true

# --- Python ---
if [[ "$SKIP_PYTHON" -eq 0 ]]; then
  log "Ensuring Python (arch=$ARCH, prefix=$PREFIX)"
  MK_PY_ARGS=()
  [[ "$FORCE_PYTHON" -eq 1 ]] && MK_PY_ARGS+=(--force)
  # Prefer a faster first build on slow filesystems unless user opts in
  : "${PYTHON_OPTIMIZE:=0}"
  export PYTHON_OPTIMIZE
  "$ROOT/bin/mk-python.sh" "${MK_PY_ARGS[@]+"${MK_PY_ARGS[@]}"}"
else
  log "Skipping Python (--skip-python)"
fi

# Prefer arch python for the rest of the install
if [[ -x "$PREFIX/bin/python3.13" ]]; then
  PY="$PREFIX/bin/python3.13"
elif [[ -x "$PREFIX/bin/python3" ]]; then
  PY="$PREFIX/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
  log "WARNING: using system $PY (arch Python not found at $PREFIX)"
else
  die "no python3 available; re-run without --skip-python"
fi

# Arch bin before portable scripts (avoid shadowing by legacy bin/python)
export PATH="$PREFIX/bin:$ROOT/bin:$PATH"
export LD_LIBRARY_PATH="$PREFIX/lib:${PREFIX}/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# Quick health report
if "$PY" -c 'import _ctypes' 2>/dev/null; then
  log "Python OK: $("$PY" -c 'import sys; print(sys.version.split()[0])') ($PY) + _ctypes"
else
  log "WARNING: $PY cannot import _ctypes"
fi

# --- Vim / clangd ---
if [[ "$SKIP_VIM" -eq 0 ]]; then
  log "Ensuring Vim + clangd helpers"
  "$ROOT/bin/mk-vim.sh" || log "WARNING: mk-vim.sh had errors (continuing)"
else
  log "Skipping Vim (--skip-vim)"
fi

# --- Dotfiles / packages / keys ---
if [[ "$SKIP_DOTFILES" -eq 0 ]]; then
  log "Running install.py with $PY"
  cd "$ROOT"
  "$PY" "$ROOT/install.py"
else
  log "Skipping install.py (--skip-dotfiles)"
fi

log "Done."
log "  Open a new shell, or:  source ~/.bashaux"
log "  Python: $PREFIX/bin/python3.13"
log "  Scripts: $ROOT/bin"
if [[ -x "$PREFIX/bin/vim" ]]; then
  log "  Vim: $PREFIX/bin/vim  (run :PlugInstall once inside vim)"
fi
