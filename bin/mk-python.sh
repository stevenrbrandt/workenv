#!/usr/bin/env bash
# Build Python into a platform-specific prefix under workenv (no root required).
# Ensures libffi (_ctypes), OpenSSL (ssl), liblzma (_lzma), sqlite3 (_sqlite3),
# and libbz2 (_bz2) — system or built into prefix. These are stdlib C modules;
# pip cannot add them. Missing libbz2 also breaks `make altinstall` on 3.13.
#
# Usage:
#   mk-python.sh              # install PY_VER (default 3.13.14) if needed
#   mk-python.sh --force      # rebuild even if smoke tests pass
#   PY_VER=3.13.14 mk-python.sh
#   PYTHON_OPTIMIZE=0 mk-python.sh   # skip PGO (much faster)
#   OPENSSL_BUNDLE=1 mk-python.sh    # force OpenSSL into prefix (portable/apptainer)
#   Default: use system OpenSSL if present; only build into prefix when missing.
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
# bzip2 / libbz2 (Python _bz2). Without it, Python 3.13 make altinstall can fail:
#   install: cannot stat 'Modules/_bz2.cpython-…so': No such file or directory
BZIP2_VER="${BZIP2_VER:-1.0.8}"
# SQLite autoconf amalgamation year + version id (see https://www.sqlite.org/download.html)
# 3490100 = 3.49.1 — override with SQLITE_YEAR / SQLITE_VER if a URL 404s
SQLITE_YEAR="${SQLITE_YEAR:-2025}"
SQLITE_VER="${SQLITE_VER:-3490100}"
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

# Directory of hashed certs (Debian/Ubuntu style) usable with curl --capath.
find_ca_path() {
  local d
  for d in \
    "${SSL_CERT_DIR:-}" \
    /etc/ssl/certs \
    /etc/pki/tls/certs \
    /usr/lib/ssl/certs
  do
    if [[ -n "$d" && -d "$d" ]]; then
      printf '%s\n' "$d"
      return 0
    fi
  done
  return 1
}

# Drop env vars that point at missing CA files (common cluster misconfig → curl 77).
clear_broken_ca_env() {
  local v val
  for v in SSL_CERT_FILE CURL_CA_BUNDLE REQUESTS_CA_BUNDLE; do
    eval "val=\${$v-}"
    if [[ -n "$val" && ! -r "$val" ]]; then
      log "Unsetting $v=$val (not readable; causes curl error 77)"
      unset "$v"
    fi
  done
  if [[ -n "${SSL_CERT_DIR:-}" && ! -d "${SSL_CERT_DIR}" ]]; then
    unset SSL_CERT_DIR
  fi
}

# Run a command without PREFIX on LD_LIBRARY_PATH / PKG_CONFIG_PATH.
# System curl/wget are linked against distro OpenSSL; if an older bundled
# libssl.so is first on LD_LIBRARY_PATH, curl fails with e.g.
#   version `OPENSSL_3.2.0' not found (required by libcurl.so)
with_system_libs() {
  local cleaned_ld="" cleaned_pc="" p
  local -a envargs=()
  local IFS=':'
  for p in ${LD_LIBRARY_PATH-}; do
    [[ -z "$p" ]] && continue
    [[ "$p" == "$PREFIX/lib" || "$p" == "$PREFIX/lib64" ]] && continue
    cleaned_ld="${cleaned_ld:+$cleaned_ld:}$p"
  done
  for p in ${PKG_CONFIG_PATH-}; do
    [[ -z "$p" ]] && continue
    [[ "$p" == "$PREFIX/lib/pkgconfig" || "$p" == "$PREFIX/lib64/pkgconfig" ]] && continue
    cleaned_pc="${cleaned_pc:+$cleaned_pc:}$p"
  done
  if [[ -n "$cleaned_ld" ]]; then
    envargs+=(LD_LIBRARY_PATH="$cleaned_ld")
  else
    envargs+=(-u LD_LIBRARY_PATH)
  fi
  if [[ -n "$cleaned_pc" ]]; then
    envargs+=(PKG_CONFIG_PATH="$cleaned_pc")
  else
    envargs+=(-u PKG_CONFIG_PATH)
  fi
  env "${envargs[@]}" "$@"
}

