# orggle

Sync org-mode clock entries to Toggl Track with multi-profile support for multiple accounts.

## Features

- **Multi-Profile Support**: Manage multiple Toggl accounts with named profiles
- **Environment Variable Substitution**: Securely store API tokens in environment variables using `${VAR_NAME}` syntax
- **Per-Profile Settings**: Each profile can have its own tags, projects, and regex mappings
- **Parse CLOCK entries**: Extract time entries from org-mode files
- **Sync to Toggl Track**: Upload entries with automatic retry on network failure
- **Batch Mode**: Daily grouped syncing with confirmation
- **Skip Already Synced**: Track synced entries in local SQLite database per profile
- **Configurable Entry Mappings**: Regex-based description replacement per profile
- **Delete & Re-sync**: Clear existing entries and re-sync specific days
- **XDG Base Directory**: Config stored in `~/.config/orggle/` following Linux standards

## Installation

### Quick Setup (Recommended)

Clone the repository and run the appropriate installation script:

#### For bash/Linux/macOS:

```bash
git clone https://github.com/khajavi/orggle.git
cd orggle
chmod +x install.sh
./install.sh
```

#### For fish shell:

```fish
git clone https://github.com/khajavi/orggle.git
cd orggle
chmod +x install.fish
./install.fish
```

The installer will:
1. Check for Python 3 and curl
2. Create an isolated Python virtual environment (`.venv/`)
3. Install dependencies (PyYAML - optional, falls back to JSON config if unavailable)
4. Create `~/.config/orggle/` directory for configuration
5. Create an initial `config.yaml` with default profile
6. Create an `orggle` wrapper script in the project directory
7. Prompt you to set the API token

### Manual Setup

If you prefer not to use the installer:

```bash
# Clone the repository
git clone https://github.com/khajavi/orggle.git
cd orggle

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (optional)
pip install -r requirements.txt

# Create config directory
mkdir -p ~/.config/orggle
```

## Configuration

### Basic Setup

Configuration is stored in `~/.config/orggle/config.yaml`. After installation, set your API token:

```bash
export TOGGL_API_TOKEN="your_api_token"
```

For fish shell:

```fish
set -gx TOGGL_API_TOKEN 'your_api_token'
```

### Single Profile (Default)

By default, orggle comes with a single `default` profile:

```yaml
# ~/.config/orggle/config.yaml

default_profile: default
tag: orggle  # Global default tag

profiles:
  default:
    api_token: ${TOGGL_API_TOKEN}
    default_project: Documentation
    org_mappings:
      - pattern: "^\\s*- rest$"
        description: "Break Time"
```

### Multiple Profiles

To manage multiple Toggl accounts, add more profiles:

```yaml
# ~/.config/orggle/config.yaml

default_profile: work

# Global default tag (used if profile doesn't specify one)
tag: orggle

profiles:
  work:
    # Environment variables are substituted at runtime
    api_token: ${WORK_TOGGL_TOKEN}
    tag: orggle-work  # Override global tag
    default_project: Work
    org_mappings:
      - pattern: "^\\s*- rest$"
        description: "Break Time"
      - pattern: "^\\s*- meeting$"
        description: "Meeting"
  
  personal:
    api_token: ${PERSONAL_TOGGL_TOKEN}
    tag: personal-time
    default_project: Personal
    org_mappings:
      - pattern: "^\\s*- rest$"
        description: "Leisure Time"
```

Set environment variables before running:

```bash
export WORK_TOGGL_TOKEN="your_work_token"
export PERSONAL_TOGGL_TOKEN="your_personal_token"
```

### Configuration Options

| Field | Required | Description |
|-------|----------|-------------|
| `default_profile` | Yes | Profile name to use if `--profile` not specified |
| `tag` | No | Global default tag for entries (defaults to "orggle") |
| `profiles.<name>.api_token` | Yes | Toggl API token (supports `${ENV_VAR}` substitution) |
| `profiles.<name>.tag` | No | Tag for this profile (overrides global tag) |
| `profiles.<name>.default_project` | Yes | Default Toggl project name |
| `profiles.<name>.org_mappings` | No | Regex patterns to replace entry descriptions |

