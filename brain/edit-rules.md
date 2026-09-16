# Where to edit

If a change should survive `envup` / `install.sh` / `python3 install.py`, put it in the **source** listed here. Editing the generated file is a waste.

| Want to change | Edit this | Then |
|----------------|-----------|------|
| PATH, aliases, `envup`, locale, history, PYTHONUSERBASE logic | the bashaux **template string** in `install.py` | `python3 install.py` from repo root (or `./install.sh --skip-python --skip-vim`) |
| Platform detection / compatible prefix PATH | `bin/workenv-platform.sh` | `source ~/.bashrc` (bashaux sources it live; no regenerate needed for the function, but the call site lives in the bashaux template) |
| Bootstrap flags / python+vim prompts | `install.sh` | just commit; next `envup` uses it |
| Python build | `bin/mk-python.sh` | `./install.sh --force-python` |
| Vim build / node version / clangd | `bin/mk-vim.sh` and/or `NODE_VER`/`CLANGD_VER` in `install.py` | `./install.sh --skip-python` or `mk-vim.sh --force` |
| grok/claude install location | `bin/grok-install.sh`, `bin/claude-install.sh`, plus `ensure_prefix_cli_bins()` in `install.py` | re-run the wrapper |
| Default vimrc for **new** machines | `VIMRC_DEFAULT` / `VIM_COC_PLUG_BLOCK` in `install.py` | existing `~/.vimrc` is only patched, not replaced |
| LecturedInjury colorscheme | `vim/colors/LecturedInjury.vim` | copy is skipped if `~/.vim/colors/LecturedInjury.vim` already exists |
| torture colorscheme | the inline string in `install.py` | same: only written if missing |
| Human install docs | `README.md` | keep it consistent with this brain |
| LLM environment docs | `brain/*.md` (this tree) | |
| Cactus API / build knowledge | `etc/cactus-docs.md`, `etc/cactus-build-ref.md` | unrelated to PATH/vim |
| Phylanx, spack-root search, cactup, SING_OPTS | `~/.bashrc` (user-owned) | workenv will not overwrite, except grok-block strip and `source ~/.bashaux` |

## `install.py` template escaping

The bashaux body is a Python `"""...""".format(here=here)` string. Every bash `{` `}` that is not `{here}` must be doubled: `{{` `}}`. `${{PYTHONUSERBASE:-}}`, `${{_arch}}`, etc. If you add a `{` and forget, `install.py` throws `KeyError` and you get no bashaux.

## After edits, verify

Host:

```
source ~/.bashrc
echo $WORKENV_PLATFORM $WORKENV_PREFIX
command -v vim node grok claude python3
```

Inside the Cactus image:

```
apptainer exec --bind /work /work/sbrandt/etk/Cactus/cactus-cuda_latest.sif bash -lc \
  'echo $WORKENV_PLATFORM; command -v vim node; timeout 8 vim --not-a-term -c messages -c qa!'
```

Expect `WORKENV_PLATFORM=x86_64-glibc-2.36`, vim/node from a ≤2.36 prefix, and **no** `[coc.nvim] "node" is not executable`.
