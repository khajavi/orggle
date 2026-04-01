# B-003: Fix Description Update Gap (Hash-Based Deduplication Issue)

**Priority:** Tier 1 (Critical) - Users lose confidence when edits don't sync
**Effort:** Medium (M - 6 hours)
**Dependencies:** None

---

## Problem Statement

Orggle uses hash-based deduplication to skip already-synced entries. The hash is computed as `sha256(start-stop-duration)`. This has a critical flaw:

**Scenario:**
1. User syncs entry: "Work on project A" from 9-12 (3h)
2. Later, user edits org file: changes description to "Work on project A - urgent"
3. User re-runs sync with `--day` (expects update)
4. Orggle computes hash from same start/stop/duration → hash matches
5. Orggle skips entry as "already synced"
6. Toggl still shows old description "Work on project A"

**Result:** User cannot correct typos, update descriptions, or reflect changes in org file because hash didn't change.

**User quote:** "I fixed the typo in my org file but Toggl still shows the old description. I tried re-syncing but it didn't update."

---

## Why This Happens

From code analysis:

```python
def hash_entry(entry: dict) -> str:
    """Generate a hash for an entry to detect duplicates."""
    # Current implementation (lines 271-275):
    key = f"{entry['start']}-{entry['stop']}-{entry['duration']}"
    return hashlib.sha256(key.encode()).hexdigest()
```

The hash uses only:
- `start` timestamp
- `stop` timestamp
- `duration` (derived)

It **excludes** description.

Later in `is_published()` (line 565-571), entries already in DB with matching hash are marked as "published" and skipped.

---

## Proposed Solutions (Options)

We need to balance:
- True deduplication (same time entry should not create duplicates)
- Update capability (changed description should propagate)
- User control (user should decide what to do)

### Option A: Include Description in Hash (Breaking Change)

**Change hash to:** `sha256(start-stop-description)`

**Pros:**
- Simple, one-line change
- Description changes automatically cause re-sync

**Cons:**
- If user edits description in Toggl directly, next sync will re-create entry (duplicate in Toggl)
- Hash changes if description format changes (e.g., adding "DONE" prefix, then removing)
- Loses ability to detect "same entry" if description varies slightly (whitespace, emoji, etc.)
- Breaking change for existing DB: all entries appear as "new" on first run after upgrade

**Verdict:** Too breaking. Not recommended.

---

### Option B: Add `--force` or `--update-descriptions` Flag (Recommended)

Keep existing hash for deduplication, but add a mode that bypasses the hash check and **always** submits entries, updating descriptions if they differ.

**Implementation:**

```python
def should_skip_entry(entry_hash: str, profile_name: str, force_update: bool = False) -> bool:
    """Determine if entry should be skipped based on sync history."""
    if force_update:
        return False  # Never skip when forcing
    return is_published(entry_hash, profile_name)

# In main()'s sync loop (around line 795):
for entry in entries:
    entry_hash = hash_entry(entry)
    if should_skip_entry(entry_hash, profile_name, force=args.force):
        already_synced += 1
        continue

    # Check if entry exists in Toggl with different description
    # This is complex; simpler: just POST and let Toggl handle (POST creates new or updates? No, Toggl creates new each time)
    # Actually Toggl API POST always creates new entry. There's no PATCH/PUT for updates.
    # So to "update" we must DELETE old and CREATE new. That's what --delete-existing does.

    # Therefore --force alone cannot update descriptions; it would create duplicates.
    # We need a smarter approach.
```

**Problem:** Toggl API **does not have an update endpoint**. POST creates new entries. To "update" an entry, you must:
1. Find the existing entry (by some identifier)
2. DELETE it
3. POST the updated version

Orggle's `--delete-existing` does bulk delete but requires knowing the day/range.

---

### Option C: Smart Update - Compare and Offer to Replace (Complex but UX-friendly)

**Workflow:**
1. For each entry that matches hash (already synced), fetch the corresponding Toggl entry by time range and description
2. If description differs, prompt user:
   ```
   Description changed: "Old description" → "New description"
   Update in Toggl? [y/n/a/q] (yes/no/all/quit)
   ```
3. If yes, delete old and create new

**Implementation:**
- Extend `is_published()` to return entry data (toggl_id, description) not just bool
- After parsing, for each entry with matching hash:
  - Call a new `get_entries_in_time_range(start, stop)` to fetch from Toggl
  - Find entry with matching start/stop
  - Compare descriptions
  - If different, prompt (or auto with `--force-update`)

