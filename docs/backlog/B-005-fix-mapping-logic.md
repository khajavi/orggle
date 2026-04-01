# B-005: Fix Description Mapping Logic

**Priority:** Tier 2 (High) - Users get confused by incorrect description assignments
**Effort:** Small (S - 3 hours)
**Dependencies:** None

---

## Problem Statement

The `org_mappings` feature allows regex-based description rewriting. However, the current implementation has **counterintuitive behavior** that trips up users.

### Current Implementation (Buggy)

From code (lines 426-443):

```python
# Apply mappings: pattern matches ANY line after a CLOCK entry, but applies to LAST entry
for mapping in org_mappings:
    pattern = mapping.get("pattern", "")
    replacement = mapping.get("description", "")
    if re.search(pattern, line, re.IGNORECASE):
        if entries:
            last_entry = entries[-1]  # Gets LAST entry in the list
            last_entry["description"] = replacement
            mapped = True
            break
```

**Problem:** This applies the mapped description to the **most recent entry** in the list (the last one parsed so far). But the pattern appears **after** that entry's CLOCK line, which could be many lines later.

### User Expectation vs Reality

**Org file:**
```org
* TODO Work on project A
  CLOCK: [2026-03-28 Sat 09:00]--[2026-03-28 Sat 12:00] => 3:00
  Some notes about this task...
  - rest

* TODO Work on project B
  CLOCK: [2026-03-28 Sat 14:00]--[2026-03-28 Sat 17:00] => 3:00
```

**User expectation:**
- `- rest` tag after "project A" should map "Work on project A" → "Break Time"
- Project B should remain "Work on project B"

**Actual behavior:**
- `- rest` matches, applies to **last entry** which is "Work on project B"
- Result: Project B becomes "Break Time", Project A stays unchanged
- **Backwards!**

---

## Why It's Currently Working (But Wrong)

The entries list is built in order parsed. When the parser reads:
1. Enters task A heading
2. Parses CLOCK → appends Entry A to `entries` (entries[-1] = Entry A)
3. Reads notes and `- rest` line → applies to Entry A **at that moment** ✓ This is correct!
4. Enters task B heading
5. Parses CLOCK → appends Entry B (entries[-1] = Entry B) ✓
6. Reads `- rest` again? Actually the file might not have it. But if it did after B, that's when mapping would apply.

Wait, let's re-trace the parsing flow (line 201-403):

The parser iterates through lines. When it encounters a CLOCK line, it creates an entry and appends to `entries`. Then later, when a non-CLOCK line is read, it checks for mappings **on every non-CLOCK line** and applies to `entries[-1]` if a match.

**So the mapping applies to the entry that was last added BEFORE the current line.** That is actually the **immediately preceding entry** (the one whose CLOCK was just parsed and not yet replaced by another heading). That seems correct!

Let's test mentally with sample:

```
Line 1: * TODO A          (heading, sets current_heading)
Line 2:   CLOCK: [...]     (parsed, creates entry with heading "A", appended to entries)
         entries = [Entry A]
Line 3:   - rest           (non-clock, looks for pattern, matches "- rest")
                         → applies to entries[-1] which is Entry A ✓
Line 4: * TODO B          (new heading, current_heading = "B")
Line 5:   CLOCK: [...]     (creates Entry B, appended)
         entries = [Entry A, Entry B]
Line 6:   (no mapping line)
```

So it should work correctly. The last entry at the time of matching is indeed the one we want.

**But the bug report says mappings apply to wrong entry.** Why?

Looking at test_sample.org:
```org
* TODO Work on project A
  CLOCK: [2026-03-25 Wed 09:00]--[2026-03-25 Wed 11:00] =>  2:00

* TODO Work on project B
  CLOCK: [2026-03-28 Sat 13:00]--[2026-03-28 Sat 15:00] =>  2:00
  - rest   <-- Wait, the "- rest" is on line 5 AFTER the CLOCK line for project B, but still indented under B

* TODO Meeting with team
  CLOCK: [2026-03-29 Sun 10:00]--[2026-03-29 Sun 11:30] =>  1:30

* TODO Personal errands
  CLOCK: [2026-04-01 Mon 14:00]--[2026-04-01 Mon 15:00] =>  1:00
```

