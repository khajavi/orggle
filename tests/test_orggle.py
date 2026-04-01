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

