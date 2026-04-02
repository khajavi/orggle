#!/usr/bin/env python3
"""Sync org-mode clock entries to Toggl Track."""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

__version__ = "0.1.1"

# Global variables - will be set per profile
DB_PATH = None
TOGGL_TAG = None
DEFAULT_PROJECT_NAME = None
ORG_MAPPINGS = None


def get_config_dir() -> Path:
    """Return the config directory path, creating it if needed."""
    config_dir = Path.home() / ".config" / "orggle"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Return the config file path."""
    return get_config_dir() / "config.yaml"


def get_db_path(profile_name: str) -> Path:
    """Return the database path for a given profile."""
    return get_config_dir() / f"{profile_name}.db"


def substitute_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} patterns with environment variable values."""
    if not isinstance(value, str):
        return value
    
    pattern = re.compile(r'\$\{([^}]+)\}')
    
    def replace_var(match):
        var_name = match.group(1)
        if var_name not in os.environ:
            raise ValueError(f"Environment variable '{var_name}' not found")
        return os.environ[var_name]
    
    return pattern.sub(replace_var, value)


def is_old_config_format(config: dict) -> bool:
    """Check if config uses old format (has 'toggl' key, no 'profiles' key)."""
    return 'toggl' in config and 'profiles' not in config


def migrate_old_config(config: dict) -> dict:
    """Migrate old config format to new profile-based format."""
    print("Warning: Migrating old config format to new profile-based format...")
    
    old_toggl = config.get("toggl", {})
    old_mappings = config.get("org_mappings", [])
    
    new_config = {
        "default_profile": "default",
        "tag": old_toggl.get("tag", "orggle"),  # Global default tag
        "profiles": {
            "default": {
                "api_token": "${TOGGL_API_TOKEN}",
                "default_project": old_toggl.get("default_project", "Documentation"),
            }
        }
    }
    
    # Add org_mappings if they exist
    if old_mappings:
        new_config["profiles"]["default"]["org_mappings"] = old_mappings
    
    print("Migration complete. Config has been updated.")
    print("Note: Set TOGGL_API_TOKEN environment variable before running again.")
    
    return new_config


def validate_profile(profile_config: dict, profile_name: str) -> bool:
    """Validate that a profile has all required fields."""
    required_fields = ["api_token", "default_project"]
    
    for field in required_fields:
        if field not in profile_config:
            raise ValueError(f"Profile '{profile_name}' missing required field '{field}'")
        if not profile_config[field]:
            raise ValueError(f"Profile '{profile_name}' has empty '{field}'")
    
    return True


def load_profile_config(profile_name: str, full_config: dict) -> dict:
    """Load and validate a specific profile, handling environment variable substitution."""
    if "profiles" not in full_config or profile_name not in full_config["profiles"]:
        available = ", ".join(full_config.get("profiles", {}).keys())
        raise ValueError(f"Profile '{profile_name}' not found. Available profiles: {available}")
    
    profile_config = full_config["profiles"][profile_name].copy()
    
    # Substitute environment variables in api_token
    try:
        profile_config["api_token"] = substitute_env_vars(profile_config["api_token"])
    except ValueError as e:
        raise ValueError(f"In profile '{profile_name}': {e}")
    
    # Validate required fields
    validate_profile(profile_config, profile_name)
    
    # Apply global defaults for optional fields
    if "tag" not in profile_config and "tag" in full_config:
        profile_config["tag"] = full_config["tag"]
    
    if "tag" not in profile_config:
        profile_config["tag"] = "orggle"
    
    # Merge org_mappings with global defaults
    if "org_mappings" not in profile_config and "org_mappings" in full_config:
        profile_config["org_mappings"] = full_config["org_mappings"]
    else:
        profile_config["org_mappings"] = profile_config.get("org_mappings", [])
    
    return profile_config


def get_profile_name(args: argparse.Namespace, config: dict) -> str:
    """Resolve which profile to use: explicit flag -> default_profile."""
    if hasattr(args, 'profile') and args.profile:
        return args.profile
    
    if "default_profile" not in config:
        raise ValueError(
            "No default_profile defined in config. "
            "Either set default_profile in ~/.config/orggle/config.yaml or use --profile flag"
        )
    
    return config["default_profile"]


