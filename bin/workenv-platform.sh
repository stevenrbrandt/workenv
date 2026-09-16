# Shared platform id for workenv toolchain + PYTHONUSERBASE.
# Source this file; sets/exports WORKENV_PLATFORM (e.g. x86_64-glibc-2.35).
#
# Override: export WORKENV_PLATFORM=... before sourcing.
#
# Also defines workenv_compatible_bin_path: exact $WORKENV_PREFIX/bin, then
# older same-arch glibc prefixes (those binaries run on newer glibc). That
# keeps host vim/node/python working inside an apptainer image whose own
# prefix has not been built yet.

workenv_detect_platform() {
  local arch libc
  arch="$(uname -m)"
  # pipefail-safe: getconf may be missing (musl / odd chroots)
  libc="$(getconf GNU_LIBC_VERSION 2>/dev/null | sed 's/ /-/g' || true)"
  if [ -z "$libc" ]; then
    if command -v ldd >/dev/null 2>&1 && ldd --version 2>&1 | head -n1 | grep -qi musl; then
      libc=musl
    else
      libc=unknown-libc
    fi
  fi
  printf '%s\n' "${arch}-${libc}"
}

if [ -z "${WORKENV_PLATFORM:-}" ]; then
  WORKENV_PLATFORM="$(workenv_detect_platform)"
fi
export WORKENV_PLATFORM

# Colon-separated bin dirs for PATH. Exact platform first.
workenv_compatible_bin_path() {
  local root="${WORKENV_ROOT:-}"
  local prefix="${WORKENV_PREFIX:-}"
  local path arch libc my_ver dir ver
  if [ -z "$prefix" ] && [ -n "$root" ]; then
    prefix="$root/$WORKENV_PLATFORM"
  fi
  path="${prefix:+$prefix/bin}"
  [ -n "$root" ] || { printf '%s\n' "$path"; return 0; }
  arch="${WORKENV_PLATFORM%%-*}"
  libc="${WORKENV_PLATFORM#*-}"
  case "$libc" in
    glibc-*)
      my_ver="${libc#glibc-}"
      for dir in "$root/${arch}-glibc-"*; do
        [ -d "$dir/bin" ] || continue
        [ -n "$prefix" ] && [ "$dir" = "$prefix" ] && continue
        ver="${dir##*-glibc-}"
        # Keep prefixes with glibc <= current (sort -V: last line is newest).
        if [ "$(printf '%s\n%s\n' "$ver" "$my_ver" | sort -V | tail -n1)" = "$my_ver" ]; then
          if [ -n "$path" ]; then
            path="$path:$dir/bin"
          else
            path="$dir/bin"
          fi
        fi
      done
      ;;
  esac
  printf '%s\n' "$path"
}
