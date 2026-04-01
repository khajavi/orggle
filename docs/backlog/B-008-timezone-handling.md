# B-008: Timezone Handling Improvements

**Priority:** Tier 2 (High) - Critical for users in multiple timezones or traveling
**Effort:** Medium (M - 6 hours)
**Dependencies:** None

---

## Problem Statement

Org-mode CLOCK timestamps are **timezone-naive** (no offset). They represent local time at the user's location when the clock was recorded. Orggle assumes the system's local timezone when converting to ISO format for Toggl.

**Issues:**

1. **Traveling / Different Timezones**: User travels from NY to LA. Org file written in NY time, but system timezone now PST. Running orggle interprets NY times as PST → 3 hour shift → entries appear at wrong times in Toggl.

2. **Daylight Saving Time (DST)**: Clock changes cause ambiguity. "2026-03-14 02:30" might not exist (spring forward) or might be ambiguous (fall back). DST transitions cause 1-hour discrepancies.

3. **Multiple Timezones in One File**: User tracks work across multiple timezones in same org file (e.g., traveling). Single system timezone cannot represent all correctly.

4. **No Documentation**: README doesn't explain timezone assumption. User unaware.

**Impact:** Entries appear at wrong hours in Toggl, causing confusion and manual correction.

---

## User Scenarios

**Scenario A - Remote worker traveling:**
- Mon-Fri in NY (EST), writes org entries at 9-5 local
- Returns to CA (PST), runs orggle on Sunday to sync week's entries
- System timezone = PST → 9am EST becomes 9am PST (should be 12pm PST)
- Toggl shows entries 3 hours earlier than actual work time

**Scenario B - DST transition:**
- Spring forward: Mar 14, 2am clocks skip to 3am. Work from 1am-3am? That's 2 hours but clock might show [02:00--04:00]? Actually clocks jump, so "missing hour" can't be clocked normally. Still, naive times around DST are ambiguous.

**Scenario C - Shared org file across timezones:**
- Team shares org file in git. Each member's system timezone differs. Running orggle on different machines produces different Toggl times.

---

## Proposed Solution

### Phase 1: Documentation & Timezone Assumption Flag (Immediate)

1. **Document current behavior clearly:**
   - "All clock times are interpreted in your system's local timezone."
   - "If you travel or work across timezones, set your system timezone to the timezone of the work being synced."

2. **Add `--timezone` option** to override system timezone:

```bash
orggle journal.org --timezone America/New_York
```

This sets the timezone used to interpret org clock times.

**Implementation:**
```python
import zoneinfo  # Python 3.9+
# or backports.zoneinfo for older

parser.add_argument(
    "--timezone",
    help="Timezone for interpreting org clock times (e.g., 'America/New_York', 'UTC'). Defaults to system local time."
)

# In parse_org_file or where we build datetime objects:
tz = timezone  # from args or system
if tz:
    tzinfo = zoneinfo.ZoneInfo(tz)
else:
    tzinfo = datetime.now().astimezone().tzinfo

# When building ISO string:
dt = datetime.strptime(date_str + " " + time_str, "%Y-%m-%d %H:%M")
dt = dt.replace(tzinfo=tzinfo)
iso = dt.isoformat()
```

**Code location:** When creating entry datetime in `parse_org_file` (around line 335-345):

Currently:
```python
start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
start_iso = start_dt.isoformat()  # naive, no tz
```

Change to assign timezone before iso:

```python
start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
# Add timezone
if timezone:
    tz = zoneinfo.ZoneInfo(timezone)
else:
    tz = datetime.now().astimezone().tzinfo
start_dt = start_dt.replace(tzinfo=tz)
start_iso = start_dt.isoformat()
```

**Effort:** 3 hours (including tests, docs)

---

### Phase 2: Org File Timezone Properties (Advanced)

Org-mode has built-in timezone support via `TIMEZONE` property or `#+TIMEZONE:` file keyword.