There is NO `- rest` tag in the sample! That means mapping was not tested in manual test. Let's check if there's any pattern in the sample: actually test_sample.org just has plain entries.

**But the issue arises from manual testing where user had `- rest` and saw B get mapped instead of A.** That suggests a real bug.

Let me read the mapping application code more carefully:

Around line 201-403, the main parsing loop:

When a **non-empty, non-CLOCK line** is encountered (`elif line.strip():`), it:
1. Checks if matches `hashtag_pattern` (skip)
2. Checks if matches heading pattern: if so, set `current_heading`
3. Else: tries `org_mappings`

```python
for mapping in org_mappings:
    pattern = mapping.get("pattern", "")
    replacement = mapping.get("description", "")
    if re.search(pattern, line, re.IGNORECASE):
        if entries:
            last_entry = entries[-1]
            last_entry["description"] = replacement
            mapped = True
            break
```

So for **every** non-heading, non-empty line, it tries to apply mapping to current `entries[-1]`.

**Problem possibility**: What if the mapping line appears BEFORE the CLOCK line of the entry you want to map?

From the issue: The mapping is intended to transform the **next** entry, not the previous one. Users might write:

```
* TODO Meeting
  - meeting   <-- want this to map the next clock, not the previous
  CLOCK: [2026-...] => ...
```

Or they might write:

```
* TODO Meeting
  CLOCK: ...
  - meeting   <-- This maps the meeting entry (correct)
```

Which is intended? Usually people put tags/notes **before** the clock or **after**. In org-mode, you can have properties before CLOCK:

```
* TODO Some task
  :PROPERTIES:
  :Effort: 2h
  :END:
  CLOCK: ...
```

Or after:

```
* TODO Some task
  CLOCK: ...
  - meeting
```