# Cluster "module" trees (e.g. /usr/local/packages/python/3.7.6) often provide
# libffi/ssl/sqlite/bz2 via pkg-config. Linking against them succeeds, but
# Python's RUNSHARED LD_LIBRARY_PATH is only builddir+PREFIX — import checks
# then fail with "libbz2.so.1.0: cannot open shared object file" and the
# successfully-built _bz2.so is deleted. Only trust PREFIX + distro paths.
is_portable_prefix() {
  local p="${1%/}"
  case "$p" in
    "$PREFIX"|"$PREFIX"/*) return 0 ;;
    /usr/local/packages|/usr/local/packages/*) return 1 ;;
    /usr/local/Modules|/usr/local/Modules/*) return 1 ;;
    /opt/ohpc|/opt/ohpc/*) return 1 ;;
    /opt/intel|/opt/intel/*) return 1 ;;
    /usr|/usr/lib|/usr/lib64|/usr/lib/*|/usr/lib64/*|/usr/include|/usr/include/*) return 0 ;;
    /usr/local|/usr/local/lib|/usr/local/lib64|/usr/local/include) return 0 ;;
    /usr/local/lib/*|/usr/local/lib64/*|/usr/local/include/*)
      # Allow normal /usr/local installs; reject module-style trees above.
      return 0
      ;;
    /lib|/lib64|/lib/*|/lib64/*) return 0 ;;
    *) return 1 ;;
  esac
}

# PKG_CONFIG_PATH / LD_LIBRARY_PATH limited to PREFIX + distro locations.
portable_pkg_config_path() {
  local p out=""
  local IFS=':'
  for p in ${PKG_CONFIG_PATH-}; do
    [[ -z "$p" ]] && continue
    case "$p" in
      "$PREFIX"/*|/usr/lib/pkgconfig|/usr/lib64/pkgconfig|/usr/share/pkgconfig|/usr/local/lib/pkgconfig|/usr/local/lib64/pkgconfig|/usr/lib/*/pkgconfig)
        out="${out:+$out:}$p"
        ;;
    esac
  done
  # Always prefer PREFIX entries first
  printf '%s' "$PREFIX/lib/pkgconfig:$PREFIX/lib64/pkgconfig${out:+:$out}"
}

portable_ld_library_path() {
  printf '%s' "$PREFIX/lib:$PREFIX/lib64:/usr/lib64:/usr/lib:/lib64:/lib"
}

# Run a command as the Python build will see libs at extension-import time.
with_portable_libs() {
  env LD_LIBRARY_PATH="$(portable_ld_library_path)" \
      PKG_CONFIG_PATH="$(portable_pkg_config_path)" \
      "$@"
}

