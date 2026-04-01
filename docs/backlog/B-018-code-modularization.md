# B-018: Code Modularization (Split into Multiple Files)

**Priority:** Tier 4 (Low) - Long-term maintainability
**Effort:** Large (L - 2-3 days)
**Dependencies:** None

---

## Problem Statement

`orggle.py` is a single 870-line file containing:
- Configuration loading
- Database operations
- Org parsing
- Toggl API client
- CLI argument parsing
- Main sync loop
- Utilities

This makes:
- Hard to navigate
- Testing individual components difficult
- Risk of merge conflicts in team development
- Unclear module boundaries

---

## Proposed Refactor

Split into package structure:

```
orggle/
├── __init__.py
├── __main__.py       # python -m orggle entry
├── cli.py            # Argument parsing, main()
├── config.py         # Config loading, validation, profiles
├── db.py             # Database connection, is_published, mark_published
├── parser.py         # parse_org_file, CLOCK extraction
├── api.py            # Toggl API client (curl_request, retry_request)
├── utils.py          # Date validation, filtering, hashing
└── completions/      # Fish completions file?
```

Then top-level `orggle` script becomes:

```python
#!/usr/bin/env python3
from orggle.cli import main
if __name__ == '__main__':
    main()
```

---

## Benefits

- Clear separation of concerns
- Easier to test (import individual modules)
- Better code reuse
- Clearer interfaces (module APIs)
- Scalable for future features

---

## Migration Strategy

1. Create `orggle/` package, move code piece by piece
2. Ensure existing `orggle.py` still works as single script (maybe keep it as wrapper that imports from package)
3. Update install script to install package (pip install -e . or just copy .py files)
4. Update documentation for developers

Given it's pre-1.0, can do disruptive change if version bump.

---

## Acceptance

- [ ] All existing functionality preserved
- [ ] Tests still pass
- [ ] Single-file `orggle.py` still available for simple deployment (or decide to require package install)
- [ ] Import cycles avoided
- [ ] Clear module boundaries documented

---

## Effort

- Design package structure: 4h
- Refactor code: 12h
- Update tests: 4h
- Update documentation: 4h
- **Total:** ~24h (L)

---

## Related

This enables easier development of other features.

---

**Status:** Deferred (technical debt)
**Created:** 2025-04-01
