# Platform id and containers

## Detection

`bin/workenv-platform.sh` (source it; do not execute):

```
WORKENV_PLATFORM=$(uname -m)-$(getconf GNU_LIBC_VERSION | sed 's/ /-/g')
# example: x86_64-glibc-2.34
```

If `getconf GNU_LIBC_VERSION` is empty, it probes `ldd --version` for musl, else `unknown-libc`.

Override: `export WORKENV_PLATFORM=...` **before** sourcing, and do **not** unset it. `~/.bashaux` always unsets it first so a container shell cannot inherit the host value.

`WORKENV_PREFIX=$WORKENV_ROOT/$WORKENV_PLATFORM`.

## Compatible PATH (`workenv_compatible_bin_path`)

Returns a colon-separated list:

1. `$WORKENV_PREFIX/bin` (current libc), even if that directory does not exist yet
2. every `$WORKENV_ROOT/<arch>-glibc-<ver>/bin` whose `<ver>` is **≤** current glibc (`sort -V`)

So on the Cactus CUDA image (glibc 2.36) with only a host prefix built:

```
/home/sbrandt/workenv/x86_64-glibc-2.36/bin:/home/sbrandt/workenv/x86_64-glibc-2.34/bin
```

`command -v vim` skips the empty 2.36 dir and finds the 2.34 vim. That binary **does** run on 2.36 (only needs `libc`, `libm`, `libtinfo.so.6`).

A 2.36-built binary would **not** be put on a 2.34 host PATH.

Musl prefixes are not mixed into the glibc fallback list.

## Entering an image

Typical:

```
apptainer shell --bind /work /work/sbrandt/etk/Cactus/cactus-cuda_latest.sif
# or
apptainer exec --bind /work IMAGE bash -l
```

`~/.bashrc` `SING_OPTS` already wants `/work` plus a few `/etc` files bound. Home is bound by default.

On interactive login shells, `~/.bashrc` → `~/.bashaux` redetects libc. Non-login `apptainer exec IMAGE vim` may keep the **host** PATH; that can be fine (host vim on newer glibc) or fatal (host vim on *older* glibc). Prefer `bash -l` inside images.

## When the fallback is not enough

If the image libc is *older* than every built prefix, host binaries will fail (`GLIBC_2.34 not found`). Then build a prefix **inside** the image:

```
OPENSSL_BUNDLE=1 PYTHON_OPTIMIZE=0 envup -y
# or from the clone:
./install.sh -y
```

That creates e.g. `x86_64-glibc-2.28/` next to the host prefix. Both stay on disk; PATH picks the matching one.

## `PYTHONUSERBASE` across enter/exit

`~/.bashaux` resets `PYTHONUSERBASE` to `$HOME/.local/$WORKENV_PLATFORM` when it is unset, equal to `$HOME/.local`, or already a workenv-style `$HOME/.local/*-glibc-*` (or musl / unknown-libc). Custom values (`/usr/local/userbase`, `~/.rpi3`, a venv) are left alone.

`~/.bashrc` (user file, after bashaux) may still override this for old Phylanx images and Raspberry Pi slurm partitions, and if `/usr/local/userbase` exists.