def load_config() -> dict:
    """Load configuration from ~/.config/orggle/config.yaml or config.json."""
    config_path = get_config_path()
    
    # Try to load from YAML first
    if config_path.exists():
        try:
            import yaml
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
                
                # Migrate old format if needed
                if is_old_config_format(config):
                    config = migrate_old_config(config)
                
                return config
        except ImportError:
            pass
        except Exception as e:
            print(f"Error loading config from {config_path}: {e}")
            sys.exit(1)
    
    # Try to load from JSON as fallback
    json_path = config_path.parent / "config.json"
    if json_path.exists():
        try:
            with open(json_path, "r") as f:
                config = json.load(f) or {}
                
                # Migrate old format if needed
                if is_old_config_format(config):
                    config = migrate_old_config(config)
                
                return config
        except Exception as e:
            print(f"Error loading config from {json_path}: {e}")
            sys.exit(1)
    
    # Create default config if none exists
    print(f"Config not found at {config_path}")
    print("Creating default configuration...")
    
    config_dir = get_config_dir()
    default_config = {
        "default_profile": "default",
        "tag": "orggle",
        "profiles": {
            "default": {
                "api_token": "${TOGGL_API_TOKEN}",
                "default_project": "Documentation",
                "org_mappings": [
                    {
                        "pattern": "^\\s*- rest$",
                        "description": "Break Time"
                    }
                ]
            }
        }
    }
    
    # Try to save the default config
    try:
        with open(config_path, "w") as f:
            import yaml
            yaml.dump(default_config, f, default_flow_style=False)
            print(f"Created default config at {config_path}")
    except ImportError:
        # Fall back to JSON
        json_path = config_dir / "config.json"
        with open(json_path, "w") as f:
            json.dump(default_config, f, indent=2)
            print(f"Created default config at {json_path}")
    
    return default_config


def init_db(profile_name: str):
    """Initialize the SQLite database for a given profile."""
    db_path = get_db_path(profile_name)
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            hash TEXT PRIMARY KEY,
            description TEXT,
            start TEXT,
            stop TEXT,
            duration INTEGER,
            published INTEGER DEFAULT 0,
            toggl_id TEXT,
            synced_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def hash_entry(entry: dict) -> str:
    """Generate a unique hash for an entry."""
    key = f"{entry['start']}-{entry['stop']}-{entry['duration']}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def is_published(entry_hash: str, profile_name: str) -> bool:
    """Check if an entry is already published."""
    db_path = get_db_path(profile_name)
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT published FROM entries WHERE hash = ?", (entry_hash,))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] == 1


