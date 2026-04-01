# B-002: Confirm Before Delete with `--delete-existing`

**Priority:** Tier 1 (Critical) - Prevents catastrophic data loss
**Effort:** Extra Small (XS - 1 hour)
**Dependencies:** None

---

## Problem Statement

The `--delete-existing` flag **immediately deletes** all matching Toggl entries **without any confirmation prompt**. This is extremely dangerous:

- User typos in date: `--day 2026-03-28` → typo → `2026-03-82` (invalid) won't run, but `--day 2026-04-01` (wrong day) deletes real data
- User misunderstanding: Thinks `--delete-existing` only deletes from local DB, not Toggl
- No second chance: Once deleted from Toggl, entries are gone (unless user manually re-imports)

**User scenario:** "I wanted to fix yesterday's entries, but I accidentally specified the wrong date and deleted a week of data."

**Impact:** Critical - Data loss is irreversible. Once deleted from Toggl, entries cannot be recovered through orggle.

---

## Proposed Solution

Require explicit confirmation before performing deletions. The confirmation should:

1. Show exactly what will be deleted (count and date range/day)
2. Require typed confirmation (not just Enter/Y)
3. Use a verification string to prevent accidental Enter presses
4. Be impossible to bypass (no `--force` flag yet)

---

## Implementation Details

### Current Behavior (Problem)

```python
# Around line 734-747 in main():
if args.delete_existing and not args.org_file:
    print(f"Fetching existing entries for {args.day}...")
    existing = get_entries_for_day(...)
    if existing:
        print(f"Found {len(existing)} existing entries, deleting...")
        for entry in existing:
            delete_entry(...)  # IMMEDIATE DELETION, NO PROMPT
```

And around line 775-787:

```python
if args.day and args.delete_existing:
    print(f"Fetching existing entries for {args.day}...")
    existing = get_entries_for_day(...)
    if existing:
        print(f"Found {len(existing)} existing entries, deleting...")
        for entry in existing:
            delete_entry(...)  # IMMEDIATE DELETION
```

### New Behavior

Add confirmation step BEFORE any deletion:

```python
def confirm_delete(count: int, date_range: str) -> bool:
    """Prompt user to confirm deletion."""
    print(f"\n⚠️  WARNING: This will delete {count} existing Toggl entries")
    print(f"   Date range: {date_range}")
    print(f"   Type 'DELETE {count}' to confirm, or any other input to cancel: ", end="")
    try:
        response = input().strip()
        return response == f"DELETE {count}"
    except (EOFError, KeyboardInterrupt):
        return False

# In main(), replace deletion blocks:

# Case 1: --delete-existing without org_file (single day)
if args.delete_existing and not args.org_file:
    existing = get_entries_for_day(api_token, workspace_id, proxies, args.day)
    if not existing:
        print(f"No entries found for {args.day}.")
        sys.exit(0)

    # NEW: Confirmation prompt
    if not confirm_delete(len(existing), f"{args.day} (single day)"):
        print("Deletion cancelled.")
        sys.exit(0)

    print(f"Deleting {len(existing)} entries...")
    for entry in existing:
        # deletion loop

# Case 2: --delete-existing with org_file (after day or range filter)
# Insert after args.day and date range filtering, around line 775-787:
if args.delete_existing:
    # Determine which entries are about to be synced (already filtered)
    # We want to delete entries that EXIST in Toggl for the same time range
    # Build date/range description for confirmation
    if args.day:
        date_desc = f"{args.day} (single day)"
        existing = get_entries_for_day(api_token, workspace_id, proxies, args.day)
    elif args.from_date or args.to_date:
        date_desc = f"{args.from_date or '...'} to {args.to_date or '...'} (date range)"
        # Need to fetch existing entries in range - can reuse logic from later?
        # Actually, get_entries_for_day only works for single day.
        # We'll need to fetch by range using get_entries_in_range (to be created)
        # Or we can simplify: just warn "This will delete existing entries in the range"
        # But we don't know count until after we fetch
        # Current code only deletes after batch sync, not before
        # Actually looking at line 775-787, it deletes AFTER displaying days but BEFORE syncing each day
        # Let's re-read the flow...

        # Actually the code at 775-787 is: "if args.day and args.delete_existing"
        # So it's tied to --day, not range.
        # But what about --from/--to with delete-existing? Let's check...
        # Line 734: if args.delete_existing and not args.org_file: (delete-only mode)
        # That's for "orggle --day X --delete-existing" (no org file)
        # For "orggle file.org --from X --to Y --delete-existing", it goes through full flow.

        # In the full flow at line 775-787, it says:
        # if args.day and args.delete_existing:
        #     print(f"Fetching existing entries for {args.day}...")
        # So it only handles --day, not --from/--to.
        # BUG: --from/--to with --delete-existing doesn't actually delete?
        # Let's check further: line 789 does batch loop, but no delete in that path?
        # Hmm, this needs investigation. For now, implement confirmation for --day path only.
        pass

    if not existing:
        print("No existing entries found.")
        # Continue to sync without deletion (user may want to just add)
    else:
        # Confirmation
        if not confirm_delete(len(existing), date_desc):
            print("Deletion cancelled.")
            # Should we exit? Or continue without deleting?
            # Probably exit because user expected delete, cancel = abort
            sys.exit(0)
        print(f"Deleting {len(existing)} entries...")
        for entry in existing:
            delete_entry(...)
```

