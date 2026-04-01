# B-011: Exclude Entries with Regex Filter (`--exclude`)

**Priority:** Tier 3 (Medium) - Flexibility for selective syncing
**Effort:** Small (S - 2 hours)
**Dependencies:** None

---

## Problem Statement

Currently, users can only filter by date (`--day`, `--from`, `--to`). There's no way to exclude entries based on their description or other attributes without editing the org file.

**Use cases:**
- Exclude "break", "lunch", "meeting" categories that user wants to track separately
- Exclude entries with certain tags in org file that aren't properly mapped
- Temporarily skip a project during sync
- Filter out "admin" tasks without affecting org file

**User quote:** "I have some entries I don't want to sync to Toggl because they're personal. I don't want to delete them from org. I wish I could filter them out."

---

## Proposed Solution

Add `--exclude` flag that accepts a regex pattern. Entries whose description matches the pattern (case-insensitive by default) are excluded from sync.

```bash
orggle journal.org --exclude "break|lunch|meeting"
orggle journal.org --exclude "^Admin:"   # Entries starting with "Admin:"
```

**Implementation:**

1. Add argument:
```python
parser.add_argument(
    "--exclude",
    help="Exclude entries whose description matches the given regex pattern (case-insensitive). Example: --exclude 'break|lunch'"
)
```

2. After parsing entries and applying `--day`/`--from`/`--to` filters, also apply exclude filter:

```python
if args.exclude:
    pattern = re.compile(args.exclude, re.IGNORECASE)
    entries = [e for e in entries if not pattern.search(e["description"])]
    # Optionally report how many excluded
    print(f"Excluded {excluded_count} entries matching pattern: {args.exclude}")
```

3. Must work together with all other filters.

4. Should exclude before checking already-synced to avoid marking as skipped.

---

## Example

```bash
$ ./orggle journal.org --exclude "rest|break"
Parsing journal.org...
Found 20 entries (after date filter), excluded 3 matching 'rest|break'
Syncing 17 entries...
```

---

## Edge Cases

- Pattern with no matches → exclude 0, proceed
- Pattern that matches everything → result empty, show "No entries found after applying exclude filter" and exit 0? Or treat as error? Better: exit 0 with message.
- Invalid regex → validate at startup just like date validation, exit with error
- Combine with `--dry-run`: Show which entries would be excluded

---

## Validation

Add to argument parsing section (around line 660):

```python
if args.exclude:
    try:
        re.compile(args.exclude)
    except re.error as e:
        print(f"Error: Invalid regex pattern for --exclude: {e}")
        sys.exit(1)
```

---

## Acceptance Criteria

- [ ] `--exclude` flag accepts regex pattern
- [ ] Invalid regex produces clear error
- [ ] Entries matching pattern are removed from sync list
- [ ] Exclusion applied after date filters but before sync decisions
- [ ] Count of excluded entries printed (unless `--quiet`)
- [ ] Works with interactive, batch, --yes, --dry-run
- [ ] Test case: pattern matches, pattern doesn't match, invalid pattern
- [ ] Test integration with date filters

---

## Effort

- Argument add + validation: 1h
- Filter application: 30m
- Tests: 30m
- Docs: 30m
- Total: ~2h

---

## Documentation

Add to README:

### Exclude Entries

Filter out entries by description using a regex:

```bash
orggle journal.org --exclude "break|lunch|personal"
```

Useful for ignoring certain types of tasks without modifying your org file.

Combine with date filters:

```bash
orggle journal.org --from 2026-03-01 --to 2026-03-15 --exclude "Meeting"
```

---

## Related

- `--include` could be future opposite (whitelist)
- `org_mappings` can transform, not exclude

---

**Status:** Planned
**Created:** 2025-04-01