# True if pkg-config package resolves to a portable prefix.
pkg_config_portable() {
  local pc="$1"
  shift || true
  have pkg-config || return 1
  with_portable_libs pkg-config --exists "$pc" 2>/dev/null || return 1
  local pref
  pref="$(with_portable_libs pkg-config --variable=prefix "$pc" 2>/dev/null || true)"
  [[ -n "$pref" ]] || return 1
  is_portable_prefix "$pref" || return 1
  if (($#)); then
    with_portable_libs pkg-config "$@" "$pc"
  fi
  return 0
}

# Drop non-portable entries from the ambient PKG_CONFIG_PATH / LD_LIBRARY_PATH
# so later probes and Python configure do not pick up cluster module libs.
scrub_nonportable_lib_env() {
  local p out_pc="" out_ld=""
  local IFS=':'
  for p in ${PKG_CONFIG_PATH-}; do
    [[ -z "$p" ]] && continue
    case "$p" in
      "$PREFIX"/*|/usr/lib/pkgconfig|/usr/lib64/pkgconfig|/usr/share/pkgconfig|/usr/local/lib/pkgconfig|/usr/local/lib64/pkgconfig|/usr/lib/*/pkgconfig)
        out_pc="${out_pc:+$out_pc:}$p"
        ;;
      *)
        log "Ignoring non-portable PKG_CONFIG_PATH entry: $p"
        ;;
    esac
  done
  for p in ${LD_LIBRARY_PATH-}; do
    [[ -z "$p" ]] && continue
    if is_portable_prefix "$p" || [[ "$p" == "$PREFIX/lib" || "$p" == "$PREFIX/lib64" ]]; then
      case "$p" in
        /usr/local/packages/*|/usr/local/Modules/*|/opt/ohpc/*)
          log "Ignoring non-portable LD_LIBRARY_PATH entry: $p"
          continue
          ;;
      esac
      out_ld="${out_ld:+$out_ld:}$p"
    else
      log "Ignoring non-portable LD_LIBRARY_PATH entry: $p"
    fi
  done
  export PKG_CONFIG_PATH="$out_pc"
  export LD_LIBRARY_PATH="$out_ld"
}

# Download url → out. Clears bad CA env, tries verify, then insecure bootstrap.
download() {
  local url="$1" out="$2"
  local ca="" capath=""
  have wget || have curl || die "need wget or curl to download $url"

  clear_broken_ca_env
  ca="$(find_ca_bundle || true)"
  capath="$(find_ca_path || true)"
  if [[ -n "$ca" ]]; then
    export SSL_CERT_FILE="$ca"
    export CURL_CA_BUNDLE="$ca"
    export REQUESTS_CA_BUNDLE="$ca"
  fi
  if [[ -n "$capath" ]]; then
    export SSL_CERT_DIR="$capath"
  fi

  _download_once() {
    # $1 = verify|insecure
    local mode="$1"
    rm -f "$out"
    if have curl; then
      local -a cargs=(-fL --progress-bar -o "$out" --connect-timeout 30 --retry 2)
      if [[ "$mode" == insecure ]]; then
        cargs+=(-k)
      else
        # Explicit paths beat curl's compile-time default (often a missing file on HPC).
        if [[ -n "$ca" ]]; then
          cargs+=(--cacert "$ca")
        fi
        if [[ -n "$capath" ]]; then
          cargs+=(--capath "$capath")
        fi
        # If we have neither, skip verify attempt for curl (would hit error 77).
        if [[ -z "$ca" && -z "$capath" ]]; then
          return 1
        fi
      fi
      if with_system_libs curl "${cargs[@]}" "$url" && [[ -s "$out" ]]; then
        return 0
      fi
    fi
    if have wget; then
      local -a wargs=(-q --show-progress -O "$out" --timeout=30 --tries=2)
      if [[ "$mode" == insecure ]]; then
        wargs+=(--no-check-certificate)
      elif [[ -n "$ca" ]]; then
        wargs+=(--ca-certificate="$ca")
      else
        return 1
      fi
      if with_system_libs wget "${wargs[@]}" "$url" && [[ -s "$out" ]]; then
        return 0
      fi
    fi
    return 1
  }

  if [[ -n "$ca" || -n "$capath" ]] && _download_once verify; then
    return 0
  fi

  # Chicken-and-egg: broken/missing CA is common on HPC; we need the tarball
  # to build OpenSSL / Python that will verify TLS correctly later.
  if [[ -n "$ca" || -n "$capath" ]]; then
    log "WARNING: TLS verify failed for $url"
    [[ -n "$ca" ]] && log "  (tried CA bundle: $ca)"
    [[ -n "$capath" ]] && log "  (tried CA path: $capath)"
  else
    log "WARNING: no usable CA bundle/path; downloading without TLS verify (bootstrap only)"
    log "  $url"
  fi
  log "  using curl -k / wget --no-check-certificate"
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
  # stdlib C extensions — cannot be fixed with pip after the fact.
  # _posixsubprocess is required by subprocess (install.py imports it early).
  "$py" -c 'import _posixsubprocess, subprocess, _ctypes, ssl, lzma, sqlite3; assert ssl.OPENSSL_VERSION' 2>/dev/null || return 1
  return 0
}

TARGET_PY="$PREFIX/bin/python${PY_MM}"

if [[ "$FORCE" -eq 0 ]] && python_smoke "$TARGET_PY"; then
  log "Python $PY_VER already OK at $TARGET_PY (_posixsubprocess + _ctypes + ssl + lzma + sqlite3)"
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
# LD_LIBRARY_PATH helps the build find libs just installed into PREFIX, but
# download()/with_system_libs strip PREFIX so system curl is not broken by an
# older bundled libssl. Prefer RUNPATH on installed binaries for runtime.
export LD_LIBRARY_PATH="$PREFIX/lib:$PREFIX/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig:$PREFIX/lib64/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
# Drop cluster-module pkg-config / lib paths (e.g. .../packages/python/3.7.6)
# before probing deps — those libs are invisible to Python's RUNSHARED.
scrub_nonportable_lib_env
export LD_LIBRARY_PATH="$PREFIX/lib:$PREFIX/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig:$PREFIX/lib64/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export CPPFLAGS="-I$PREFIX/include ${CPPFLAGS:-}"
export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 ${LDFLAGS:-}"

# --- libffi (required for _ctypes) ---
ffi_usable() {
  if pkg_config_portable libffi; then
    return 0
  fi
  # Compiler can see ffi.h and link -lffi via PREFIX or distro paths only
  cat >"$BUILD_ROOT/ffi_probe.c" <<'EOF'
#include <ffi.h>
int main(void) {
  ffi_cif cif;
  (void)cif;
  return 0;
}
EOF
  # shellcheck disable=SC2086
  with_portable_libs cc $CPPFLAGS $LDFLAGS "$BUILD_ROOT/ffi_probe.c" -lffi -o "$BUILD_ROOT/ffi_probe" 2>/dev/null \
    && with_portable_libs "$BUILD_ROOT/ffi_probe" >/dev/null 2>&1
}

# Export LIBFFI_CFLAGS / LIBFFI_LIBS for Python's configure (in addition to CPPFLAGS).
set_libffi_env_from_pkgconfig_or_prefix() {
  local cflags="" libs=""
  if pkg_config_portable libffi; then
    cflags="$(with_portable_libs pkg-config --cflags libffi 2>/dev/null || true)"
    libs="$(with_portable_libs pkg-config --libs libffi 2>/dev/null || true)"
    log "  pkg-config libffi: $(with_portable_libs pkg-config --modversion libffi)"
  elif [[ -r "$PREFIX/include/ffi.h" ]] || ls "$PREFIX"/lib/libffi-*/include/ffi.h >/dev/null 2>&1; then
    # libffi often installs headers under lib/libffi-X.Y/include/
    local inc="$PREFIX/include"
    local nested
    nested="$(ls -d "$PREFIX"/lib/libffi-*/include 2>/dev/null | head -1 || true)"
    [[ -n "$nested" ]] && inc="$nested"
    cflags="-I$inc"
    libs="-L$PREFIX/lib -L$PREFIX/lib64 -lffi"
  fi
  if [[ -n "$cflags" || -n "$libs" ]]; then
    export CPPFLAGS="$cflags $CPPFLAGS"
    export LDFLAGS="$libs $LDFLAGS"
    export LIBFFI_CFLAGS="$cflags"
    export LIBFFI_LIBS="$libs"
  fi
}

