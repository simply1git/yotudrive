# Google OAuth Setup (Web Auth)

This guide configures live Google login for the web API endpoints:

- `GET /api/auth/google/start`
- `GET /api/auth/google/callback`

## 1. Create Google OAuth Credentials

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable Google Identity Services and OAuth consent screen.
4. Create OAuth client credentials with application type `Web application`.
5. Add an authorized redirect URI that matches your server callback endpoint.

Example redirect URI for local dev:

- `http://127.0.0.1:5000/api/auth/google/callback`

## 2. Set Environment Variables

Set these variables before running `python app.py`:

- `YOTU_GOOGLE_CLIENT_ID`
- `YOTU_GOOGLE_CLIENT_SECRET`
- optional `YOTU_GOOGLE_REDIRECT_URI`

PowerShell example:

```powershell
$env:YOTU_GOOGLE_CLIENT_ID = "your-client-id.apps.googleusercontent.com"
$env:YOTU_GOOGLE_CLIENT_SECRET = "your-client-secret"
$env:YOTU_GOOGLE_REDIRECT_URI = "http://127.0.0.1:5000/api/auth/google/callback"
python app.py
```

## 3. Bootstrap Admin and Allowlist Members

Google identity alone is not enough. The email must be allowlisted in YotuDrive membership.

1. Bootstrap the first admin in a fresh environment:

```bash
curl -X POST http://127.0.0.1:5000/api/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com"}'
```

2. Use admin session token to add users via `POST /api/admin/users`.

## 4. Test Login Flow

1. Call `GET /api/auth/google/start` and open returned `auth_url`.
2. Complete Google sign-in.
3. Google redirects to callback with `state` and `code`.
4. Callback returns YotuDrive `session` token when allowlist check passes.

## 5. Common Errors

- `oauth_not_configured`: missing environment variables.
- `invalid_state`: callback state expired or invalid.
- `auth_denied`: Google email is not allowlisted or account is disabled.
- `oauth_exchange_failed`: invalid code, redirect mismatch, or Google API misconfiguration.