**Example:**
```org
#+TIMEZONE: America/New_York
* TODO Work
  CLOCK: [2026-03-28 Sat 09:00]--[2026-03-28 Sat 17:00] => 8:00
```

Or per-heading:
```org
* TODO Meeting in London
  :PROPERTIES:
  :TIMEZONE: Europe/London
  :END:
  CLOCK: [2026-03-28 Sat 14:00]--[2026-03-28 Sat 15:00] => 1:00
```

**Implementation:**
- During parsing, detect file-level `#+TIMEZONE:` (line starting with that)
- Store in a variable `file_timezone`
- When parsing a heading, check for `:TIMEZONE:` property
- Use heading's timezone if present, else file timezone, else `--timezone` arg, else system local
- Apply to entry's datetimes

**Effort:** 8 hours (property parsing, priority chain, testing)

**Priority:** Tier 3 (Medium) - Nice for multi-timezone files

---

### Phase 3: Automatic Timezone Detection from CLOCK

Some org files encode timezone in timestamps like:
```
CLOCK: [2026-03-28 Sat 09:00--2026-03-28 Sat 17:00] => 8:00
```
If timestamps had "Fri 09:00EST" or used diary-time-style? But org-mode typically stores in local time without offset.

**Not feasible** because offset lost. Phase 1/2 are better.

---

## Detailed Implementation (Phase 1)

### 1. Imports

```python
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Py3.8-
```

Actually Python 3.9+ has zoneinfo builtin. Check project Python version requirement (probably 3.7+ from README). Use backport for 3.7/3.8? Can add conditional import or just require Python 3.9+. But README says 3.7+. So we should support 3.7.

Options:
- Use `pytz` (already maybe not in deps)
- Use `zoneinfo` backport: `pip install backports.zoneinfo`
- Or fallback to `pytz` if available, else system tz only

Simpler: Only support Python 3.9+ for `--timezone` feature? That would be a version bump. Or use `pytz` which is common. But that adds dependency.

**Decision:** For now, implement using `datetime.timezone` and `zoneinfo` if available. If not, maybe use `pytz` as optional? Let's not overcomplicate.

Actually we can handle timezone conversion without external libs by using standard library only:

```python
import datetime
import time

# Get system timezone name? Not easily portable.
# But we can create a timezone from offset: datetime.timezone(timedelta(hours=-5))
# Not helpful for named zones.

# If user provides --timezone as "America/New_York", we need zoneinfo.
# So we should add backports.zoneinfo as dependency for Python < 3.9.
# Update requirements.txt: backports.zoneinfo; python-<3.9 dependency?
```

Better approach: Add `zoneinfo` to install script (pip install). Since project already has virtual environment setup, we can add it to requirements.txt.

**requirements.txt currently:** PyYAML (optional?). Actually file is empty.

We'll modify install to add `zoneinfo` backport for Python < 3.9, and use builtin for >=3.9.

Thus:

```python
import sys
if sys.version_info >= (3, 9):
    from zoneinfo import ZoneInfo
else:
    from backports.zoneinfo import ZoneInfo
```

Add to dependencies:
```
backports.zoneinfo; python_version<'3.9'
```

Or just always install backport, it's harmless on >=3.9 (just no-op? Actually backport packages itself as zoneinfo, would conflict). Use conditional.

For simplicity in backlog spec: assume we manage dependencies properly.

---

### 2. Parser Argument

```python
parser.add_argument(
    "--timezone",
    help="Override system timezone for interpreting clock times (e.g., 'America/New_York', 'UTC'). Useful when syncing from a different timezone."
)
```

### 3. Modify `parse_org_file`

Current signature: `def parse_org_file(file_path: str, org_mappings: List[dict] = None) -> List[dict]:`

We need to pass timezone. Possibly also propagate through.

Option: make `parse_org_file` accept a `timezone` param. Update call in `main()`:

```python
entries = parse_org_file(args.org_file, org_mappings, timezone=args.timezone)
```

