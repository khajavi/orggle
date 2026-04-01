# B-017: Resume Capability for Interrupted Syncs

**Priority:** Tier 4 (Low) - Edge case for large syncs with failures
**Effort:** Medium (M - 4 hours)
**Dependencies:** None

---

## Problem Statement

If a sync is interrupted (Ctrl+C, network drop, crash), the user must restart from the beginning. For large syncs (hundreds of entries), this wastes time and may cause duplicates if partial entries already created (because they'll be skipped next run due to hash, but if interrupted before marking as published, they'll be re-sent, potentially creating duplicates in Toggl).

Actually duplicates: Orgle uses hash to avoid creating duplicates. If an entry was created but not marked as published (DB update happens after successful sync), next run will try to create again → duplicate in Toggl. That's a bug.

Current code: In sync loop, after successful POST, we call `mark_published(entry_hash, profile_name, toggl_id)`. If interruption happens between POST and mark, we lose the record → duplicate on next run.

**Impact:** Duplicate Toggl entries for same time.

---

## Proposed Solution

Add resumability: Store sync session state in DB, allow `--resume` to continue from where left off.

**Simpler fix:** Move `mark_published` to happen BEFORE the POST? No, that would mark as published even if POST fails. Wrong.

**Better:** Use atomic transaction: mark entry as "pending" first, then confirm after success. Or use a separate "sync_sessions" table to track which entries were attempted in a given run.

Given low priority, maybe simpler: accept the small duplicate risk; user can use `--delete-existing` to clean up.

But we can spec resume for future.

---

## Implementation Sketch

1. Add `sync_sessions` table:
```sql
CREATE TABLE sync_sessions (
    id INTEGER PRIMARY KEY,
    started_at TEXT,
    completed_at TEXT
);
CREATE TABLE session_entries (
    session_id INTEGER,
    entry_hash TEXT,
    status TEXT,  -- 'synced', 'failed'
    toggl_id TEXT,
    error TEXT,
    FOREIGN KEY(session_id) REFERENCES sync_sessions(id)
);
```

2. At start of `main()`, create a new session row, get session_id.

3. For each entry to sync, before attempting, insert row with status 'pending'? Or after success, insert session_entry with status='synced' and toggl_id.

4. On interruption (signal handler for SIGINT/SIGTERM), mark session as interrupted (update completed_at null). On next run with `--resume`, find latest incomplete session for same org file+profile? Then read session_entries to know which entries already synced, which failed.

5. Build set of hashes that are already synced in this session, treat them as done (skip). For failures, retry.

Complex.

Given low priority, deferral recommended.

---

## Deferral Decision

This is a robustness feature but edge case. Many users won't encounter. Duplicate creation can be mitigated by using `--delete-existing` after a failed sync to clean up duplicates before retry.

Mark as **Tier 4** and schedule if time.

---

**Status:** Deferred
**Created:** 2025-04-01
