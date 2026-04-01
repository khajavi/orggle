# B-006: Add `orggle config validate` Command

**Priority:** Tier 2 (High) - Catch configuration errors early, before sync failures
**Effort:** Medium (M - 5 hours)
**Dependencies:** `orggle config` command structure (B-014) would be helpful but not required

---

## Problem Statement

Users configure orggle via `~/.config/orggle/config.yaml`. Errors in this config are only discovered **at runtime** when they cause failures:

- Invalid regex pattern in `org_mappings`: Silently ignored (line 428-429 just `pass`)
  ```python
  try:
      compiled = re.compile(pattern)
  except re.error:
      pass  # BUG: should report error
  ```
- Non-existent project name: Prints warning but continues, entries sync without project → user doesn't notice until they see unprojected entries in Toggl
- Missing required fields (api_token, default_project): Detected later when API calls are made, not at startup
- Environment variable reference `${VAR}` with unset VAR: Error at runtime, not config load time
- YAML syntax errors: Caught at load time, but message is generic "Error loading config"

**User quote:** "My mapping regex was wrong, but orggle didn't tell me. Entries just didn't get renamed."

**Impact:** Misconfiguration leads to silent failures or missing features, harming data quality and user trust.

---

## Proposed Solution

Add a subcommand: `orggle config validate` that performs comprehensive checks:

1. **Syntax**: Config file is valid YAML/JSON (already done by load_config)
2. **Schema**:
   - `default_profile` present and points to existing profile
   - Each profile has required fields: `api_token`, `default_project`
   - `api_token` non-empty string (after env var substitution)
   - `org_mappings` are valid regex patterns (compile check)
3. **Connectivity** (optional, with `--online` flag):
   - API token is valid format (non-empty, maybe check length)
   - Toggl API reachable
   - Workspace exists and can be fetched
   - Project name exists in workspace (or warn if not)
4. **Permissions**: API token has required scopes (hard to check without API call, but can attempt `/me` and check 401/403)

The command should:
- Return exit code 0 if all checks pass
- Return non-zero if any check fails
- Print clear error messages with suggested fixes
- Support `--fix` to attempt auto-fixes (e.g., migrate old config) - but maybe later

---

## Implementation Approach

### Current State

`load_config()` (line 105-143) already does basic loading and migration. But it doesn't validate per-profile deeply.

We could add validation there, but that would make `load_config()` raise errors on bad config, which is good! But the current code catches these in `main()` and exits with generic message.

Better: separate `validate_config(full_config)` function that runs after load.

### New Command Structure

Register subcommand `config` with sub-subcommands:

```
orggle config validate [--online] [--fix]
orggle config show [--profile] [--json]
orggle config get <key>
orggle config set <key> <value>
```

But for backlog B-006, we just implement `validate`.

**Add to `main()`:**

```python
def main():
    parser = create_parser()  # current top-level parser
    # We need subparsers? Current design doesn't have subcommands; all arguments are optional flags.
    # To add subcommands, we'd need to refactor to use subparsers.
    # That's a breaking change? Not if we keep existing top-level args and add a new 'command' positional.

    # Option A: Add subparsers
    # Option B: Use --config subcommand as a flag: --config-command validate
    # Option C: Make 'config' a separate executable? No.

    # Current usage: orggle [global-args] org_file
    # New: orggle config validate [config-args]
    # That means first positional argument could be "config". That's a breaking change if someone had org file named "config"!

    # Better: Introduce subparsers, but require that if first arg is not recognized as command, treat as org_file.
    # This is typical CLI evolution.

    # Let's do subparsers:
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    parser_config = subparsers.add_parser('config', help='Configuration management')
    config_subparsers = parser_config.add_subparsers(dest='config_command')
    # validate subcommand
    parser_validate = config_subparsers.add_parser('validate', help='Validate configuration')
    parser_validate.add_argument('--online', action='store_true', help='Perform online checks (API connectivity)')
    parser_validate.add_argument('--fix', action='store_true', help='Attempt to fix issues automatically')
```

This is a significant refactor to support subcommands. But it's B-014 (Config UX). We can implement `config validate` as a separate top-level flag? Not clean.

**Alternative:** Keep current flat parser and add:

