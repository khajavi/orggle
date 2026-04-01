# B-016: Automatic Batch Mode Based on Entry Count

**Priority:** Tier 3 (Low) - Reduce friction for heavy sync days
**Effort:** Small (S - 2 hours)
**Dependencies:** None

---

## Problem Statement

By default, orggle prompts **per entry**. When there are many entries (20+), confirming each is tedious. The `--batch daily` mode groups by day, but user must remember to use it and decide when.

**User quote:** "I ended up with 50 entries and had to press 'y' 50 times. I forgot to use --batch."

---

## Proposed Solution

Add a configurable threshold: if number of entries exceeds N, automatically switch to batch mode (daily grouping) or automatically say "yes" to all.

**Better:** Add a flag `--auto-batch[=N]` that:
- If just `--auto-batch` → use default threshold (10)
- If `--auto-batch=N` → threshold of N entries
- When entry count > threshold, behave as if `--batch daily --yes` was specified (auto-accept days)
- But still show summary

Alternatively, add config option in YAML:

```yaml
defaults:
  auto_batch_threshold: 15
```

---

## Implementation

**Option A (CLI flag):**

```python
parser.add_argument(
    "--auto-batch",
    nargs='?', const=10, type=int,  # --auto-batch means 10, --auto-batch=20 means 20
    metavar="N",
    help="Automatically enable batch mode if more than N entries (default: 10). Equivalent to '--batch daily --yes' when threshold exceeded."
)
```

In `main()`, after parsing entries and before any interactive prompts:

```python
if args.auto_batch and len(entries) > args.auto_batch:
    print(f"Auto-enabling batch mode (>{args.auto_batch} entries)")
    args.batch = 'daily'
    args.yes = True  # or just skip prompts, but --yes also skips delete confirm; careful
```

Caution: `--yes` also skips `--delete-existing` confirmation (B-002). That might be too aggressive. Instead, maybe auto-batch should just set batch mode but not auto-accept days unless also `--yes`. Or auto-batch could imply `--yes` for batch prompts only. Simpler: auto-batch means "group by day and accept all days automatically". That's essentially batch+yes. But might surprise users who want to review days. So we could make it not imply yes, just batch. But the pain is having to confirm many entries; batch already reduces to per-day, but still prompts per day. If auto-batch doesn't auto-accept days, user still has to confirm each day. So auto-batch really needs to include auto-accept for the full hands-off experience.

Maybe auto-batch says: if count > threshold, `args.batch='daily'` and `args.auto_accept=True` (new flag that only affects batch mode). But we already have `--yes`. So auto-batch should set both batch and yes.

**Edge:** User specified `--yes` already, fine. User specified `--no-confirm`? Not exists.

**Option B (config default):** Add `defaults.auto_batch_threshold` to config file, no CLI flag. Simpler and more persistent (user sets once). But CLI flag is more flexible.

**Recommendation:** CLI flag `--auto-batch[=N]` as it's one-off convenience.

---

## Acceptance Criteria

- [ ] `--auto-batch` flag exists, optional integer N default 10
- [ ] When entry count > N, automatically sets `args.batch = 'daily'` and `args.yes = True` (or equivalent)
- [ ] User is notified: "Auto-enabling batch mode (N>threshold)"
- [ ] Works with all other flags (dry-run, delete-existing, etc.)
- [ ] Overrides manual `--batch` setting? If user already set `--batch` or not, we force batch if threshold exceeded. That's okay.
- [ ] Edge: If threshold is 0, always auto-batch.
- [ ] Tests: count above threshold triggers batch+yes, count below does not

---

## Effort

- Parser argument: 15m
- Logic in main: 30m
- Tests: 15m
- **Total:** 1h

---

## Documentation

```markdown
### Automatic Batch Mode

If you often have many entries to sync, use `--auto-batch[=N]` to automatically batch and accept when entry count exceeds threshold:

```bash
orggle journal.org --auto-batch        # threshold 10
orggle journal.org --auto-batch=5      # threshold 5
```

This is equivalent to `--batch daily --yes` when triggered.

---

## Risks

- Could cause unexpected large sync if user just testing with small dataset but threshold low. But they chose flag.
- Not a big deal.

---

**Status:** Planned
**Created:** 2025-04-01
