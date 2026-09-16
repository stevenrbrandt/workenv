# Grok and Claude CLIs

Both official installers ignore workenv and drop binaries where PATH cannot see them. Always use the wrappers in `bin/`.

## Grok (`bin/grok-install.sh`)

Official: `curl -fsSL https://x.ai/cli/install.sh | bash`

That script:

- Downloads a **static pie** linux-x86_64 binary to `~/.grok/downloads/`
- Links `~/.grok/bin/grok` and `agent` (or `$GROK_BIN_DIR`)
- If `GROK_BIN_DIR` is not already on PATH, symlinks into `~/.local/bin`
- **Always** writes a `PATH=$HOME/.grok/bin` block into `~/.bashrc`, even when `GROK_BIN_DIR` is set

The wrapper:

```
export GROK_BIN_DIR=$WORKENV_PREFIX/bin
# run official installer
# strip the bashrc/bash_profile grok installer block
# rm ~/.local/bin/{grok,agent} if they are shims
```

Config/auth/completions stay under `~/.grok/` (`GROK_HOME`, `auth.json`, `config.toml`). That is fine — those are data, not libc-bound ELF. Only the launcher belongs in the prefix.

Grok is statically linked, so a 2.34-prefix grok also runs in a 2.36 image via the PATH fallback.

Update: re-run `grok-install.sh` (optional version arg). Do not `curl | bash` the official script.

## Claude (`bin/claude-install.sh`)

Official: `curl -fsSL https://claude.ai/install.sh | bash` then `$binary install`

Native claude is a dynamically linked bun ELF (`glibc 2.30+`). It **hardcodes** `~/.local/bin/claude` → `~/.local/share/claude/versions/<ver>`. There is no useful prefix flag.

The wrapper runs the official installer, then:

```
cp ~/.local/bin/claude  →  $PREFIX/share/claude/versions/<ver>
ln -sfn that            →  $PREFIX/bin/claude
rm -f ~/.local/bin/claude
```

`~/.local/share/claude` may still grow on `claude update`. After an update, re-run `claude-install.sh` so the prefix symlink tracks the new version. Config stays in `~/.claude/` / `~/.claude.json`.

## `install.py` migration

`ensure_prefix_cli_bins()` copies/links existing grok/claude into the current prefix if the prefix launchers are missing. Safe to run repeatedly. It will delete `~/.local/bin/claude` after copying.

## Verify

```
command -v grok claude vim node
# expect $WORKENV_ROOT/$WORKENV_PLATFORM/bin/...
grok --version
claude --version
```

Inside an image, the 2.34 prefix paths are OK until a 2.36 prefix is built.
