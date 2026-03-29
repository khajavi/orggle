# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-29

### Added
- Multi-profile support for managing multiple Toggl Track accounts
- Environment variable substitution in configuration (${VAR_NAME} syntax)
- Per-profile tag customization with global defaults
- Per-profile org-mode regex mappings for flexible entry description handling
- Batch mode for daily syncing of all org-mode entries
- Day-specific sync with force re-sync capability (--day, --delete-existing flags)
- Comprehensive bash installer (install.sh) with virtual environment setup
- Fish shell installer support (install.fish)
- Comprehensive uninstaller scripts for both bash and fish shells
- XDG Base Directory Specification compliance for config and database storage
- SQLite database for tracking synchronization state per profile
- Full org-mode clock entry parsing and validation
- Automatic Toggl Track time entry synchronization
- Extensive documentation with multi-profile examples

### Features
- **Full org-mode Support**: Parse and sync clock entries from org-mode files
- **Toggl Integration**: Direct synchronization with Toggl Track API
- **Multi-Account Management**: Handle multiple Toggl profiles in single installation
- **Flexible Configuration**: YAML-based config with environment variable support
- **State Tracking**: SQLite database prevents duplicate syncs
- **Batch Operations**: Sync entire days or specific entries
- **Force Re-sync**: Delete and re-sync existing entries with --delete-existing

### Technical Details
- Python 3.8+ compatibility
- Zero external dependencies (PyYAML only)
- Secure token storage via environment variables
- Professional-grade installation/uninstallation
- Clean command-line interface with argparse

### Security
- Environment variable substitution for API tokens
- No hardcoded credentials
- Secure configuration file handling
