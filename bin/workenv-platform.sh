# Shared platform id for workenv toolchain + PYTHONUSERBASE.
# Source this file; sets/exports WORKENV_PLATFORM (e.g. x86_64-glibc-2.35).
#
# Override: export WORKENV_PLATFORM=... before sourcing.

# Avoid re-running detection if already set (e.g. parent install.sh).
if [ -n "${WORKENV_PLATFORM:-}" ]; then
  return 0 2>/dev/null || exit 0
fi

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

WORKENV_PLATFORM="$(workenv_detect_platform)"
export WORKENV_PLATFORM
