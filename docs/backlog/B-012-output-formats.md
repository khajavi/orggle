# B-012: Output Formats (JSON/Quiet) for Scriptability

**Priority:** Tier 3 (Medium) - Enables automation and machine parsing
**Effort:** Small (S - 3 hours)
**Dependencies:** None

---

## Problem Statement

Orggle's output is human-readable but not machine-parseable. Scripts that call orggle cannot easily get structured results (counts, entry IDs, errors).

**Use cases:**
- Dashboard showing "entries synced today" by parsing output (fragile)
- CI job that needs to know if sync succeeded or failed
- Aggregating stats across multiple profiles
- Passing results to other tools via pipe

**Current output:** Multi-line text with emojis, not parsable reliably.

---

## Proposed Solution

Add `--output` option with choices: `text` (default), `json`, `quiet`.

```bash
orggle journal.org --output json
```

Outputs a single JSON object to stdout with fields:
```json
{
  "status": "success",
  "profile": "work",
  "synced": [
    {"description": "Task A", "toggl_id": "123", "start": "2026-03-28T09:00:00-04:00"}
  ],
  "skipped": [
    {"description": "Task B", "reason": "already_synced"}
  ],
  "failed": [
    {"description": "Task C", "error": "Network error"}
  ],
  "summary": {
    "total_entries": 10,
    "synced_count": 8,
    "skipped_count": 1,
    "failed_count": 1,
    "total_duration_seconds": 28800
  }
}
```

**JSON schema**: Document in README or separate file.

---

## Implementation

1. Add argument:

```python
parser.add_argument(
    "--output",
    choices=["text", "json", "quiet"],
    default="text",
    help="Output format: 'text' (default, human-readable), 'json' (machine-readable), 'quiet' (minimal output)"
)
```

2. Collect results in structured dict throughout sync:

```python
result = {
    "profile": profile_name,
    "synced": [],
    "skipped": [],
    "failed": [],
}
```

When an entry is synced:
```python
result["synced"].append({
    "description": entry["description"],
    "toggl_id": toggl_id,
    "start": entry["start"],
    "stop": entry["stop"],
    "duration": entry["duration"]
})
```

When skipped (already synced):
```python
result["skipped"].append({
    "description": entry["description"],
    "reason": "already_synced",
    "hash": entry_hash
})
```

When failed:
```python
result["failed"].append({
    "description": entry["description"],
    "error": error_msg
})
```

3. At end, if `args.output == 'json'`:

```python
import json
result["status"] = "success" if result["failed_count"] == 0 else "partial_failure"
result["summary"] = {
    "total_entries": len(entries),
    "synced_count": len(result["synced"]),
    "skipped_count": len(result["skipped"]),
    "failed_count": len(result["failed"]),
    "total_duration_seconds": sum(e["duration"] for e in result["synced"])
}
print(json.dumps(result, indent=2))
sys.exit(0 if result["failed_count"] == 0 else 1)  # exit non-zero if any failures
```

4. If `args.output == 'quiet'`:
- Suppress all non-essential output
- Still print errors to stderr
- No progress, no per-entry success (maybe only final count or nothing)
- Exit code: 0 if all synced, non-zero if any failures

5. If `args.output == 'text'`: current behavior.

---

## Edge Cases

- **Large result sets**: JSON could be large. Keep it; for very large, consider streaming. Not needed.
- **Sensitive data**: API tokens not included. toggl_id is okay (not secret).
- **Exit codes**: Need to define: success = all entries synced (or only skips), failure = any entry failed network? Usually exit 0 if processed without infrastructure error, but maybe want non-zero if any skipped? Probably non-zero only if any entry failed to sync (network or API error).
- **Dry-run**: With `--dry-run` and `--output json`, should output what would happen (no network calls). Include `dry_run: true` in JSON.

---

## Acceptance

- [ ] `--output` flag with choices text/json/quiet
- [ ] JSON output includes structured entries with key fields
- [ ] Summary included with counts and total duration
- [ ] Exit code: 0 on full success, >0 on any entry failures or argument errors
- [ ] `quiet` mode suppresses non-essential output (errors still to stderr)
- [ ] JSON output is valid and schema-stable
- [ ] Works with all other flags (dry-run, batch, etc.)
- [ ] Tests: capture json output, parse, assert keys/values
- [ ] Document JSON schema in README or separate file

---

## Effort

- Argument: 30m
- Data collection structs: 1h
- Output formatters: 1h
- Tests: 30m
- Docs: 30m
- Total: ~3h

---

## Documentation

### README addition:

```markdown
### Machine-Readable Output

For scripting and automation, use `--output json`:

```bash
orggle journal.org --output json > result.json
```

The JSON includes per-entry results and summary:

```json
{
  "profile": "work",
  "synced": [...],
  "skipped": [...],
  "failed": [...],
  "summary": {
    "total_entries": 10,
    "synced_count": 8,
    "skipped_count": 1,
    "failed_count": 1,
    "total_duration_seconds": 28800
  },
  "status": "success"
}
```

Use `jq` to extract information:

```bash
total_duration=$(jq '.summary.total_duration_seconds' result.json)
```

To suppress all normal output, use `--output quiet`. Errors still printed to stderr.
```

---

## Future Enhancements

- Streaming JSON (ndjson) for large syncs
- `--output yaml` (if PyYAML available)
- Include configuration and timing metadata

---

## Related

- B-001: dry-run could output JSON with "would_sync" list
- B-004: --yes pairs well with --output json for automation

---

**Status:** Planned
**Created:** 2025-04-01
