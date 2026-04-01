# B-001: Dry-Run / Preview Mode

**Priority:** Tier 1 (Critical) - Prevents accidental syncs and builds user confidence
**Effort:** Small (XS - 2 hours)
**Dependencies:** None

---

## Problem Statement

Users cannot see what will be synced before actually syncing. This leads to:
- Fear of accidentally syncing wrong entries
- Tedious manual verification (must confirm each entry interactively)
- No way to preview bulk operations (date ranges) before committing
- Poor user experience when testing configuration changes

**User quote:** "I wish I could see what entries would be synced before actually sending them to Toggl."

---

## Proposed Solution

Add a `--dry-run` flag that:
1. Parses org file and applies all filters (`--day`, `--from`, `--to`, `--batch`)
2. Shows what WOULD be synced (entries, dates, durations)
3. **Makes NO API calls** (doesn't fetch workspace/project, doesn't POST to Toggl)
4. Exits with status 0, prints summary to stdout

---

## Implementation Details

### Changes to `orggle.py`

**1. Add argument in `create_parser()` (around line 632):**

```python
parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Preview what would be synced without making any API calls"
)
```

**2. Early exit check in `main()` (after filtering, before workspace lookup, around line 670):**

```python
# After line 767 where filtering is applied:
if args.dry_run:
    print("\n=== DRY RUN ===")
    print(f"Would sync {len(entries)} entries:")
    total_duration = 0
    for entry in entries:
        duration_mins = entry["duration"] // 60
        print(f"  {entry['start'][:10]}: {entry['description']} ({duration_mins}m)")
        total_duration += duration_mins
    print(f"\nTotal duration: {total_duration // 60}h {total_duration % 60}m")
    print("(No API calls were made)")
    sys.exit(0)
```

Insert this BEFORE:
- `print(f"Using profile: {profile_name}")` (line 710)
- `init_db(profile_name)` (line 713)
- any network/API calls

**3. Make `--dry-run` incompatible with `--delete-existing`:**

```python
# Around line 675, add:
if args.dry_run and args.delete_existing:
    print("Error: --dry-run cannot be used with --delete-existing")
    print("(Use --dry-run first to preview, then run without it to actually delete and sync)")
    sys.exit(1)
```

---

## Acceptance Criteria

### Functional Requirements
- [ ] `--dry-run` flag exists and is documented in help
- [ ] When used, orggle parses org file, applies filters, shows preview
- [ ] NO network calls are made (verify by mocking/stubbing or inspecting logs)
- [ ] NO database operations occur (no `init_db`, no `is_published`, etc.)
- [ ] Shows entry list with date, description, duration
- [ ] Shows total count and duration summary
- [ ] Exits cleanly with status 0
- [ ] Cannot be combined with `--delete-existing` (error)
- [ ] Works with all filter modes: `--day`, `--from`/`--to`, `--batch daily`

### User Experience
- [ ] Output clearly labeled "DRY RUN" / "PREVIEW MODE"
- [ ] Format: `YYYY-MM-DD: Description (duration in minutes)`
- [ ] Total displayed in hours and minutes (e.g., "8h 30m")
- [ ] Informational message: "(No API calls were made)"

### Error Cases
- [ ] `--dry-run` with `--delete-existing` shows clear error
- [ ] Dry-run respects all validation (date format, mutual exclusion)
- [ ] Invalid org file path shows error before dry-run

---

## Example Usage

```bash
# Preview what would sync for a date range
$ ./orggle journal.org --from 2026-03-01 --to 2026-03-15 --dry-run

=== DRY RUN ===
Would sync 15 entries:
  2026-03-15: Work on project X (180m)
  2026-03-15: Team meeting (60m)
  2026-03-14: Code review (90m)
  ...

Total duration: 23h 45m
(No API calls were made)
```

```bash
# Preview batch mode
$ ./orggle journal.org --batch daily --dry-run

=== DRY RUN ===
Found 45 entries grouped into 5 days

Day 2026-03-15 (3 entries, 5h 30m total):
  - Work on project X (3h)
  - Team meeting (1h)
  - Code review (1.5h)

Day 2026-03-14 (2 entries, 2h 30m total):
  ...

Would sync 5 days, 15 entries total.
(No API calls were made)
```

---

## Edge Cases & Considerations

1. **Batch mode with dry-run**: Should still show day grouping but not prompt
2. **Empty result**: If no entries match filters, show "Would sync 0 entries" and exit 0
3. **Large datasets**: For 1000+ entries, consider limiting output or paginating. But dry-run implies user wants to see, so show all.
4. **Performance**: Dry-run skips all API/network, so should be very fast. No need for progress indicator.
5. **Exit code**: Always 0 (success) unless usage error or argument error. Non-zero only for bad input.
6. **Color output**: Could add `--color` flag or auto-detect terminal support. For now, plain text.

---

## Testing Strategy

**Unit tests** (existing test file):
- Test that `--dry-run` flag is parsed correctly
- Test that dry-run exits early (can mock `sys.exit`)
- Test that no network calls are made when dry-run enabled

**Manual tests**:
```bash
# 1. Basic dry-run
./orggle test_sample.org --from 2026-03-25 --to 2026-03-29 --dry-run

# 2. Dry-run with batch
./orggle test_sample.org --batch daily --dry-run

# 3. Dry-run with day
./orggle test_sample.org --day 2026-03-28 --dry-run

# 4. Dry-run with no matches
./orggle test_sample.org --from 2099-01-01 --dry-run  # Should show 0 entries

# 5. Dry-run conflict
./orggle test_sample.org --delete-existing --dry-run  # Error
```

---

## Documentation Updates

### README.md

Add new section:

```markdown
### Preview Changes (Dry Run)

See what would be synced without making any actual changes to Toggl:

```bash
orggle journal.org --from 2026-03-01 --to 2026-03-15 --dry-run
```

This parses your org file, applies filters, and shows exactly which entries would be uploaded, along with total duration. No API calls are made, and nothing is changed in Toggl.

Useful for:
- Verifying date ranges before bulk sync
- Testing filters and `org_mappings` configuration
- Checking what entries are about to be synced in interactive modes

Note: `--dry-run` cannot be used with `--delete-existing`.
```

Update help text section to include `--dry-run`.

### Fish Completions

Add completion for `--dry-run`:
```fish
complete -c orggle -l dry-run -d "Preview sync without making API calls"
```

---

## Implementation Checklist

- [ ] Add `--dry-run` argument to parser
- [ ] Add early exit logic in `main()` before API calls
- [ ] Format output with date, description, duration
- [ ] Add mutual exclusion with `--delete-existing`
- [ ] Update README with usage example
- [ ] Update fish completions
- [ ] Add tests for argument parsing and dry-run behavior
- [ ] Manual testing on sample org files
- [ ] Verify no network calls (use Wireshark/tcpdump or verbose logging)

---

## Future Enhancements (Post-MVP)

After basic dry-run works, consider:

1. **`--dry-run --output json`**: Machine-readable preview for scripts
2. **Include workspace/project in preview**: Show which Toggl project each entry would use (requires config validation)
3. **Show what would be skipped**: Include count of already-synced entries that would be skipped
4. **Preview deletion**: With `--delete-existing` (separately), show "Would delete X entries" before delete
5. **Cost estimation**: If using Toggl paid features, estimate "cost" of synced hours

---

## Related Backlog Items

- **B-002**: Dry-run is safer alternative to testing delete-existing
- **B-004**: `--yes` can be combined with dry-run for automation testing
- **B-006**: Config validation should work in dry-run mode

---

**Status:** Planned
**Created:** 2025-04-01
