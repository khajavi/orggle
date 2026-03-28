# orggle

Sync org-mode clock entries to Toggl Track.

## Features

- Parse CLOCK entries from org-mode files
- Sync time entries to Toggl Track with automatic retry on network failure
- Batch mode for daily grouped syncing with confirmation
- Skip already-synced entries (tracked in local SQLite database)
- Support for rest entries (synced as configured in config)
- Default project configuration
- Local timezone handling
- Delete existing Toggl entries for specific days

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/orggle.git
cd orggle

# Install dependencies (optional, uses system curl by default)
pip install -r requirements.txt
```

## Configuration

Set your Toggl API token:

```bash
export TOGGL_API_TOKEN="your_api_token"
```

Optional: Set a proxy if needed:

```bash
export TOGGL_PROXY="http://localhost:10709"
# or
export HTTPS_PROXY="http://localhost:10709"
```

### Toggl Settings

Edit `config.yaml` to customize:

```yaml
toggl:
  tag: orggle
  rest_description: "Break Time"
  default_project: Documentation
```

Note: If PyYAML is not installed, the script will fall back to `config.json`.

## Usage

### Basic Sync

Sync all clock entries from an org-mode file:

```bash
python3 orggle.py your-org-file.org
```

### Batch Mode (Daily)

Use `--batch daily` to sync entries grouped by day. You'll confirm each day individually:

```bash
python3 orggle.py your-org-file.org --batch daily
```

### Sync Specific Day

Sync entries for a specific day, ignoring previous sync status:

```bash
python3 orggle.py your-org-file.org --day 2026-03-28
```

### Delete and Re-sync

Delete existing Toggl entries for a day before syncing:

```bash
python3 orggle.py your-org-file.org --day 2026-03-28 --delete-existing
```

### Delete Only

Delete existing Toggl entries without syncing new ones:

```bash
python3 orggle.py --day 2026-03-28 --delete-existing
```

## Options

| Option | Description |
|--------|-------------|
| `org_file` | Path to org-mode file (optional with --delete-existing) |
| `--batch {daily}` | Batch mode: syncs all entries grouped by day |
| `--day DAY` | Sync specific day (YYYY-MM-DD), ignores previous sync status |
| `--delete-existing` | Delete existing entries for --day before syncing |

## How It Works

### Entry Parsing

orggle parses CLOCK entries from org-mode files:

```
CLOCK: [2026-03-28 Thu 09:00]--[2026-03-28 Thu 12:00] =>  3:00
```

The script extracts:
- Task description (status tags like DONE, TODO are removed)
- Start and stop times (converted to local timezone)
- Duration

### Rest Entries

Entries followed by `- rest` in the org file are synced as configured in `rest_description`:

```
CLOCK: [2026-03-28 Thu 12:00]--[2026-03-28 Thu 13:00] =>  1:00
- rest
CLOCK: [2026-03-28 Thu 13:00]--[2026-03-28 Thu 17:00] =>  4:00
```

### Tracking

Synced entries are tracked in a local SQLite database (`~/.orggle.db`). By default, already-synced entries are skipped on subsequent runs.

### Retry Logic

Network failures trigger automatic retry with fibonacci backoff (1s, 1s, 2s, 3s, 5s, 8s, 13s, 21s, 34s, 55s).

## Database

Location: `~/.orggle.db`

Schema:

```sql
CREATE TABLE entries (
    hash TEXT PRIMARY KEY,
    description TEXT,
    start TEXT,
    stop TEXT,
    duration INTEGER,
    is_rest INTEGER,
    published INTEGER DEFAULT 0,
    toggl_id TEXT,
    synced_at TEXT
)
```

## Examples

### Full Workflow

```bash
# Initial sync of all entries
python3 orggle.py journal.org

# Check what's new since last sync
python3 orggle.py journal.org --batch daily

# Re-sync a specific day (will re-sync all entries for that day)
python3 orggle.py journal.org --day 2026-03-28 --delete-existing

# Just delete entries for a day without syncing
python3 orggle.py --day 2026-03-28 --delete-existing
```

## Requirements

- Python 3.7+
- curl (used for API calls)
- Toggl Track account with API token
- PyYAML (optional, for YAML config)

## License

MIT
