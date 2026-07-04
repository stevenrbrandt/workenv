#!/bin/bash
# install_python13.sh - Builds latest Python 3.13.x into ~/workenv (no sudo)

#set -euo pipefail

PREFIX="$HOME/workenv"
echo "Installing latest Python 3.13.x to $PREFIX/bin"
mkdir -p "$PREFIX"

# --- Detect latest 3.13.x version robustly ---
echo "Detecting latest Python 3.13 release..."
LATEST=$(curl -s https://www.python.org/downloads/ \
  | grep -oP 'Python 3\.13\.\K[0-9]+' \
  | sort -n | tail -1)

if [[ -z "$LATEST" ]]; then
    echo "WARNING: Could not auto-detect latest version, falling back to 3.13.14"
    LATEST=14
fi

TARBALL="Python-3.13.${LATEST}.tar.xz"
URL="https://www.python.org/ftp/python/3.13.${LATEST}/${TARBALL}"

echo "Latest detected: 3.13.${LATEST}"
echo "Downloading from: $URL"

# --- Download with explicit check ---
cd /tmp
rm -f "$TARBALL" 2>/dev/null || true

if ! wget -q --show-progress "$URL" -O "$TARBALL"; then
    echo "ERROR: wget failed to download $URL"
    echo "Check your internet connection or try manually:"
    echo "  wget $URL"
    exit 1
fi

if [[ ! -s "$TARBALL" ]]; then
    echo "ERROR: Downloaded file is empty or missing: $TARBALL"
    exit 1
fi
echo "Download successful."

# --- Extract with check ---
if ! tar -xf "$TARBALL"; then
    echo "ERROR: tar extraction failed for $TARBALL"
    exit 1
fi

DIR="Python-3.13.${LATEST}"
if [[ ! -d "$DIR" ]]; then
    echo "ERROR: Expected source directory not found: $DIR"
    exit 1
fi
cd "$DIR"
echo "Extraction successful."

# --- Configure ---
echo "Configuring..."
if ! ./configure --prefix="$PREFIX" \
                 --enable-optimizations \
                 --enable-shared \
                 --with-ensurepip=install; then
    echo "ERROR: ./configure failed"
    exit 1
fi

# --- Build ---
echo "Building (this will take a while)..."
if ! make -j "$(nproc)"; then
    echo "ERROR: make failed"
    exit 1
fi

# --- Install ---
echo "Installing..."
if ! make altinstall; then
    echo "ERROR: make altinstall failed"
    exit 1
fi

# --- Symlinks ---
ln -sf "$PREFIX/bin/python3.13" "$PREFIX/bin/python" || true
ln -sf "$PREFIX/bin/pip3.13"    "$PREFIX/bin/pip"    || true

echo "***********************************"
echo "SUCCESS: Python 3.13.${LATEST} installed to $PREFIX"
echo "Add to your PATH:"
echo "  export PATH=\"$PREFIX/bin:\$PATH\""
echo "Verify with: $PREFIX/bin/python --version"