The current implementation applies mapping to the most recent entry **at the time the mapping line is parsed**. If the mapping line is BEFORE the CLOCK, there is no recent entry yet (or it's from previous task), so it would apply to the wrong entry.

**Conclusion:** The bug is that mappings should apply to the **upcoming** CLOCK entry, not the **previous** one. Or at least it should be configurable. But documentation and common usage (like example in README) shows:

```org
* TODO Task
  CLOCK: [2026-03-28 ...] => 1:00
  - rest
```

That's after the clock, so it would correctly map to that task. So the README example is correct.

But if a user puts mapping before clock, it fails. Is that the pain point? Possibly.

**Let's search the code for a comment explaining this:**

There's a comment at line 428: `# mappings applied to current entry`. Hmm, that's vague.

The README (line 410-424) shows mapping applied after clock (tag line after). So that's the expected use.

**Wait, there's a deeper bug:** Look at parsing flow when a heading is encountered:

- At line ~230: `if re.match(r'^\*+', line):` sets `current_heading`
- But what if there's a mapping line under a heading **before** the CLOCK? That would try to apply to `entries[-1]` which is the previous task's entry (wrong).

So the safety gap: **mapping lines appearing before a CLOCK line will incorrectly map to the previous task's entry.**

Also, what about multiple mapping lines? Only the first match applies (due to `break`). That's fine.

---

## Proposed Fix

We need to **delay** mapping application until we see a CLOCK entry, then apply any pending mappings to that new entry.

### Algorithm Change

Instead of applying mapping immediately when matching line seen:

1. Maintain a `pending_mappings` list (or set) of replacements that have been seen but not yet applied
2. When a non-heading line matches a mapping pattern, **add** it to `pending_mappings` (but don't modify any entry yet)
3. When a CLOCK line is encountered and a new entry is created, apply all pending mappings to that entry **in order** (first match wins, so order matters)
4. After applying, clear `pending_mappings` for that entry? Or allow multiple mappings (only first applies anyway)? Should clear after entry created so next entry starts fresh.
5. Also apply any mappings that were collected **during** the parsing of that task (lines before the next CLOCK).

But wait: The original design might have intended that mappings apply to the **most recent entry** because they want mapping tags to appear anywhere within the task's subtree (notes, properties, etc.). That is, after the CLOCK, you can have any number of lines and the mapping applies if any of them match. That's what current code does.

The issue is: if you have multiple tasks in a row, each with `- rest` after its clock, they all get mapped. That's correct.

The problematic case is when you have a mapping line **before** any CLOCK (like at top of file), or between heading and clock. That would apply to previous entry.

**Solution:** Change logic:

- Only apply mappings to the **current section** (entries that belong to the current heading) **after** a CLOCK is found
- Keep a buffer of mapping lines seen since last CLOCK
- On new entry creation, apply buffered mappings to that entry

But the existing code already applies to `entries[-1]` which is the most recent entry. That entry is from the current heading unless we just started a new heading without a clock yet. Hmm.

Let's simulate problematic case:

```
Line 1: * TODO A  (current_heading = "A")
Line 2:   - rest   (no entries yet, entries=[], so `if entries:` false, no mapping applied) ✓ Good
Line 3:   CLOCK:   (creates Entry A, entries=[A])
Line 4: * TODO B  (current_heading = "B")
Line 5:   - rest   (entries exists, entries[-1] is Entry A! Maps to A)
```

This is the bug: mapping under B heading before its clock applies to A.

**Why?** Because Entry B hasn't been created yet when the mapping line is seen. The mapping line is encountered **before** the CLOCK line for B.

So we need to buffer mapping lines for the current heading until we see a CLOCK.

---

## Recommended Implementation

### Option 1: Buffer Mappings (More Robust)

Maintain:

```python
pending_mappings = []  # List of (pattern, replacement) that have been seen for current heading

# When non-heading line matches a mapping:
for mapping in org_mappings:
    if re.search(pattern, line, re.IGNORECASE):
        pending_mappings.insert(0, (pattern, replacement))  # prepend to preserve order
        break  # first match wins

# When creating a new entry from a CLOCK:
entry = {
    "description": current_heading,
    ...
}
# Apply first pending mapping that matches description? Wait, mappings are not applied to description auto-magically.
# Actually mappings replace the ENTIRE description with the replacement string.
# So: if pending_mappings exist, take the first one (most recent? but they all apply). Use first match logic:
if pending_mappings:
    # Apply the first pending mapping (original code used first match in loop order)
    # But we need to decide which mapping to apply. Actually the mapping is not a filter, it's a direct replacement.
    # The mapping's pattern is used to decide if it applies. The replacement is the new description.
    # So we need to re-run the pattern match? Or we already matched when buffering.
    # Better to buffer as (replacement, matched_pattern) or just apply immediately but to the future entry.
    pass
```

This is getting complex. Simpler: **Change semantics to apply mappings to the NEXT entry, not the previous one.** That is a design decision.

**New rule:** Mapping lines are collected and applied to the **next** CLOCK entry encountered in the same heading (or after the mapping). That matches user intuition: "This tag describes the task I'm about to clock."

Implementation: maintain `next_entry_mapping` variable (string or None). When a mapping line matches, set `next_entry_mapping = replacement`. When a new entry is created from a CLOCK, if `next_entry_mapping` is set, use it as description and clear it.

But: What if there are multiple mapping lines before the clock? Last one wins (overwrites). That's fine.

What if mapping appears after clock? That would be for that entry (current behavior). To preserve both behaviors, we need two-phase: mappings before clock apply to next entry; mappings after clock apply to that same entry. That's actually implicit: after clock, `next_entry_mapping` is None (cleared), but if another mapping line appears, it sets `next_entry_mapping`, which then would apply to the **next** clock, not the current. So to apply to current, the mapping must appear before the clock? No, after clock we need immediate application. So we need both:
- Mappings before CLOCK: apply to that CLOCK when seen
- Mappings after CLOCK: apply immediately to that entry

What defines "after CLOCK"? The entry already exists and is in `entries[-1]`. If `next_entry_mapping` is None and we see a mapping line, we can apply directly to `entries[-1]` (current behavior). But if we also support before-CLOCK mappings via buffer, we need to know whether we've seen a CLOCK since the last mapping line.

Simpler approach: **Mappings only apply to the immediately preceding CLOCK entry.** That's current behavior. The bug is when a mapping appears under a new heading before its CLOCK; it shouldn't apply to previous heading. So we just need to ensure we only apply to entries that belong to the **current heading**.

### Option 2: Track Current Entry Properly (Simplest Fix)

The problem: When we see a mapping line under heading B but before its CLOCK, `entries[-1]` is still Entry A from previous heading. We should check that the entry's heading matches `current_heading` before applying.

Solution: Store heading in entry (already done!). Then when applying mapping, verify:

```python
if entries:
    last_entry = entries[-1]
    # Check that last_entry's heading matches current_heading
    # But entry["heading"] holds heading at time of CLOCK, which was set by current_heading then.
    # If current_heading has changed since entry was created, this mapping belongs to new heading, not this entry.
    if last_entry.get("heading") == current_heading:
        last_entry["description"] = replacement
```

**This single check prevents cross-heading mapping leakage!**

Let's verify with problematic case:

```
Line 1: * TODO A  → current_heading="A"
Line 2:   CLOCK   → creates Entry A with heading="A"
Line 3: * TODO B  → current_heading="B"
Line 4:   - rest  → entries[-1] = Entry A, but Entry A heading="A" != current_heading "B" → SKIP mapping ✓
Line 5:   CLOCK   → creates Entry B with heading="B"
         Now if there was another - rest after, it would apply because heading matches.
```

**Edge case:** What if heading line appears but no CLOCK yet, and a mapping appears? `current_heading` changes, entries[-1] still old entry with different heading → skip. Correct.

**What about mapping lines that appear after clock within same heading?** heading matches → apply. Good.

**What about mapping lines that appear after multiple non-heading lines?** Still in same heading, last entry heading still matches current_heading? Yes, unless we parsed another heading (which would change current_heading). So mapping applies to most recent entry from current heading. That's correct.

---

## Implementation (Option 2 - Simple)

Modify mapping application block (around line 434-442):

```python
if re.search(pattern, line, re.IGNORECASE):
    if entries:
        last_entry = entries[-1]
        # NEW: Only apply if this entry belongs to current heading
        if last_entry.get("heading") == current_heading:
            last_entry["description"] = replacement
            mapped = True
            break
```

That's it! One line addition.

But wait: `current_heading` includes TODO/DOING tags? The heading parsing (line 230-237) strips those and stores plain text in `current_heading`. Entry's heading also gets stripped (line 334-338). So they should match exactly.

Test:

Org: `* TODO Task A` → current_heading = "Task A"
Entry: `"heading": "Task A"` → match ✓

Edge: What if entry created from heading that had no tags, then later heading with tags changes current_heading but doesn't affect old entry. Fine.

---

## Edge Cases to Consider

1. **Multiple CLOCKs under same heading** (common for split sessions):
   ```
   * TODO Task
     CLOCK: [9-10]
     Some notes
     - rest
     CLOCK: [11-12]
     - meeting
   ```
   After first CLOCK, entry A added. Mapping `- rest` → applies to Entry A (heading matches). Good.
   Second CLOCK, entry B added. Last entry now Entry B. Mapping `- meeting` → applies to Entry B (heading matches). Good.

2. **Entry without heading** (shouldn't happen, but if current_heading is None):
   - Entry gets heading from current_heading which could be None
   - Mapping check: last_entry.get("heading") == current_heading (both None) → True
   - Acceptable?

3. **Heading change without content**:
   ```
   * Heading A
   * Heading B
     CLOCK: ...
   ```
   After second heading, current_heading = "Heading B". Entry B heading="Heading B". Match.

4. **Mapping line in middle of task but after several other headings?** Not possible because the mapping line would be under some heading; that heading becomes current_heading; if there's no entry yet for that heading, `entries[-1]` is from previous heading but heading mismatch prevents apply.

**All good.**

---

## Acceptance Criteria

- [ ] Mapping lines under a new heading **before** its CLOCK do NOT apply to previous heading's entry
- [ ] Mapping lines after a CLOCK under same heading DO apply to that heading's entry
- [ ] Multiple mappings per heading work correctly (first match wins)
- [ ] Existing tests still pass
- [ ] New test added: verifies cross-heading leakage is prevented

---

## Example Fix

**Before fix:**

```org
* Task A
  CLOCK: ...
* Task B
  - rest   (maps to Task A - WRONG)
  CLOCK: ...
```

After fix:
- `- rest` under "Task B" heading is ignored because no entry yet for B
- To map Task B, put `- rest` **after** its CLOCK or add another `- rest` after.

**Recommended doc update:** Show correct usage pattern:

```org
* TODO My Task
  CLOCK: [2026-03-28 Sat 09:00]--[2026-03-28 Sat 10:00] => 1:00
  - rest   # This will map "My Task" → "Break Time"
```

Instead of:

```org
* TODO My Task
  - rest   # This is IGNORED (no entry yet)
  CLOCK: ...
```

---

## Testing Strategy

**New unit test** (add to test_orggle.py):

```python
def test_mapping_applies_only_to_current_heading():
    """Mapping lines under a new heading should not affect previous entry."""
    org_content = """
* TODO Task A
  CLOCK: [2026-03-28 Sat 09:00]--[2026-03-28 Sat 10:00] => 1:00

* TODO Task B
  - rest
  CLOCK: [2026-03-28 Sat 11:00]--[2026-03-28 Sat 12:00] => 1:00
"""
    config = {
        "org_mappings": [
            {"pattern": "^\\s*- rest$", "description": "Break Time"}
        ]
    }
    entries = parse_org_file_from_string(org_content, config.get("org_mappings", []))
    assert len(entries) == 2
    assert entries[0]["description"] == "Task A"  # Not mapped
    assert entries[1]["description"] == "Break Time"  # Mapped (after clock? Actually - rest before clock for B)
```

Wait, for Task B, `- rest` is before its CLOCK. With current (fixed) logic, it would be skipped because there's no entry yet. Then when CLOCK comes, there's no pending mapping. So Task B would NOT be mapped. That means user's expected behavior (pre-clock mapping) still fails.

**So the simple heading check prevents cross-heading leakage but doesn't enable pre-clock mapping.** Pre-clock mapping would require buffering. Is pre-clock mapping a common use case? Possibly not; the README shows after-clock. But could be used.

If we want to support pre-clock mapping (mapping before the clock), we need buffering. That's more work.

**Decision:** Should we support pre-clock mapping? Let's evaluate user scenarios:

- In org-mode, it's common to write notes **before** clocking? Maybe:
  ```
  * TODO Task
    :PROPERTIES:
    :Effort: 2h
    :END:
    CLOCK: ...
  ```
  Properties are before clock. If someone wants to map based on a property, they'd want that. But mapping uses regex on line content, so they could put `:toggl: Break` or similar. That's plausible.

But the original design: `org_mappings` were meant to replace placeholder descriptions like "- rest" that appear **after** the clock as a tag. The README example is after-clock.

**Verdict:** Enforce after-clock mapping only. Document: "Place your mapping pattern (e.g., `- rest`) after the CLOCK line." This is the simplest and matches current expectations (the README already shows that).

Thus the heading-check fix is sufficient: it prevents cross-heading bleed. Users who put mapping before clock will just not get mapping (they'll see it's not working and move it after). That's acceptable UX (may cause confusion initially but can be documented).

---

## Implementation Checklist

- [ ] Add heading equality check in mapping application code (line ~440)
- [ ] Add unit test for cross-heading mapping leakage
- [ ] Update README to clarify: "Mappings must appear AFTER the CLOCK line of the entry they should modify"
- [ ] Manual test with sample org showing before/after behavior
- [ ] Run existing tests to ensure no regression
- [ ] Consider performance: `last_entry.get("heading")` is cheap

---

## Documentation Update

Add to README under "Entry Mapping":

> **Important:** Mapping patterns (like `- rest`) must appear **after** the `CLOCK:` line they should apply to. Placing them before the clock will not map the entry.

Example:

```org
* TODO Correct
  CLOCK: [2026-03-28 ...] => 1:00
  - rest    ← This maps the entry to "Break Time"

* TODO Incorrect
  - rest    ← This is ignored (no entry yet)
  CLOCK: ...
```

---

## Related Backlog Items

None directly, but good foundation for B-006 (config validation) which might validate that mappings compile.

---

**Status:** Planned
**Created:** 2025-04-01
