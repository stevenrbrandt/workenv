# Platform Python

## Why

Cluster / image `python3` is often 3.6–3.9, missing `_ctypes`, or missing `ssl`. Scientific work (and `install.py` itself) wants 3.13 with those modules. pip cannot add C stdlib modules; they have to be built in.

## Build

`bin/mk-python.sh` → `$WORKENV_PREFIX`.

Default `PY_VER=3.13.14`. Smoke-tests `_ctypes`, `ssl`, `_lzma`, `_sqlite3`. `--force` rebuilds.

Dependencies, system or bundled into the prefix:

- libffi (`_ctypes`)
- OpenSSL (`ssl`) — system if present, else built, or always built with `OPENSSL_BUNDLE=1`
- xz/liblzma (`_lzma`)
- sqlite3 (`_sqlite3`)

`PYTHON_OPTIMIZE=0` skips PGO (much faster; `install.sh` sets this by default).

Self-contained image build:

```
OPENSSL_BUNDLE=1 PYTHON_OPTIMIZE=0 ./install.sh --force-python
```

Python/OpenSSL use RUNPATH into the prefix. **Do not** add the prefix to `LD_LIBRARY_PATH` (breaks distro curl). See [invariants.md](invariants.md).

## `PYTHONUSERBASE`

```
export PYTHONUSERBASE=$HOME/.local/$WORKENV_PLATFORM
```

Keeps native wheels from a 2.34 host out of a 2.36 container site-packages and vice versa. `~/.bashaux` refreshes this when entering/leaving images if the value looks like a workenv platform path.

`alias pip3='python3 -m pip'` in bashaux.

## If platform Python is missing

`install.sh --skip-python` uses whatever `python3` is on PATH and warns. `install.py` still runs (it is 3.x, has a urllib fallback). Features that need 3.13 / `_ctypes` will not.

On this host the 2.34 prefix currently has vim/node/grok/claude; Python may still be absent until someone answers yes to the install.sh prompt.