ensure_libffi() {
  if ffi_usable; then
    log "libffi available (system or prefix)"
    set_libffi_env_from_pkgconfig_or_prefix
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
  set_libffi_env_from_pkgconfig_or_prefix
  ffi_usable || die "libffi still not usable after local build"
  log "libffi installed to $PREFIX"
}

ensure_libffi

# --- OpenSSL (required for ssl module / pip HTTPS, e.g. inside apptainer) ---
# Only build into PREFIX when the system has no usable OpenSSL (or OPENSSL_BUNDLE=1).
# Preferring a prior PREFIX bundle unconditionally is wrong: an older libssl on
# LD_LIBRARY_PATH breaks distro curl (needs newer OPENSSL_* symbols).

prefix_openssl_usable() {
  if [[ -r "$PREFIX/include/openssl/ssl.h" ]] && \
     { [[ -e "$PREFIX/lib/libssl.so" ]] || [[ -e "$PREFIX/lib64/libssl.so" ]] || \
       ls "$PREFIX"/lib/libssl.so* >/dev/null 2>&1 || ls "$PREFIX"/lib64/libssl.so* >/dev/null 2>&1; }; then
    return 0
  fi
  return 1
}

# Distro/system OpenSSL only — ignore PREFIX pkg-config and -I/-L so a leftover
# bundle does not masquerade as "system has OpenSSL".
system_openssl_usable() {
  if have pkg-config && with_system_libs pkg-config --exists openssl; then
    return 0
  fi
  cat >"$BUILD_ROOT/ssl_probe_sys.c" <<'EOF'
#include <openssl/ssl.h>
#include <openssl/opensslv.h>
int main(void) {
  return (OPENSSL_VERSION_NUMBER > 0) ? 0 : 1;
}
EOF
  # No PREFIX CPPFLAGS/LDFLAGS — pure system headers and libs
  with_system_libs cc "$BUILD_ROOT/ssl_probe_sys.c" -lssl -lcrypto \
    -o "$BUILD_ROOT/ssl_probe_sys" 2>/dev/null
}

use_system_openssl() {
  local cflags libs pref
  if have pkg-config && with_system_libs pkg-config --exists openssl; then
    log "OpenSSL available (system): $(with_system_libs pkg-config --modversion openssl)"
    cflags="$(with_system_libs pkg-config --cflags openssl 2>/dev/null || true)"
    libs="$(with_system_libs pkg-config --libs openssl 2>/dev/null || true)"
    pref="$(with_system_libs pkg-config --variable=prefix openssl 2>/dev/null || true)"
    export CPPFLAGS="$cflags $CPPFLAGS"
    export LDFLAGS="$libs $LDFLAGS"
    # Python --with-openssl wants a root that contains include/ and lib(or lib64)/
    if [[ -n "$pref" && -r "$pref/include/openssl/ssl.h" ]]; then
      OPENSSL_DIR="$pref"
    else
      OPENSSL_DIR="/usr"
    fi
  else
    log "OpenSSL available via compiler default paths"
    OPENSSL_DIR="/usr"
  fi
  if prefix_openssl_usable; then
    log "  note: PREFIX also has OpenSSL from a prior bundle; ignoring it (OPENSSL_BUNDLE=0)."
    log "  (Leave PREFIX libssl off LD_LIBRARY_PATH so system curl keeps working.)"
  fi
}

use_prefix_openssl() {
  log "OpenSSL available in prefix $PREFIX"
  export CPPFLAGS="-I$PREFIX/include $CPPFLAGS"
  export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 $LDFLAGS"
  OPENSSL_DIR="$PREFIX"
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
  prefix_openssl_usable || die "OpenSSL still not usable after local build"
  log "OpenSSL installed to $PREFIX"
}