### Environment Variable Substitution

API tokens can reference environment variables using `${VAR_NAME}` syntax:

```yaml
profiles:
  work:
    api_token: ${WORK_TOGGL_TOKEN}  # Reads from WORK_TOGGL_TOKEN env var
```

The variable **must be set** before running orggle, or you'll get an error:

```bash
Error: Environment variable 'WORK_TOGGL_TOKEN' not found in profile 'work'
```

### Optional Proxy

Set a proxy if needed:

```bash
export TOGGL_PROXY="http://localhost:10709"
# or
export HTTPS_PROXY="http://localhost:10709"
```

## Usage

### Basic Sync (Default Profile)

Sync all clock entries from an org-mode file using the default profile:

```bash
./orggle journal.org
```

Output:
```
Using profile: work
Fetching workspace ID...
Using workspace ID: 12345
Looking up project 'Work'...
Using project ID: 67890
Parsing journal.org...
Found 5 clock entries (latest first)
New: 5

[Entry 1] Task description (3:00)
Sync this entry? (y/n/q): y
  ✓ Synced: https://track.toggl.com/timer/987654321
```

### Use Specific Profile

Sync using a different profile:

```bash
./orggle journal.org --profile personal
```

Or set it in the config:

```yaml
default_profile: personal  # Now 'personal' is default
```

### Batch Mode (Daily)

Sync entries grouped by day, confirming each day:

```bash
./orggle journal.org --batch daily
```

Output:
```
Using profile: work
Found 10 clock entries (latest first)
New: 10

Day: 2026-03-29 (3 entries, 8:00 total)
  [Entry 1] Task 1 (3:00)
  [Entry 2] Task 2 (5:00)
Sync this day? (y/n/q): y
  ✓ Synced: https://track.toggl.com/timer/987654321
  ✓ Synced: https://track.toggl.com/timer/987654322

Day: 2026-03-28 (2 entries, 5:00 total)
...
```

### Sync Specific Day

Sync entries for a specific day, ignoring previous sync status:

```bash
./orggle journal.org --day 2026-03-28
```

This re-syncs all entries from that day, regardless of whether they were previously synced.

### Delete and Re-sync

Delete existing Toggl entries for a day before syncing:

```bash
./orggle journal.org --day 2026-03-28 --delete-existing
```

Useful for correcting mistakes or updating entries.

### Delete Only

Delete existing entries without syncing new ones:

```bash
./orggle --day 2026-03-28 --delete-existing
```

### All Options

```
usage: orggle.py [-h] [--profile PROFILE] [--batch {daily}] [--day DAY] [--delete-existing] [org_file]

Sync org-mode clock entries to Toggl

positional arguments:
  org_file              Path to org-mode file (optional with --delete-existing)

optional arguments:
  -h, --help            show this help message and exit
  --profile PROFILE     Toggl profile to use (default from config)
  --batch {daily}       Batch mode: 'daily' syncs all entries grouped by day
  --day DAY             Sync specific day (YYYY-MM-DD), ignores previous sync status
  --delete-existing     Delete existing entries for --day before syncing
```

## How It Works

### Entry Parsing

orggle parses CLOCK entries from org-mode files:

```org
CLOCK: [2026-03-28 Thu 09:00]--[2026-03-28 Thu 12:00] =>  3:00
```

The script extracts:
- Task description (status tags like DONE, TODO are removed)
- Start and stop times (converted to local timezone)
- Duration

### Entry Mapping

Entries can be renamed based on regex patterns in `org_mappings`. This is useful for replacing placeholders with meaningful descriptions:

```org
CLOCK: [2026-03-28 Thu 12:00]--[2026-03-28 Thu 13:00] =>  1:00
- rest
CLOCK: [2026-03-28 Thu 13:00]--[2026-03-28 Thu 14:00] =>  1:00
- meeting
```

Config:
```yaml
org_mappings:
  - pattern: "^\\s*- rest$"
    description: "Break Time"
  - pattern: "^\\s*- meeting$"
    description: "Meeting"
```

