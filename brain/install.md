# Install / bootstrap

## Entry point

```
./install.sh [flags]
```

from the clone. Needs network, a C compiler for Python/Vim builds, and write access to the clone + `$HOME`.

Flags: `--force-python`, `--skip-python`, `--skip-vim`, `--skip-dotfiles`, `-y`/`--yes`.

Env: `PY_VER` (default 3.13.14), `PYTHON_OPTIMIZE` (install.sh defaults this to `0` = skip PGO, faster), `OPENSSL_BUNDLE=1` (build OpenSSL into the prefix; needed in images with no libssl), `WORKENV_YES=1`.

## Sequence

1. Source `bin/workenv-platform.sh`, set `PREFIX=$WORKENV_ROOT/$WORKENV_PLATFORM`
2. Unless `--skip-python`: prompt, then `bin/mk-python.sh`
3. Put prefix + `bin/` on PATH; set `PYTHONUSERBASE`
4. Unless `--skip-vim`: prompt, then `bin/mk-vim.sh` (errors are warnings; install continues)
5. Unless `--skip-dotfiles`: run `install.py` with the platform python if present, else system python3

Non-interactive (no `/dev/tty`) skips Python and Vim unless `-y` or `--force-python`.

## `install.py` (must run from `$WORKENV_ROOT`)

It uses a relative open of `vim/colors/LecturedInjury.vim`.

Side effects:

- Ensure `source ~/.bashaux` in `~/.bashrc`
- Strip official grok installer PATH block from `~/.bashrc` / `~/.bash_profile`
- **Overwrite** `~/.bashaux` from the template string in `install.py` (braces doubled for `.format(here=...)`)
- `ensure_vimrc()` — write or patch coc.nvim guards
- Copy colorschemes to `~/.vim/colors`
- Write a default `~/.gitconfig` only if missing
- vim-plug, Node into prefix, clone coc.nvim, clangd into prefix, `coc-settings.json`
- `ensure_prefix_cli_bins()` — if grok/claude already exist under `~/.grok` / `~/.local`, link/copy them into `$WORKENV_PREFIX/bin` and remove `~/.local/bin/{grok,agent,claude}`
- Append known SSH public keys to `~/.ssh/authorized_keys`; `chmod 700 ~/.ssh`, `chmod 755 $HOME`

`pkg_install()` exists for distro packages but the no-sudo path is the one that matters.

## Refresh after a code change to bashaux

```
cd $WORKENV_ROOT
./install.sh --skip-python --skip-vim
# or: python3 install.py
source ~/.bashrc
```

## New machine

```
git clone <this-repo> ~/workenv
cd ~/workenv
./install.sh          # answer y for python/vim if you want them
grok-install.sh       # optional
claude-install.sh     # optional
```

Then open a new shell.