ensure_openssl() {
  OPENSSL_DIR=""

  if [[ "$OPENSSL_BUNDLE" == "1" ]]; then
    log "OPENSSL_BUNDLE=1 — building OpenSSL into prefix even if system has it"
    if prefix_openssl_usable; then
      log "  reusing existing OpenSSL in $PREFIX (delete it or use a clean PREFIX to rebuild)"
      use_prefix_openssl
    else
      build_openssl_into_prefix
      OPENSSL_DIR="$PREFIX"
    fi
    return 0
  fi

  # Default: system first, then a prior prefix bundle, else build.
  if system_openssl_usable; then
    use_system_openssl
    return 0
  fi

  if prefix_openssl_usable; then
    log "no system OpenSSL; using existing prefix build"
    use_prefix_openssl
    return 0
  fi

  log "no usable system OpenSSL; building into prefix (set OPENSSL_BUNDLE=1 to force this)"
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
  if pkg_config_portable liblzma; then
    return 0
  fi
  cat >"$BUILD_ROOT/lzma_probe.c" <<'EOF'
#include <lzma.h>
int main(void) {
  return (LZMA_VERSION > 0) ? 0 : 1;
}
EOF
  # shellcheck disable=SC2086
  with_portable_libs cc $CPPFLAGS $LDFLAGS "$BUILD_ROOT/lzma_probe.c" -llzma -o "$BUILD_ROOT/lzma_probe" 2>/dev/null \
    && with_portable_libs "$BUILD_ROOT/lzma_probe" >/dev/null 2>&1
}

