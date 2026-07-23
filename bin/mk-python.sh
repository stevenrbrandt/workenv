#!/usr/bin/env bash
# Build Python into a platform-specific prefix under workenv (no root required).
# Ensures libffi (_ctypes), OpenSSL (ssl / pip HTTPS), and liblzma (_lzma) —
# system or built into prefix.
#
# Usage:
#   mk-python.sh              # install PY_VER (default 3.13.14) if needed
#   mk-python.sh --force      # rebuild even if smoke tests pass
#   PY_VER=3.13.14 mk-python.sh
#   PYTHON_OPTIMIZE=0 mk-python.sh   # skip PGO (much faster)
#   OPENSSL_BUNDLE=1 mk-python.sh    # always build OpenSSL into prefix (portable)
#
# Installs to: $WORKENV_ROOT/$WORKENV_PLATFORM
#   e.g. ~/workenv/x86_64-glibc-2.35  (arch + libc; see workenv-platform.sh)

set -euo pipefail

PY_VER="${PY_VER:-3.13.14}"
PY_MM="${PY_VER%.*}"          # 3.13
FORCE=0
PYTHON_OPTIMIZE="${PYTHON_OPTIMIZE:-1}"
LIBFFI_VER="${LIBFFI_VER:-3.4.6}"
# OpenSSL 3.0 LTS — good default for Python 3.11+ and cluster portability
OPENSSL_VER="${OPENSSL_VER:-3.0.15}"
# 1 = always build OpenSSL into PREFIX (recommended for apptainer/home-on-cluster)
OPENSSL_BUNDLE="${OPENSSL_BUNDLE:-0}"
# liblzma / xz (Python _lzma module — required by nrpy and many scientific packages)
XZ_VER="${XZ_VER:-5.6.3}"
BUILD_ROOT="${BUILD_ROOT:-/tmp/workenv-python-build-$$}"
NPROC="${NPROC:-$(nproc 2>/dev/null || echo 2)}"
# Set by ensure_openssl: directory passed to Python --with-openssl=
OPENSSL_DIR=""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKENV_ROOT="${WORKENV_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
# shellcheck source=workenv-platform.sh
. "$SCRIPT_DIR/workenv-platform.sh"
PREFIX="${PREFIX:-$WORKENV_ROOT/$WORKENV_PLATFORM}"

for arg in "$@"; do
  case "$arg" in
    --force|-f) FORCE=1 ;;
    --help|-h)
      sed -n '2,14p' "$0"
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

# Locate a usable CA bundle (clusters often point curl at a missing path → error 77).
find_ca_bundle() {
  local c
  for c in \
    "${SSL_CERT_FILE:-}" \
    "${CURL_CA_BUNDLE:-}" \
    "${REQUESTS_CA_BUNDLE:-}" \
    /etc/ssl/certs/ca-certificates.crt \
    /etc/pki/tls/certs/ca-bundle.crt \
    /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem \
    /etc/ssl/cert.pem \
    /usr/lib/ssl/cert.pem \
    /etc/ssl/ca-bundle.pem \
    /etc/pki/tls/cert.pem
  do
    if [[ -n "$c" && -r "$c" && -s "$c" ]]; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  return 1
}

# Download url → out. Retries with an explicit CA, then insecure (bootstrap).
download() {
  local url="$1" out="$2"
  local ca=""
  have wget || have curl || die "need wget or curl to download $url"

  ca="$(find_ca_bundle || true)"
  if [[ -n "$ca" ]]; then
    export SSL_CERT_FILE="$ca"
    export CURL_CA_BUNDLE="$ca"
    export REQUESTS_CA_BUNDLE="$ca"
  fi

  _download_once() {
    # $1 = verify|insecure
    local mode="$1"
    rm -f "$out"
    if have curl; then
      local -a cargs=(-fL --progress-bar -o "$out" --connect-timeout 30 --retry 2)
      if [[ "$mode" == insecure ]]; then
        cargs+=(-k)
      elif [[ -n "$ca" ]]; then
        cargs+=(--cacert "$ca")
      fi
      if curl "${cargs[@]}" "$url" && [[ -s "$out" ]]; then
        return 0
      fi
    fi
    if have wget; then
      local -a wargs=(-q --show-progress -O "$out" --timeout=30 --tries=2)
      if [[ "$mode" == insecure ]]; then
        wargs+=(--no-check-certificate)
      elif [[ -n "$ca" ]]; then
        wargs+=(--ca-certificate="$ca")
      fi
      if wget "${wargs[@]}" "$url" && [[ -s "$out" ]]; then
        return 0
      fi
    fi
    return 1
  }

  if _download_once verify; then
    return 0
  fi

  # Chicken-and-egg: broken CA config is common on HPC nodes; we need the
  # tarball to build OpenSSL / Python that will verify TLS correctly later.
  log "WARNING: TLS verify failed for $url"
  if [[ -n "$ca" ]]; then
    log "  (tried CA bundle: $ca)"
  else
    log "  (no CA bundle found under /etc/ssl or /etc/pki)"
  fi
  log "  retrying without certificate verification (bootstrap only)"
  if _download_once insecure; then
    return 0
  fi
  return 1
}

