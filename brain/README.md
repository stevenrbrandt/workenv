# workenv brain

Read this directory before changing how shells, PATH, Python, Vim, grok, claude, or containers work.

This repo is Steven Brandt's portable Linux work environment. Clone it onto a new machine, run `./install.sh`, and the home directory (vim, PATH, scripts, git/ssh helpers) matches every other machine. Native binaries are **not** shared blindly across hosts and containers: they live in a per-libc prefix.

## Read in this order

1. [invariants.md](invariants.md) — rules that, if broken, make the environment fail
2. [layout.md](layout.md) — what is source vs generated vs platform toolchain
3. [platform.md](platform.md) — `WORKENV_PLATFORM`, host vs apptainer, PATH fallback
4. [shell.md](shell.md) — `~/.bashaux` vs `~/.bashrc`, env vars, `envup`
5. [install.md](install.md) — bootstrap (`install.sh` / `install.py` / `mk-*.sh`)
6. [vim.md](vim.md) — vim, node, coc.nvim, clangd
7. [python.md](python.md) — platform Python, `PYTHONUSERBASE`, OpenSSL
8. [cli-tools.md](cli-tools.md) — grok and claude install into the prefix, not `~/.local`
9. [hpc.md](hpc.md) — this cluster (rostam), Cactus SIF images, spack, cactup
10. [scripts.md](scripts.md) — map of `bin/` (only the ones that matter)
11. [edit-rules.md](edit-rules.md) — where to edit so a change survives `envup`
12. [pitfalls.md](pitfalls.md) — failures already hit and how they look

Cactus/Einstein Toolkit *code* knowledge lives in `etc/cactus-docs.md` and `etc/cactus-build-ref.md`. This brain is about making the *environment* work, not about writing thorns.

## Current machine snapshot (rostam, 2026-09)

| Item | Value |
|------|--------|
| Host | `rostam1.rostam.cct.lsu.edu` |
| Home | `/home/sbrandt` |
| This repo | `/home/sbrandt/workenv` |
| Host libc | glibc 2.34 → prefix `x86_64-glibc-2.34/` |
| Typical Cactus image | `/work/sbrandt/etk/Cactus/cactus-cuda_latest.sif` (glibc 2.36) |
| Image from | Docker `stevenrbrandt/cactus-cuda` |

That snapshot goes stale. Re-detect with `bin/workenv-platform.sh` and `getconf GNU_LIBC_VERSION`.
