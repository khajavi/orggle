#!/usr/bin/env python3
"""Tests for orggle command-line argument parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import orggle

def test_from_to_arguments_are_parsed():
    """Test that --from and --to arguments are correctly parsed."""
    parser = orggle.create_parser()
    args = parser.parse_args(["journal.org", "--from", "2026-03-01", "--to", "2026-03-15"])
    assert args.from_date == "2026-03-01"
    assert args.to_date == "2026-03-15"

def test_from_to_arguments_with_day():
    """Test that --from, --to, and --day can be used together."""
    parser = orggle.create_parser()
    args = parser.parse_args(["journal.org", "--from", "2026-03-01", "--to", "2026-03-15", "--day", "2026-03-10"])
    assert args.from_date == "2026-03-01"
    assert args.to_date == "2026-03-15"
    assert args.day == "2026-03-10"

def test_from_to_arguments_optional():
    """Test that --from and --to are optional and default to None."""
    parser = orggle.create_parser()
    args = parser.parse_args(["journal.org"])
    assert args.from_date is None
    assert args.to_date is None

def test_validate_date():
    assert orggle.validate_date("2026-03-28") == True
    assert orggle.validate_date("invalid") == False
    assert orggle.validate_date("2026-13-01") == False
    assert orggle.validate_date("2026-02-30") == False

def test_validate_date_range():
    assert orggle.validate_date_range("2026-03-01", "2026-03-15") == True
    assert orggle.validate_date_range("2026-03-15", "2026-03-01") == False

def test_filter_entries_by_date_range():
    entries = [
        {"start": "2026-03-28T09:00:00+00:00", "description": "Entry 1"},
        {"start": "2026-03-29T10:00:00+00:00", "description": "Entry 2"},
        {"start": "2026-04-01T11:00:00+00:00", "description": "Entry 3"},
    ]

    # No filter
    result = orggle.filter_entries_by_date_range(entries)
    assert len(result) == 3

    # Only from_date
    result = orggle.filter_entries_by_date_range(entries, from_date="2026-03-29")
    assert len(result) == 2
    assert result[0]["description"] == "Entry 2"
    assert result[1]["description"] == "Entry 3"

    # Only to_date
    result = orggle.filter_entries_by_date_range(entries, to_date="2026-03-29")
    assert len(result) == 2
    assert result[0]["description"] == "Entry 1"
    assert result[1]["description"] == "Entry 2"

    # Both bounds
    result = orggle.filter_entries_by_date_range(entries, from_date="2026-03-28", to_date="2026-03-29")
    assert len(result) == 2
    assert result[0]["description"] == "Entry 1"
    assert result[1]["description"] == "Entry 2"

    # No matching entries
    result = orggle.filter_entries_by_date_range(entries, from_date="2026-05-01", to_date="2026-05-31")
    assert len(result) == 0

def test_filter_entries_inclusive_bounds():
    """Test that date range is inclusive."""
    entries = [
        {"start": "2026-03-15T09:00:00+00:00", "description": "Boundary test"},
    ]
    result = orggle.filter_entries_by_date_range(entries, from_date="2026-03-15", to_date="2026-03-15")
    assert len(result) == 1

def test_should_resync_all():
    """Test the should_resync_all decision logic."""
    class Args:
        pass

    args = Args()

    # With --day only
    args.day = "2026-03-28"
    args.from_date = None
    args.to_date = None
    assert orggle.should_resync_all(args) == True

    # With --from only
    args.day = None
    args.from_date = "2026-03-01"
    args.to_date = None
    assert orggle.should_resync_all(args) == True

    # With --to only
    args.day = None
    args.from_date = None
    args.to_date = "2026-03-31"
    assert orggle.should_resync_all(args) == True

    # With both --from and --to
    args.day = None
    args.from_date = "2026-03-01"
    args.to_date = "2026-03-31"
    assert orggle.should_resync_all(args) == True

    # With none
    args.day = None
    args.from_date = None
    args.to_date = None
    assert orggle.should_resync_all(args) == False

def test_day_and_from_are_mutually_exclusive():
    """Test that using --day with --from or --to results in error."""
    import subprocess
    import sys

    # Test --day with --from
    result = subprocess.run(
        [sys.executable, "orggle.py", "test.org", "--day", "2026-03-28", "--from", "2026-03-01"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 1
    assert "Error: --day cannot be used with --from or --to" in result.stderr or "Error: --day cannot be used with --from or --to" in result.stdout

    # Test --day with --to
    result = subprocess.run(
        [sys.executable, "orggle.py", "test.org", "--day", "2026-03-28", "--to", "2026-03-31"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 1
    assert "Error: --day cannot be used with --from or --to" in result.stderr or "Error: --day cannot be used with --from or --to" in result.stdout


def test_dry_run_flag_parsed():
    """Test that --dry-run flag is correctly parsed."""
    parser = orggle.create_parser()
    args = parser.parse_args(["journal.org", "--dry-run"])
    assert args.dry_run == True
    # Also ensure default is False
    args2 = parser.parse_args(["journal.org"])
    assert args2.dry_run == False


def test_dry_run_conflict_with_delete_existing():
    """Test that --dry-run cannot be used with --delete-existing."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "orggle.py", "test.org", "--dry-run", "--delete-existing"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 1
    assert "--dry-run cannot be used with --delete-existing" in result.stderr or "--dry-run cannot be used with --delete-existing" in result.stdout