**Pros:**
- Users can fix descriptions
- No bulk delete needed
- Selective updates

**Cons:**
- Requires additional API call per entry (rate limit concern)
- Slow for many entries
- Complex to implement
- Still doesn't handle duration changes (would need delete+create anyway)

---

### Option D: Clarify Hash Semantics and Use `--force` to Delete-and-Recreate Entire Set (Simplest Fix)

Given that **Toggl has no update endpoint**, any change to entry (description, duration, tags) requires delete + recreate.

The right tool for this is already `--delete-existing`, but it's cumbersome:
- Must know exact day/range
- Deletes everything in range, even those not changed
- Re-syncs everything (could skip unchanged but we don't know what changed)

**Better approach:**

Add a new flag `--update-changed` that:
1. For each synced entry, compare stored description/duration with current org entry
2. If different, mark for delete-and-recreate
3. For new entries, create normally
4. For unchanged entries, skip

But wait: We don't store description/duration in DB? Let's check DB schema:

```sql
CREATE TABLE entries (
    hash TEXT PRIMARY KEY,
    description TEXT,
    start TEXT,
    stop TEXT,
    duration INTEGER,
    published INTEGER DEFAULT 0,
    toggl_id TEXT,
    synced_at TEXT
)
```

**YES we do store!** We store `description`, `start`, `stop`, `duration`, `toggl_id`.

So we CAN compare stored entry with current entry.

---

## Recommended Solution: Option D (Smart Re-sync with `--update-changed`)

Add flag `--update-changed` (or `--update` for short) that:

1. For entries that are in DB (already synced):
   - Compare current org entry (description, start, stop, duration) with DB record
   - If identical → skip (already synced)
   - If different → delete old Toggl entry (using stored `toggl_id`) and create new with current data
2. For new entries → create normally

**Key insight:** The DB stores full entry data, not just hash. We can detect changes!

**Implementation steps:**

**Step 1:** Modify `is_published()` to return full entry record or None

```python
def get_published_entry(entry_hash: str, profile_name: str) -> Optional[dict]:
    """Get the stored entry that matches this hash, or None."""
    conn = sqlite3.connect(get_db_path(profile_name))
    cur = conn.cursor()
    cur.execute(
        "SELECT hash, description, start, stop, duration, toggl_id FROM entries WHERE hash = ?",
        (entry_hash,)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "hash": row[0],
            "description": row[1],
            "start": row[2],
            "stop": row[3],
            "duration": row[4],
            "toggl_id": row[5]
        }
    return None
```

**Step 2:** Change sync loop:

```python
for entry in entries:
    entry_hash = hash_entry(entry)

    if args.update_changed:
        # Get stored entry
        stored = get_published_entry(entry_hash, profile_name)
        if stored:
            # Check if anything changed
            changes = []
            if entry["description"] != stored["description"]:
                changes.append(f"description: '{stored['description']}' → '{entry['description']}'")
            if entry["duration"] != stored["duration"]:
                changes.append(f"duration: {stored['duration']} → {entry['duration']}")
            if entry["start"] != stored["start"] or entry["stop"] != stored["stop"]:
                changes.append("timestamps")
            if changes:
                # Delete old and recreate
                print(f"Updating entry: {', '.join(changes)}")
                delete_entry(api_token, workspace_id, proxies, stored["toggl_id"])
                # Then create new below (don't skip)
            else:
                already_synced += 1
                continue  # Skip
        # else: new entry, continue to create
    else:
        # Original behavior
        if is_published(entry_hash, profile_name):
            already_synced += 1
            continue

    # Create new entry...
```

**Step 3:** Add flag to parser:

```python
parser.add_argument(
    "--update-changed",
    action="store_true",
    help="Update entries that have changed (description, duration, time) by deleting and re-creating them"
)
```

**Step 4:** Make `--update-changed` mutually exclusive with `--day`? Not necessary, but should work together.

**Step 5:** Update README with examples.

---

## Alternative Simpler Approach (MVP)

If full `--update-changed` is too complex, go with Option B + documentation:

1. Add `--force-recreate` flag that:
   - Deletes ALL entries in the filtered set (like `--delete-existing` but scoped to filtered range)
   - Then syncs everything fresh

**This combines delete + sync in one flag, convenient for corrections:**

```bash
# Fix yesterday's entries after editing org file:
orggle journal.org --day 2026-03-28 --force-recreate
# Equivalent to: --delete-existing --day 2026-03-28 (but without double-typing)

# Fix a range:
orggle journal.org --from 2026-03-01 --to 2026-03-15 --force-recreate
```

**Implementation:** Just add `--force-recreate` as shorthand that implies `--delete-existing` for the filtered set, **WITH CONFIRMATION** (B-002).

**Downside:** Deletes and recreates EVERYTHING in range, even unchanged entries. But that's what user wants when they say "update everything after edits".

**Effort:** XS (reuse existing delete logic)

---

## Acceptance Criteria (MVP: Option B Simplest)

### Minimum Viable Fix

- [ ] Add `orggle --version` test output includes new flag
- [ ] `--force-recreate` deletes and re-syncs all entries in filtered set
- [ ] Requires confirmation (B-002) before deletion
- [ ] Works with `--day`, `--from/--to`
- [ ] Works with `--batch` (deletes once, syncs fresh)
- [ ] Documented in README with example
- [ ] Backward compatible: no changes to default behavior

### Full Smart Update (Option D)

- [ ] `--update-changed` flag exists
- [ ] Compares current entry with stored DB entry (description, duration, timestamps)
- [ ] Unchanged entries are skipped (counted as "already synced")
- [ ] Changed entries are deleted and recreated (counted as "updated")
- [ ] New entries are created (counted as "new")
- [ ] Shows per-entry update message: "Updating: description changed from X to Y"
- [ ] Works in batch mode and interactive mode
- [ ] Database performance: single SELECT per entry (can batch fetch)
- [ ] No breaking changes to existing DB schema (uses existing stored data)

---

## Example Usage

### MVP - Force Recreate:
```bash
$ ./orggle journal.org --day 2026-03-28 --force-recreate

Would delete 3 existing entries and re-sync.
Type 'DELETE 3' to confirm: DELETE 3

Deleting 3 old entries...
Creating 3 new entries...
✓ Synced: ...
```

### Full Smart Update:
```bash
$ ./orggle journal.org --day 2026-03-28 --update-changed

Found 3 entries:
  ✓ Updating (description changed): "Fix typo" (entry 12345)
  ⊘ Skipped (unchanged): "Regular meeting" (entry 12346)
  ⊕ New: "New task today" (entry 12347)
```

---

## Efforts & Timeline

**Option A** (bad): 1 hour, high risk
**Option B** (`--force-recreate` as shorthand): 2 hours (XS), recommended immediate fix
**Option C** (smart compare with prompts): 12+ hours (L), complex
**Option D** (full `--update-changed`): 6 hours (M), best long-term

**Recommendation:** Implement Option D (smart update) as it's the right UX and uses existing DB data. Effort is Medium, not Large.

---

## Testing Strategy

**Unit tests:**
- `test_get_published_entry()` returns correct data
- `test_entry_has_changed()` compares hash entry vs stored
- Test all change types: description diff, duration diff, timestamp diff, no diff

**Integration tests:**
- Sync initial set → modify org descriptions → run `--update-changed` → verify Toggl has new descriptions
- Modify duration → verify old deleted, new created

**Manual tests:**
1. Create entry, sync (creates in Toggl)
2. Edit org file: fix typo in description
3. Run `--update-changed` → should update
4. Edit org file: change duration
5. Run `--update-changed` → should update
6. Make no changes
7. Run `--update-changed` → should skip

---

## Implementation Checklist (Option D)

- [ ] Add `get_published_entry(hash, profile)` that returns full dict or None
- [ ] Add `entries_are_equal(org_entry, db_entry)` comparison function
- [ ] Add `--update-changed` argument to parser
- [ ] Modify sync loop to:
  - For entries with hash match, fetch stored entry
  - Compare fields
  - If different: delete old (using toggl_id), then create new
  - Track counts: new, updated, skipped, failed
- [ ] Add output messages: "Updating (X changed): description", "Skipped (unchanged)"
- [ ] Handle errors: delete fails, create fails (should retry?)
- [ ] Add tests for comparison logic
- [ ] Update README
- [ ] Performance: optimize with batch fetch of stored entries (SELECT WHERE hash IN (...))

---

## Related Backlog Items

- **B-002**: `--force-recreate` needs delete confirmation
- **B-001**: Dry-run should show "would update X entries"
- **B-017**: Resume could combine with update-changed

---

**Status:** Planned
**Created:** 2025-04-01