# --- Already good? ---
python_smoke() {
  local py="$1"
  [[ -x "$py" ]] || return 1
  local got
  got="$("$py" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null)" || return 1
  [[ "$got" == "$PY_VER" ]] || return 1
  # _ctypes, ssl, lzma — needed for pip, HTTPS, and packages like nrpy
  "$py" -c 'import _ctypes, ssl, lzma; assert ssl.OPENSSL_VERSION' 2>/dev/null || return 1
  return 0
}

TARGET_PY="$PREFIX/bin/python${PY_MM}"

if [[ "$FORCE" -eq 0 ]] && python_smoke "$TARGET_PY"; then
  log "Python $PY_VER already OK at $TARGET_PY (including _ctypes + ssl + lzma)"
  log "  ssl: $("$TARGET_PY" -c 'import ssl; print(ssl.OPENSSL_VERSION)')"
  # Keep convenience symlinks inside the platform prefix
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

# --- OpenSSL (required for ssl module / pip HTTPS, e.g. inside apptainer) ---
openssl_usable() {
  # Prefer a prefix we already installed into
  if [[ -r "$PREFIX/include/openssl/ssl.h" ]] && \
     { [[ -e "$PREFIX/lib/libssl.so" ]] || [[ -e "$PREFIX/lib64/libssl.so" ]] || \
       ls "$PREFIX"/lib/libssl.so* >/dev/null 2>&1 || ls "$PREFIX"/lib64/libssl.so* >/dev/null 2>&1; }; then
    return 0
  fi
  if have pkg-config && pkg-config --exists openssl; then
    return 0
  fi
  cat >"$BUILD_ROOT/ssl_probe.c" <<'EOF'
#include <openssl/ssl.h>
#include <openssl/opensslv.h>
int main(void) {
  return (OPENSSL_VERSION_NUMBER > 0) ? 0 : 1;
}
EOF
  # shellcheck disable=SC2086
  cc $CPPFLAGS $LDFLAGS "$BUILD_ROOT/ssl_probe.c" -lssl -lcrypto -o "$BUILD_ROOT/ssl_probe" 2>/dev/null
}

build_openssl_into_prefix() {
  log "Building OpenSSL $OPENSSL_VER into $PREFIX (no root; portable for apptainer)"
  need_cmds perl
  local tarball="openssl-${OPENSSL_VER}.tar.gz"
  # github mirror is reliable; official source is also fine
  local url="https://github.com/openssl/openssl/releases/download/openssl-${OPENSSL_VER}/${tarball}"
  local url_alt="https://www.openssl.org/source/${tarball}"
  cd "$BUILD_ROOT"
  if ! download "$url" "$tarball"; then
    log "primary OpenSSL URL failed; trying openssl.org"
    download "$url_alt" "$tarball" || die "failed to download OpenSSL $OPENSSL_VER"
  fi
  tar -xzf "$tarball"
  cd "openssl-${OPENSSL_VER}"
  # shared libs; rpath so _ssl finds them when only $PREFIX is visible (apptainer)
  local cfg=(--prefix="$PREFIX" --openssldir="$PREFIX/ssl" shared)
  cat >"$BUILD_ROOT/zlib_probe.c" <<'ZEOF'
#include <zlib.h>
int main(void){return 0;}
ZEOF
  # shellcheck disable=SC2086
  if cc $CPPFLAGS -c "$BUILD_ROOT/zlib_probe.c" -o "$BUILD_ROOT/zlib_probe.o" 2>/dev/null; then
    cfg+=(zlib)
  fi
  ./Configure "${cfg[@]}" \
    "-Wl,-rpath,$PREFIX/lib" "-Wl,-rpath,$PREFIX/lib64"
  make -j"$NPROC"
  # libs + headers only (skip man pages)
  make install_sw
  export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig:$PREFIX/lib64/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
  export CPPFLAGS="-I$PREFIX/include $CPPFLAGS"
  export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 $LDFLAGS"
  openssl_usable || die "OpenSSL still not usable after local build"
  log "OpenSSL installed to $PREFIX"
}

