# HPC / this cluster

## Machine

- Hostnames like `rostam1.rostam.cct.lsu.edu` (CCT/LSU Rostam)
- Shared home: `/home/sbrandt`
- Scratch/work: `/work/sbrandt` (and other `/work/<user>`)
- Apptainer and Singularity both installed (`/usr/bin/apptainer`, `/usr/bin/singularity`)

## Cactus CUDA image

```
/work/sbrandt/etk/Cactus/cactus-cuda_latest.sif
```

(~6GB, Docker bootstrap `stevenrbrandt/cactus-cuda`, glibc **2.36**, Debian-ish `/usr/bin/vim` 9.0). User shorthand `/work/etk/Cactus/*.sif` means this tree.

Enter:

```
apptainer shell --bind /work /work/sbrandt/etk/Cactus/cactus-cuda_latest.sif
```

Home is bound automatically. After a login shell, `WORKENV_PLATFORM` becomes `x86_64-glibc-2.36`. Vim/node/grok come from the 2.34 prefix until someone builds a 2.36 prefix.

## Cactus checkouts (not this repo)

| Path | What |
|------|------|
| `/work/sbrandt/etk/Cactus` | working Cactus tree + the `.sif` |
| `~/.cactup/cacti/refine-building/Cactus` | cactup-managed checkout |
| `~/etk` | present, often empty |
| `etc/cactus-docs.md` | flesh/thorn API reference for agents |
| `etc/cactus-build-ref.md` | CST / ThornList / SimFactory build model |

`bin/et-devel.sh`, `et-release.sh`, `et-test.sh` fetch GetComponents + einsteintoolkit.th.

`bin/simfactory-configure.py` is a large helper for SimFactory optionlists.

`cactup-dev` in `~/.bashrc` runs `cargo run --manifest-path $HOME/repos/Cactup/Cargo.toml`.

## Spack

`~/.bashrc` sets `SPACK_ROOT` to the first existing of `$HOME/spack`, `/work/$USER/spack`, `/spack`, then sources `setup-env.sh`. bashaux also reloads spack if `SPACK_ROOT` changes.

`bin/spack-init.sh`, `spack-load.sh`, `spack-cfg2.sh`, `spack-reconfigure.py`, `spackc.py` wrap common flows.

## Other images / leftovers in `~/.bashrc`

Old Phylanx Singularity images, Jetlag, Raspberry Pi slurm partitions (`rpi3`, `rpi4`) set `PYTHONUSERBASE` to special trees. They run **after** bashaux. Do not "clean those up" unless asked; they are unrelated to the Cactus image but they can override `PYTHONUSERBASE` if `/usr/local/userbase` exists inside a container.

`SINGULARITY_CACHEDIR=/work/sbrandt/sing-cache`.

## Bind mounts

When debugging "works on host, missing in image", check whether `/work`, the SIF, and home are visible. `SING_OPTS` in bashrc binds `/work` plus a few `/etc` files. Extra GPUs/devices are image-specific (`cactus-cuda`).
