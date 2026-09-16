# Layout

Repo root is `$WORKENV_ROOT` (on this machine `/home/sbrandt/workenv`).

```
workenv/
  README.md              human install notes (keep in sync with behavior)
  install.sh             bootstrap: python, vim, then install.py
  install.py             generates ~/.bashaux, vimrc/coc helpers, ssh keys, grok/claude shims
  brain/                 this LLM onboarding set
  bin/                   portable scripts (on PATH via ~/.bashaux)
  py/                    portable Python modules (on PYTHONPATH)
  vim/colors/            source for LecturedInjury.vim (copied to ~/.vim/colors)
  etc/                   reference docs (Cactus, coding agents, gnuplot, crontab)
  x86_64-glibc-2.34/     THIS MACHINE's toolchain (untracked, not in git)
  x86_64-glibc-2.NN/     other prefixes appear when you install inside other libcs
```

Platform prefixes are **not** committed. They are large (node, vim runtime, claude ~200MB). They show up as untracked files; leave them untracked.

## Generated / home-side files (not in this repo)

| Path | Owner | Notes |
|------|--------|--------|
| `~/.bashaux` | `install.py` | **overwritten** each run |
| `~/.bashrc` | user + workenv | workenv only appends `source ~/.bashaux` and strips grok installer block |
| `~/.vimrc` | `install.py` `ensure_vimrc()` | created or coc-block patched; existing colorscheme left alone |
| `~/.vim/autoload/plug.vim` | mk-vim / install.py | vim-plug |
| `~/.vim/plugged/coc.nvim` | mk-vim / install.py | cloned `release` branch |
| `~/.vim/colors/{LecturedInjury,torture}.vim` | install.py | torture inlined in install.py if missing |
| `~/.vim/coc-settings.json` | install.py | clangd path |
| `~/.gitconfig` | install.py | only if missing |
| `~/.ssh/authorized_keys` | install.py | appends known public keys |

## `$WORKENV_PREFIX` contents (example: `x86_64-glibc-2.34/`)

```
bin/python3.13   (if mk-python.sh has been run)
bin/vim          workenv-built 9.1 (mk-vim.sh)
bin/node npm     official Node tarball (for coc.nvim)
bin/clangd       optional official clangd zip
bin/grok agent   symlinks into ~/.grok/downloads/ (static pie)
bin/claude       symlink to share/claude/versions/<ver>
share/vim/vim91  vim runtime (VIMRUNTIME)
share/claude/versions/<ver>
```

On this host, Python may not yet be in the prefix even if vim/node are. `install.sh` prompts `[y/N]` and defaults to skip.

## Home is shared with containers

Apptainer/Singularity bind-mount `$HOME` by default. Dotfiles and this repo are visible inside the image. The *libc* is not. That is the whole reason for `$WORKENV_PLATFORM`.
