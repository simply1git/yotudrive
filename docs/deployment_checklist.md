# YotuDrive Deployment Checklist (Production)

Use this checklist to deploy the web API to a managed host (Render, Railway, or similar) and verify it is production-ready.

## 1. Pre-Deploy Inputs

Prepare these before deployment:

- Git repo with latest release code.
- Google OAuth web client configured with production callback URL.
- Rotated secrets (do not reuse previously exposed keys).
- Target host URL (example: `https://api.yotudrive.example.com`).

## 2. Required Environment Variables

Set these variables in your hosting dashboard:

- `FLASK_ENV=production`
- `FLASK_DEBUG=0`
- `PORT` (host-provided; keep default if managed automatically)
- `SECRET_KEY` (strong random string)
- `YOTU_GOOGLE_CLIENT_ID`
- `YOTU_GOOGLE_CLIENT_SECRET`
- `YOTU_GOOGLE_REDIRECT_URI` (must exactly match Google OAuth callback)

Optional / future-use:

- `DATABASE_URL` (reserved for future Postgres migration)
- `YOUTUBE_API_KEY` (only required for features that need it)

Legacy compatibility (supported but not recommended for new deploys):

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`

## 3. Google OAuth Configuration

In Google Cloud OAuth client settings:

- Add authorized redirect URI:
  - `https://<your-domain>/api/auth/google/callback`
- Ensure OAuth consent screen is configured for your user type and scopes.

## 4. Deploy Steps

1. Create a new web service from your repository.
2. Set build command:
   - `pip install -r requirements.txt`
3. Set start command:
   - `python app.py`
4. Add all required environment variables.
5. Deploy and wait for service healthy state.

## 5. First-Boot Initialization

Run once on a fresh environment:

1. Bootstrap admin:

```bash
curl -X POST https://<your-domain>/api/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com"}'
```

2. Save returned admin bearer token securely.
3. Add allowlisted members via `POST /api/admin/users`.

## 6. Post-Deploy Verification

Run these checks:

1. Health check:

```bash
curl https://<your-domain>/api/health
```

Expected: HTTP `200`, JSON with `ok: true`.

2. OAuth config status:

```bash
curl https://<your-domain>/api/auth/google/status
```

Expected: `configured: true`.

3. Admin endpoint access:

```bash
curl https://<your-domain>/api/admin/users \
  -H "Authorization: Bearer <admin-token>"
```

Expected: HTTP `200`.

4. Session observability:

```bash
curl "https://<your-domain>/api/admin/sessions?include_revoked=true" \
  -H "Authorization: Bearer <admin-token>"
```

Expected: session rows with audit fields including `token_id`, `revoked_by`, and `revoke_reason`.

## 7. Security Hardening

- Rotate all secrets before go-live if they were ever shared in plaintext.
- Enforce HTTPS only.
- Restrict admin email set and review membership list weekly.
- Keep `.env` files out of source control.
- Keep logs retained for incident triage.

## 8. Release Publishing (Tag-Based)

When ready to publish release assets:

```bash
git tag v1.1.0
git push origin v1.1.0
```

This triggers `.github/workflows/release.yml` to produce and publish Windows artifacts.
