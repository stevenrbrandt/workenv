#!/usr/bin/env bash
# Build Python into an arch-specific prefix under workenv (no root required).
# Fixes missing _ctypes by ensuring libffi is available (system or built into prefix).
#
# Usage:
#   mk-python.sh              # install PY_VER (default 3.13.14) if needed
#   mk-python.sh --force      # rebuild even if smoke tests pass
#   PY_VER=3.13.14 mk-python.sh
#   PYTHON_OPTIMIZE=0 mk-python.sh   # skip PGO (much faster)
#
# Installs to: $WORKENV_ROOT/$(uname -m)   e.g. ~/workenv/x86_64

set -euo pipefail

PY_VER="${PY_VER:-3.13.14}"
PY_MM="${PY_VER%.*}"          # 3.13
FORCE=0
PYTHON_OPTIMIZE="${PYTHON_OPTIMIZE:-1}"
LIBFFI_VER="${LIBFFI_VER:-3.4.6}"
BUILD_ROOT="${BUILD_ROOT:-/tmp/workenv-python-build-$$}"
NPROC="${NPROC:-$(nproc 2>/dev/null || echo 2)}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKENV_ROOT="${WORKENV_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
ARCH="$(uname -m)"
PREFIX="${PREFIX:-$WORKENV_ROOT/$ARCH}"

for arg in "$@"; do
  case "$arg" in
    --force|-f) FORCE=1 ;;
    --help|-h)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