ensure_openssl() {
  OPENSSL_DIR=""

  if [[ "$OPENSSL_BUNDLE" == "1" ]]; then
    log "OPENSSL_BUNDLE=1 — building OpenSSL into prefix even if system has it"
    build_openssl_into_prefix
    OPENSSL_DIR="$PREFIX"
    return 0
  fi

  if openssl_usable; then
    if [[ -r "$PREFIX/include/openssl/ssl.h" ]]; then
      log "OpenSSL available in prefix $PREFIX"
      OPENSSL_DIR="$PREFIX"
    elif have pkg-config && pkg-config --exists openssl; then
      log "OpenSSL available (system): $(pkg-config --modversion openssl)"
      local cflags libs pref
      cflags="$(pkg-config --cflags openssl 2>/dev/null || true)"
      libs="$(pkg-config --libs openssl 2>/dev/null || true)"
      pref="$(pkg-config --variable=prefix openssl 2>/dev/null || true)"
      export CPPFLAGS="$cflags $CPPFLAGS"
      export LDFLAGS="$libs $LDFLAGS"
      # Python --with-openssl wants a root that contains include/ and lib/
      if [[ -n "$pref" && -r "$pref/include/openssl/ssl.h" ]]; then
        OPENSSL_DIR="$pref"
      else
        OPENSSL_DIR="/usr"
      fi
    else
      log "OpenSSL available via compiler default paths"
      OPENSSL_DIR="/usr"
    fi
    return 0
  fi

  build_openssl_into_prefix
  OPENSSL_DIR="$PREFIX"
}

ensure_openssl
[[ -n "$OPENSSL_DIR" ]] || die "OPENSSL_DIR unset after ensure_openssl"

# --- liblzma / xz (required for Python _lzma — used by nrpy, etc.) ---
lzma_usable() {
  if [[ -r "$PREFIX/include/lzma.h" ]] && \
     { [[ -e "$PREFIX/lib/liblzma.so" ]] || [[ -e "$PREFIX/lib64/liblzma.so" ]] || \
       ls "$PREFIX"/lib/liblzma.so* >/dev/null 2>&1 || ls "$PREFIX"/lib64/liblzma.so* >/dev/null 2>&1; }; then
    return 0
  fi
  if have pkg-config && pkg-config --exists liblzma; then
    return 0
  fi
  cat >"$BUILD_ROOT/lzma_probe.c" <<'EOF'
#include <lzma.h>
int main(void) {
  return (LZMA_VERSION > 0) ? 0 : 1;
}
EOF
  # shellcheck disable=SC2086
  cc $CPPFLAGS $LDFLAGS "$BUILD_ROOT/lzma_probe.c" -llzma -o "$BUILD_ROOT/lzma_probe" 2>/dev/null
}

