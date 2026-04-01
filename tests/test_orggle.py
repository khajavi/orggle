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
