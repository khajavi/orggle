# B-014: Config UX Commands (`orggle config` subcommands)

**Priority:** Tier 3 (Medium) - Improves configuration ergonomics
**Effort:** Medium (M - 6 hours)
**Dependencies:** None (but B-006's validation logic useful)

---

## Problem Statement

Configuration is edited by hand in `~/.config/orggle/config.yaml`. There is no way to:
- View current effective configuration
- Check what profile is active
- Set or update a single value without editing entire file
- Add a new profile from CLI
- Validate config with a dedicated command (see B-006)

**Users accustomed to `git config`, `kubectl config`, `aws configure` expect similar UX.**

---

## Proposed Solution

Introduce `orggle config` command family:

```bash
orggle config show [--profile <name>] [--json]   # Show effective config
orggle config get <key>                          # Get single value (dot notation)
orggle config set <key> <value>                  # Set single value (creates if missing)
orggle config delete <key>                       # Remove a key
orggle config profiles add <name> --api-token ... --project ...
orggle config profiles remove <name>
orggle config validate [--online]                # B-006 moved here
```

**Example:**

```bash
$ orggle config show
default_profile: work
profiles:
  work:
    api_token: ******** (env: WORK_TOKEN)
    default_project: Acme Corp
    tags: [work]

$ orggle config get profiles.work.default_project
Acme Corp

$ orggle config set profiles.work.default_project "New Project Name"
Saved.

$ orggle config profiles add personal --api-token $PERSONAL_TOKEN --project "Personal"
Added profile 'personal'
```

---

## Implementation Approach

This is a **significant refactor** because current code uses global argparse parser with only flags. We need subparsers.

### Restructure `create_parser()`

Add `subparsers = parser.add_subparsers(dest='command')`

Keep existing global flags (like `--profile`, `--batch`, etc.) as top-level for backward compatibility? Or move them under `sync` subcommand?

**Decision:** Maintain backward compatibility: existing usage `orggle journal.org` should continue working. So we can't force subcommand. Instead, use:

- If first positional argument looks like an org file (ends with .org or exists as file), treat as legacy mode (sync)
- Else if first positional is a command like "config", "version", etc., route to subcommand

This is messy.

Alternative: Introduce `orggle sync` as explicit subcommand for old functionality, and `orggle config ...` as separate. But that would break existing user habits. We could support both:

```bash
# Old style (no subcommand) still works for sync
orggle journal.org --from ...

# New style (explicit)
orggle sync journal.org --from ...
orggle config show
```

That’s cleaner: create a `sync` subcommand that has all current sync args. Keep old top-level parser for backward compat? Actually if we move all sync arguments under `sync`, the old command `orggle journal.org` without subcommand would no longer be recognized as sync—it would see "journal.org" as command, error.

So we need to either:
1. Keep current flat parser and also add subcommands separately (dual parser registration) - hacky
2. Break backward compatibility, but provide a wrapper or message. Given it's pre-1.0 (version 0.1.1), breaking change maybe acceptable? But many users may have scripts.

Better: Keep global parser, but add `config` as a special flag? Actually we can treat `config` as a pseudo-flag: `orggle config show`. That means the first positional argument "config" is captured as `org_file` currently. So we need special handling:

In `main()`:

```python
args = parser.parse_args()

if args.org_file == 'config':
    # handle_config_subcommand(args[1]? need subparser for config subcommands)
    # but we didn't use subparsers; we'd need manual command dispatch
    handle_config(args)
else:
    # regular sync
```

That's doable without subparsers: just parse `config` as org_file, then within `main()` branch.

For `orggle config show`, we'd parse `config` as org_file, and `show` as... nothing currently. Could add `config_action` argument with choices=('show','get','set',...) and make it a flag? Or treat second positional as config subcommand. We would need a second parser or manual.

Simpler: add a top-level argument `--config-cmd` that is None normally, but if user passes `--config-cmd show` we run config. But that's not natural UX.

Let's step back: The full UX of `orggle config` is nice but complex. Since B-014 is Medium priority and we already have B-006 (validate flag) which we could implement as `--validate-config`, maybe we postpone B-014 to later.

Given this is backlog spec, we can outline design but note it's larger effort requiring subcommand architecture.

I'll write spec for optional approach using `orggle-config` separate script? Or maintain as future major version.

Given the context, maybe just spec the design but mark as requires parser refactor.

---

## Design (if we adopt subcommands)

**Parser tree:**

```
orggle
├─ sync (default)
│   ├─ org_file (positional)
│   ├─ --profile
│   ├─ --batch
│   ├─ --day
│   ├─ --from/--to/--since/--until
│   ├─ --delete-existing
│   ├─ --dry-run
│   ├─ --yes
│   └─ ...other sync flags
├─ config
│   ├─ show [--profile] [--json]
│   ├─ get <key>
│   ├─ set <key> <value>
│   ├─ delete <key>
│   ├─ profiles add <name> --api-token ... --project ...
│   ├─ profiles remove <name>
│   └─ validate [--online]
└─ version (already exists as --version)
```

**Implementation files:**

- `orggle/cli.py`: main entry, parses subcommand, delegates
- `orggle/commands/sync.py`
- `orggle/commands/config.py`

**But we're in single-file right now.** Could still split later.

---

## For Backlog, Let's Keep It Simple

Instead of full subcommands, implement config flags incrementally:

1. `--validate-config` (B-006)
2. `--config-show` or `orggle --show-config`? Not great.
3. Maybe provide a separate executable `orggle-config` that only handles config. Install alongside. That avoids parser complexity in main orggle. Users run `orggle-config show`.

**Decision:** Go with separate `orggle-config` script. Add to repo: `orggle_config.py` with its own CLI. It imports config loading logic from `orggle.py` (need to refactor common code into `orggle/common.py`).

This is smarter: main orggle stays simple for sync; config tool focuses on config management.

**Files:**
- `orggle/config.py` (extract config functions)
- `orggle_config.py` (new entry point for config commands)

Then in `install.sh`, install both `orggle` and `orggle-config` symlinks.

---

## Spec for `orggle-config`

Commands:

```
orggle-config show [--profile <name>] [--json]
orggle-config get <key>               # jq-style path: profiles.work.default_project
orggle-config set <key> <value>
orggle-config delete <key>
orggle-config profiles add <name> --api-token $TOKEN --project "Name" [--tag TAG]
orggle-config profiles remove <name>
orggle-config validate [--online]
```

Uses same config file (`~/.config/orggle/config.yaml`).

---

## Effort Ref Estimate

- Extract config code into separate module: 4h
- Build `orggle-config` CLI: 4h
- Implement commands: show, get, set, validate: 4h
- Tests for config commands: 2h
- Update install script: 1h
- Docs: 2h
- **Total:** ~16h (L)

---

## Acceptance Criteria (High-level)

- [ ] Separate `orggle-config` command available
- [ ] `show` displays effective config, masks API token (shows ********), resolves env var names
- [ ] `get`/`set` work with dot notation paths
- [ ] `profiles add` creates new profile with required fields
- [ ] `validate` performs checks (B-006)
- [ ] Backward compatibility: old orggle usage unchanged
- [ ] Integration: `orggle` still works after config module extraction

---

## Status

This is a larger undertaking that would improve usability significantly but requires careful design. Consider scheduling after core improvements (B-001-B-006) are done.

---

**Status:** Planned (requires arch review)
**Created:** 2025-04-01