def test_dry_run_preview_output():
    """Test that --dry-run produces expected output without making API calls."""
    import subprocess
    import os
    from pathlib import Path

    # Check that config exists; skip test if not (e.g., sandboxed environment)
    config_path = Path.home() / ".config" / "orggle" / "config.yaml"
    if not config_path.exists():
        print("Skipping test_dry_run_preview_output: config file not found")
        return

    # Create a temporary org file with known entries
    test_org_content = """* TODO Test task A
  CLOCK: [2026-03-28 Sat 09:00]--[2026-03-28 Sat 10:00] => 1:00

* TODO Test task B
  CLOCK: [2026-03-28 Sat 11:00]--[2026-03-28 Sat 12:00] => 1:00
"""
    test_org_path = Path("test_dry_run_sample.org")
    try:
        test_org_path.write_text(test_org_content)
        # Run with dry-run
        result = subprocess.run(
            [sys.executable, "orggle.py", str(test_org_path), "--dry-run"],
            capture_output=True,
            text=True,
            env={**os.environ, "TOGGL_API_TOKEN": os.getenv("TOGGL_API_TOKEN", "dummy")}
        )
        # Should exit 0
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        # Output should contain "DRY RUN"
        assert "DRY RUN" in result.stdout or "DRY RUN" in result.stderr
        # Should mention both entries
        assert "Test task A" in result.stdout or "Test task A" in result.stderr
        assert "Test task B" in result.stdout or "Test task B" in result.stderr
        # Should show total duration ~2h (120m)
        assert ("2h" in result.stdout or "120m" in result.stdout) or ("2h" in result.stderr or "120m" in result.stderr)
        # Should NOT contain "workspace" or "project" (network calls)
        assert "workspace" not in result.stdout.lower() and "workspace" not in result.stderr.lower()
    finally:
        if test_org_path.exists():
            test_org_path.unlink()


def test_confirm_delete_requires_tty():
    """Test that confirm_delete exits with error when stdin is not a TTY."""
    import subprocess
    # Run a subprocess that calls confirm_delete with no TTY (input provided)
    code = "import orggle; orggle.confirm_delete(3, 'test')"
    result = subprocess.run(
        [sys.executable, "-c", code],
        input="",
        capture_output=True,
        text=True
    )
    assert result.returncode == 1, f"Expected non-zero exit, got {result.returncode}. stderr: {result.stderr}"
    assert "requires an interactive terminal" in result.stderr or "requires an interactive terminal" in result.stdout


def test_yes_flag_parsed():
    """Test that --yes flag is correctly parsed."""
    parser = orggle.create_parser()
    args = parser.parse_args(["journal.org", "--yes"])
    assert args.yes == True
    # Also test short form
    args2 = parser.parse_args(["journal.org", "-y"])
    assert args2.yes == True
    # Ensure default is False
    args3 = parser.parse_args(["journal.org"])
    assert args3.yes == False


def test_yes_with_dry_run():
    """Test that --yes can be used with --dry-run."""
    import subprocess
    import os
    from pathlib import Path

    # Create a temporary org file with known entries
    test_org_content = """* TODO Test task
  CLOCK: [2026-03-28 Sat 09:00]--[2026-03-28 Sat 10:00] => 1:00
"""
    test_org_path = Path("test_yes_dry_run_sample.org")
    try:
        test_org_path.write_text(test_org_content)
        result = subprocess.run(
            [sys.executable, "orggle.py", str(test_org_path), "--yes", "--dry-run"],
            capture_output=True,
            text=True,
            env={**os.environ, "TOGGL_API_TOKEN": "dummy_token"}
        )
        # Should not error - both flags are compatible
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        # Output should contain "DRY RUN"
        assert "DRY RUN" in result.stdout or "DRY RUN" in result.stderr
        # Should mention the entry
        assert "Test task" in result.stdout or "Test task" in result.stderr
    finally:
        if test_org_path.exists():
            test_org_path.unlink()