def get_published_entry(entry_hash: str, profile_name: str) -> Optional[dict]:
    """Retrieve a stored entry by its hash.

    Returns a dict with entry data (description, start, stop, duration, toggl_id) or None if not found.
    """
    db_path = get_db_path(profile_name)
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("""
        SELECT description, start, stop, duration, toggl_id
        FROM entries WHERE hash = ?
    """, (entry_hash,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "description": row[0],
            "start": row[1],
            "stop": row[2],
            "duration": row[3],
            "toggl_id": row[4]
        }
    return None


def entries_are_equal(entry1: dict, entry2: dict) -> bool:
    """Compare two entry dicts for equality in fields that matter for updates.

    Checks description, start, stop, and duration. Ignores toggl_id and other metadata.
    """
    return (
        entry1.get('description') == entry2.get('description') and
        entry1.get('start') == entry2.get('start') and
        entry1.get('stop') == entry2.get('stop') and
        entry1.get('duration') == entry2.get('duration')
    )


def mark_published(entry_hash: str, toggl_id: str, profile_name: str, entry: dict):
    """Mark an entry as published and store its full data for future change detection."""
    db_path = get_db_path(profile_name)
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("""
        INSERT INTO entries (hash, description, start, stop, duration, published, toggl_id, synced_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, datetime('now'))
        ON CONFLICT(hash) DO UPDATE SET
            description = excluded.description,
            start = excluded.start,
            stop = excluded.stop,
            duration = excluded.duration,
            published = 1,
            toggl_id = excluded.toggl_id,
            synced_at = datetime('now')
    """, (entry_hash, entry['description'], entry['start'], entry['stop'], entry['duration'], toggl_id))
    conn.commit()
    conn.close()


def get_proxies() -> dict:
    """Get proxy settings from environment variables."""
    proxies = {}
    proxy = os.environ.get("TOGGL_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if proxy:
        proxies["https"] = proxy
        proxies["http"] = proxy
    return proxies


def curl_request(method: str, url: str, api_token: str, proxies: dict, data: Optional[dict] = None) -> Tuple[int, dict]:
    """Make HTTP request using curl. Returns (status_code, response_json)."""
    cmd = ["curl", "-s", "-w", "\\n%{http_code}", "-X", method, "-u", f"{api_token}:api_token"]
    
    if proxies:
        proxy = proxies.get("https") or proxies.get("http")
        if proxy:
            cmd.extend(["-x", proxy])
    
    cmd.append("-k")
    
    cmd.extend(["-H", "Content-Type: application/json", url])
    
    if data:
        cmd.extend(["-d", json.dumps(data)])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    lines = result.stdout.strip().split("\n")
    status_code = int(lines[-1])
    body = "\n".join(lines[:-1])
    
    try:
        response_data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        response_data = {"raw": body}
    
    return status_code, response_data


def retry_request(func, *args, **kwargs):
    """Retry a function with fibonacci backoff on network failure."""
    fib = [1, 1]
    max_retries = 10
    
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            is_network_error = (
                "Failed to establish a new connection" in error_msg or
                "Connection reset by peer" in error_msg or
                "timed out" in error_msg.lower() or
                "Connection refused" in error_msg or
                ": 0 - " in error_msg
            )
            
            if not is_network_error or attempt == max_retries - 1:
                raise
            
            delay = fib[-1] + fib[-2]
            fib.append(delay)
            print(f"Network error: {error_msg}")
            print(f"Retrying in {delay}s...")
            time.sleep(delay)


def get_workspace_id(api_token: str, proxies: dict) -> int:
    """Fetch user's default workspace ID."""
    def fetch():
        status, data = curl_request("GET", "https://api.track.toggl.com/api/v9/me", api_token, proxies)
        if status == 200:
            return data.get("default_workspace_id")
        else:
            raise Exception(f"Failed to get user info: {status} - {data}")
    
    return retry_request(fetch)


def get_project_id_by_name(api_token: str, workspace_id: int, proxies: dict, project_name: str) -> Optional[int]:
    """Fetch project ID by name. Returns None if not found."""
    def fetch():
        status, data = curl_request("GET", f"https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/projects", api_token, proxies)
        if status == 200:
            for project in data:
                if project.get("name") == project_name:
                    return project.get("id")
        else:
            raise Exception(f"Failed to get projects: {status} - {data}")
        return None
    
    return retry_request(fetch)


def get_entries_for_day(api_token: str, workspace_id: int, proxies: dict, day: str) -> List[dict]:
    """Fetch time entries for a specific day from Toggl."""
    def fetch():
        from urllib.parse import quote
        start_date = quote(f"{day}T00:00:00Z")
        end_date = quote(f"{day}T23:59:59Z")
        status, data = curl_request(
            "GET",
            f"https://api.track.toggl.com/api/v9/me/time_entries?start_date={start_date}&end_date={end_date}",
            api_token,
            proxies
        )
        if status == 200:
            return data
        else:
            raise Exception(f"Failed to get entries: {status} - {data}")
    
    return retry_request(fetch)


def delete_entry(api_token: str, workspace_id: int, proxies: dict, entry_id: int):
    """Delete a time entry from Toggl."""
    def fetch():
        status, data = curl_request(
            "DELETE",
            f"https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/time_entries/{entry_id}",
            api_token,
            proxies
        )
        if status != 200:
            raise Exception(f"Failed to delete entry {entry_id}: {status} - {data}")
    
    retry_request(fetch)


def parse_org_file(filepath: str, org_mappings: list = None) -> List[dict]:
    """Parse CLOCK entries from org-mode file, latest first."""
    if org_mappings is None:
        org_mappings = []
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    current_task = None
    
    mapping_patterns = []
    for mapping in org_mappings:
        pattern = mapping.get("pattern", "")
        description = mapping.get("description", "")
        if pattern and description:
            try:
                mapping_patterns.append((re.compile(pattern), description))
            except re.error:
                pass

    lines = content.split("\n")
    for i, line in enumerate(lines):
        task_match = re.match(r"^\*+\s+(.+)$", line)
        if task_match:
            task_text = task_match.group(1).strip()
            current_task = re.sub(r"^(DONE|TODO|DOING|NEXT|WAITING|CANCELLED)\s+", "", task_text)

        for pattern, description in mapping_patterns:
            if pattern.match(line):
                if entries:
                    last_entry = entries[-1]
                    # Only apply mapping if the entry belongs to the current heading
                    if last_entry.get("heading") == current_task:
                        last_entry["description"] = description
                break

        clock_match = re.search(
            r"CLOCK:\s+\[(\d{4}-\d{2}-\d{2})\s+(\w+)\s+(\d{2}:\d{2})\]\s*--\s*\[(\d{4}-\d{2}-\d{2})\s+(\w+)\s+(\d{2}:\d{2})\]\s*=>\s*(\d+):(\d{2})",
            line,
        )
        if clock_match and current_task:
            start_date, _, start_time, end_date, _, end_time, hours, minutes = clock_match.groups()

            start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
            duration_minutes = int(hours) * 60 + int(minutes)

            if duration_minutes == 0:
                continue

            local_tz = datetime.now().astimezone().tzinfo
            start_dt = start_dt.replace(tzinfo=local_tz)
            end_dt = end_dt.replace(tzinfo=local_tz)

            entry = {
                "description": current_task,
                "heading": current_task,
                "start": start_dt.isoformat(),
                "stop": end_dt.isoformat(),
                "duration": duration_minutes * 60,
            }
            entries.append(entry)

    entries.sort(key=lambda x: x["start"], reverse=True)
    return entries


def create_toggl_entry(entry: dict, api_token: str, workspace_id: int, proxies: dict, project_id: Optional[int] = None, tag: str = None) -> Optional[str]:
    """Create a time entry in Toggl. Returns entry URL on success."""
    url = f"https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/time_entries"

    description = entry["description"]

    payload = {
        "description": description,
        "start": entry["start"],
        "stop": entry["stop"],
        "duration": entry["duration"],
        "wid": workspace_id,
        "created_with": "orggle",
    }

    # Only add tags if tag is provided and non-empty
    if tag:
        payload["tags"] = [tag]

    if project_id:
        payload["project_id"] = project_id

    fib = [1, 1]
    max_retries = 10
    
    for attempt in range(max_retries):
        status, data = curl_request("POST", url, api_token, proxies, payload)

        if status == 200:
            return f"https://track.toggl.com/timer/{data.get('id', 'N/A')}"
        
        if attempt < max_retries - 1:
            delay = fib[-1] + fib[-2]
            fib.append(delay)
            print(f"  Error: {status} - {data}")
            print(f"  Retrying in {delay}s...")
            time.sleep(delay)
        else:
            print(f"  Error: {status} - {data}")
            return None
    
    return None


def confirm_sync(entry: dict) -> str:
    """Ask user to confirm sync. Returns 'y', 'n', or 'q'."""
    desc = entry["description"]
    start = entry["start"][:16].replace("T", " ")
    stop = entry["stop"][:16].replace("T", " ")
    hours = entry["duration"] // 3600
    minutes = (entry["duration"] % 3600) // 60
    duration = f"{hours}:{minutes:02d}"

    prompt = f'Sync "{desc}" - {start} to {stop} ({duration})? [Y/n/q]: '
    
    while True:
        try:
            response = input(prompt).strip().lower()
            if response == "":
                return "y"
            elif response in ["y", "n", "q"]:
                return response
        except (KeyboardInterrupt, EOFError):
            return "q"


def group_entries_by_day(entries: List[dict]) -> Dict[str, List[dict]]:
    """Group entries by date (YYYY-MM-DD)."""
    grouped = {}
    for entry in entries:
        day = entry["start"][:10]
        if day not in grouped:
            grouped[day] = []
        grouped[day].append(entry)
    return grouped


def confirm_day(day: str, entries: List[dict]) -> str:
    """Ask user to confirm syncing all entries for a day. Returns 'y', 'n', or 'q'."""
    total_minutes = sum(e["duration"] // 60 for e in entries)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    print(f"\n=== {day} ===")
    print(f"Total work time: {hours}h {minutes:02d}m")
    print("Entries:")
    for e in entries:
        desc = e["description"]
        start = e["start"][11:16]
        stop = e["stop"][11:16]
        dur_min = e["duration"] // 60
        dur_hours = dur_min // 60
        dur_mins = dur_min % 60
        print(f"  - {start} to {stop} ({dur_hours}:{dur_mins:02d}): {desc}")

    prompt = f"\nSync {len(entries)} entries for {day}? [Y/n/q]: "

    while True:
        try:
            response = input(prompt).strip().lower()
            if response == "":
                return "y"
            elif response in ["y", "n", "q"]:
                return response
        except (KeyboardInterrupt, EOFError):
            return "q"


def validate_date(date_str: str) -> bool:
    """Validate a date string is in YYYY-MM-DD format and is a valid date."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_date_range(from_date: str, to_date: str) -> bool:
    """Validate that from_date <= to_date."""
    if not (validate_date(from_date) and validate_date(to_date)):
        return False
    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    to_dt = datetime.strptime(to_date, "%Y-%m-%d")
    return from_dt <= to_dt


def filter_entries_by_date_range(entries: List[dict], from_date: str = None, to_date: str = None) -> List[dict]:
    """
    Filter entries to include only those within the specified date range.
    Dates are inclusive and compared against the entry's start date.
    Args:
        entries: List of entry dictionaries with 'start' key in ISO format
        from_date: Start date in YYYY-MM-DD format (inclusive), or None for no lower bound
        to_date: End date in YYYY-MM-DD format (inclusive), or None for no upper bound
    Returns:
        Filtered list of entries
    """
    if from_date is None and to_date is None:
        return entries

    filtered = []
    for entry in entries:
        entry_date = entry["start"][:10]  # Extract YYYY-MM-DD from ISO timestamp

        # Check lower bound
        if from_date and entry_date < from_date:
            continue

        # Check upper bound
        if to_date and entry_date > to_date:
            continue

        filtered.append(entry)

    return filtered


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(description="Sync org-mode clock entries to Toggl")
    parser.add_argument("--version", action="version", version=f"orggle {__version__}")
    parser.add_argument("org_file", nargs="?", help="Path to org-mode file (optional with --delete-existing)")
    parser.add_argument("--profile", type=str, default=None, help="Toggl profile to use (default from config)")
    parser.add_argument("--batch", choices=["daily"], help="Batch mode: 'daily' syncs all entries grouped by day")
    parser.add_argument("--day", help="Sync specific day (YYYY-MM-DD), ignores previous sync status")
    parser.add_argument("--from", dest='from_date',
        help="Start date for range (YYYY-MM-DD, inclusive)")
    parser.add_argument("--to", dest='to_date',
        help="End date for range (YYYY-MM-DD, inclusive)")
    parser.add_argument("--delete-existing", action="store_true", help="Delete existing entries for --day before syncing")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be synced without making any API calls")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-accept all prompts (non-interactive mode). Useful for scripts and cron jobs.")
    parser.add_argument("--update-changed", action="store_true", help="Update entries that have changed (description, duration, time) by deleting and re-creating them")
    return parser


def should_resync_all(args) -> bool:
    """Determine if we should re-sync all entries (skipping already-synced check)."""
    return bool(args.day or args.from_date or args.to_date)


def confirm_delete(count: int, date_desc: str) -> bool:
    """Prompt user to confirm deletion of existing Toggl entries.

    Args:
        count: Number of entries to delete
        date_desc: Human-readable date range or day description

    Returns:
        True if user confirmed by typing "DELETE {count}", False otherwise
    """
    if not sys.stdin.isatty():
        print("Error: --delete-existing requires an interactive terminal for confirmation.")
        sys.exit(1)

    print(f"\n⚠️  WARNING: This will delete {count} existing Toggl entries")
    print(f"   Date range: {date_desc}")
    print(f"   Type 'DELETE {count}' to confirm, or any other input to cancel: ", end="", flush=True)
    try:
        response = input().strip()
        return response == f"DELETE {count}"
    except (EOFError, KeyboardInterrupt):
        print()  # newline after ^C or EOF
        return False


def main():
    parser = create_parser()
    args = parser.parse_args()

    # Validate date arguments
    if args.from_date and not validate_date(args.from_date):
        print(f"Error: Invalid date format for --from: {args.from_date}. Use YYYY-MM-DD")
        sys.exit(1)

    if args.to_date and not validate_date(args.to_date):
        print(f"Error: Invalid date format for --to: {args.to_date}. Use YYYY-MM-DD")
        sys.exit(1)

    if args.from_date and args.to_date and not validate_date_range(args.from_date, args.to_date):
        print(f"Error: --from date ({args.from_date}) must be before or equal to --to date ({args.to_date})")
        sys.exit(1)

    # Check mutual exclusivity between --day and --from/--to
    if args.day and (args.from_date or args.to_date):
        print("Error: --day cannot be used with --from or --to. Use one date filter at a time.")
        sys.exit(1)

    # Check mutual exclusivity between --dry-run and --delete-existing
    if args.dry_run and args.delete_existing:
        print("Error: --dry-run cannot be used with --delete-existing.")
        print("(Use --dry-run first to preview, then run without it to actually delete and sync)")
        sys.exit(1)

    # Check that interactive mode has a TTY (unless --yes is used)
    if not args.yes and not sys.stdin.isatty() and not args.dry_run:
        print("Error: orggle requires an interactive terminal for prompts.")
        print("Use --yes (or -y) to run non-interactively.")
        sys.exit(1)

    if args.delete_existing and not args.org_file:
        if not args.day:
            print("Error: --day is required when --delete-existing is used without org_file")
            sys.exit(1)
        if args.batch:
            print("Error: --batch cannot be used with --delete-existing without org_file")
            sys.exit(1)

    # Load full config
    try:
        full_config = load_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    # Resolve which profile to use
    try:
        profile_name = get_profile_name(args, full_config)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Load profile config
    try:
        profile_config = load_profile_config(profile_name, full_config)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Extract settings from profile
    api_token = profile_config['api_token']
    toggl_tag = profile_config.get('tag', 'orggle')
    default_project_name = profile_config['default_project']
    org_mappings = profile_config.get('org_mappings', [])

    print(f"Using profile: {profile_name}")

    # Initialize database for this profile
    init_db(profile_name)

    # Handle dry-run mode: preview without API calls
    if args.dry_run:
        # Validate org_file
        if not args.org_file:
            print("Error: org_file is required when using --dry-run")
            sys.exit(1)
        if not os.path.isfile(args.org_file):
            print(f"Error: File not found: {args.org_file}")
            sys.exit(1)

        # Parse org file
        print(f"Parsing {args.org_file}...")
        entries = parse_org_file(args.org_file, org_mappings)

        if not entries:
            print("No clock entries found.")
            sys.exit(0)

        # Apply date filters
        if args.day:
            entries = [e for e in entries if e["start"].startswith(args.day)]
            if not entries:
                print(f"No entries found for {args.day}.")
                sys.exit(0)
            print(f"Filtering to day: {args.day}\n")
        elif args.from_date or args.to_date:
            entries = filter_entries_by_date_range(entries, args.from_date, args.to_date)
            if not entries:
                range_desc = f"{args.from_date or '...'} to {args.to_date or '...'}"
                print(f"No entries found in date range {range_desc}.")
                sys.exit(0)
            print(f"Filtering to date range: {args.from_date or '...'} to {args.to_date or '...'}\n")

        # Determine which entries would be synced vs skipped (already published)
        would_sync = []
        would_skip = []
        for entry in entries:
            entry_hash = hash_entry(entry)
            if args.update_changed:
                stored = get_published_entry(entry_hash, profile_name)
                if stored:
                    if entries_are_equal(entry, stored):
                        would_skip.append(entry)
                    else:
                        would_sync.append(entry)
                else:
                    would_sync.append(entry)
            else:
                if is_published(entry_hash, profile_name):
                    would_skip.append(entry)
                else:
                    would_sync.append(entry)

        # Display results
        print("\n" + "="*40)
        print("DRY RUN - No changes will be made")
        print("="*40)

        if args.batch == "daily":
            # Group would_sync by day
            grouped = group_entries_by_day(would_sync)
            total_duration_sec = sum(e["duration"] for e in would_sync)
            total_duration_mins = total_duration_sec // 60
            print(f"Would sync {len(would_sync)} entries across {len(grouped)} day(s):\n")
            for day in sorted(grouped.keys(), reverse=True):
                day_entries = grouped[day]
                day_duration_sec = sum(e["duration"] for e in day_entries)
                day_duration_mins = day_duration_sec // 60
                print(f"Day {day} ({len(day_entries)} entries, {day_duration_mins//60}h {day_duration_mins%60}m):")
                for e in day_entries:
                    mins = e["duration"] // 60
                    desc = e['description'][:60]
                    print(f"  - {desc} ({mins}m)")
                print()

            if would_skip:
                skip_grouped = group_entries_by_day(would_skip)
                print(f"Would skip {len(would_skip)} entries (already synced) across {len(skip_grouped)} day(s):")
                for day in sorted(skip_grouped.keys(), reverse=True):
                    print(f"  {day}: {len(skip_grouped[day])} entries")
                print()
        else:
            # Interactive mode: flat list
            total_duration_sec = sum(e["duration"] for e in would_sync)
            total_duration_mins = total_duration_sec // 60
            print(f"Would sync {len(would_sync)} entries:\n")
            for entry in would_sync:
                mins = entry["duration"] // 60
                desc = entry['description'][:60]
                print(f"  {entry['start'][:10]}: {desc} ({mins}m)")
            print()
            if would_skip:
                print(f"Would skip {len(would_skip)} entries (already synced):")
                for entry in would_skip:
                    print(f"  {entry['start'][:10]}: {entry['description'][:60]}")
                print()

        print("="*40)
        print(f"Total duration to sync: {total_duration_mins//60}h {total_duration_mins%60}m")
        print("(No API calls were made)")
        sys.exit(0)

    proxies = get_proxies()
    if proxies:
        print(f"Using proxy: {proxies.get('https', 'N/A')}")

    print("Fetching workspace ID...")
    try:
        workspace_id = get_workspace_id(api_token, proxies)
        print(f"Using workspace ID: {workspace_id}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Looking up project '{default_project_name}'...")
    project_id = get_project_id_by_name(api_token, workspace_id, proxies, default_project_name)
    if project_id:
        print(f"Using project ID: {project_id}")
    else:
        print(f"Warning: Project '{default_project_name}' not found, entries will be without project")

    if args.delete_existing and not args.org_file:
        print(f"Fetching existing entries for {args.day}...")
        existing = get_entries_for_day(api_token, workspace_id, proxies, args.day)
        if existing:
            # Require confirmation before deletion
            if not confirm_delete(len(existing), f"{args.day} (single day)"):
                print("Deletion cancelled.")
                sys.exit(0)
            print(f"Deleting {len(existing)} entries...")
            for entry in existing:
                entry_id = entry.get("id")
                if entry_id:
                    delete_entry(api_token, workspace_id, proxies, entry_id)
                    print(f"  Deleted entry {entry_id}")
            print("Done.")
        else:
            print("No existing entries found.")
        sys.exit(0)

    if not os.path.isfile(args.org_file):
        print(f"Error: File not found: {args.org_file}")
        sys.exit(1)

    print(f"Parsing {args.org_file}...")
    entries = parse_org_file(args.org_file, org_mappings)

    if not entries:
        print("No clock entries found.")
        sys.exit(0)

    if args.day:
        entries = [e for e in entries if e["start"].startswith(args.day)]
        if not entries:
            print(f"No entries found for {args.day}.")
            sys.exit(0)
        print(f"Filtering to day: {args.day}\n")
    elif args.from_date or args.to_date:
        entries = filter_entries_by_date_range(entries, args.from_date, args.to_date)
        if not entries:
            range_desc = f"{args.from_date or '...'} to {args.to_date or '...'}"
            print(f"No entries found in date range {range_desc}.")
            sys.exit(0)
        print(f"Filtering to date range: {args.from_date or '...'} to {args.to_date or '...'}\n")


    if args.day and args.delete_existing:
        print(f"Fetching existing entries for {args.day}...")
        existing = get_entries_for_day(api_token, workspace_id, proxies, args.day)
        if existing:
            # Require confirmation before deletion
            if not confirm_delete(len(existing), f"{args.day} (single day)"):
                print("Deletion cancelled.")
                sys.exit(0)
            print(f"Deleting {len(existing)} entries...")
            for entry in existing:
                entry_id = entry.get("id")
                if entry_id:
                    delete_entry(api_token, workspace_id, proxies, entry_id)
                    print(f"  Deleted entry {entry_id}")
            print()
        else:
            print("No existing entries found.\n")

    new_entries = []
    already_synced = 0
    if args.update_changed:
        # Always use change detection, even with date filters
        for entry in entries:
            entry_hash = hash_entry(entry)
            stored = get_published_entry(entry_hash, profile_name)
            if stored:
                if entries_are_equal(entry, stored):
                    already_synced += 1
                else:
                    # Mark for update: delete old then create new
                    entry['_old_toggl_id'] = stored['toggl_id']
                    entry['_old_description'] = stored['description']
                    new_entries.append(entry)
            else:
                new_entries.append(entry)
    else:
        if should_resync_all(args):
            new_entries = entries
        else:
            for entry in entries:
                entry_hash = hash_entry(entry)
                if is_published(entry_hash, profile_name):
                    already_synced += 1
                else:
                    new_entries.append(entry)

    print(f"Found {len(entries)} clock entries (latest first)")
    if already_synced > 0:
        print(f"Already synced: {already_synced}, New: {len(new_entries)}\n")
    else:
        print()

    if not new_entries:
        print("All entries already synced.")
        sys.exit(0)

    synced = 0
    skipped = 0
    quit_flag = False

    if args.batch == "daily":
        grouped = group_entries_by_day(new_entries)
        for day in sorted(grouped.keys(), reverse=True):
            day_entries = grouped[day]
            if args.yes:
                response = "y"
            else:
                response = confirm_day(day, day_entries)
            
            if response == "q":
                quit_flag = True
                break
            elif response == "n":
                skipped += len(day_entries)
                print("  Skipped\n")
            else:
                for entry in day_entries:
                    # If entry needs update (changed), delete old first
                    if '_old_toggl_id' in entry:
                        old_id = entry['_old_toggl_id']
                        # Show update message
                        old_desc = entry.get('_old_description', '')
                        new_desc = entry.get('description', '')
                        change_desc = f" (description changed: '{old_desc}' → '{new_desc}')" if old_desc != new_desc else ""
                        print(f"  Updating entry {old_id}{change_desc}...")
                        if not delete_entry(api_token, workspace_id, proxies, old_id):
                            print(f"  ✗ Failed to delete old entry {old_id}, skipping")
                            skipped += 1
                            continue
                    # Create new entry
                    url = create_toggl_entry(entry, api_token, workspace_id, proxies, project_id, toggl_tag)
                    if url:
                        entry_hash = hash_entry(entry)
                        toggl_id = url.split("/")[-1]
                        mark_published(entry_hash, toggl_id, profile_name, entry)
                        print(f"  ✓ Synced: {url}")
                        synced += 1
                    else:
                        skipped += 1
                        print("  ✗ Failed to sync")
                print()
    else:
        for entry in new_entries:
            if args.yes:
                response = "y"
            else:
                response = confirm_sync(entry)

            if response == "q":
                quit_flag = True
                break
            elif response == "n":
                skipped += 1
                print("  Skipped\n")
            else:
                # If entry needs update (changed), delete old first
                if '_old_toggl_id' in entry:
                    old_id = entry['_old_toggl_id']
                    old_desc = entry.get('_old_description', '')
                    new_desc = entry.get('description', '')
                    change_desc = f" (description changed: '{old_desc}' → '{new_desc}')" if old_desc != new_desc else ""
                    print(f"  Updating entry {old_id}{change_desc}...")
                    if not delete_entry(api_token, workspace_id, proxies, old_id):
                        print(f"  ✗ Failed to delete old entry {old_id}, skipping")
                        skipped += 1
                        continue
                # Create new entry
                url = create_toggl_entry(entry, api_token, workspace_id, proxies, project_id, toggl_tag)
                if url:
                    entry_hash = hash_entry(entry)
                    toggl_id = url.split("/")[-1]
                    mark_published(entry_hash, toggl_id, profile_name, entry)
                    print(f"  ✓ Synced: {url}\n")
                    synced += 1
                else:
                    skipped += 1
                    print("  ✗ Failed to sync\n")

    print("-" * 40)
    if quit_flag:
        print("Sync interrupted.")
    print(f"Synced: {synced}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
