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
from typing import Optional

DB_PATH = os.path.expanduser("~/.orggle.db")


def load_config() -> dict:
    """Load configuration from config.yaml or config.json."""
    config_path = Path(__file__).parent
    
    yaml_path = config_path / "config.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path, "r") as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            pass
    
    json_path = config_path / "config.json"
    if json_path.exists():
        with open(json_path, "r") as f:
            return json.load(f) or {}
    
    return {
        "toggl": {
            "tag": "orggle",
            "default_project": "Documentation",
        },
        "org_mappings": [],
    }


CONFIG = load_config()

TOGGL_TAG = CONFIG.get("toggl", {}).get("tag", "orggle")
DEFAULT_PROJECT_NAME = CONFIG.get("toggl", {}).get("default_project", "Documentation")
ORG_MAPPINGS = CONFIG.get("org_mappings", [])


def init_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
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


def is_published(entry_hash: str) -> bool:
    """Check if an entry is already published."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT published FROM entries WHERE hash = ?", (entry_hash,))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] == 1


def mark_published(entry_hash: str, toggl_id: str):
    """Mark an entry as published and store the Toggl ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO entries (hash, published, toggl_id, synced_at)
        VALUES (?, 1, ?, datetime('now'))
        ON CONFLICT(hash) DO UPDATE SET published = 1, toggl_id = ?, synced_at = datetime('now')
    """, (entry_hash, toggl_id, toggl_id))
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


def curl_request(method: str, url: str, api_token: str, proxies: dict, data: Optional[dict] = None) -> tuple[int, dict]:
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


def get_entries_for_day(api_token: str, workspace_id: int, proxies: dict, day: str) -> list[dict]:
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


def parse_org_file(filepath: str) -> list[dict]:
    """Parse CLOCK entries from org-mode file, latest first."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    current_task = None
    
    mapping_patterns = []
    for mapping in ORG_MAPPINGS:
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
                "start": start_dt.isoformat(),
                "stop": end_dt.isoformat(),
                "duration": duration_minutes * 60,
            }
            entries.append(entry)

    entries.sort(key=lambda x: x["start"], reverse=True)
    return entries


def create_toggl_entry(entry: dict, api_token: str, workspace_id: int, proxies: dict, project_id: Optional[int] = None) -> Optional[str]:
    """Create a time entry in Toggl. Returns entry URL on success."""
    url = f"https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/time_entries"

    description = entry["description"]

    payload = {
        "description": description,
        "start": entry["start"],
        "stop": entry["stop"],
        "duration": entry["duration"],
        "wid": workspace_id,
        "tags": [TOGGL_TAG],
        "created_with": "orggle",
    }

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


def group_entries_by_day(entries: list[dict]) -> dict[str, list[dict]]:
    """Group entries by date (YYYY-MM-DD)."""
    grouped = {}
    for entry in entries:
        day = entry["start"][:10]
        if day not in grouped:
            grouped[day] = []
        grouped[day].append(entry)
    return grouped


def confirm_day(day: str, entries: list[dict]) -> str:
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


def main():
    parser = argparse.ArgumentParser(description="Sync org-mode clock entries to Toggl")
    parser.add_argument("org_file", nargs="?", help="Path to org-mode file (optional with --delete-existing)")
    parser.add_argument("--batch", choices=["daily"], help="Batch mode: 'daily' syncs all entries grouped by day")
    parser.add_argument("--day", help="Sync specific day (YYYY-MM-DD), ignores previous sync status")
    parser.add_argument("--delete-existing", action="store_true", help="Delete existing entries for --day before syncing")
    args = parser.parse_args()

    if args.delete_existing and not args.org_file:
        if not args.day:
            print("Error: --day is required when --delete-existing is used without org_file")
            sys.exit(1)
        if args.batch:
            print("Error: --batch cannot be used with --delete-existing without org_file")
            sys.exit(1)

    init_db()

    api_token = os.environ.get("TOGGL_API_TOKEN")
    if not api_token:
        print("Error: TOGGL_API_TOKEN environment variable not set")
        print("Run: export TOGGL_API_TOKEN='your_api_token'")
        sys.exit(1)

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

    print(f"Looking up project '{DEFAULT_PROJECT_NAME}'...")
    project_id = get_project_id_by_name(api_token, workspace_id, proxies, DEFAULT_PROJECT_NAME)
    if project_id:
        print(f"Using project ID: {project_id}")
    else:
        print(f"Warning: Project '{DEFAULT_PROJECT_NAME}' not found, entries will be without project")

    if args.delete_existing and not args.org_file:
        print(f"Fetching existing entries for {args.day}...")
        existing = get_entries_for_day(api_token, workspace_id, proxies, args.day)
        if existing:
            print(f"Found {len(existing)} existing entries, deleting...")
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
    entries = parse_org_file(args.org_file)

    if not entries:
        print("No clock entries found.")
        sys.exit(0)

    if args.day:
        entries = [e for e in entries if e["start"].startswith(args.day)]
        if not entries:
            print(f"No entries found for {args.day}.")
            sys.exit(0)
        print(f"Filtering to day: {args.day}\n")

    if args.day and args.delete_existing:
        print(f"Fetching existing entries for {args.day}...")
        existing = get_entries_for_day(api_token, workspace_id, proxies, args.day)
        if existing:
            print(f"Found {len(existing)} existing entries, deleting...")
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
    if args.day:
        new_entries = entries
    else:
        for entry in entries:
            entry_hash = hash_entry(entry)
            if is_published(entry_hash):
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
            response = confirm_day(day, day_entries)
            
            if response == "q":
                quit_flag = True
                break
            elif response == "n":
                skipped += len(day_entries)
                print("  Skipped\n")
            else:
                for entry in day_entries:
                    url = create_toggl_entry(entry, api_token, workspace_id, proxies, project_id)
                    if url:
                        entry_hash = hash_entry(entry)
                        toggl_id = url.split("/")[-1]
                        mark_published(entry_hash, toggl_id)
                        print(f"  ✓ Synced: {url}")
                        synced += 1
                    else:
                        skipped += 1
                        print("  ✗ Failed to sync")
                print()
    else:
        for entry in new_entries:
            response = confirm_sync(entry)

            if response == "q":
                quit_flag = True
                break
            elif response == "n":
                skipped += 1
                print("  Skipped\n")
            else:
                url = create_toggl_entry(entry, api_token, workspace_id, proxies, project_id)
                if url:
                    entry_hash = hash_entry(entry)
                    toggl_id = url.split("/")[-1]
                    mark_published(entry_hash, toggl_id)
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
