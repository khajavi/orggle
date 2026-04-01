# B-015: Overlap Detection with Existing Toggl Entries

**Priority:** Tier 3 (Medium) - Prevent accidental double-booking
**Effort:** Medium (M - 5 hours)
**Dependencies:** None

---

## Problem Statement

Orggle blindly creates entries in Toggl without checking if an entry already exists for the same time range. This can lead to overlapping entries:

- User has manually created an entry in Toggl for same time
- Or another sync from different source created overlapping entry
- Or same org entry synced twice due to mistake

Result: Two entries overlapping in time, double-counting hours.

**User scenario:** "I forgot I already logged that meeting in Toggl, and orggle added it again. Now I have 2 entries for the same 1-hour meeting."

---

## Proposed Solution

Before creating a new entry, query Toggl for entries that overlap with the time range. If any found, warn user and skip (or prompt depending on mode).

### Overlap Definition

Two time intervals overlap if:
```
start1 < stop2 AND stop1 > start2
```
[i.e., intersection is non-empty]

---

## Implementation

### Query Overlapping Entries from Toggl

Toggl API v9 supports time entry query with `start_date` and `end_date`:

```
GET /api/v9/time_entries?start_date=2026-03-28T00:00:00Z&end_date=2026-03-29T00:00:00Z
```

We can fetch entries within a range that covers our entry's start/stop, then check each for overlap.

But note: this is an extra API call per entry (or per batch day). That's a lot of rate limit usage.

**Optimization 1**: Bulk fetch all entries for the day (or range) once, then check locally.

**Workflow:**
- For `--day`: fetch all entries for that day from Toggl once, store in dict keyed by time range.
- For `--from/--to` range: fetch all entries overlapping that entire range once.
- Then for each orggle entry, check against the fetched set.

**Cost:** One extra `GET /time_entries` per sync (or per day), not per entry.

### Implementation Steps

1. Early in `main()`, after determining filters, if not `--dry-run` and not already fetched existing entries, call:

```python
def fetch_existing_entries(api_token, workspace_id, proxies, start_dt, end_dt):
    """Fetch existing Toggl time entries within the given range (inclusive)."""
    # Use ISO with Z? Toggl expects RFC3339? We can use start/end parameters
    params = [
        f"start_date={start_dt.isoformat()}",
        f"end_date={end_dt.isoformat()}"
    ]
    url = f"https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/time_entries"
    # add auth, proxies
    response = curl_request("GET", url, ...)
    if response.status == 200:
        return response.json  # list of entries
    else:
        # handle error
        return []
```

**Determining fetch range:**
- For `--day X`: fetch from X 00:00:00 to X 23:59:59 in UTC? But we need to match orggle's timezone interpretation. Orggle's entries have timezone-aware ISO strings. We can compute the min start and max stop among all entries we plan to upload, and fetch entries that overlap that entire span.

Simpler: fetch for the same date(s) as our entries but in UTC? Could miss entries if timezones differ. Better: fetch with a range that definitely covers all our entries: from earliest start of our entries minus 1 day, to latest stop plus 1 day. Over-fetch but safe.

Actually Toggl's `start_date` and `end_date` filter by the entry's `start` timestamp. So we can fetch all entries that started between our earliest start and our latest stop. That will include any overlapping entry because any overlapping entry must start before our entry's stop and end after our entry's start. So fetch entries that start during our time window should catch most overlaps, except an entry that starts before our window but overlaps into it. Example: our entry 10-12, existing entry 9-11 overlaps. Existing starts at 9, which might be before our earliest start if earliest start is 10. So we need to extend start back by max duration? Better: fetch entries with `start_date` = min(our starts) - (max duration buffer) and `end_date` = max(our stops) + buffer. Or fetch a full day range.

Simplify: For per-day operations (`--day`), fetch all entries for that day (00:00 to 23:59 local? But we need timezone awareness). This gets messy.

**Alternative**: For each entry, after creating, check if any existing entry with same start and stop? That's too late. Or use Toggl's duplicate detection? Toggl doesn't have that.

Given complexity, maybe we skip this for now or make it optional `--check-overlap` flag with a warning that it's slow.

---

## Simpler Approach: Warn Only, Not Prevent

Instead of preventing overlap, just log a warning after creating if Toggl already has overlapping entries. But then we'd have double entry. Not helpful.

---

## Revised Approach: Hash-Based Conflict Detection via Local DB

Alternatively, we could use local DB to track entries we synced, and also optionally fetch Toggl IDs for entries that we know about. But overlaps could be from other sources.

Maybe this is not a high-value improvement given the complexity and API cost. Overlap detection would require either:

- Extra API call per day/range (acceptable) but careful timezone math
- Complex logic to match by start/stop

Given the priority is Medium and effort M, we can spec but maybe not implement soon.

---

## Spec Outline (if implemented)

1. Add `--check-overlap` flag (opt-in, because it adds API call and time). Default off.
2. If enabled, at start of sync:
   - Determine time window to query: from min(entry start) to max(entry stop) across all entries to be synced.
   - Fetch existing Toggl entries for the workspace with start_date and end_date covering that window.
   - Store in list: `{id, start, stop}`
3. For each entry we are about to create:
   - Check if any fetched entry overlaps (interval check)
   - If overlap found:
     - In interactive mode: prompt: "Entry 'X' overlaps with existing Toggl entry 'Y' (9-10am). Skip? [Y/n]"
     - In batch mode with `--yes`: skip automatically with warning
     - Log warning
4. Count skipped overlaps.
5. Show summary: "Skipped N entries due to overlap with existing Toggl entries."

---

## Acceptance Criteria (if implemented)

- [ ] `--check-overlap` flag exists
- [ ] Fetches overlapping entries from Toggl in a single API call per sync
- [ ] Correctly identifies overlapping intervals
- [ ] Interactive mode prompts for each overlap (unless --yes)
- [ ] Batch mode skips by default with warning
- [ ] Overlap check works regardless of timezone (accounts for ISO strings)
- [ ] Summary includes overlap count
- [ ] Tests: interval overlap function, mock API fetch

---

## Effort (re-estimate)

- Overlap logic function: 1h
- Fetch existing entries API call: 2h (including error handling, timezone math)
- Integrate into sync flow: 2h
- Tests: 2h
- **Total:** ~7h (M-L)

---

## Conclusion

This is a valuable safety net for users with multi-source sync, but introduces network overhead and complexity. Recommend implementing after core safety features (dry-run, delete confirmation) and after modularizing API client.

Could be `--overlap-action=skip|warn|error` for flexibility.

For now, document as known limitation and maybe add `--check-overlap` in a future release.

---

**Status:** Deferred (consider after B-001-B-010)
**Created:** 2025-04-01
