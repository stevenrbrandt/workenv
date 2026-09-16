# `bin/` map

Everything in `bin/` is on PATH (`$WORKENV_ROOT/bin`). These are the ones that affect the environment or Cactus workflow. The rest are personal utilities (bookmarks, encryption, writing tools); ignore them unless the user names them.

## Environment (load-bearing)

| Script | Role |
|--------|------|
| `workenv-platform.sh` | source: `WORKENV_PLATFORM`, `workenv_compatible_bin_path` |
| `mk-python.sh` | build Python into the prefix |
| `mk-vim.sh` | build vim 9.1, node, coc, clangd helpers |
| `grok-install.sh` | grok CLI → prefix |
| `claude-install.sh` | claude CLI → prefix |
| `long-cmd-notify.sh` | sourced by bashaux; terminal-title hourglass |

## Cactus / Einstein Toolkit

| Script | Role |
|--------|------|
| `et-devel.sh` / `et-release.sh` / `et-test.sh` | checkout ET via GetComponents |
| `simfactory-configure.py` | SimFactory optionlist / machine helper |
| `sim-report.sh` | simulation reporting |
| `carpetx-spack-install.sh` | CarpetX via spack |
| `build-amrex.sh` | AMReX |
| `vix` | open `file:line`, remap `configs/*/build` paths back to arrangement sources |

## Containers / cluster

| Script | Role |
|--------|------|
| `sing-build.sh` | `singularity build` into `/work/sbrandt/images` |
| `singssh` | ssh + `singularity exec` using `$SINGULARITY_CONTAINER` |
| `auth-cmd.sh` | force commands through a singularity image listed in `~/sing.txt` |
| `unslurm.py` | slurm env cleanup |
| `run-batch.py` | batch jobs |
| `mpirun.py` | mpirun wrapper |

## Spack

`spack-init.sh`, `spack-load.sh`, `spack-cfg2.sh`, `spack-reconfigure.py`, `spackc.py`.

## Git helpers

`gitdiff`, `git_diff_wrapper`, `to-git.sh`, `upstream.sh`, `unshallow.sh`, `urepos`, `reponator`, `theirs.py`.

## Backup of files being edited

`vback` / `vbackup` / `vsave` / `vrestore` / `vfindbackup` / `vtouch` — versioned backup around editor sessions. `any` dispatches a file to a viewer and often calls `vback` first.

When changing environment behavior, you almost always want `workenv-platform.sh`, `install.sh`, `install.py`, or the `mk-*` / `*-install.sh` wrappers — not a random script in this list.