ensure_liblzma() {
  if lzma_usable; then
    log "liblzma available (system or prefix)"
    if have pkg-config && pkg-config --exists liblzma; then
      log "  pkg-config liblzma: $(pkg-config --modversion liblzma)"
      local cflags libs
      cflags="$(pkg-config --cflags liblzma 2>/dev/null || true)"
      libs="$(pkg-config --libs liblzma 2>/dev/null || true)"
      export CPPFLAGS="$cflags $CPPFLAGS"
      export LDFLAGS="$libs $LDFLAGS"
    elif [[ -r "$PREFIX/include/lzma.h" ]]; then
      export CPPFLAGS="-I$PREFIX/include $CPPFLAGS"
      export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 $LDFLAGS"
    fi
    return 0
  fi

  log "liblzma not found; building xz $XZ_VER into $PREFIX (no root)"
  local tarball="xz-${XZ_VER}.tar.gz"
  local url="https://github.com/tukaani-project/xz/releases/download/v${XZ_VER}/${tarball}"
  local url_alt="https://github.com/tukaani-project/xz/releases/download/v${XZ_VER}/xz-${XZ_VER}.tar.xz"
  cd "$BUILD_ROOT"
  if ! download "$url" "$tarball"; then
    log "primary xz URL failed; trying .tar.xz release asset name"
    tarball="xz-${XZ_VER}.tar.xz"
    download "$url_alt" "$tarball" || die "failed to download xz $XZ_VER"
  fi
  tar -xf "$tarball"
  cd "xz-${XZ_VER}"
  # Libraries only (headers + liblzma); skip CLI tools / docs
  ./configure --prefix="$PREFIX" --disable-doc --disable-scripts \
    --disable-xzdec --disable-lzmadec --disable-lzmainfo --disable-lzma-links \
    --enable-shared
  make -j"$NPROC"
  make install
  export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig:$PREFIX/lib64/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
  export CPPFLAGS="-I$PREFIX/include $CPPFLAGS"
  export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 $LDFLAGS"
  lzma_usable || die "liblzma still not usable after local build"
  log "liblzma installed to $PREFIX"
}

ensure_liblzma

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
warn_missing_headers "zlib" "zlib.h"
warn_missing_headers "SQLite3" "sqlite3.h"
warn_missing_headers "readline" "readline/readline.h"
warn_missing_headers "bzip2" "bzlib.h"

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
  --with-openssl="$OPENSSL_DIR"
  # Embed rpath so _ssl finds libssl inside apptainer when only $PREFIX is bound
  --with-openssl-rpath=auto
)

if [[ "$PYTHON_OPTIMIZE" == "1" ]]; then
  CONFIG_ARGS+=(--enable-optimizations)
  log "Configuring with --enable-optimizations (slow; set PYTHON_OPTIMIZE=0 to skip)"
else
  log "Configuring without PGO optimizations"
fi

log "configure --prefix=$PREFIX --with-openssl=$OPENSSL_DIR ..."
./configure "${CONFIG_ARGS[@]}" \
  CPPFLAGS="$CPPFLAGS" \
  LDFLAGS="$LDFLAGS"

log "Building (make -j$NPROC) ..."
make -j"$NPROC"

log "Installing (make altinstall) ..."
make altinstall

# Symlinks inside platform prefix only (portable scripts stay in $WORKENV_ROOT/bin)
ln -sfn "python${PY_MM}" "$PREFIX/bin/python"
ln -sfn "python${PY_MM}" "$PREFIX/bin/python3"
if [[ -x "$PREFIX/bin/pip${PY_MM}" ]]; then
  ln -sfn "pip${PY_MM}" "$PREFIX/bin/pip"
  ln -sfn "pip${PY_MM}" "$PREFIX/bin/pip3"
fi

# --- Verify required modules ---
if ! "$TARGET_PY" -c 'import _ctypes; print("_ctypes OK:", _ctypes.__file__)'; then
  die "Python installed but _ctypes still missing. Check libffi / config.log in $BUILD_ROOT"
fi
if ! "$TARGET_PY" -c 'import ssl; print("ssl OK:", ssl.OPENSSL_VERSION, ssl.__file__)'; then
  die "Python installed but ssl still missing. Check OpenSSL / --with-openssl=$OPENSSL_DIR / config.log"
fi
if ! "$TARGET_PY" -c 'import lzma; print("lzma OK:", lzma.__file__)'; then
  die "Python installed but _lzma still missing. Check liblzma / xz headers and config.log in $BUILD_ROOT"
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
log "  OpenSSL: $("$TARGET_PY" -c 'import ssl; print(ssl.OPENSSL_VERSION)')"
log "  lzma: OK"
log "  Add to PATH via install.sh / ~/.bashaux (platform prefix: $WORKENV_PLATFORM)"
