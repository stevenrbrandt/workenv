#!/usr/bin/env bash
# Build a modern Vim into the platform-specific workenv prefix (no root), and
# install vim-plug + a clangd-friendly coc setup helpers.
#
# Usage:
#   mk-vim.sh                 # install if system/prefix vim is too old
#   mk-vim.sh --force
#   MIN_VIM=9.1 mk-vim.sh
#   SKIP_CLANGD=1 mk-vim.sh
#
# Installs to: $WORKENV_ROOT/$WORKENV_PLATFORM  (see workenv-platform.sh)

set -euo pipefail

FORCE=0
MIN_VIM="${MIN_VIM:-9.1}"
VIM_TAG="${VIM_TAG:-v9.1.0}"
SKIP_CLANGD="${SKIP_CLANGD:-0}"
BUILD_ROOT="${BUILD_ROOT:-/tmp/workenv-vim-build-$$}"
NPROC="${NPROC:-$(nproc 2>/dev/null || echo 2)}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKENV_ROOT="${WORKENV_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
# shellcheck source=workenv-platform.sh
. "$SCRIPT_DIR/workenv-platform.sh"
PREFIX="${PREFIX:-$WORKENV_ROOT/$WORKENV_PLATFORM}"

for arg in "$@"; do
  case "$arg" in
    --force|-f) FORCE=1 ;;
    --help|-h)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

log() { printf '+ %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

version_ge() {
  # return 0 if $1 >= $2 (dotted numeric)
  printf '%s\n%s\n' "$2" "$1" | sort -V | head -1 | grep -qx "$2"
}

vim_version() {
  local v
  v="$("$1" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1 || true)"
  printf '%s' "$v"
}

pick_vim() {
  if [[ -x "$PREFIX/bin/vim" ]]; then
    printf '%s' "$PREFIX/bin/vim"
  elif have vim; then
    command -v vim
  else
    printf ''
  fi
}

install_vim_plug() {
  local dest="$HOME/.vim/autoload/plug.vim"
  if [[ -f "$dest" ]]; then
    log "vim-plug already present: $dest"
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  local url="https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim"
  log "Installing vim-plug -> $dest"
  if have curl; then
    curl -fLo "$dest" --create-dirs "$url"
  elif have wget; then
    wget -q -O "$dest" "$url"
  else
    log "WARNING: no curl/wget; skip vim-plug"
    return 1
  fi
}

# Best-effort clangd: system binary, or official clangd release zip (much smaller than full LLVM).
install_clangd() {
  if [[ "$SKIP_CLANGD" == "1" ]]; then
    log "SKIP_CLANGD=1 — not installing clangd"
    return 0
  fi
  if [[ -x "$PREFIX/bin/clangd" ]]; then
    log "clangd already at $PREFIX/bin/clangd"
    return 0
  fi
  if have clangd; then
    log "clangd on PATH: $(command -v clangd)"
    return 0
  fi

  # https://github.com/clangd/clangd/releases — linux x86_64 / arm64
  local clangd_ver="${CLANGD_VER:-19.1.2}"
  local asset=""
  case "$ARCH" in
    x86_64|amd64) asset="clangd-linux-${clangd_ver}.zip" ;;
    aarch64|arm64) asset="clangd-linux-arm64-${clangd_ver}.zip" ;;
    *)
      log "WARNING: no prebuilt clangd for arch=$ARCH; install clangd manually"
      return 0
      ;;
  esac

  local url="https://github.com/clangd/clangd/releases/download/${clangd_ver}/${asset}"
  log "Downloading clangd ${clangd_ver}: $url"
  mkdir -p "$BUILD_ROOT" "$PREFIX/bin"
  cd "$BUILD_ROOT"
  if have wget; then
    wget -q --show-progress -O clangd.zip "$url" || { log "WARNING: clangd download failed"; return 0; }
  elif have curl; then
    curl -fL --progress-bar -o clangd.zip "$url" || { log "WARNING: clangd download failed"; return 0; }
  else
    log "WARNING: no curl/wget for clangd"
    return 0
  fi
  if have unzip; then
    unzip -o -q clangd.zip
  elif have python3; then
    python3 - <<'PY'
import zipfile
zipfile.ZipFile("clangd.zip").extractall(".")
PY
  else
    log "WARNING: need unzip or python3 to extract clangd.zip"
    return 0
  fi
  local found
  found="$(find "$BUILD_ROOT" -type f -name clangd -perm -u+x 2>/dev/null | head -1 || true)"
  if [[ -z "$found" ]]; then
    found="$(find "$BUILD_ROOT" -type f -name clangd 2>/dev/null | head -1 || true)"
  fi
  if [[ -n "$found" ]]; then
    cp -f "$found" "$PREFIX/bin/clangd"
    chmod +x "$PREFIX/bin/clangd"
    log "Installed $PREFIX/bin/clangd"
  else
    log "WARNING: clangd binary not found after extract"
  fi
}

write_coc_settings() {
  local dir="$HOME/.vim"
  mkdir -p "$dir"
  local settings="$dir/coc-settings.json"
  if [[ -f "$settings" ]]; then
    log "Leaving existing $settings"
    return 0
  fi
  cat >"$settings" <<'JSON'
{
  "languageserver": {
    "clangd": {
      "command": "clangd",
      "args": ["--background-index", "--clang-tidy"],
      "rootPatterns": [
        "compile_commands.json",
        ".clangd",
        ".git",
        "CMakeLists.txt"
      ],
      "filetypes": ["c", "cc", "cpp", "c++", "objc", "objcpp", "cuda"]
    }
  },
  "clangd.path": "clangd",
  "clangd.arguments": ["--background-index", "--clang-tidy"]
}
JSON
  log "Wrote $settings"
}

CURRENT="$(pick_vim)"
NEED_BUILD=1
if [[ "$FORCE" -eq 0 && -n "$CURRENT" ]]; then
  VER="$(vim_version "$CURRENT")"
  if [[ -n "$VER" ]] && version_ge "$VER" "$MIN_VIM"; then
    log "Vim $VER at $CURRENT meets MIN_VIM=$MIN_VIM"
    NEED_BUILD=0
  else
    log "Vim at ${CURRENT:-none} (ver=${VER:-unknown}) is older than $MIN_VIM"
  fi
fi

if [[ "$NEED_BUILD" -eq 1 ]]; then
  have git || die "git required to build vim"
  have cc || die "cc required to build vim"
  have make || die "make required to build vim"
  mkdir -p "$PREFIX" "$BUILD_ROOT"
  cleanup() { rm -rf "$BUILD_ROOT"; }
  trap cleanup EXIT

  log "Building Vim $VIM_TAG -> $PREFIX"
  cd "$BUILD_ROOT"
  git clone --depth 1 --branch "$VIM_TAG" https://github.com/vim/vim.git vim-src
  cd vim-src
  ./configure \
    --prefix="$PREFIX" \
    --with-features=huge \
    --enable-multibyte \
    --disable-gui \
    --without-x \
    --enable-terminal \
    --with-compiledby="workenv mk-vim.sh"
  make -j"$NPROC"
  make install
  log "Installed $($PREFIX/bin/vim --version | head -1)"
fi

install_vim_plug || true
write_coc_settings
install_clangd || true

log "Vim setup done. Open vim and run :PlugInstall once to fetch coc.nvim."