def test_update_changed_dry_run():
    """Test that --update-changed correctly identifies changed vs unchanged entries in dry-run."""
    import subprocess
    import os
    import sqlite3
    import tempfile
    from pathlib import Path

    # We'll create a temporary HOME environment with a pre-seeded DB
    with tempfile.TemporaryDirectory() as tmpdir:
        home_dir = Path(tmpdir)
        config_dir = home_dir / ".config" / "orggle"
        config_dir.mkdir(parents=True)
        db_path = config_dir / "default.db"

        # Create config.yaml with default profile
        config_yaml = """default_profile: default
tag: orggle
profiles:
  default:
    api_token: ${TOGGL_API_TOKEN}
    default_project: Test
"""
        (config_dir / "config.yaml").write_text(config_yaml)

        # Initialize DB schema
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("""
            CREATE TABLE entries (
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

        # Create org file with two entries
        org_content = """* TODO Task A (unchanged)
  CLOCK: [2026-03-28 Sat 09:00]--[2026-03-28 Sat 10:00] => 1:00

* TODO Task B changed version
  CLOCK: [2026-03-28 Sat 10:00]--[2026-03-28 Sat 11:00] => 1:00
"""
        org_file = config_dir / "test_update.org"
        org_file.write_text(org_content)

        # Parse the org file in the test process to get the actual entry data (timestamps, durations) as orggle would parse them.
        entries = orggle.parse_org_file(str(org_file), org_mappings=[])
        assert len(entries) == 2
        # Identify entry A and B by description content (but descriptions are from org file; we want to store original versions)
        # In org, entry B description is "Task B changed version". That's the current (new) description.
        # We want to store in DB entry B with a different original description.
        # So we'll find entry with start 09:00 as Entry A, and 10:00 as Entry B.
        entry_a = next(e for e in entries if e['start'].startswith('2026-03-28T09:00'))
        entry_b = next(e for e in entries if e['start'].startswith('2026-03-28T10:00'))

        # Compute hashes
        hash_a = orggle.hash_entry(entry_a)
        hash_b = orggle.hash_entry(entry_b)

        # Insert into DB:
        # For Entry A: use same description as org (unchanged)
        # For Entry B: use a different description (original version)
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("""
            INSERT INTO entries (hash, description, start, stop, duration, published, toggl_id, synced_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, datetime('now'))
        """, (hash_a, "Task A (unchanged)", entry_a['start'], entry_a['stop'], entry_a['duration'], "toggl_a"))
        c.execute("""
            INSERT INTO entries (hash, description, start, stop, duration, published, toggl_id, synced_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, datetime('now'))
        """, (hash_b, "Task B original version", entry_b['start'], entry_b['stop'], entry_b['duration'], "toggl_b"))
        conn.commit()
        conn.close()

        # Set up environment for subprocess: HOME=tmpdir, TOGGL_API_TOKEN=dummy
        env = os.environ.copy()
        env["HOME"] = str(home_dir)
        env["TOGGL_API_TOKEN"] = "dummy_token"

        # Determine repo root (where orggle.py resides). We assume test file is in tests/ in repo root.
        repo_root = Path(__file__).parent.parent

        # Run orggle with --dry-run --update-changed
        result = subprocess.run(
            [sys.executable, "orggle.py", str(org_file), "--dry-run", "--update-changed"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(repo_root)
        )

        # Should exit 0
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

        output = result.stdout + result.stderr

        # Check counts: Would sync 1, Would skip 1
        assert "Would sync 1" in output, f"Expected 'Would sync 1' in output, got: {output}"
        assert "Would skip 1" in output, f"Expected 'Would skip 1' in output, got: {output}"

        # Extract sync section: after "Would sync 1 entries:" up to next section (Would skip or end)
        if "Would sync 1 entries:" in output:
            after_sync = output.split("Would sync 1 entries:", 1)[1]
            # If there is a "Would skip" after, take part before that; else whole after
            if "Would skip" in after_sync:
                sync_section = after_sync.split("Would skip", 1)[0]
            else:
                sync_section = after_sync
            assert "Task B changed version" in sync_section, f"Changed entry should appear in sync section. Sync section: {sync_section}"

        # Extract skip section: after "Would skip 1 entries (already synced):" until end or next section
        if "Would skip 1 entries (already synced):" in output:
            after_skip = output.split("Would skip 1 entries (already synced):", 1)[1]
            # Next possible section could be nothing or maybe other output
            skip_section = after_skip  # rest is fine
            assert "Task A (unchanged)" in skip_section, f"Unchanged entry should appear in skip section. Skip section: {skip_section}"


def test_confirm_delete_with_mock():
    """Test confirm_delete returns True only for exact confirmation string."""
    try:
        from unittest.mock import patch
    except ImportError:
        print("Skipping test_confirm_delete_with_mock: unittest.mock not available")
        return

    # Simulate TTY and correct confirmation
    with patch('sys.stdin.isatty', return_value=True):
        with patch('builtins.input', return_value="DELETE 3"):
            result = orggle.confirm_delete(3, "test")
            assert result == True

    # Simulate incorrect confirmation
    with patch('sys.stdin.isatty', return_value=True):
        with patch('builtins.input', return_value="yes"):
            result = orggle.confirm_delete(3, "test")
            assert result == False

    # Simulate whitespace-padded confirmation
    with patch('sys.stdin.isatty', return_value=True):
        with patch('builtins.input', return_value="  DELETE 3  "):
            result = orggle.confirm_delete(3, "test")
            assert result == True  # strip() makes it match

    # Simulate EOF
    with patch('sys.stdin.isatty', return_value=True):
        with patch('builtins.input', side_effect=EOFError):
            result = orggle.confirm_delete(3, "test")
            assert result == False

    # Simulate KeyboardInterrupt
    with patch('sys.stdin.isatty', return_value=True):
        with patch('builtins.input', side_effect=KeyboardInterrupt):
            result = orggle.confirm_delete(3, "test")
            assert result == False


def test_entries_are_equal():
    """Test entries_are_equal comparison."""
    entry1 = {
        "description": "Test task",
        "start": "2026-03-28T09:00:00+00:00",
        "stop": "2026-03-28T10:00:00+00:00",
        "duration": 3600,
        "toggl_id": "123"
    }
    entry2 = {
        "description": "Test task",
        "start": "2026-03-28T09:00:00+00:00",
        "stop": "2026-03-28T10:00:00+00:00",
        "duration": 3600,
        "toggl_id": "456"
    }
    # Same critical fields, different toggl_id -> equal
    assert orggle.entries_are_equal(entry1, entry2) == True

    # Different description
    entry3 = dict(entry1)
    entry3["description"] = "Changed description"
    assert orggle.entries_are_equal(entry1, entry3) == False

    # Different duration
    entry4 = dict(entry1)
    entry4["duration"] = 7200
    assert orggle.entries_are_equal(entry1, entry4) == False

    # Different start
    entry5 = dict(entry1)
    entry5["start"] = "2026-03-28T10:00:00+00:00"
    assert orggle.entries_are_equal(entry1, entry5) == False

    # Different stop
    entry6 = dict(entry1)
    entry6["stop"] = "2026-03-28T11:00:00+00:00"
    assert orggle.entries_are_equal(entry1, entry6) == False


def test_get_published_entry():
    """Test get_published_entry retrieves stored entry data."""
    import tempfile
    from pathlib import Path
    try:
        from unittest.mock import patch
    except ImportError:
        print("Skipping test_get_published_entry: unittest.mock not available")
        return

    # Create a temporary database for a test profile
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        # Monkey-patch get_db_path to return our test db
        original_get_db_path = orggle.get_db_path
        def mock_get_db_path(profile_name):
            return str(db_path)
        orggle.get_db_path = mock_get_db_path

        try:
            # Initialize DB for profile 'test'
            orggle.init_db('test')
            # Insert a sample entry
            entry_hash = "abc123"
            entry_data = {
                'description': 'Original task',
                'start': '2026-03-28T09:00:00+00:00',
                'stop': '2026-03-28T10:00:00+00:00',
                'duration': 3600,
                'toggl_id': 'toggl123'
            }
            orggle.mark_published(entry_hash, 'toggl123', 'test', entry_data)

            # Retrieve it
            stored = orggle.get_published_entry(entry_hash, 'test')
            assert stored is not None
            assert stored['description'] == 'Original task'
            assert stored['toggl_id'] == 'toggl123'
            assert stored['start'] == entry_data['start']
            assert stored['stop'] == entry_data['stop']
            assert stored['duration'] == 3600

            # Non-existent hash returns None
            stored2 = orggle.get_published_entry('nonexistent', 'test')
            assert stored2 is None
        finally:
            orggle.get_db_path = original_get_db_path


if __name__ == "__main__":
    # Run all tests
    test_functions = [
        test_from_to_arguments_are_parsed,
        test_from_to_arguments_with_day,
        test_from_to_arguments_optional,
        test_validate_date,
        test_validate_date_range,
        test_filter_entries_by_date_range,
        test_filter_entries_inclusive_bounds,
        test_should_resync_all,
        test_day_and_from_are_mutually_exclusive,
        test_dry_run_flag_parsed,
        test_dry_run_conflict_with_delete_existing,
        test_dry_run_preview_output,
        test_yes_flag_parsed,
        test_yes_with_dry_run,
        test_update_changed_dry_run,
        test_confirm_delete_requires_tty,
        test_confirm_delete_with_mock,
    ]
    failed = 0
    for test in test_functions:
        try:
            test()
            print(f"✓ {test.__name__}")
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
    sys.exit(failed)
