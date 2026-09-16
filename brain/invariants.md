# Invariants

Treat these as load-bearing. Violating one is the usual reason "it works on the host and dies in the image."

## 1. Native binaries go in `$WORKENV_PREFIX`, never `~/.local/bin`

```
WORKENV_ROOT    = clone of this repo (e.g. $HOME/workenv)
WORKENV_PLATFORM = $(uname -m)-$(getconf GNU_LIBC_VERSION | sed 's/ /-/g')
                 e.g. x86_64-glibc-2.34
WORKENV_PREFIX  = $WORKENV_ROOT/$WORKENV_PLATFORM
```

Python, vim, node, clangd, grok, and claude install into `$WORKENV_PREFIX/bin`.

`~/.local/bin` is **not** on PATH. `~/.bashrc` even comments that line out. Official grok/claude installers default there; workenv wrappers relocate them. See [cli-tools.md](cli-tools.md).

pip `--user` installs go to `PYTHONUSERBASE=$HOME/.local/$WORKENV_PLATFORM`, not `$HOME/.local`.

## 2. Portable vs native

| Tree | What belongs there | Shared across host/container? |
|------|--------------------|-------------------------------|
| `bin/`, `py/` | scripts, pure-Python modules | yes (this git repo) |
| `$WORKENV_PLATFORM/` | ELF binaries, libs, vim runtime, node | no — libc-bound |
| `~/.local/$WORKENV_PLATFORM/` | pip user site | no — wheels are libc-bound |
| `~/.vim/`, `~/.vimrc`, `~/.bashaux` | dotfiles | yes (home is bind-mounted into images) |

Do not drop a glibc-2.34 binary into `bin/`. Do not put a portable shell script only in the platform prefix.

## 3. Never put `$WORKENV_PREFIX` on `LD_LIBRARY_PATH`

Platform Python/OpenSSL are built with RUNPATH. Prepending a bundled `libssl.so` shadows the distro one and breaks system `curl`/`wget` (`OPENSSL_3.2.0 not found` and similar).

## 4. `~/.bashaux` is generated

`install.py` **overwrites** `~/.bashaux` every run. Edit the template string in `install.py`, then re-run `./install.sh --skip-python --skip-vim` (or `python3 install.py` from the repo root). Hand-edits to `~/.bashaux` vanish on `envup`. See [edit-rules.md](edit-rules.md).

`~/.bashrc` is **not** owned by workenv except: it must contain `source ~/.bashaux`, and workenv strips the official grok installer PATH block from it.

## 5. Redetect platform on every shell

`~/.bashaux` unsets `WORKENV_PLATFORM` and re-sources `bin/workenv-platform.sh`. Host and container often have different glibc. A leftover `WORKENV_PLATFORM` from the parent shell is wrong.

## 6. Older-glibc prefixes may be used as fallback, never newer

glibc is backward compatible: a binary built on 2.34 runs on 2.36. The reverse does not.

`workenv_compatible_bin_path` puts `$WORKENV_PREFIX/bin` first, then other `$WORKENV_ROOT/<arch>-glibc-*` prefixes whose glibc version is **≤** the current one. That is why host vim/node still work inside the Cactus 2.36 image before that image has its own prefix.

Do not add a *newer*-glibc prefix onto a *older* host PATH.

## 7. No sudo

Bootstrap, vim, node, clangd, Python, grok, and claude all install into home/workenv. If a change needs root, it does not belong here.

## 8. Do not curl-pipe official CLI installers without the workenv wrappers

```
# wrong
curl -fsSL https://x.ai/cli/install.sh | bash
curl -fsSL https://claude.ai/install.sh | bash

# right
grok-install.sh
claude-install.sh
```

The wrappers set `GROK_BIN_DIR` / copy the claude binary into `$WORKENV_PREFIX` and undo `~/.local` / bashrc pollution.
