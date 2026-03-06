# YotuDrive Release Runbook

This document is the practical path from "working project" to "real-world product".

For hosting/web go-live steps, see `docs/deployment_checklist.md`.

## 1. Release Criteria (Go/No-Go)

All items below must be true for a release candidate:

- Clean environment install succeeds on target OS.
- Unit/smoke/integration test gates pass.
- Executable build succeeds and launches.
- One real file roundtrip (encode -> video -> decode) passes with matching SHA-256.
- No unhandled exceptions in app logs during smoke test.
- API health endpoint returns 200.
- README and API docs match current behavior and paths.

## 2. Pre-Release Validation

From repository root:

```powershell
python -m venv .venv_cleancheck
.\.venv_cleancheck\Scripts\python -m pip install --upgrade pip
.\.venv_cleancheck\Scripts\python -m pip install -r requirements.txt
```

Run tests:

```powershell
python -m unittest tests.test_core_engine tests.test_web_api_smoke tests.test_header_v5_module tests.test_settings_module tests.test_decoder_detection tests.test_encoder_executor_selection
python tests/test_full_cycle.py
```

Web smoke:

```powershell
.\.venv_cleancheck\Scripts\python -c "from app import app; c=app.test_client(); print(c.get('/api/health').status_code, c.get('/').status_code)"
```

Expected output: `200 200`

## 3. Build and Desktop Smoke

Build:

```powershell
.\.venv_cleancheck\Scripts\python build_exe.py
```

Expected artifact:

- `dist/YotuDrive/YotuDrive.exe`

Desktop smoke steps:

1. Launch `dist/YotuDrive/YotuDrive.exe`.
2. Encode a representative file (at least 1-10 MB).
3. Complete restore flow from produced video.
4. Confirm GUI returns to ready state with no crashes.

Integrity verification (external):

```powershell
$orig='C:\path\to\input.file'
$rest='E:\New folder\yotudrive\dist\YotuDrive\restored_files\input.file'
(Get-FileHash $orig -Algorithm SHA256).Hash
(Get-FileHash $rest -Algorithm SHA256).Hash
```

Hashes must match exactly.

## 4. Runtime Operations

- Logs location: `logs/` (source mode) and `dist/YotuDrive/logs/` (exe mode).
- Keep at least the last 7 days of logs for incident triage.
- If a user reports corruption, always request:
  - source file hash
  - restored file hash
  - relevant log file
  - used block size/ecc settings

## 5. Incident Playbook

If encode/decode fails in production:

1. Reproduce with same input/settings in latest build.
2. Compare behavior in source mode vs exe mode.
3. Collect traceback and logs.
4. Run full test gates locally.
5. Add a regression test before shipping fix.

## 6. Security and Secrets

- Never commit OAuth credentials or tokens.
- Keep YouTube OAuth client files outside version control.
- Rotate any leaked tokens immediately.
- Use unlisted/private visibility by default for uploads unless explicitly needed.

## 7. Versioning and Release Notes

Recommended release process:

1. Create release branch.
2. Run full validation in this document.
3. Tag version (`vX.Y.Z`).
4. Publish changelog with:
   - fixed bugs
   - known limitations
   - migration notes (if any)

GitHub release automation:

- Push tag `vX.Y.Z` to trigger `.github/workflows/release.yml`.
- Download and verify release assets:
  - `YotuDrive-vX.Y.Z-windows-x64.zip`
  - `SHA256SUMS.txt`

## 8. Current Known Constraints

- Windows frozen builds intentionally use thread pool for encoder worker stability.
- This may be slower than process pool, but is significantly more reliable for PyInstaller runtime.

## 9. 30-Day Productization Plan

Week 1:

- Add automated build artifact upload in CI.
- Add scripted desktop smoke test checklist.

Week 2:

- Add structured log format and simple crash signature classification.
- Add backup/restore test for `yotudrive.json` database.

Week 3:

- Add API auth layer for non-local deployments.
- Add rate limits for async job endpoints.

Week 4:

- Publish installer package and signed binary pipeline.
- Publish support playbook (FAQ + issue templates).