---

## Edge Cases to Handle

1. **Empty result**: If no existing entries found, no confirmation needed, just continue
2. **Large count**: If count > 999, still show full number in confirmation string
3. **Multiple deletion sessions**: In batch mode, would we delete once at start or per day?
   - Current code deletes per day (if `--day` used). With range, should delete once for whole range or per day?
   - Decision: Delete **once** for entire operation (either single day or entire range), not per batch day.
   - But current batch mode code at 775-787 is inside day loop? Actually no, it's before batch loop.
   - Check: line 775-787 is inside `if args.day and args.delete_existing`, which is before batch loop (line 489? No line numbers shifted).
   - Let's re-examine current behavior by reading code around batch...

Actually, the safest is to:
- For `--day`: Delete all entries for that day BEFORE syncing, one operation
- For `--from/--to` with batch: Delete all entries in range BEFORE any syncing, one operation

So confirmation should happen once with total count.

4. **Non-interactive mode**: What if user pipes input or uses `--yes` (future flag)?
   - When `--yes` is added (B-004), it should skip confirmation but still show warning
   - For now, if stdin is not a TTY, error out and ask user to run interactively
   - Add: `if not sys.stdin.isatty(): print("Error: --delete-existing requires interactive terminal for confirmation"); sys.exit(1)`

---

## Acceptance Criteria

### Functional Requirements
- [ ] When `--delete-existing` is used, user is prompted for confirmation BEFORE any deletion
- [ ] Confirmation shows exact number of entries to be deleted
- [ ] Confirmation shows date range or day being deleted
- [ ] Must type exact string "DELETE N" where N is count
- [ ] Any other input cancels deletion
- [ ] Ctrl+C / EOF also cancels safely
- [ ] If cancelled, orggle exits with status 0 (user abort, not error)
- [ ] If confirmed, deletion proceeds with per-entry logging
- [ ] Non-interactive (piped) stdin shows error message and exits with status 1

### User Experience
- [ ] Warning symbol (⚠️) or "WARNING:" in message
- [ ] Clear statement: "This will delete N existing Toggl entries"
- [ ] Date range clearly specified
- [ ] Instruction: "Type 'DELETE N' to confirm"
- [ ] On cancel: "Deletion cancelled."

### Safety
- [ ] No deletion occurs without correct confirmation
- [ ] Confirmation string cannot be guessed or triggered by accident (typing "yes", pressing Enter)
- [ ] Deletion count in confirmation matches actual deletions performed

---

## Example Interaction

### Confirmation (correct):
```bash
$ ./orggle journal.org --day 2026-03-28 --delete-existing

Using profile: work
Looking up project 'Work'...
Parsing journal.org...
Found 3 clock entries for 2026-03-28

⚠️  WARNING: This will delete 3 existing Toggl entries
   Date: 2026-03-28 (single day)
   Type 'DELETE 3' to confirm, or any other input to cancel: DELETE 3

Deleting 3 entries...
  ✓ Deleted entry 12345
  ✓ Deleted entry 12346
  ✓ Deleted entry 12347
```

### Cancellation:
```
   Type 'DELETE 3' to confirm, or any other input to cancel: no
Deletion cancelled.
```

### Non-interactive error:
```bash
$ echo | ./orggle journal.org --day 2026-03-28 --delete-existing
Error: --delete-existing requires an interactive terminal for confirmation.
Please run without piping input.
```

---

## Testing Strategy

**Manual tests:**
1. Run with `--delete-existing` and provide correct confirmation
2. Run with `--delete-existing` and provide wrong confirmation
3. Run with `--delete-existing` and press Ctrl+C
4. Run with `--delete-existing` in piped context
5. Verify deletion count matches confirmation count
6. Test with 0 existing entries (no prompt)
7. Test with large count (100+ entries)

**Automated tests** (in test_orggle.py):
- Subprocess test that runs with `--delete-existing` and feeds input via stdin
- Assert correct exit codes for confirm/cancel

---

## Implementation Checklist

- [ ] Create `confirm_delete(count, date_desc)` helper function
- [ ] Hook into `--delete-existing` path for `--day` case (line 775-787)
- [ ] Hook into `--delete-existing` for without-org-file case (line 734-747)
- [ ] Handle case where `--from/--to` also uses delete (currently not implemented, may need fix)
- [ ] Add `--yes` flag compatibility (future work, but note in code)
- [ ] Add non-interactive detection (`sys.stdin.isatty()`)
- [ ] Update tests with subprocess + stdin tests
- [ ] Update README to warn about confirmation requirement
- [ ] Manual testing with real Toggl (use test workspace)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Confirmation too strict, users annoyed | Medium | Keep string matching but maybe make it case-insensitive; show example clearly |
| Deletion takes long, no progress | Low | Already shows per-entry deletion, consider adding count progress for large deletes |
| Batch mode deletes per-day (multiple confirmations) | Medium | Current code may already do this; make sure we understand flow. Should be ONE confirmation for entire operation. |
| Race condition: entries added between confirmation and deletion | Low | Acceptable; just show count at time of fetch |

---

## Related Backlog Items

- **B-001**: Dry-run would show deletion count before confirming
- **B-004**: `--yes` flag would skip confirmation (but still show warning)
- **B-017**: Resume could re-delete if interrupted

---

**Status:** Planned
**Created:** 2025-04-01