ensure_liblzma() {
  if lzma_usable; then
    log "liblzma available (system or prefix)"
    if pkg_config_portable liblzma; then
      log "  pkg-config liblzma: $(with_portable_libs pkg-config --modversion liblzma)"
      local cflags libs
      cflags="$(with_portable_libs pkg-config --cflags liblzma 2>/dev/null || true)"
      libs="$(with_portable_libs pkg-config --libs liblzma 2>/dev/null || true)"
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

# --- SQLite (required for Python _sqlite3 — used by optuna, etc.) ---
sqlite_usable() {
  if [[ -r "$PREFIX/include/sqlite3.h" ]] && \
     { [[ -e "$PREFIX/lib/libsqlite3.so" ]] || [[ -e "$PREFIX/lib64/libsqlite3.so" ]] || \
       ls "$PREFIX"/lib/libsqlite3.so* >/dev/null 2>&1 || ls "$PREFIX"/lib64/libsqlite3.so* >/dev/null 2>&1; }; then
    return 0
  fi
  if pkg_config_portable sqlite3; then
    return 0
  fi
  cat >"$BUILD_ROOT/sqlite_probe.c" <<'EOF'
#include <sqlite3.h>
int main(void) {
  return (sqlite3_libversion_number() > 0) ? 0 : 1;
}
EOF
  # shellcheck disable=SC2086
  with_portable_libs cc $CPPFLAGS $LDFLAGS "$BUILD_ROOT/sqlite_probe.c" -lsqlite3 -o "$BUILD_ROOT/sqlite_probe" 2>/dev/null \
    && with_portable_libs "$BUILD_ROOT/sqlite_probe" >/dev/null 2>&1
}

ensure_sqlite() {
  if sqlite_usable; then
    log "sqlite3 available (system or prefix)"
    if pkg_config_portable sqlite3; then
      log "  pkg-config sqlite3: $(with_portable_libs pkg-config --modversion sqlite3)"
      local cflags libs
      cflags="$(with_portable_libs pkg-config --cflags sqlite3 2>/dev/null || true)"
      libs="$(with_portable_libs pkg-config --libs sqlite3 2>/dev/null || true)"
      export CPPFLAGS="$cflags $CPPFLAGS"
      export LDFLAGS="$libs $LDFLAGS"
    elif [[ -r "$PREFIX/include/sqlite3.h" ]]; then
      export CPPFLAGS="-I$PREFIX/include $CPPFLAGS"
      export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 $LDFLAGS"
    fi
    return 0
  fi

  log "sqlite3 not found; building SQLite $SQLITE_VER into $PREFIX (no root)"
  local tarball="sqlite-autoconf-${SQLITE_VER}.tar.gz"
  local url="https://www.sqlite.org/${SQLITE_YEAR}/${tarball}"
  # Fallbacks if the year/version combo 404s on a given mirror layout
  local url_alt="https://www.sqlite.org/2024/sqlite-autoconf-3470200.tar.gz"
  cd "$BUILD_ROOT"
  if ! download "$url" "$tarball"; then
    log "primary SQLite URL failed; trying 3.47.2 fallback"
    tarball="sqlite-autoconf-3470200.tar.gz"
    download "$url_alt" "$tarball" || die "failed to download SQLite amalgamation"
  fi
  # Directory name = tarball stem (avoid "tar | head" under pipefail — can exit 141)
  local srcdir="${tarball%.tar.gz}"
  srcdir="${srcdir%.tgz}"
  log "Extracting $tarball → $srcdir"
  tar -xzf "$tarball"
  [[ -d "$srcdir" ]] || die "expected directory $srcdir after extracting $tarball"
  cd "$srcdir"
  # Recommended feature flags for a modern Python build
  local _cflags_save="${CFLAGS-}"
  export CFLAGS="${CFLAGS:-} -O2 -DSQLITE_ENABLE_FTS3 -DSQLITE_ENABLE_FTS4 -DSQLITE_ENABLE_FTS5 -DSQLITE_ENABLE_JSON1 -DSQLITE_ENABLE_RTREE -DSQLITE_ENABLE_COLUMN_METADATA"
  log "configure --prefix=$PREFIX (sqlite)"
  ./configure --prefix="$PREFIX" --enable-shared --disable-static
  log "Building sqlite (make -j$NPROC) ..."
  make -j"$NPROC"
  log "Installing sqlite into $PREFIX ..."
  make install
  if [[ -n "$_cflags_save" ]]; then export CFLAGS="$_cflags_save"; else unset CFLAGS; fi
  export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig:$PREFIX/lib64/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
  export CPPFLAGS="-I$PREFIX/include $CPPFLAGS"
  export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 $LDFLAGS"
  sqlite_usable || die "sqlite3 still not usable after local build"
  log "sqlite3 installed to $PREFIX"
}

ensure_sqlite

# --- bzip2 / libbz2 (needed for _bz2; missing .so breaks make sharedinstall) ---
# Python's extension import check needs libbz2.so.1.0 visible via PREFIX/lib.
bzip2_soname_ok() {
  # Shared object with the soname Python's _bz2 typically needs
  [[ -e "$PREFIX/lib/libbz2.so.1.0" || -e "$PREFIX/lib64/libbz2.so.1.0" ]] \
    || [[ -e "$PREFIX/lib/libbz2.so.1.0.8" || -e "$PREFIX/lib64/libbz2.so.1.0.8" ]]
}

bzip2_usable() {
  # Prefer a PREFIX install that is loadable the way RUNSHARED will see it.
  if [[ -r "$PREFIX/include/bzlib.h" ]] && bzip2_soname_ok; then
    cat >"$BUILD_ROOT/bz2_probe.c" <<'EOF'
#include <bzlib.h>
int main(void) { return 0; }
EOF
    # shellcheck disable=SC2086
    if with_portable_libs cc -I"$PREFIX/include" -L"$PREFIX/lib" -L"$PREFIX/lib64" \
         "$BUILD_ROOT/bz2_probe.c" -lbz2 -o "$BUILD_ROOT/bz2_probe" 2>/dev/null \
       && with_portable_libs "$BUILD_ROOT/bz2_probe" >/dev/null 2>&1; then
      return 0
    fi
  fi
  # Distro libbz2 only (not cluster module trees)
  cat >"$BUILD_ROOT/bz2_probe.c" <<'EOF'
#include <bzlib.h>
int main(void) {
  return 0;
}
EOF
  # shellcheck disable=SC2086
  with_portable_libs cc $CPPFLAGS $LDFLAGS "$BUILD_ROOT/bz2_probe.c" -lbz2 -o "$BUILD_ROOT/bz2_probe" 2>/dev/null \
    && with_portable_libs "$BUILD_ROOT/bz2_probe" >/dev/null 2>&1
}

ensure_prefix_bzip2_symlinks() {
  mkdir -p "$PREFIX/lib"
  local so=""
  so="$(ls -1 "$PREFIX"/lib/libbz2.so.1.0.[0-9]* 2>/dev/null | head -1 || true)"
  if [[ -z "$so" ]]; then
    so="$(ls -1 "$PREFIX"/lib/libbz2.so.[0-9]* 2>/dev/null | head -1 || true)"
  fi
  [[ -n "$so" ]] || return 1
  local base
  base="$(basename "$so")"
  # Soname expected by bzip2 shared builds / _bz2
  ln -sfn "$base" "$PREFIX/lib/libbz2.so.1.0"
  ln -sfn "libbz2.so.1.0" "$PREFIX/lib/libbz2.so"
  return 0
}

ensure_bzip2() {
  if bzip2_usable; then
    log "libbz2 available (portable system or prefix)"
    if [[ -r "$PREFIX/include/bzlib.h" ]] && bzip2_soname_ok; then
      export CPPFLAGS="-I$PREFIX/include $CPPFLAGS"
      export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 $LDFLAGS"
      export BZIP2_CFLAGS="-I$PREFIX/include"
      export BZIP2_LIBS="-L$PREFIX/lib -L$PREFIX/lib64 -lbz2"
    fi
    return 0
  fi

  log "libbz2 not found in PREFIX/distro paths; building bzip2 $BZIP2_VER into $PREFIX (no root)"
  log "  (cluster module libs like .../packages/python/*/lib are ignored — invisible to RUNSHARED)"
  local tarball="bzip2-${BZIP2_VER}.tar.gz"
  # sourceware is canonical; OSUOSL mirrors the same tarball layout
  local url="https://sourceware.org/pub/bzip2/${tarball}"
  local url_alt="https://ftp.osuosl.org/pub/clfs/conglomeration/bzip2/${tarball}"
  cd "$BUILD_ROOT"
  if ! download "$url" "$tarball"; then
    log "primary bzip2 URL failed; trying OSUOSL mirror"
    download "$url_alt" "$tarball" || die "failed to download bzip2 $BZIP2_VER"
  fi
  tar -xzf "$tarball"
  local srcdir=""
  if [[ -d "bzip2-${BZIP2_VER}" ]]; then
    srcdir="bzip2-${BZIP2_VER}"
  else
    srcdir="$(find . -maxdepth 1 -type d -name 'bzip2*' | head -1 | sed 's|^\./||')"
  fi
  [[ -n "$srcdir" && -d "$srcdir" ]] || die "bzip2 source dir not found after extract"
  cd "$srcdir"
  mkdir -p "$PREFIX/lib" "$PREFIX/include"
  # Shared lib first (Python links -lbz2 as .so). Copy .so out before `make clean`
  # (main Makefile clean is usually fine, but Makefile-libbz2_so clean removes .so).
  # -fPIC required so objects can participate in shared module links.
  make -f Makefile-libbz2_so CFLAGS="-fPIC -O2 -g -D_FILE_OFFSET_BITS=64" -j"$NPROC"
  cp -a libbz2.so* "$PREFIX/lib/" 2>/dev/null || true
  make clean
  make CFLAGS="-fPIC -O2 -g -D_FILE_OFFSET_BITS=64" -j"$NPROC"
  make install PREFIX="$PREFIX" CFLAGS="-fPIC -O2 -g -D_FILE_OFFSET_BITS=64"
  ensure_prefix_bzip2_symlinks || die "libbz2 shared library missing after install"
  # Prove the soname is loadable the way Python's import check will see it
  cat >"$BUILD_ROOT/bz2_probe2.c" <<'EOF'
#include <bzlib.h>
int main(void) { return 0; }
EOF
  # shellcheck disable=SC2086
  with_portable_libs cc -I"$PREFIX/include" -L"$PREFIX/lib" -L"$PREFIX/lib64" \
    "$BUILD_ROOT/bz2_probe2.c" -lbz2 -o "$BUILD_ROOT/bz2_probe2" \
    || die "failed to link probe against PREFIX libbz2"
  with_portable_libs "$BUILD_ROOT/bz2_probe2" \
    || die "PREFIX libbz2.so.1.0 not loadable (check symlinks under $PREFIX/lib)"
  export CPPFLAGS="-I$PREFIX/include $CPPFLAGS"
  export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 $LDFLAGS"
  export BZIP2_CFLAGS="-I$PREFIX/include"
  export BZIP2_LIBS="-L$PREFIX/lib -L$PREFIX/lib64 -lbz2"
  bzip2_usable || die "libbz2 still not usable after local build"
  log "libbz2 installed to $PREFIX (libbz2.so.1.0 -> $(readlink -f "$PREFIX/lib/libbz2.so.1.0" 2>/dev/null || echo '?'))"
}

ensure_bzip2

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
warn_missing_headers "readline" "readline/readline.h"

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
# shellcheck disable=SC2086
./configure "${CONFIG_ARGS[@]}" \
  CPPFLAGS="$CPPFLAGS" \
  LDFLAGS="$LDFLAGS" \
  ${BZIP2_CFLAGS:+BZIP2_CFLAGS="$BZIP2_CFLAGS"} \
  ${BZIP2_LIBS:+BZIP2_LIBS="$BZIP2_LIBS"} \
  ${LIBFFI_CFLAGS:+LIBFFI_CFLAGS="$LIBFFI_CFLAGS"} \
  ${LIBFFI_LIBS:+LIBFFI_LIBS="$LIBFFI_LIBS"}

log "Building (make -j$NPROC) ..."
make -j"$NPROC"

# Resolve EXT_SUFFIX from the build Makefile (e.g. .cpython-313-x86_64-linux-gnu.so).
ext_suffix() {
  local s
  s="$(sed -n 's/^EXT_SUFFIX=[[:space:]]*//p' Makefile 2>/dev/null | head -1)"
  # Fallback: pick any built module's suffix
  if [[ -z "$s" ]]; then
    s="$(basename "$(ls -1 Modules/math.cpython-*.so 2>/dev/null | head -1)" | sed 's/^math//')"
  fi
  printf '%s' "$s"
}

# Python 3.12+ can list a shared module for install even when the .so was never
# built (e.g. optional dep missing mid-build). sharedinstall then aborts with
# "cannot stat 'Modules/_bz2….so'". Drop only those missing entries.
#
# IMPORTANT: Makefile SHAREDMODS uses Modules/foo$(EXT_SUFFIX) — expand that
# before testing -f. Treating $(EXT_SUFFIX) literally emptied SHAREDMODS and
# installed a Python with no C extensions (_ctypes, _posixsubprocess, …).
filter_missing_sharedmods() {
  local mf=Makefile
  [[ -f "$mf" ]] || return 0
  local suffix line mods m path new=() required_missing=()
  suffix="$(ext_suffix)"
  [[ -n "$suffix" ]] || {
    log "WARNING: could not determine EXT_SUFFIX; skipping SHAREDMODS filter"
    return 0
  }
  line="$(grep '^SHAREDMODS=' "$mf" | head -1 || true)"
  [[ -n "$line" ]] || return 0
  mods="${line#SHAREDMODS=}"
  for m in $mods; do
    path="${m//'$(EXT_SUFFIX)'/$suffix}"
    # Also accept already-expanded paths
    if [[ -f "$path" || -f "$m" ]]; then
      new+=("$m")
    else
      case "$path" in
        */_ctypes"$suffix"|*/_posixsubprocess"$suffix"|*/_ssl"$suffix"|*/_lzma"$suffix"|*/_sqlite3"$suffix"|*/_bz2"$suffix")
          required_missing+=("$path")
          ;;
        *)
          log "WARNING: omitting missing optional shared module from install: $path"
          ;;
      esac
    fi
  done
  if ((${#required_missing[@]})); then
    log "ERROR: required extension(s) missing after make:"
    local r
    for r in "${required_missing[@]}"; do
      log "  - $r"
    done
    log "  Check config.log / build output for libffi, openssl, xz, sqlite, bzip2."
    die "required Python C extensions failed to build (see above)"
  fi
  local tmp="$BUILD_ROOT/Makefile.sharedmods"
  awk -v repl="SHAREDMODS=${new[*]}" '
    BEGIN { done=0 }
    /^SHAREDMODS=/ && !done { print repl; done=1; next }
    { print }
  ' "$mf" >"$tmp"
  mv "$tmp" "$mf"
}

# Hard check: required .so files must exist in the build tree before install.
require_built_module() {
  local name="$1"
  local suffix="$2"
  local so="Modules/${name}${suffix}"
  if [[ ! -f "$so" ]]; then
    # ctypes objects live under Modules/_ctypes/ but the .so is Modules/_ctypes.so
    log "ERROR: $so was not built"
    return 1
  fi
  log "  built $so"
  return 0
}

_EXT_SUFFIX="$(ext_suffix)"
[[ -n "$_EXT_SUFFIX" ]] || die "EXT_SUFFIX unknown after make; cannot verify extensions"
log "EXT_SUFFIX=$_EXT_SUFFIX"
require_built_module "_posixsubprocess" "$_EXT_SUFFIX" || die "_posixsubprocess missing — stdlib build is broken"
require_built_module "_ctypes" "$_EXT_SUFFIX" || die "_ctypes missing — libffi not found/linked; see ensure_libffi / config.log"
require_built_module "_ssl" "$_EXT_SUFFIX" || die "_ssl missing — OpenSSL not found/linked; see ensure_openssl / config.log"
require_built_module "_lzma" "$_EXT_SUFFIX" || die "_lzma missing — liblzma not found/linked; see ensure_liblzma / config.log"
require_built_module "_sqlite3" "$_EXT_SUFFIX" || die "_sqlite3 missing — sqlite3 not found/linked; see ensure_sqlite / config.log"
if ! require_built_module "_bz2" "$_EXT_SUFFIX"; then
  die "_bz2 missing — often built then deleted when libbz2.so.1.0 is not on RUNSHARED (cluster module libs). See ensure_bzip2 / config.log"
fi

filter_missing_sharedmods

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
if ! "$TARGET_PY" -c 'import sqlite3; print("sqlite3 OK:", sqlite3.sqlite_version, sqlite3.__file__)'; then
  die "Python installed but _sqlite3 still missing. Check libsqlite3 headers and config.log in $BUILD_ROOT"
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
log "  sqlite3: $("$TARGET_PY" -c 'import sqlite3; print(sqlite3.sqlite_version)')"
log "  Add to PATH via install.sh / ~/.bashaux (platform prefix: $WORKENV_PLATFORM)"