Result in Toggl: "Break Time" and "Meeting" instead of original task names.

### Tracking

Synced entries are tracked in a profile-specific SQLite database:

```
~/.config/orggle/
├── default.db      # Default profile database
├── work.db         # Work profile database
└── personal.db     # Personal profile database
```

By default, already-synced entries are skipped on subsequent runs. Use `--day` to re-sync.

### Retry Logic

Network failures trigger automatic retry with fibonacci backoff (1s, 1s, 2s, 3s, 5s, 8s, 13s, 21s, 34s, 55s).

## Examples

### Full Workflow: Multi-Profile Management

```bash
# Set up environment variables for both accounts
export WORK_TOGGL_TOKEN="work_token_here"
export PERSONAL_TOGGL_TOKEN="personal_token_here"

# Sync work entries with default profile
./orggle work.org

# Sync personal entries with different profile
./orggle personal.org --profile personal

# Check what would be synced (batch mode)
./orggle work.org --batch daily

# Re-sync yesterday's entries after corrections
./orggle work.org --day 2026-03-28 --delete-existing

# Sync specific day for personal account
./orggle personal.org --profile personal --day 2026-03-27
```

### Config Example: Three Profiles

```yaml
# ~/.config/orggle/config.yaml

default_profile: work

tag: orggle

profiles:
  work:
    api_token: ${WORK_TOKEN}
    default_project: Work
    org_mappings:
      - pattern: "^\\s*- rest$"
        description: "Break"
      - pattern: "^\\s*- meeting$"
        description: "Meeting"
  
  personal:
    api_token: ${PERSONAL_TOKEN}
    default_project: Personal
    org_mappings:
      - pattern: "^\\s*- rest$"
        description: "Leisure"
  
  client:
    api_token: ${CLIENT_TOKEN}
    tag: client-billing
    default_project: Client Project
    org_mappings:
      - pattern: "^\\s*- paid$"
        description: "Billable Work"
      - pattern: "^\\s*- free$"
        description: "Pro Bono"
```

## Uninstallation

To remove orggle and all associated files:

#### For bash/Linux/macOS:

```bash
cd orggle
chmod +x uninstall.sh
./uninstall.sh
```

#### For fish shell:

```fish
cd orggle
chmod +x uninstall.fish
./uninstall.fish
```

The uninstaller will prompt you to remove:
- Virtual environment (`.venv/`)
- Wrapper script (`orggle`)
- Local databases (`~/.config/orggle/*.db`)

You can answer `y` or `n` for each component.

## Database

Databases are stored in `~/.config/orggle/`:

```
~/.config/orggle/
├── config.yaml    # Configuration file
├── default.db     # Default profile database
├── work.db        # Work profile database
└── personal.db    # Personal profile database
```

### Database Schema

```sql
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
```

## Troubleshooting

### Profile Not Found

**Error**: `Profile 'xyz' not found. Available profiles: default, work`

**Solution**: Use one of the available profiles with `--profile`, or add the profile to `~/.config/orggle/config.yaml`

### Missing Environment Variable

**Error**: `Environment variable 'WORK_TOGGL_TOKEN' not found in profile 'work'`

**Solution**: Set the environment variable before running:
```bash
export WORK_TOGGL_TOKEN="your_token"
./orggle journal.org --profile work
```

### No Default Profile

**Error**: `No default_profile defined in config`

**Solution**: Add to `~/.config/orggle/config.yaml`:
```yaml
default_profile: work
```

### Config Not Found

**Error**: `Config not found at ~/.config/orggle/config.yaml`

**Solution**: Run installer again, or create manually:
```bash
mkdir -p ~/.config/orggle
# Create config.yaml
```

## Requirements

- Python 3.7+
- curl (used for API calls)
- Toggl Track account with API token
- PyYAML (optional, for YAML config; falls back to JSON)

## Migration from Older Versions

If you have an old config in the project root, orggle will:
1. Detect the old format
2. Auto-migrate to new format
3. Create `~/.config/orggle/config.yaml`
4. Show a warning message

Your data is preserved during migration.

## License

MIT
