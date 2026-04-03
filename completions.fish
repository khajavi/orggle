# Fish shell completions for orggle
# Place this file in ~/.config/fish/completions/orggle.fish

# Get available profiles from config file
function __fish_orggle_profiles
    set -l config_file ~/.config/orggle/config.yaml
    if test -f $config_file
        # Extract profile names from config.yaml
        cat $config_file | grep -E '^\s+[a-zA-Z_][a-zA-Z0-9_]*:\s*$' | sed 's/^\s\+//; s/:\s*$//' | grep -v '^profiles$'
    end
end

# Get org-mode files in current directory
function __fish_orggle_org_files
    find . -maxdepth 1 -type f -name "*.org" 2>/dev/null | sed 's|^\./||'
end

# Main command description
complete -c orggle -f -d "Sync org-mode clock entries to Toggl Track"

# Positional argument: org_file (only suggest if no flags are being used)
complete -c orggle -f -n "__fish_seen_subcommand_from" -a "(__fish_orggle_org_files)" -d "Path to org-mode file"

# Global options
complete -c orggle -s h -l help -f -d "Show help message and exit"
complete -c orggle -l version -f -d "Show program version and exit"

# Profile option
complete -c orggle -l profile -x -d "Toggl profile to use (default from config)" -a "(__fish_orggle_profiles)"

# Batch mode option
complete -c orggle -l batch -x -f -d "Batch mode: 'daily' syncs all entries grouped by day" -a "daily"

# Day option (YYYY-MM-DD format) with date suggestions
function __fish_orggle_dates
    # Generate dates from 1 year ago to 3 months in future (approx 455 days)
    # Uses GNU date syntax (Linux, NixOS)
    set -l start (date -d "1 year ago" +%Y-%m-%d 2>/dev/null)
    if test $status -ne 0
        # Fallback: just output today
        date +%Y-%m-%d 2>/dev/null
        return
    end
    # Generate about 455 days (covers 1 year + 3 months)
    for i in (seq 0 455)
        date -d "$start + $i days" +%Y-%m-%d 2>/dev/null
    end
end

complete -c orggle -l day -x -d "Sync specific day (format: YYYY-MM-DD). Ignores previous sync status" -a "(__fish_orggle_dates)"

# From option (YYYY-MM-DD format, inclusive) with date completion
complete -c orggle -l from -x -d "Start date for range (YYYY-MM-DD, inclusive)" -a "(__fish_orggle_dates)"

# To option (YYYY-MM-DD format, inclusive) with date completion
complete -c orggle -l to -x -d "End date for range (YYYY-MM-DD, inclusive)" -a "(__fish_orggle_dates)"

# Delete existing flag
complete -c orggle -l delete-existing -f -d "Delete existing Toggl entries for specified day/range before syncing"

# Dry-run flag
complete -c orggle -l dry-run -f -d "Preview what would be synced without making any API calls"

# Yes flag (auto-accept prompts)
complete -c orggle -s y -l yes -f -d "Auto-accept all prompts (non-interactive mode)"

# Update-changed flag (smart updates)
complete -c orggle -l update-changed -f -d "Update entries that have changed (description, duration, time) by deleting and re-creating them"

# Validate config flag
complete -c orggle -l validate-config -f -d "Validate configuration and exit"
complete -c orggle -l online -f -d "Include online checks (API connectivity) when validating config"

# Combination help: --day with --delete-existing
complete -c orggle -n "__fish_seen_subcommand_from --day" -l delete-existing -f -d "Delete existing entries for this day before syncing"

# Usage examples (as descriptions in completion)
# orggle <org_file>
# orggle <org_file> --profile work
# orggle <org_file> --batch daily
# orggle --day 2026-03-29
# orggle --day 2026-03-29 --delete-existing