log()  { printf '+ %s\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

need_cmds() {
  local c
  for c in "$@"; do
    have "$c" || die "required command not found: $c"
  done
}

download() {
  local url="$1" out="$2"
  if have wget; then
    wget -q --show-progress -O "$out" "$url" || return 1
  elif have curl; then
    curl -fL --progress-bar -o "$out" "$url" || return 1
  else
    die "need wget or curl to download $url"
  fi
  [[ -s "$out" ]] || return 1
}

# --- Already good? ---
python_smoke() {
  local py="$1"
  [[ -x "$py" ]] || return 1
  local got
  got="$("$py" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null)" || return 1
  [[ "$got" == "$PY_VER" ]] || return 1
  "$py" -c 'import _ctypes' 2>/dev/null || return 1
  return 0
}

TARGET_PY="$PREFIX/bin/python${PY_MM}"

if [[ "$FORCE" -eq 0 ]] && python_smoke "$TARGET_PY"; then
  log "Python $PY_VER already OK at $TARGET_PY (including _ctypes)"
  # Keep convenience symlinks inside the arch prefix
  ln -sfn "python${PY_MM}" "$PREFIX/bin/python"
  ln -sfn "python${PY_MM}" "$PREFIX/bin/python3"
  if [[ -x "$PREFIX/bin/pip${PY_MM}" ]]; then
    ln -sfn "pip${PY_MM}" "$PREFIX/bin/pip"
    ln -sfn "pip${PY_MM}" "$PREFIX/bin/pip3"
  fi
  exit 0
fi

need_cmds cc make tar
have wget || have curl || die "need wget or curl"

mkdir -p "$PREFIX" "$BUILD_ROOT"
cleanup() { rm -rf "$BUILD_ROOT"; }
trap cleanup EXIT

export PATH="$PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="$PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig:$PREFIX/lib64/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export CPPFLAGS="-I$PREFIX/include ${CPPFLAGS:-}"
export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 ${LDFLAGS:-}"

# --- libffi (required for _ctypes) ---
ffi_usable() {
  if have pkg-config && pkg-config --exists libffi; then
    return 0
  fi
  # Compiler can see ffi.h and link -lffi (system multiarch paths)
  cat >"$BUILD_ROOT/ffi_probe.c" <<'EOF'
#include <ffi.h>
int main(void) {
  ffi_cif cif;
  (void)cif;
  return 0;
}
EOF
  cc $CPPFLAGS $LDFLAGS "$BUILD_ROOT/ffi_probe.c" -lffi -o "$BUILD_ROOT/ffi_probe" 2>/dev/null
}

ensure_libffi() {
  if ffi_usable; then
    log "libffi available (system or prefix)"
    if have pkg-config && pkg-config --exists libffi; then
      log "  pkg-config libffi: $(pkg-config --modversion libffi)"
      # Merge system cflags/libs so Python configure finds multiarch headers
      local cflags libs
      cflags="$(pkg-config --cflags libffi 2>/dev/null || true)"
      libs="$(pkg-config --libs libffi 2>/dev/null || true)"
      export CPPFLAGS="$cflags $CPPFLAGS"
      export LDFLAGS="$libs $LDFLAGS"
    fi
    return 0
  fi

  log "libffi not found; building libffi $LIBFFI_VER into $PREFIX (no root)"
  local tarball="libffi-${LIBFFI_VER}.tar.gz"
  local url="https://github.com/libffi/libffi/releases/download/v${LIBFFI_VER}/${tarball}"
  cd "$BUILD_ROOT"
  download "$url" "$tarball" || die "failed to download $url"
  tar -xzf "$tarball"
  cd "libffi-${LIBFFI_VER}"
  ./configure --prefix="$PREFIX" --disable-docs
  make -j"$NPROC"
  make install
  export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig:$PREFIX/lib64/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
  export CPPFLAGS="-I$PREFIX/include $CPPFLAGS"
  export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 $LDFLAGS"
  ffi_usable || die "libffi still not usable after local build"
  log "libffi installed to $PREFIX"
}

ensure_libffi

# Helpful optional deps (warn only — do not fail the build)
warn_missing_headers() {
  local name="$1" header="$2"
  cat >"$BUILD_ROOT/hdr_probe.c" <<EOF
#include <$header>
int main(void){return 0;}
EOF
  if ! cc $CPPFLAGS -c "$BUILD_ROOT/hdr_probe.c" -o "$BUILD_ROOT/hdr_probe.o" 2>/dev/null; then
    log "WARNING: $name headers not found ($header) — related Python modules may be omitted"
  fi
}
warn_missing_headers "OpenSSL" "openssl/ssl.h"
warn_missing_headers "zlib" "zlib.h"
warn_missing_headers "SQLite3" "sqlite3.h"
warn_missing_headers "readline" "readline/readline.h"
warn_missing_headers "bzip2" "bzlib.h"
warn_missing_headers "xz/lzma" "lzma.h"

# --- Python source ---
TARBALL="Python-${PY_VER}.tar.xz"
URL="https://www.python.org/ftp/python/${PY_VER}/${TARBALL}"
log "Downloading Python ${PY_VER}"
cd "$BUILD_ROOT"
download "$URL" "$TARBALL" || die "failed to download $URL — check PY_VER=$PY_VER"
tar -xf "$TARBALL"
cd "Python-${PY_VER}"

CONFIG_ARGS=(
  --prefix="$PREFIX"
  --enable-shared
  --with-ensurepip=install
  --with-system-ffi
)

if [[ "$PYTHON_OPTIMIZE" == "1" ]]; then
  CONFIG_ARGS+=(--enable-optimizations)
  log "Configuring with --enable-optimizations (slow; set PYTHON_OPTIMIZE=0 to skip)"
else
  log "Configuring without PGO optimizations"
fi

log "configure --prefix=$PREFIX ..."
./configure "${CONFIG_ARGS[@]}" \
  CPPFLAGS="$CPPFLAGS" \
  LDFLAGS="$LDFLAGS"

log "Building (make -j$NPROC) ..."
make -j"$NPROC"

log "Installing (make altinstall) ..."
make altinstall

# Symlinks inside arch prefix only (portable scripts stay in $WORKENV_ROOT/bin)
ln -sfn "python${PY_MM}" "$PREFIX/bin/python"
ln -sfn "python${PY_MM}" "$PREFIX/bin/python3"
if [[ -x "$PREFIX/bin/pip${PY_MM}" ]]; then
  ln -sfn "pip${PY_MM}" "$PREFIX/bin/pip"
  ln -sfn "pip${PY_MM}" "$PREFIX/bin/pip3"
fi

# --- Verify _ctypes ---
if ! "$TARGET_PY" -c 'import _ctypes; print("_ctypes OK:", _ctypes.__file__)'; then
  die "Python installed but _ctypes still missing. Check libffi / config.log in $BUILD_ROOT"
fi

# Report other modules
"$TARGET_PY" - <<'PY'
import importlib
mods = ["ssl", "zlib", "sqlite3", "readline", "bz2", "lzma", "hashlib"]
for m in mods:
    try:
        importlib.import_module(m)
        print(f"  OK   {m}")
    except Exception as e:
        print(f"  MISS {m}: {e}")
PY

log "SUCCESS: Python $PY_VER -> $PREFIX"
log "  $TARGET_PY"
log "  Add to PATH via install.sh / ~/.bashaux (arch prefix: $ARCH)"
