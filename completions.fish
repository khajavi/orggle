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
    # Generate dates from 5 years ago to 1 year in future (~2190 days)
    # Use caching to avoid regenerating on every completion
    # Cache stored in a universal variable that persists across fish sessions

    # Cache invalidation: store cache with a "generation date". If the day has changed, regenerate.
    set -q __fish_orggle_date_cache_gen; or set -U __fish_orggle_date_cache_gen 0
    set -l today (date +%Y-%m-%d 2>/dev/null)
    if test -z "$today"
        date +%Y-%m-%d 2>/dev/null
        return
    end

    # If cache exists and is from today, use it
    if test "$__fish_orggle_date_cache_gen" = "$today"
        for d in $__fish_orggle_date_cache
            echo $d
        end
        return
    end

    # Generate new cache
    set -l start (date -d "5 years ago" +%Y-%m-%d 2>/dev/null)
    if test $status -ne 0
        date +%Y-%m-%d 2>/dev/null
        return
    end

    set -l dates
    for i in (seq 0 2190)
        set -l d (date -d "$start + $i days" +%Y-%m-%d 2>/dev/null)
        if test -n "$d"
            set -a dates $d
        end
    end

    # Store in universal variables
    set -U __fish_orggle_date_cache $dates
    set -U __fish_orggle_date_cache_gen $today

    # Output
    for d in $dates
        echo $d
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