```python
parser.add_argument('--validate-config', action='store_true', help='Validate configuration and exit')
```

Then in `main()`:

```python
if args.validate_config:
    full_config = load_config()
    errors = validate_config(full_config)
    if errors:
        for e in errors: print(f"ERROR: {e}")
        sys.exit(1)
    else:
        print("✓ Configuration valid")
        sys.exit(0)
```

That's simpler and doesn't require subcommand restructuring. But it's a flag, not a command. It's fine: `orggle --validate-config`

But the user asked for `orggle config validate`. To get that, we need subcommands. Given this is backlog, we can plan for refactor in B-014. For B-006, we can implement as a flag now and later move to subcommand.

**Decision:** Implement as `--validate-config` flag first (quick win), then later B-014 reorganizes everything into `orggle config` subcommands. The validation logic itself will be the same.

---

## Validation Logic

```python
def validate_config(config: dict) -> List[str]:
    """Return list of validation errors (empty if valid)."""
    errors = []

    # 1. Check default_profile exists and is string
    if "default_profile" not in config:
        errors.append("Missing 'default_profile' in config")
    else:
        if not isinstance(config["default_profile"], str):
            errors.append("'default_profile' must be a string")

    # 2. Check profiles exist
    if "profiles" not in config or not isinstance(config["profiles"], dict):
        errors.append("Missing 'profiles' section or not a dictionary")
    else:
        profiles = config["profiles"]
        # Check each profile
        for name, profile in profiles.items():
            # Required fields
            for field in ["api_token", "default_project"]:
                if field not in profile:
                    errors.append(f"Profile '{name}' missing required field '{field}'")
                elif not profile[field]:
                    errors.append(f"Profile '{name}' has empty '{field}'")

            # Validate api_token after env substitution (can't fully, but check non-empty)
            api_token = profile.get("api_token", "")
            if api_token and not isinstance(api_token, str):
                errors.append(f"Profile '{name}': 'api_token' must be a string")

            # Validate org_mappings if present
            for mapping in profile.get("org_mappings", []):
                if not isinstance(mapping, dict):
                    errors.append(f"Profile '{name}': org_mappings entries must be dictionaries")
                    continue
                if "pattern" not in mapping:
                    errors.append(f"Profile '{name}': mapping missing 'pattern'")
                    continue
                try:
                    re.compile(mapping["pattern"])
                except re.error as e:
                    errors.append(f"Profile '{name}': invalid regex pattern '{mapping['pattern']}': {e}")

            # Default project should be string
            project = profile.get("default_project")
            if project and not isinstance(project, str):
                errors.append(f"Profile '{name}': 'default_project' must be a string")

    # 3. Check that default_profile refers to an existing profile
    if "default_profile" in config and "profiles" in config:
        if config["default_profile"] not in config["profiles"]:
            errors.append(f"default_profile '{config['default_profile']}' not found in profiles")

    # 4. Global tag should be string if present
    if "tag" in config and not isinstance(config["tag"], str):
        errors.append("Global 'tag' must be a string")

    # 5. Profile-level tag should be string if present
    for name, profile in profiles.items():
        if "tag" in profile and not isinstance(profile["tag"], (str, type(None))):
            errors.append(f"Profile '{name}': 'tag' must be a string or omitted")

    return errors
```

**Note:** This validates syntax and types, but not online connectivity.

### Online Validation (`--online`)

If `--online` flag provided:

1. Substitute env vars in profile's `api_token`
2. Check if token looks valid (maybe just non-empty)
3. Perform `/me` API call to verify token works
4. Fetch workspaces, check if workspace exists (though we fetch default anyway)
5. For each profile's `default_project`, attempt to get project ID; if not found, warn but not error (could be created later)
6. Check rate limits? Not necessary.

```python
def validate_config_online(profile_name: str, profile_config: dict) -> List[str]:
    errors = []
    try:
        # Get workspace
        workspace_id = get_workspace_id(api_token, proxies)  # reuse existing function
        # Try get project
        project_id = get_project_id_by_name(api_token, workspace_id, proxies, profile_config["default_project"])
        if project_id is None:
            errors.append(f"Project '{profile_config['default_project']}' not found in workspace")
    except Exception as e:
        errors.append(f"Online check failed: {e}")
    return errors
```

