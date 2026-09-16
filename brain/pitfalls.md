# Pitfalls

## Official grok/claude installers vs workenv

**Looks like:** `claude: command not found` after a successful install; or grok works only because `~/.bashrc` grew a `# >>> grok installer >>>` PATH block.

**Why:** binaries landed in `~/.local/bin` or `~/.grok/bin`. Workenv PATH is prefix + `workenv/bin` + `~/bin`. `~/.local/bin` is intentionally off PATH.

**Fix:** `grok-install.sh` / `claude-install.sh`, not `curl | bash`. `install.py` also migrates leftovers into the prefix and strips the grok bashrc block. Do not put that block back.

## Vim errors inside the Cactus SIF

**Looks like:**

```
[coc.nvim] "node" is not executable, checkout https://nodejs.org/en/download/
```

sometimes plus `Press ENTER` on every vim launch. `which vim` is `/usr/bin/vim` (Debian 9.0).

**Why:** image glibc ≠ host glibc, so `WORKENV_PREFIX` points at an empty directory. System vim still loads `~/.vimrc` (home is bound) and coc.nvim, but node is in the host prefix.

**Fix already in tree:** `workenv_compatible_bin_path`. If it regresses, `command -v vim` / `node` inside the image are the canary. Host-built vim 9.1 **does** run on this image (needs `libtinfo.so.6`).

If the image libc is *older* than the host, fallback cannot help — build a prefix inside the image (`OPENSSL_BUNDLE=1 ./install.sh -y`).

## `LD_LIBRARY_PATH=$WORKENV_PREFIX/lib`

**Looks like:** system `curl` / `wget` die with OpenSSL symbol-version errors after `envup`.

**Why:** bundled libssl shadows distro libssl. Prefix binaries already have RUNPATH.

**Fix:** never export that. Comments in `install.sh` and bashaux exist specifically because this was hit.

## Hand-editing `~/.bashaux`

**Looks like:** a PATH/alias fix works until the next `envup` or `install.py`, then vanishes.

**Fix:** edit the template in `install.py`. See [edit-rules.md](edit-rules.md).

## `install.py` not run from repo root

**Looks like:** `FileNotFoundError: vim/colors/LecturedInjury.vim`.

**Fix:** `cd $WORKENV_ROOT` first. `install.sh` does this.

## bashaux `.format` braces

**Looks like:** `KeyError` while running `install.py`, bashaux not updated.

**Fix:** double braces in the template except `{here}`.

## `PYTHONUSERBASE` stuck on the host platform inside a container

**Looks like:** pip `--user` installs into `~/.local/x86_64-glibc-2.34` even though `WORKENV_PLATFORM` is 2.36.

**Why:** older bashaux only reset PYTHONUSERBASE when unset or exactly `$HOME/.local`. Parent shell exported the host value.

**Fix in current bashaux:** also reset values matching `$HOME/.local/*-glibc-*`. User bashrc can still override (`/usr/local/userbase` if that directory exists in the image).

## Non-login `apptainer exec IMAGE vim`

May not source bashaux, so you get whatever PATH the parent exported. Use `bash -lc` or `apptainer shell` for interactive work.

## coc on old system Vim

RHEL/Alma 8–9 system vim is 8.2. Without the version guard, coc throws Vim9 errors on startup. The guard skips coc; Tab still indents. Do not "fix" that by forcing Plug on 8.2 — build prefix vim instead.

## `claude update` vs prefix

`claude update` writes under `~/.local/share/claude/versions/` and may recreate `~/.local/bin/claude`. Prefix `bin/claude` then points at a stale copy. Re-run `claude-install.sh`.

## Prompt skipped, Python/Vim missing

`install.sh` defaults to **no** without `-y` and without a TTY. `envup` after `git pull` will not build Python unless you pass `-y` or answer `y` on `/dev/tty`.
