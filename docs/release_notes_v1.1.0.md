# YotuDrive v1.1.0 Release Notes

Release date: 2026-03-06

## Highlights

- Completed Mode A backend foundations for closed-beta account operations.
- Added production-style auth/session/job control-plane APIs with ownership enforcement.
- Delivered admin observability and session/device-style controls.
- Finalized packaged Windows product artifact and checksum manifests.

## New Capabilities

### Authentication and Membership

- Closed-beta membership controls with admin bootstrap and allowlist enforcement.
- Session-based auth lifecycle:
  - `/api/auth/bootstrap-admin`
  - `/api/auth/dev/login`
  - `/api/auth/session`
  - `/api/auth/logout`
- Google OAuth web flow:
  - `/api/auth/google/start`
  - `/api/auth/google/callback`
  - `/api/auth/google/status`

### Account and Ownership Scoping

- Account-scoped file operations:
  - `/api/me/files`
  - `/api/me/files/<file_id>`
  - `/api/me/files/<file_id>/attach`
- Authenticated mutation routes now enforce ownership unless user is admin.

### Job Operations and Persistence

- Persistent job store and owner-aware visibility controls.
- User job APIs:
  - `/api/me/jobs`
  - `/api/me/jobs/<job_id>`
- Admin job APIs:
  - `/api/admin/jobs`
  - `/api/admin/jobs/<job_id>`
  - `DELETE /api/admin/jobs/<job_id>`
- Job retention pruning by age and max record count.

### Session Operations and Auditability

- Self-service session listing/revocation:
  - `/api/me/sessions`
  - `DELETE /api/me/sessions`
  - `DELETE /api/me/sessions/<token_id>`
- Admin session operations:
  - `/api/admin/sessions`
  - `DELETE /api/admin/sessions`
  - `DELETE /api/admin/sessions/<token_id>`
- Session payload metadata:
  - `created_from_ip`, `user_agent`, `last_seen_at`
  - `revoked_by`, `revoke_reason`
- Revoke audit filtering support on session list endpoints:
  - `revoked_by`, `revoke_reason`

### Admin Observability

- New control-plane metrics endpoint:
  - `GET /api/admin/metrics`
- Aggregates users, sessions, jobs (including `by_status`), and files.

## Reliability and Validation

- Strengthened numeric input validation for pagination and verify parameters.
- Smoke and runbook validation passed:
  - Core/unit web suite
  - Full-cycle encode/decode integration
  - Web health endpoint checks
  - Windows executable build

## Artifacts

- Executable: `dist/YotuDrive/YotuDrive.exe`
- Release zip: `dist/YotuDrive-final-windows-x64.zip`
- Checksums: `dist/SHA256SUMS.txt`
- Final handoff manifest: `FINAL_PRODUCT.md`

## Notes

This release is aligned with Mode A goals in `docs/platform_blueprint_mode_a.md` for controlled beta operation with metadata-centric architecture and robust operational controls.
