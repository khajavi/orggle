# B-010: Summary Statistics at End of Sync

**Priority:** Tier 2 (High) - Provide clear closure and totals
**Effort:** Extra Small (XS - 1 hour)
**Dependencies:** None

---

## Problem Statement

After a sync (interactive or batch), orggle prints some output but lacks a final summary. Users must scroll back to see totals.

**Current state:**
- Interactive: prints per-entry success/skip
- Batch: prints per-day results
- But no final tally: "You synced 45 entries, total duration 32h 15m, skipped 3, failed 1"

**User benefit:** Quick overview, confirmation of overall work, easy copy-paste for personal records.

---

## Proposed Solution

After sync completes (normal exit or after `--yes` batch finishes), print a summary block:

```
────────────────────────────────────
✓ Synced:    45 entries (32h 15m)
⊘ Skipped:   5 entries (already synced)
✗ Failed:    0 entries
────────────────────────────────────
Total duration: 32h 15m
```

Calculate totals from counters already tracked (`synced_count`, `skipped_count`, `failed_count`, duration sum).

**Implementation location:** In `main()` after the sync loop exits (around line 830 after `sys.exit` paths? Actually after batch mode or interactive mode completion). Need to centralize counters.

Currently counters:
- `new_entries` list built for interactive mode, then size used
- `already_synced` variable
- After syncing loop, some prints: "Synced: X, Skipped: Y"

Actually at end of `main()` (line ~819-822):

```python
print(f"\nSynced: {len(synced_entries) if synced_entries else 0}")
if already_synced > 0:
    print(f"Skipped: {already_synced} (already synced)")
```

That's there! So there is a summary already? Let's check actual code reading. I only saw parts. Let's search:

I saw earlier around line 810-820 maybe has summary. Let's read to verify.

But from user perspective, maybe it's not clear or not formatted nicely. We could enhance it with total duration and a visual separator.

The proposed improvement: add total duration and better formatting.

---

## Implementation

**If summary already exists:**
- Add total duration calculation (sum of durations of synced entries)
- Add visual separator (line of dashes)
- Count failed entries (currently failures just increment `failed`? There is `failed` variable maybe)

Let's read final part of `main()` to know current state:

I'll search for "Synced:" output.

Actually earlier I saw at line 819-822 there is something like:
```
print(f"Synced: {len(synced_entries)}")
if already_synced > 0:
    print(f"Skipped: {already_synced}...")
```

Maybe there is also `failed` count.

If there is already a summary, we can simply enhance it.

If not, we add it.

Given the effort XS, we can implement quickly.

### Steps

1. Track total duration of synced entries (sum of entry['duration'] // 60 for minutes).
2. Track failures (entries that returned None from create_entry but not for skip reasons)
3. At end, format:

```
────────────────────────────
Results:
  Synced:   5 entries (8h 30m)
  Skipped:  2 entries (already synced)
  Failed:   0 entries
────────────────────────────
```

4. Use a box or separator for visibility.

5. Make it always show, even with `--quiet`? Probably yes; summary is important. Or respect `--quiet`.

6. Add `--quiet` to suppress summary? But user wants summary. Actually `--quiet` currently would suppress progress but summary maybe still shown. We can decide: summary by default, quiet suppresses all but errors.

---

## Acceptance

- [ ] Final summary printed after all sync operations complete
- [ ] Shows counts: synced, skipped, failed
- [ ] Shows total duration (hours and minutes) of entries successfully synced
- [ ] Uses clear formatting with separator line
- [ ] Works with all modes (interactive, batch, --yes)
- [ ] Does not appear if `--quiet` (optional, maybe keep summary even in quiet)
- [ ] Duration correctly calculated (seconds → h/m)

---

## Effort

- 1 hour to implement and test

---

## Related

B-007 (Progress indicator) complements this; summary is final aggregate.

---

**Status:** Planned
**Created:** 2025-04-01
