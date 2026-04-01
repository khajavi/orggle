# B-007: Progress Indicators for Long Syncs

**Priority:** Tier 2 (High) - Reduces anxiety, improves perceived performance
**Effort:** Small (S - 3 hours)
**Dependencies:** None

---

## Problem Statement

When syncing many entries (50+), orggle provides little feedback during network operations:

- Interactive mode: one entry at a time, but only shows after completion or failure
- Batch mode: per-day sync, but each day may have many entries with no progress indication
- No ETA, no percentage, just sequential output
- Long delays (network latency, retries) leave user wondering if it's hung

**User quote:** "I have 200 entries from a conference. I ran batch mode and it took 10 minutes. I had no idea how far along it was or how much longer."

---

## Proposed Solution

Add progress indicators that show:
1. Current entry being processed (index out of total)
2. Optional progress bar (using simple text or external library like `tqdm`)
3. ETA calculation based on average time per entry
4. Configurable: can be disabled with `--quiet`

### Implementation Options

**Option 1: Simple Text Counter**

```text
[12/45] Syncing: Task description...
```

Pros: trivial to implement, no dependencies
Cons: Not very pretty, no ETA

**Option 2: Progress Bar with `tqdm`**

Add dependency on `tqdm` library (already maybe in venv? no). Or implement simple bar manually.

Pros: nice visual bar, built-in ETA
Cons: additional dependency, may not be installed

**Option 3: Minimal built-in bar**

Print status line that updates in place using `\r`:
```text
Syncing: [#####---------] 12/45 (27%, ~2m remaining)
```

Pros: no dependencies, decent info
Cons: terminal handling complexity (line clearing, CI environments)

**Option 4: `--verbose` / `--progress` flags**

Don't show progress by default for small syncs (<10 entries), but show for larger.

---

## Recommended Approach (Option 1 + 3 Hybrid)

Implement a lightweight progress indicator that:
- Shows current entry number and total: `[N/M]`
- Shows entry description truncated to fit line
- Updates on each entry start (not after) for immediate feedback
- For batch mode, also show day progress: `[Day 3/5]`

**No external dependencies.** Use simple print with carriage return for in-place updates, but only if stdout is a TTY. If not TTY (e.g., piped), don't use `\r`, just print sequentially.

Implementation:

```python
def maybe_print_progress(current: int, total: int, entry: dict, *, prefix: str = "", suffix: str = ""):
    """Print progress line if appropriate."""
    # If not a tty, just print normally (with newline)
    # If tty, use \r to overwrite line
    line = f"{prefix}[{current}/{total}] {entry['description'][:50]}"
    if suffix:
        line += f" {suffix}"
    if sys.stdout.isatty():
        print(f"\r{line}", end="", flush=True)
    else:
        print(line)
```

At end of sync (or when interrupted), print newline to move cursor.

---

## Specific Changes

### In Interactive Mode

Replace current sync loop (around line 650):

```python
# Before:
for i, entry in enumerate(entries, 1):
    response = input(...)  # prompt
    if response == 'n': continue
    # sync

# After (with --yes or after user confirms):
for i, entry in enumerate(entries, 1):
    # Show progress before network call
    if not args.quiet:
        maybe_print_progress(i, len(entries), entry, suffix=f"...")
    # Make API call
    result = create_entry(...)
    if result:
        # Print success on new line if we used \r, else print as part of progress?
        if sys.stdout.isatty():
            print(f"\r✓ {entry['description'][:60]}")
        else:
            print(f"✓ [{i}/{len(entries)}] {entry['description']}")
```

Need to handle errors similarly.

### In Batch Mode

Around line 489 (batch daily grouping):

```python
for day_num, (day, day_entries) in enumerate(sorted(grouped.items(), reverse=True), 1):
    # Show day header with day progress
    if not args.quiet:
        print(f"[Day {day_num}/{len(grouped)}] {day} ({len(day_entries)} entries)")

    # Prompt user (unless --yes)
    response = input(...)

    if response in ('y', ''):
        for i, entry in enumerate(day_entries, 1):
            if not args.quiet:
                maybe_print_progress(i, len(day_entries), entry, prefix=f"  [{i}/{len(day_entries)}] ")
            # sync
```

