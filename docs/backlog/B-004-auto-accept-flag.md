# B-004: Add `--yes` Flag for Non-Interactive Automation

**Priority:** Tier 1 (Critical) - Enables scripting, cron jobs, CI/CD
**Effort:** Extra Small (XS - 1 hour)
**Dependencies:** None

---

## Problem Statement

Orggle is fundamentally an interactive tool. By default, it prompts users to confirm each entry or day before syncing. This is great for interactive use but **blocks automation**:

- Cannot run from cron jobs (no TTY)
- Cannot pipe or script without expect/fake-tty
- Users must manually press Enter/y for every sync
- CI/CD integration impossible (e.g., "auto-sync my work org file every hour")

**Workarounds exist but are hacky:**
```bash
echo "yyyy" | ./orggle journal.org  # but 'y' is per-entry, not enough
yes | ./orggle journal.org          # sends infinite y's, risky if errors
```

**User quote:** "I want to run orggle from cron to automatically sync my work journal at the end of the day."

---

## Proposed Solution

Add a boolean flag `--yes` (or `-y`) that:
1. Skips all confirmation prompts
2. Auto-accepts all entries (or days in batch mode)
3. Behaves as if user typed 'y' (or Enter) for every prompt
4. Exits cleanly if no other errors

---

## Implementation Details

### Current Behavior

In interactive mode (no `--batch`), around line 649:

```python
for entry in entries:
    # ...
    response = input(f"Sync this entry? (y/n/q): ").strip().lower()
    if response == 'n':
        continue  # skip
    elif response == 'q':
        print("Quitting.")
        break
    else:  # default 'y' or Enter
        # sync logic
```

In batch mode (`--batch daily`), around line 621:

```python
for day, day_entries in sorted(grouped.items(), reverse=True):
    # ...
    response = input(f"Sync {day} ({len(day_entries)} entries, {total_str})? [Y/n/q]: ").strip().lower()
    if response == 'n':
        continue
    elif response == 'q':
        break
    else:
        # sync all entries for this day
```

### New Behavior with `--yes`

Modify prompts to check `args.yes` flag:

```python
response = None
if args.yes:
    response = 'y'
else:
    response = input(...).strip().lower()

if response == 'n':
    continue
elif response == 'q':
    break
else:
    # proceed
```

**Add argument in `create_parser()`:**

```python
parser.add_argument(
    "-y", "--yes",
    action="store_true",
    help="Auto-accept all prompts (non-interactive mode). Useful for scripts and cron jobs."
)
```

**Make `--yes` incompatible with interactive batch prompts?** No, it's a way to bypass them. Valid.

**Make `--yes` incompatible with `--dry-run`?** No, they can coexist: `--dry-run --yes` would auto-accept dry-run (meaningless but harmless). Maybe warn? No, fine.

---

## Edge Cases & Considerations

1. **Exit on error**: With `--yes`, if one entry fails (network error), should orggle:
   - a) Continue to next entry (current behavior)? Yes.
   - b) Abort entirely? No, user can manually inspect logs after.

2. **Batch mode with `--yes`**: Should auto-accept all days in sequence. No prompts.

3. **Input conflicts**: If both `--yes` and user tries to input manually (because they forget flag), input function still works. But `--yes` pre-answers, user cannot override. This is fine — user chose `--yes`.

4. **TTY requirement**: Should we check `sys.stdin.isatty()` when `--yes` is not set? Current code doesn't, but it's polite: if stdin is not a TTY and no `--yes`, error:
   ```python
   if not args.yes and not sys.stdin.isatty():
       print("Error: orggle requires an interactive terminal for prompts.")
       print("Use --yes flag to run non-interactively.")
       sys.exit(1)
   ```
   This is a breaking change for users who pipe `yes | orggle ...`. But they should use `--yes` anyway. Add in `main()` early.

5. **Default `--batch` with `--yes`**: If user has many entries, they'll probably use `--batch daily --yes`. That's fine.

6. **Color output**: Could add `--color=auto|always|never` in future, but separate.

7. **Logging verbosity**: Consider adding `--verbose` to show what's happening even with `--yes` (currently batch mode shows some output).

---

## Acceptance Criteria

### Functional Requirements
- [ ] `-y` / `--yes` flag exists and is documented
- [ ] When `--yes` is set, ALL prompts are auto-accepted (treated as 'y' or Enter)
- [ ] Works in both interactive mode (per-entry) and batch mode (per-day)
- [ ] Works with `--dry-run` (dry-run still shows preview but exits early, no prompts anyway)
- [ ] Works with `--force-recreate` (B-002)/`--update-changed` (B-003) - those might add their own prompts
- [ ] When `--yes` is NOT set and stdin is not a TTY, error message suggests using `--yes`
- [ ] Empty stdin (EOF) still works: input() might raise EOFError, should catch and treat as 'n' or 'q'? Safer: exit with error if interactive expected.