Implement:

```python
def parse_org_file(file_path: str, org_mappings: List[dict] = None, timezone: str = None) -> List[dict]:
    # ...
    # When parsing timestamps:
    try:
        if timezone:
            tz = ZoneInfo(timezone)
        else:
            # Use system local timezone
            tz = datetime.now().astimezone().tzinfo
        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
        start_dt = start_dt.replace(tzinfo=tz)
        stop_dt = datetime.strptime(stop_str, "%Y-%m-%d %H:%M")
        stop_dt = stop_dt.replace(tzinfo=tz)
    except Exception as e:
        # Handle invalid timezone name
        raise ValueError(f"Invalid timezone '{timezone}': {e}")
```

**Validation:** Add early validation of `--timezone` argument in `main()`:

```python
if args.timezone:
    try:
        ZoneInfo(args.timezone)
    except Exception as e:
        print(f"Error: Invalid timezone '{args.timezone}': {e}")
        sys.exit(1)
```

Place after argument parsing, before config load or file parsing.

---

### 4. Duration Calculation

Duration is computed as `(stop - start).total_seconds()`. With timezone-aware datetimes, this works correctly even across DST changes (though unlikely within a single entry). Keep as is.

---

### 5. Update Help & Docs

- Add description to `--timezone` flag
- Add section in README: "Timezone Handling"
- Example: "If you're traveling, use `--timezone` to specify the timezone of your org file entries."

---

## Acceptance Criteria

- [ ] `--timezone` flag accepts IANA timezone names (e.g., "America/New_York", "UTC", "Europe/London")
- [ ] Invalid timezone (e.g., "Mars/Phobos") produces clear error before parsing file
- [ ] Clock times are interpreted in specified timezone, converted to ISO with offset
- [ ] Without `--timezone`, system local timezone is used (current behavior)
- [ ] Duration calculation remains correct
- [ ] Toggl receives timestamps with correct offset (e.g., `2026-03-28T09:00:00-04:00`)
- [ ] Works in all modes: interactive, batch, dry-run, etc.
- [ ] Unit tests: mock timezone, verify ISO strings have correct offset
- [ ] Integration test: parse org with timezone override, check entry ISO format

---

## Example

**Org file:**
```org
* TODO Work
  CLOCK: [2026-03-28 Sat 09:00]--[2026-03-28 Sat 17:00] => 8:00
```

**Command in PST system:**
```bash
orggle journal.org --timezone America/New_York
```

**Result in Toggl:** Entry shows 9am-5pm **Eastern** (offset -04:00 or -05:00 depending on DST), not PST.

---

## Testing

**Unit test:**
```python
def test_parse_with_timezone():
    org = "* Test\n  CLOCK: [2026-03-28 Sat 09:00]--[2026-03-28 Sat 10:00] => 1:00"
    # Write to temp file, parse with timezone="America/New_York"
    entries = parse_org_file(temp_path, timezone="America/New_York")
    assert entries[0]["start"] == "2026-03-28T09:00:00-05:00"  # EST or EDT depending on date
```

**Manual:**
- Set system TZ to UTC, run with `--timezone America/Los_Angeles`, check ISO includes `-08:00` or `-07:00`.

---

## Effort Breakdown

- Dependency management (backports.zoneinfo): 1h
- Add argument and validation: 1h
- Modify `parse_org_file` to use tz: 2h
- Update tests: 1h
- Documentation: 1h
- Total: ~6h

---

## Risks & Questions

- Users may not understand timezone names. Provide help link to IANA tz database.
- Default to system local: that's current behavior, no change. Good.
- Should we also support `--utc` flag? Could add as shorthand for `--timezone UTC`.
- DST: ZoneInfo handles automatically. Good.

---

## Related Backlog Items

- **B-010**: Summary could show timezone used
- No direct dependencies

---

**Status:** Planned
**Created:** 2025-04-01
