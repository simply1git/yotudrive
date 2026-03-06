# YotuDrive API Reference

## Response Envelope

All JSON responses include:

- `ok`: boolean
- `request_id`: correlation ID (also returned as `X-Request-ID` response header)

Error responses include:

- `error.error_code`
- `error.message`
- optional `error.details`
- optional `error.job_id`

## Health

- `GET /api/health`

## Authentication (Phase 1)

- `POST /api/auth/bootstrap-admin`
  - One-time bootstrap for fresh deployments with an empty membership store.
  - Body: `email`
  - Returns: admin `session` and `user`

- `POST /api/auth/dev/login`
  - Closed-beta login against allowlisted membership records.
  - Body: `email`
  - Returns: `session` and `user`

- `GET /api/auth/google/start`
  - Starts Google OAuth web flow and returns `auth_url` + `state`.
  - Requires server env config:
    - `YOTU_GOOGLE_CLIENT_ID`
    - `YOTU_GOOGLE_CLIENT_SECRET`
    - optional `YOTU_GOOGLE_REDIRECT_URI`

- `GET /api/auth/google/callback`
  - Completes Google OAuth exchange.
  - Query: `state`, `code`
  - Returns: platform `session`, `user`, and Google `identity` summary.
  - Membership allowlist is enforced after Google identity verification.

- `GET /api/auth/google/status`
  - Returns whether Google OAuth is configured and the callback redirect URI.

- `GET /api/auth/session`
  - Requires `Authorization: Bearer <token>`
  - Returns: current `session` and `user`

- `POST /api/auth/logout`
  - Requires `Authorization: Bearer <token>`
  - Optional query: `reason` for audit labeling.
  - Returns: `revoked` boolean

- `GET /api/me/sessions`
  - Requires `Authorization: Bearer <token>`.
  - Lists sessions for the signed-in user.
  - Query params: `limit`, `offset`, `include_revoked`, `revoked_by`, `revoke_reason`.
  - Validation: `limit` must be 1..200, `offset` must be >= 0.
  - Session rows expose `token_id` (not raw bearer token), `is_current`, `created_from_ip`, `user_agent`, `last_seen_at`, `revoked_by`, and `revoke_reason`.

- `DELETE /api/me/sessions`
  - Requires `Authorization: Bearer <token>`.
  - Bulk-revokes sessions for signed-in user.
  - Query params: `keep_current` (default `true`), optional `reason`.

- `DELETE /api/me/sessions/<token_id>`
  - Requires `Authorization: Bearer <token>`.
  - Optional query: `reason`.
  - Revokes one owned session by `token_id`.

## Admin Membership (Phase 1)

- `GET /api/admin/users`
  - Requires admin bearer token.
  - Returns membership `users`, active count, and `cap`.

- `POST /api/admin/users`
  - Requires admin bearer token.
  - Body: `email`, optional `role` (`admin` or `member`), optional `enabled`.
  - Enforces the configured user cap.

- `PATCH /api/admin/users/<email>`
  - Requires admin bearer token.
  - Body: `enabled`.
  - Enables/disables an existing member.

- `GET /api/admin/sessions`
  - Requires admin bearer token.
  - Lists session records for operational visibility.
  - Query params: `limit`, `offset`, `email`, `include_revoked`, `revoked_by`, `revoke_reason`.
  - Validation: `limit` must be 1..200, `offset` must be >= 0.
  - Session rows expose `token_id` (not raw bearer token), plus `created_from_ip`, `user_agent`, `last_seen_at`, `revoked_by`, and `revoke_reason`.

- `DELETE /api/admin/sessions`
  - Requires admin bearer token.
  - Bulk-revokes active sessions for the target email.
  - Query params: `email` (required), optional `reason`.

- `DELETE /api/admin/sessions/<token_id>`
  - Requires admin bearer token.
  - Optional query: `reason`.
  - Revokes one session by `token_id`.

- `GET /api/admin/metrics`
  - Requires admin bearer token.
  - Returns aggregated control-plane metrics for `users`, `sessions`, `jobs`, and `files`.
  - Includes `jobs.by_status` and file ownership split (`owned` vs `legacy`).

## Files

- `GET /api/files`
- `DELETE /api/files/<file_id>`
- `POST /api/files/<file_id>/attach`
- `POST /api/upload/manual/register`

When a bearer session is provided, mutation endpoints in this section enforce ownership (`owner_email`) unless the session user is an admin. Legacy records without an owner cannot be mutated by non-admin authenticated users.

## Account-Scoped Files

- `GET /api/me/files`
  - Requires `Authorization: Bearer <token>`.
  - Returns records owned by the logged-in user.
  - Query: `include_legacy=true` to include older unowned records.

- `DELETE /api/me/files/<file_id>`
  - Requires `Authorization: Bearer <token>`.
  - Enforces ownership (admins can manage all records).

- `POST /api/me/files/<file_id>/attach`
  - Requires `Authorization: Bearer <token>`.
  - Body: `video_id`, optional `video_url`.
  - Enforces ownership (admins can manage all records).

## Settings

- `GET /api/settings`
- `PUT /api/settings`

## Verification & Tools

- `POST /api/verify`
- `POST /api/tools/auto-join`
- `POST /api/youtube/playlist/inspect`

`POST /api/verify` validation:

- `video_path` is required.
- `max_frames` must be an integer >= 1.

## Async Jobs

- `GET /api/jobs/<job_id>`

- `GET /api/me/jobs`
  - Requires `Authorization: Bearer <token>`.
  - Lists jobs owned by the signed-in user.
  - Query params: `limit`, `offset`, `status` (comma-separated), `include_public`.
  - Response includes `total` for filtered result count.
  - Validation: `limit` must be 1..200, `offset` must be >= 0.

- `GET /api/me/jobs/<job_id>`
  - Requires `Authorization: Bearer <token>`.
  - Returns a single owned job record (admins can also view).

- `GET /api/admin/jobs`
  - Requires admin bearer token.
  - Lists jobs across users for operations visibility.
  - Query params: `limit`, `offset`, `status`, `owner_email`, `include_public`.
  - Response includes `total` for filtered result count.
  - Validation: `limit` must be 1..200, `offset` must be >= 0.

- `GET /api/admin/jobs/<job_id>`
  - Requires admin bearer token.
  - Returns a single job record regardless of owner.

- `DELETE /api/admin/jobs/<job_id>`
  - Requires admin bearer token.
  - Deletes a persisted job record for cleanup/triage.

When jobs are created under an authenticated session, they are owned by that user account. Job polling enforces ownership (admins can view all owned jobs).

Terminal jobs are retained with automatic pruning by age and max-record limits in the persistent job store.

Returned payload includes `job` object with:

- `id`, `kind`, `status`, `progress`, `message`, `result`, `error`

## Encode / Decode Endpoints

Raw core operations:

- `POST /api/encode/start`
- `POST /api/decode/start`

Full pipeline operations:

- `POST /api/pipeline/encode-video/start`
  - `input_file`, `output_video`
  - optional: `password`, `overrides`, `verify_roundtrip`, `register_in_db`
- `POST /api/pipeline/decode-video/start`
  - `video_path`, `output_file`
  - optional: `password`, `overrides`

## OAuth Upload

- `POST /api/upload/oauth/start`
  - `file_path`, `title`
  - optional: `description`, `privacy_status`, `file_id`

This starts an async job and returns `job_id`.
