# B-013: Add `--since` and `--until` as Aliases to `--from`/`--to`

**Priority:** Tier 3 (Low) - Minor UX convenience, matches common CLI conventions
**Effort:** Extra Small (XS - 30 minutes)
**Dependencies:** None

---

## Problem Statement

The `--from` and `--to` flags are clear but not mnemonic for users accustomed to `--since`/`--until` from other tools (git log, GitHub search, many APIs).

**User quote:** "I keep typing --since instead of --from because that's what I'm used to from git."

---

## Proposed Solution

Add `--since` and `--until` as exact synonyms for `--from` and `--to`.

```bash
orggle journal.org --since 2026-03-01 --until 2026-03-15  # same as --from/--to
```

Both flags can be mixed? Should they be equivalent? Probably keep simple: add both as aliases, internally map to same dest variables.

---

## Implementation

In `create_parser()`:

```python
parser.add_argument(
    "--since", dest="from_date",
    help="Alias for --from", metavar="DATE"
)
parser.add_argument(
    "--until", dest="to_date",
    help="Alias for --to", metavar="DATE"
)
```

**Note:** Using `dest` to reuse same storage as `--from`/`--to`. They will coexist in parse result.

Ensure help shows both as options. They are not mutually exclusive? Yes, they can mix:
- `--from X --until Y` works
- `--since X --to Y` should also work (mixing alias and original)
- Should we allow mixing? Probably yes for flexibility.

**Validation:** Date validation already checks `args.from_date` and `args.to_date`, regardless of which flag set them. So mixing works automatically.

**Help ordering:** Show original first, then aliases.

---

## Edge Cases

- Mixing `--since` and `--from`: last one wins? Actually argparse stores last value for same dest. If user does `--since X --from Y`, `args.from_date` will be Y. That's fine, they messed up.
- Mixing `--since` with `--to`: works.
- Conflict with `--day`: same mutual exclusion applies because check uses `args.from_date or args.to_date`. Since both set same dest, check works.

---

## Acceptance

- [ ] `--since` sets `args.from_date`
- [ ] `--until` sets `args.to_date`
- [ ] Help text includes aliases with "Alias for --from"
- [ ] Validation works regardless of which flag used
- [ ] Mutual exclusion with `--day` works (if `--since` used, `args.from_date` non-None triggers)
- [ ] Tests: parse args with `--since`, check `from_date`; parse with `--until`, check `to_date`
- [ ] Tests: mix `--since` and `--to` works
- [ ] README updated to mention aliases

---

## Effort

- Add two parser lines: 15m
- Update tests: 15m
- **Total: 30m**

---

## Documentation

Add to README:

```markdown
### Sync Date Range

You can use either `--from`/`--to` or their synonyms `--since`/`--until`:

```bash
orggle journal.org --since 2026-03-01 --until 2026-03-15
```
```

---

## Risks

- Slight parser confusion (more flags)
- Could clutter help output
- Mitigation: Keep help concise, not promote aliases too heavily.

---

## Related

None

---

**Status:** Planned
**Created:** 2025-04-01
