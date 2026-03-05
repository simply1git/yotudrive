# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-03-05

### Added
- Automated tag-driven release workflow (`.github/workflows/release.yml`) for Windows executable packaging and GitHub Release asset publishing.
- Production runbook (`docs/release_runbook.md`) with go/no-go criteria, validation steps, incident playbook, and 30-day productization plan.
- Security scanning workflow (`.github/workflows/security.yml`) using `pip-audit`, `bandit`, and `detect-secrets`.
- Regression test for frozen Windows executor strategy (`tests/test_encoder_executor_selection.py`).

### Changed
- Improved release/operations documentation in `README.md`.
- Added `.gitattributes` to enforce consistent line endings across platforms.
- Added `.gitignore` hygiene for local artifacts, virtual environments, and build output noise.

### Fixed
- Resolved frozen Windows EXE encoding crash (`BrokenProcessPool`) by using thread pool executor in frozen mode and adding multiprocessing freeze support in GUI entrypoints.
- Fixed GUI syntax blocker in encode flow (`src/gui.py`) caused by duplicated `else` branch.
- Added missing GUI dependency (`ttkbootstrap`) to `requirements.txt` and removed unused launcher dependency check for `click`.