**Important:** `--online` requires network and valid token; should be optional.

---

## User Experience

### Successful validation:

```bash
$ ./orggle --validate-config
✓ Configuration valid
  Profiles: default, work, personal
  Default profile: work
  All regex patterns compiled successfully.
```

### With errors:

```bash
$ ./orggle --validate-config
ERROR: Missing 'default_profile' in config
ERROR: Profile 'work' missing required field 'api_token'
ERROR: Profile 'personal': invalid regex pattern '^\\s*-': missing escape
```

### With --online:

```bash
$ ./orggle --validate-config --online
✓ Configuration valid
✓ Online checks passed
  - Workspace: "Acme Corp" (ID: 12345)
  - Project 'Work' exists (ID: 67890)
  - Project 'Personal' exists (ID: 98765)
```

If project missing:

```bash
WARNING: Project 'Nonexistent' not found in workspace. Entries will be created without a project.
```

---

## Effort Estimation

- `validate_config` function (syntax checks): 2 hours
- `validate_config_online` using existing API functions: 1 hour
- Add `--validate-config` flag and integration: 1 hour
- Add `--online` option: 30 min
- Tests: 1 hour
- **Total:** ~5 hours (M)

---

## Acceptance Criteria

### Functional
- [ ] `--validate-config` flag exists and runs validation
- [ ] Returns exit 0 on valid config, non-zero on any error
- [ ] Validates `default_profile` presence
- [ ] Validates each profile has `api_token` and `default_project`
- [ ] Validates all regex patterns compile successfully (re.compile)
- [ ] Validates that `default_profile` refers to an existing profile
- [ ] `--online` flag performs real API checks (workspace, project)
- [ ] `--online` gracefully handles network errors (e.g., "Cannot connect, check proxy")
- [ ] Error messages are clear and indicate config location (global vs. profile)

### User Experience
- [ ] Success message lists profiles and shows "All checks passed"
- [ ] Errors printed to stderr, clear formatting
- [ ] `--online` output includes workspace name and project existence

### Testing
- [ ] Unit tests for `validate_config()` with various invalid configs
- [ ] Integration test: run `--validate-config` on sample configs
- [ ] Test `--online` with mock API (if possible) or live test with real token

---

## Implementation Checklist

- [ ] Write `validate_config(config)` function
- [ ] Write `validate_config_online(profile_name, profile_config)` (optional, only if --online)
- [ ] Add `--validate-config` argument to parser
- [ ] Add `--online` argument to parser (or make it sub-arg of validate)
- [ ] In `main()`, check `if args.validate_config:` block before other init
- [ ] Load config, run validation (with online if requested), print results, exit
- [ ] Add tests for validation function
- [ ] Update README with validation usage
- [ ] Update fish completions for new flag

---

## Documentation Updates

### README

Add section:

```markdown
### Validate Configuration

Check your config file for errors before syncing:

```bash
./orggle --validate-config
```

This checks:
- Required fields are present
- Regex patterns are valid
- Profile references are consistent

For online checks (requires network and valid API token):

```bash
./orggle --validate-config --online
```

Also verifies:
- API token is accepted by Toggl
- Workspace can be accessed
- Default project exists in the workspace

Useful after installing or changing config.
```

---

## Future Work (B-014 Config UX)

This flag is a stopgap. Eventually we want `orggle config` subcommands:

```bash
orggle config validate --all
orggle config show
orggle config get profiles.work.api_token
orggle config test-api  # shortcut for --online
```

When B-014 is implemented, we can deprecate `--validate-config` flag.

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `--online` reveals token errors early, but network may be down | Low | Make `--online` optional; document it requires network |
| Validation too strict, rejects flexible config | Medium | Keep validation permissive: only check types, required fields, regex compile. Not value ranges. |
| Users expect `--validate-config` to fix errors automatically | Low | Don't call it `--fix` yet. Add `--fix` later for auto-migration. |
| Performance: validation could be slow if many mappings | Low | Mappings are few (<10) typically, compilation fast. |

---

## Related Backlog Items

- **B-014**: Full config UX command suite (config get/set/show)
- **B-008**: Timezone validation could be added to config validation
- **B-009**: Multiple tags schema validation

---

**Status:** Planned
**Created:** 2025-04-01
