# ORGLE Backlog

This directory contains planned improvements, features, and bug fixes for orggle, organized by priority and impact.

## Priority Tiers

- **Tier 1 (Critical)**: Prevents user harm, data loss, or breaks confidence in the tool
- **Tier 2 (High)**: Significant quality-of-life improvements for daily users
- **Tier 3 (Medium)**: Nice-to-have enhancements that improve workflow
- **Tier 4 (Low)**: Polish, optimization, or speculative features

## Backlog Index

| ID | Title | Priority | Effort | Status |
|-----|-------|----------|--------|--------|
| [B-001](B-001-dry-run-preview-mode.md) | Dry-Run / Preview Mode | Tier 1 | XS | Planned |
| [B-002](B-002-confirm-delete-existing.md) | Confirm Before Delete | Tier 1 | XS | Planned |
| [B-003](B-003-description-update-gap.md) | Fix Description Update Gap | Tier 1 | M | Planned |
| [B-004](B-004-auto-accept-flag.md) | Add `--yes` Flag | Tier 1 | XS | Planned |
| [B-005](B-005-fix-mapping-logic.md) | Fix Description Mapping Logic | Tier 2 | S | Planned |
| [B-006](B-006-config-validate-command.md) | Config Validation Command | Tier 2 | M | Planned |
| [B-007](B-007-progress-indicator.md) | Progress Indicators | Tier 2 | S | Planned |
| [B-008](B-008-timezone-handling.md) | Timezone Handling | Tier 2 | M | Planned |
| [B-009](B-009-multiple-tags-support.md) | Multiple Tags Support | Tier 2 | S | Planned |
| [B-010](B-010-summary-stats.md) | Summary Statistics | Tier 2 | XS | Planned |
| [B-011](B-011-exclude-regex-filter.md) | Exclude Regex Filter | Tier 3 | S | Planned |
| [B-012](B-012-output-formats.md) | Output Formats (JSON/Quiet) | Tier 3 | S | Planned |
| [B-013](B-013-since-until-aliases.md) | Since/Until Aliases | Tier 3 | XS | Planned |
| [B-014](B-014-config-ux-commands.md) | Config UX Commands | Tier 3 | M | Planned |
| [B-015](B-015-overlap-detection.md) | Overlap Detection | Tier 3 | M | Planned |
| [B-016](B-016-auto-batch-threshold.md) | Auto-Batch Threshold | Tier 3 | S | Planned |
| [B-017](B-017-resume-capability.md) | Resume Capability | Tier 4 | M | Planned |
| [B-018](B-018-code-modularization.md) | Code Modularization | Tier 4 | L | Planned |

**Effort Estimates:**
- **XS**: < 1 hour
- **S**: 1-4 hours
- **M**: 4-8 hours
- **L**: 8+ hours

## Epic Themes

### Data Integrity & Safety
Ensuring users don't lose data and can trust orggle to do the right thing.
- B-001 Dry-Run
- B-002 Confirm Delete
- B-003 Description Updates
- B-015 Overlap Detection

### Automation & Scripting
Making orggle work well in non-interactive contexts (cron, CI/CD, scripts).
- B-004 Auto-Accept
- B-012 Output Formats
- B-017 Resume

### Configuration & Validation
Helping users set up correctly and catch errors early.
- B-006 Config Validation
- B-014 Config UX

### User Feedback & Transparency
Showing users what's happening, how long it will take, and what happened.
- B-007 Progress Indicators
- B-010 Summary Stats
- B-012 Output Formats

### Feature Parity & Flexibility
Catching up to expected Toggl features and adding missing controls.
- B-008 Timezone Handling
- B-009 Multiple Tags
- B-011 Exclude Filter

### Code Health & Maintainability
Long-term sustainability of the codebase.
- B-005 Fix Mapping Logic
- B-013 Aliases (documentation)
- B-016 Auto-Batch
- B-018 Modularization

---

*Last updated: 2025-04-01*