### User Experience
- [ ] With `--yes`, no prompts appear, sync proceeds automatically
- [ ] Normal output (info messages) still shown (workspace ID, parsing, counts)
- [ ] Per-entry success/failure still logged
- [ ] Summary still printed at end (if batch/interactive completion)

### Safety
- [ ] `--yes` does NOT auto-accept `--delete-existing` confirmation (B-002). That's separate safety.
- [ ] `--yes` only affects sync prompts, not config validation errors or argument errors

---

## Example Usage

```bash
# Interactive (default)
$ ./orggle journal.org
[Entry 1] Task A (2h)
Sync this entry? (y/n/q): y
✓ Synced
[Entry 2] Task B (1h)
Sync this entry? (y/n/q): n
⊘ Skipped

# Non-interactive with --yes
$ ./orggle journal.org --yes
Using profile: work
Parsing journal.org... 5 entries
✓ Synced: Task A (2h) - https://track.toggl.com/...
✓ Synced: Task B (1h) - https://track.toggl.com/...
Synced 5 entries, skipped 0
```

```bash
# Cron job (runs daily at 5pm, auto-syncs yesterday's entries)
0 17 * * * cd /path/to/orggle && ./orggle journal.org --day $(date -d yesterday +%Y-%m-%d) --yes >> /var/log/orggle-cron.log 2>&1
```

```bash
# Batch mode with --yes
$ ./orggle journal.org --batch daily --yes
Using profile: work
Day 2026-03-15 (3 entries, 8h):
✓ Synced all 3 entries
Day 2026-03-14 (2 entries, 5h):
✓ Synced all 2 entries
```

---

## Testing Strategy

**Unit tests:**
- Mock `input()` to ensure it's not called when `--yes` set
- Mock `input()` and verify it's called when `--yes` not set

**Automated tests (subprocess):**
```bash
# Should exit immediately after printing count (no stdin reads)
timeout 5 ./orggle test.org --yes || echo "timed out waiting for input"

# Should fail with non-TTY if no --yes
python -c "import subprocess; subprocess.run(['./orggle', 'test.org'], stdin=subprocess.PIPE)"  # returns error code 1
```

**Manual tests:**
1. `--yes` with small file → all sync
2. `--yes` with `--batch daily` → all days auto-accepted
3. `--yes` with `--dry-run` → dry-run output, no prompts
4. `--yes` with invalid file → error exit (no prompt)
5. `--yes` with network failure → retries, if fails, continue to next

---

## Implementation Checklist

- [ ] Add `-y` / `--yes` argument to parser (line ~632)
- [ ] Add TTY check in `main()`: if not `args.yes` and not `isatty()`, error exit
- [ ] Modify interactive prompt loop in non-batch mode to check `args.yes`
- [ ] Modify batch mode prompt loop to check `args.yes`
- [ ] Ensure `--delete-existing` confirmation (B-002) is separate and still prompts even with `--yes` (or B-002 may add its own force flag)
- [ ] Add tests for TTY detection (mock `sys.stdin.isatty()`)
- [ ] Add tests for `--yes` bypassing prompts
- [ ] Update README with automation examples
- [ ] Update fish completions (suggest `--yes` for automation)
- [ ] Manual cron test: `crontab -e` add test job

---

## Documentation Updates

### README.md

Add section "Automation and Scripting":

```markdown
### Automation (Non-Interactive Mode)

Run orggle without prompts using `--yes`:

```bash
orggle journal.org --yes
```

Useful for cron jobs, scheduled tasks, or scripting:

```bash
# Sync yesterday's entries automatically at 5pm daily
0 17 * * * cd ~/orgle && ./orggle journal.org --day $(date -d yesterday +%Y-%m-%d) --yes >> /var/log/orggle.log 2>&1
```

Note: `--yes` skips all confirmation prompts. Combine with `--dry-run` to test before deploying automation.

For cron jobs, ensure environment variables (like `TOGGL_API_TOKEN`) are set in the crontab or sourced from a profile.
```

### Fish Completions

```fish
complete -c orggle -l yes -s y -d "Auto-accept all prompts for non-interactive use"
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| User runs `--yes` with wrong arguments, syncs unwanted data | Medium | `--dry-run` exists to preview; `--yes` is opt-in |
| `--yes` bypasses safety prompts (like delete confirmation) | Critical | Do NOT make `--yes` bypass `--delete-existing` confirmation (B-002). Keep that separate. |
| `--yes` hides output, user doesn't see errors | Low | Output still printed; can redirect to log file; add `--verbose` in future |
| Cron environment missing env vars | Medium | Document clearly; add `orggle config validate` in future (B-006) |

---

## Related Backlog Items

- **B-001**: `--dry-run` complements `--yes` for safe automation
- **B-002**: `--delete-existing` confirmation should NOT be bypassed by `--yes` (separate safety)
- **B-012**: `--output json` would enhance scriptability alongside `--yes`

---

**Status:** Planned
**Created:** 2025-04-01
