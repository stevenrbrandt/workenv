# Vim, node, coc.nvim, clangd

## Goal

A modern Vim (9.1+) with coc.nvim + clangd for C/C++, no sudo, no manual `:PlugInstall`.

## Pieces

| Piece | Where | Provider |
|-------|--------|----------|
| `vim` 9.1 | `$WORKENV_PREFIX/bin/vim` | `bin/mk-vim.sh` (`--prefix=$PREFIX`, huge, no GUI) |
| runtime | `$WORKENV_PREFIX/share/vim/vim91` | same build (`--prefix` is compiled in) |
| `node` | `$WORKENV_PREFIX/bin/node` | official linux-x64/arm64 tarball (default `NODE_VER=22.18.0`) |
| vim-plug | `~/.vim/autoload/plug.vim` | downloaded |
| coc.nvim | `~/.vim/plugged/coc.nvim` | `git clone --branch release` |
| clangd | prefix `bin/clangd` or system | official GitHub zip if missing |
| vimrc | `~/.vimrc` | `install.py` |
| coc settings | `~/.vim/coc-settings.json` | `install.py` |
| colors | `~/.vim/colors/{LecturedInjury,torture}.vim` | install.py |

`mk-vim.sh` skips the build if a vim on PATH/prefix is already `>= MIN_VIM` (default 9.1). `--force` rebuilds.

Vim is linked against `libc`, `libm`, `libtinfo.so.6` only. That is why the host 9.1 binary runs inside Debian-based images that ship `libtinfo.so.6`.

## vimrc contract

coc.nvim needs Neovim 0.8+ **or** Vim 9.0.0438+ (Vim9 script). The plug block is gated:

```
if filereadable(expand('~/.vim/autoload/plug.vim')) && (has('nvim-0.8.0') || has('patch-9.0.0438'))
```

`<Tab>` mappings are gated on `~/.vim/plugged/coc.nvim` existing, otherwise Tab throws `E117`.

`install.py` will patch an unguarded coc block. It does **not** replace a user's `colorscheme` line. On this machine `~/.vimrc` uses `colorscheme torture`.

If cwd is gone (deleted dir, stale mount), vimrc `cd`s to `$HOME` so coc.nvim will start.

## The Cactus-image failure (already fixed in PATH)

Symptom inside `/work/sbrandt/etk/Cactus/*.sif`:

```
[coc.nvim] "node" is not executable, checkout https://nodejs.org/en/download/
```

Cause: image glibc 2.36 → PATH used empty `x86_64-glibc-2.36/bin` → `/usr/bin/vim` (Debian 9.0) → coc loaded → node lives in the 2.34 prefix, not on PATH.

Fix: `workenv_compatible_bin_path` (see [platform.md](platform.md)). After `source ~/.bashrc` inside the image, `command -v vim` and `command -v node` must be the 2.34 (or image-local) prefix binaries, not `/usr/bin/vim`.

## Do not

- Point `VIMRUNTIME` at another prefix's `share/vim` by hand
- Run `:PlugInstall` as the install path; the clone is enough
- Expect system Vim 8.2 (RHEL 9) to load coc — the version guard skips it, which is correct
