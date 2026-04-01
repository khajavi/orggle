# B-009: Multiple Tags Support

**Priority:** Tier 2 (High) - Users want to categorize entries with multiple tags
**Effort:** Small (S - 2 hours)
**Dependencies:** None

---

## Problem Statement

Currently, a profile can define a single `tag` (string) that is applied to all entries synced with that profile.

```yaml
profiles:
  work:
    tag: work-entry  # Single tag only
```

Toggl supports multiple tags per entry, but orggle cannot set more than one.

**User need:** "I want to tag my entries with both 'work' and 'client-x' and 'deep-work' to filter later in Toggl reports."

**Current workarounds:**
- Use comma-separated tag (Toggl interprets as single tag with commas, not separate tags)
- Manually add tags in Toggl after sync (tedious)
- Use multiple profiles (overhead)

---

## Proposed Solution

Extend profile config to accept either a string (backward compatible) or a list of strings for `tag`.

**Config backward compatibility:**

```yaml
profiles:
  work:
    tag: work-entry           # Still valid → single tag
    # or
    tags: [work, client-x]    # New: multiple tags
```

**Implementation:**

1. In `load_profile_config()`, normalize to list internally:
```python
tag = profile_config.get('tag')  # old singular
tags = profile_config.get('tags')  # new plural
if tag and tags:
    raise ValueError("Cannot specify both 'tag' and 'tags'")
if tags:
    if isinstance(tags, str):
        tags = [tags]
    elif not isinstance(tags, list):
        raise ValueError("'tags' must be a string or list")
    # Validate each is string
else:
    tags = [tag] if tag else []
```

2. Store normalized `tags` list in profile_config (add new key or replace 'tag').

3. When creating Toggl payload (line 556-569), `tags` field expects array:

```python
payload = {
    ...
    "tags": profile_config.get('tags', []),  # list of strings
}
```

If using old `tag` only, we convert to `[tag]` list.

4. Update `config validation` (B-006) to accept both forms, ensure not both.

5. Update examples in README.

---

## Acceptance Criteria

- [ ] Config can have `tags: [a, b, c]` (list)
- [ ] Config can have `tag: single` (string) - backward compat
- [ ] Cannot mix `tag` and `tags` (error)
- [ ] Empty tags allowed (no tags in Toggl)
- [ ] Tags passed to Toggl API as array
- [ ] Validation: each tag must be string
- [ ] Unit test: parsing of profile with tags
- [ ] Unit test: backward compatibility with singular tag
- [ ] Integration test: verify Toggl receives multiple tags (mock API or use test workspace)

---

## Example Usage

```yaml
profiles:
  work:
    api_token: ${WORK_TOKEN}
    default_project: Acme Corp
    tags: [work, client-x, billable]
```

Results in Toggl entries with three tags.

---

## Effort

- Code changes: 2h
- Tests: 1h
- Docs: 1h
- Total: ~2h (S)

---

## Risks

- Breaking change if we change semantics of `tag`. Keep it as alias.
- Validation: order of tags? Preserve as given.
- Tag length limits? Toggl allows up to 255 chars per tag; we don't enforce but can.
- Duplicate tags? Toggl dedupes, but we can dedupe to save: `list(set(tags))` while preserving order? Not needed.

---

## Related

None

---

**Status:** Planned
**Created:** 2025-04-01