**`--quiet` flag**: Would suppress these progress lines, only show errors? Add:

```python
parser.add_argument('--quiet', '-q', action='store_true', help='Suppress progress output')
```

---

## ETA Calculation (Optional Stretch)

Track start time of sync, compute moving average duration per entry, estimate remaining:

```python
import time
start_time = time.time()
times = []

for i, entry in enumerate(entries, 1):
    iter_start = time.time()
    # sync...
    elapsed = time.time() - iter_start
    times.append(elapsed)
    if len(times) > 5:
        times.pop(0)
    avg = sum(times) / len(times)
    remaining = avg * (len(entries) - i)
    eta_str = f"{int(remaining)}s" if remaining < 60 else f"{int(remaining/60)}m"
    maybe_print_progress(i, len(entries), entry, suffix=f"[ETA: {eta_str}]")
```

---

## Acceptance Criteria

### Functional
- [ ] Progress indicator shows current entry number and total (e.g., `[12/45]`)
- [ ] Entry description displayed (truncated to ~60 chars)
- [ ] In TTY mode, updates in-place using carriage return
- [ ] In non-TTY mode (piped), prints each entry on its own line
- [ ] Works in both interactive and batch modes
- [ ] `--quiet` flag suppresses progress output (still prints errors and final summary)
- [ ] On completion, prints final summary (already exists)
- [ ] Progress shown before network call so user sees activity

### Edge Cases
- [ ] Single entry: show `[1/1]` then result
- [ ] Many entries: no line overflow (wrap? truncate)
- [ ] Failed entry: still shows progress and then error message
- [ ] User presses 'q' to quit: progress line cleared properly

### Optional Nice-to-have
- [ ] ETA calculation based on recent entries
- [ ] Daily batch progress: `[Day 2/5]` prefix

---

## Implementation Checklist

- [ ] Add `--quiet` flag to parser
- [ ] Create `maybe_print_progress()` helper
- [ ] Modify interactive loop to show progress
- [ ] Modify batch loop to show per-entry progress within day
- [ ] Ensure proper line handling when user quits or errors occur
- [ ] Add tests: capture stdout, verify progress format (hard to test TTY, maybe mock isatty)
- [ ] Manual testing with large org file (50+ entries)
- [ ] Update README to mention progress indicator (implicitly shows)

---

## Example Output

**Interactive with TTY:**
```
Using profile: work
Parsing journal.org... 45 entries

[1/45] Updated project plan documentation
  ✓ Synced
[2/45] Team standup meeting
  ✓ Synced
...
[45/45] Final review
  ✓ Synced

Synced 45 entries, skipped 0
```

**Batch mode with TTY:**
```
Using profile: work
[Day 1/3] 2026-03-15 (15 entries)
  [1/15] Task A
  ✓
  [2/15] Task B
  ...
[Day 2/3] 2026-03-14 (10 entries)
  ...
```

**With `--quiet`:**
```
Using profile: work
Parsing journal.org... 45 entries
✓ Synced: entry 1
✓ Synced: entry 2
...
```

---

## Documentation Updates

Update README: mention that progress is shown during sync, use `--quiet` to suppress.

Fish completion: add `--quiet`, `-q`.

---

## Future Enhancements

- Integrate `tqdm` if user installs it: try/except ImportError, fallback to simple
- Add `--progress=auto|always|never` for fine control (like git)
- Add spinner for initial network calls (workspace fetch, project lookup) if they take long
- Show time elapsed at end: "Completed in 2m 34s"

---

## Risks

- Overwriting lines with `\r` can break log parsing (if user redirects to file). Mitigation: only use `\r` when stdout is TTY.
- Progress adds slight overhead (formatting), negligible.
- Multi-line descriptions might wrap; truncate to single line.

---

## Related Backlog Items

- **B-010**: Summary stats complement progress
- **B-012**: `--output json` would be incompatible with live progress (needs complete result)

---

**Status:** Planned
**Created:** 2025-04-01
