# My linux work environment.

This is just a convenience that I use to set up my home directory, favorite scripts, vim settings, etc. so that when I get to a new machine I can instantly get it working the way I want. :)

## Install

```bash
# Bootstrap Python 3.13.14 (platform-specific, with _ctypes), optional vim/clangd, then dotfiles:
./install.sh

# Faster Python build (skip PGO):
PYTHON_OPTIMIZE=0 ./install.sh

# Options:
./install.sh --force-python   # rebuild Python even if smoke tests pass
./install.sh --skip-vim
./install.sh --skip-python    # only run install.py (needs an existing python3)

# Python SSL (pip HTTPS): mk-python uses system OpenSSL if present, otherwise
# builds it into the platform prefix. For apptainer/cluster when the image has
# no libssl, prefer a self-contained build:
OPENSSL_BUNDLE=1 PYTHON_OPTIMIZE=0 ./install.sh --force-python
```

Layout:

- `bin/`, `py/` — portable scripts and modules (this repo)
- `$WORKENV_PLATFORM/` — e.g. `x86_64-glibc-2.35/` — Python, vim, clangd, libs  
  (`$(uname -m)-$(getconf GNU_LIBC_VERSION | sed 's/ /-/g')`; see `bin/workenv-platform.sh`)
- `~/.local/$WORKENV_PLATFORM/` — `pip install --user` / `PYTHONUSERBASE` (keeps native wheels per libc)

Shell config is written to `~/.bashaux` (sourced from `~/.bashrc`). Refresh with `envup` or re-run `./install.sh`.

After first vim open, run `:PlugInstall` once to fetch coc.nvim (clangd hooks for C/C++).
