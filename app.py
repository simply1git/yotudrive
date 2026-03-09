"""
YotuDrive Flask REST API
All routes match docs/api.md exactly.
Run: python app.py
"""
import os
import uuid
import threading
import time
import secrets
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, request, jsonify, g
from flask_cors import CORS

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config['UPLOAD_FOLDER'] = 'data/uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

VERSION = "1.1.0"

# ---------------------------------------------------------------------------
# Lazy singletons (imported on first request to avoid import-time side effects)
# ---------------------------------------------------------------------------
_auth_store = None
_job_store = None
_db = None
_engine_instance = None
_settings_instance = None

def init_services():
    from src.janitor import start_janitor_thread
    start_janitor_thread(interval_minutes=30)
    print("[System] Janitor service started (30m interval)")

# Start background services immediately
init_services()

def _auth():
    global _auth_store
    if _auth_store is None:
        if os.environ.get("SUPABASE_URL"):
            from src.supabase_store import SupaAuthStore
            _auth_store = SupaAuthStore()
        elif os.environ.get("DATABASE_URL"):
            from src.pg_store import PGAuthStore
            _auth_store = PGAuthStore()
        else:
            from src.auth_store import AuthStore
            _auth_store = AuthStore()
    return _auth_store

def _jobs():
    from src.job_store import get_job_store
    return get_job_store()

def _engine():
    from src.core.engine import get_engine
    return get_engine()

def _settings():
    from src.settings import get_settings
    return get_settings()

# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
def ok(**kwargs):
    payload = {"ok": True, "request_id": g.get("request_id", str(uuid.uuid4()))}
    payload.update(kwargs)
    return jsonify(payload)

def err(code: str, message: str, status: int = 400, **kwargs):
    payload = {
        "ok": False,
        "request_id": g.get("request_id", str(uuid.uuid4())),
        "error": {"error_code": code, "message": message},
    }
    payload["error"].update(kwargs)
    return jsonify(payload), status

# ---------------------------------------------------------------------------
# Before/after request
# ---------------------------------------------------------------------------
@app.before_request
def set_request_id():
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

@app.after_request
def add_request_id_header(response):
    response.headers["X-Request-ID"] = g.get("request_id", "")
    return response

@app.errorhandler(500)
def handle_500(e):
    import traceback
    print(f"[Error] Global 500: {e}")
    traceback.print_exc()
    return err("internal_error", f"Station Core Failure: {str(e)}", 500)

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    print(f"[Error] Unhandled Exception: {e}")
    traceback.print_exc()
    return err("unhandled_exception", str(e), 500)

# ---------------------------------------------------------------------------
# Auth middleware helpers
# ---------------------------------------------------------------------------
def _get_bearer() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None

def require_auth():
    """Validate Bearer token. Sets g.session, g.user. Returns error response or None."""
    token = _get_bearer()
    if not token:
        return err("unauthorized", "Authorization: Bearer <token> required", 401)
    try:
        sess, user = _auth().validate_token(token)
        g.session = sess
        g.user = user
        return None
    except Exception as e:
        return err("unauthorized", str(e), 401)

def require_admin():
    e = require_auth()
    if e:
        return e
    if g.user.get("role") != "admin":
        return err("forbidden", "Admin role required", 403)
    return None

def optional_auth():
    """Try to auth; sets g.user/g.session if valid, else leaves unset."""
    token = _get_bearer()
    if token:
        try:
            sess, user = _auth().validate_token(token)
            g.session = sess
            g.user = user
        except Exception:
            g.user = None
            g.session = None
    else:
        g.user = None
        g.session = None

# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------
def _paginate():
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
        if not (1 <= limit <= 200):
            raise ValueError
        if offset < 0:
            raise ValueError
        return limit, offset, None
    except (ValueError, TypeError):
        return None, None, err("invalid_param", "limit must be 1..200 and offset must be >= 0")

# ===========================================================================
# HEALTH
# ===========================================================================
@app.get("/api/health")
@app.get("/health")
@app.get("/")
def health():
    return ok(version=VERSION, status="healthy", timestamp=time.time())

# ===========================================================================
# AUTH
# ===========================================================================
@app.post("/api/auth/bootstrap-admin")
def bootstrap_admin():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return err("invalid_param", "email is required")
    try:
        user = _auth().bootstrap_admin(email)
        token_id, raw_token = _auth().create_session(
            email,
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )
        return ok(
            session={"token_id": token_id, "bearer": raw_token},
            user=user,
        )
    except PermissionError as e:
        return err("bootstrap_forbidden", str(e), 403)
    except Exception as e:
        return err("internal_error", str(e), 500)

@app.post("/api/auth/dev/login")
def dev_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return err("invalid_param", "email is required")
    user = _auth().check_membership(email)
    if not user:
        return err("auth_denied", "Email not in allowlist or account disabled", 403)
    token_id, raw_token = _auth().create_session(
        email,
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    return ok(session={"token_id": token_id, "bearer": raw_token}, user=user)

@app.get("/api/auth/google/status")
def google_status():
    client_id = os.environ.get("YOTU_GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID")
    redirect_uri = (
        os.environ.get("YOTU_GOOGLE_REDIRECT_URI")
        or os.environ.get("GOOGLE_REDIRECT_URI")
        or f"{request.host_url.rstrip('/')}api/auth/google/callback"
    )
    return ok(configured=bool(client_id), redirect_uri=redirect_uri)

@app.get("/api/auth/google/start")
def google_start():
    client_id = os.environ.get("YOTU_GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("YOTU_GOOGLE_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return err("oauth_not_configured", "Google OAuth credentials not set in environment", 503)

    redirect_uri = (
        os.environ.get("YOTU_GOOGLE_REDIRECT_URI")
        or os.environ.get("GOOGLE_REDIRECT_URI")
        or f"{request.host_url.rstrip('/')}api/auth/google/callback"
    )
    state = secrets.token_urlsafe(32)
    _auth().store_oauth_state(state)

    params = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        f"&state={state}"
        "&access_type=offline"
    )
    return ok(auth_url=params, state=state)

@app.get("/api/auth/google/callback")
def google_callback():
    import urllib.parse, urllib.request, json as _json
    state = request.args.get("state", "")
    code = request.args.get("code", "")

    if not _auth().validate_oauth_state(state):
        return err("invalid_state", "OAuth state expired or invalid", 400)

    client_id = os.environ.get("YOTU_GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("YOTU_GOOGLE_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = (
        os.environ.get("YOTU_GOOGLE_REDIRECT_URI")
        or os.environ.get("GOOGLE_REDIRECT_URI")
        or f"{request.host_url.rstrip('/')}api/auth/google/callback"
    )

    # Exchange code for token
    try:
        token_data = urllib.parse.urlencode({
            "code": code, "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        }).encode()
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_resp = _json.loads(resp.read().decode())
    except Exception as e:
        return err("oauth_exchange_failed", str(e), 502)

    id_token_str = token_resp.get("id_token", "")
    if not id_token_str:
        return err("oauth_exchange_failed", "No id_token in Google response", 502)

    # Decode JWT payload (no verification needed — Google signed it, we just read claims)
    try:
        import base64
        parts = id_token_str.split(".")
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        claims = _json.loads(base64.urlsafe_b64decode(padded).decode())
        email = claims.get("email", "").lower()
        name = claims.get("name", "")
        picture = claims.get("picture", "")
    except Exception as e:
        return err("oauth_exchange_failed", f"JWT decode failed: {e}", 502)

    # Allowlist check
    user = _auth().check_membership(email)
    if not user:
        return err("auth_denied", "Google email is not allowlisted or account is disabled", 403)

    token_id, raw_token = _auth().create_session(
        email,
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    identity = {"email": email, "name": name, "picture": picture}
    return ok(session={"token_id": token_id, "bearer": raw_token}, user=user, identity=identity)

@app.get("/api/auth/session")
def get_session():
    e = require_auth()
    if e:
        return e
    return ok(session=g.session, user=g.user)

@app.post("/api/auth/logout")
def logout():
    e = require_auth()
    if e:
        return e
    reason = request.args.get("reason") or (request.get_json(silent=True) or {}).get("reason")
    _auth().revoke_session(g.session["token_id"], revoked_by="user", reason=reason)
    return ok(revoked=True)

# ===========================================================================
# ME — Sessions
# ===========================================================================
@app.get("/api/me/sessions")
def me_sessions():
    e = require_auth()
    if e:
        return e
    limit, offset, perr = _paginate()
    if perr:
        return perr
    include_revoked = request.args.get("include_revoked", "false").lower() == "true"
    revoked_by = request.args.get("revoked_by")
    revoke_reason = request.args.get("revoke_reason")
    sessions = _auth().list_sessions(
        email=g.user["email"],
        include_revoked=include_revoked,
        revoked_by=revoked_by,
        revoke_reason=revoke_reason,
        limit=limit,
        offset=offset,
    )
    # Mark the current session
    current_id = g.session["token_id"]
    for s in sessions:
        s["is_current"] = (s.get("token_id") == current_id)
    return ok(sessions=sessions)

@app.delete("/api/me/sessions")
def me_revoke_all_sessions():
    e = require_auth()
    if e:
        return e
    keep_current = request.args.get("keep_current", "true").lower() != "false"
    reason = request.args.get("reason")
    keep_id = g.session["token_id"] if keep_current else None
    count = _auth().revoke_sessions_for_user(
        g.user["email"],
        keep_current_id=keep_id,
        revoked_by="user",
        reason=reason,
    )
    return ok(revoked_count=count)

@app.delete("/api/me/sessions/<token_id>")
def me_revoke_session(token_id):
    e = require_auth()
    if e:
        return e
    reason = request.args.get("reason")
    # Verify ownership
    sessions = _auth().list_sessions(email=g.user["email"], include_revoked=True)
    if not any(s["token_id"] == token_id for s in sessions):
        return err("not_found", "Session not found or not yours", 404)
    _auth().revoke_session(token_id, revoked_by="user", reason=reason)
    return ok(revoked=True)

# ===========================================================================
# ME — Files
# ===========================================================================
@app.get("/api/me/files")
def me_files():
    e = require_auth()
    if e:
        return e
    include_legacy = request.args.get("include_legacy", "false").lower() == "true"
    files = _engine().list_files(owner_email=g.user["email"], include_legacy=include_legacy)
    return ok(files=files, total=len(files))

@app.delete("/api/me/files/<file_id>")
def me_delete_file(file_id):
    e = require_auth()
    if e:
        return e
    try:
        _engine().delete_file(file_id, requester_email=g.user["email"],
                              is_admin=g.user.get("role") == "admin")
        return ok(deleted=True)
    except KeyError:
        return err("not_found", "File not found", 404)
    except PermissionError as ex:
        return err("forbidden", str(ex), 403)

@app.post("/api/me/files/<file_id>/attach")
def me_attach_file(file_id):
    e = require_auth()
    if e:
        return e
    data = request.get_json(silent=True) or {}
    video_id = data.get("video_id", "").strip()
    if not video_id:
        return err("invalid_param", "video_id is required")
    entry = _engine().get_file(file_id)
    if not entry:
        return err("not_found", "File not found", 404)
    owner = entry.get("owner_email")
    if owner and owner != g.user["email"] and g.user.get("role") != "admin":
        return err("forbidden", "You do not own this file", 403)
    updated = _engine().attach_video_reference(
        file_id, video_id, video_url=data.get("video_url"), owner_email=g.user["email"]
    )
    return ok(file=updated)

# ===========================================================================
# ME — Jobs
# ===========================================================================
@app.get("/api/me/jobs")
def me_jobs():
    e = require_auth()
    if e:
        return e
    limit, offset, perr = _paginate()
    if perr:
        return perr
    status_raw = request.args.get("status", "")
    status_filter = [s.strip() for s in status_raw.split(",") if s.strip()] or None
    include_public = request.args.get("include_public", "false").lower() == "true"
    jobs, total = _jobs().list_jobs(
        owner_email=g.user["email"],
        status_filter=status_filter,
        include_public=include_public,
        limit=limit,
        offset=offset,
    )
    return ok(jobs=jobs, total=total)

@app.post("/api/me/jobs/clear")
def me_clear_jobs():
    e = require_auth()
    if e:
        return e
    _jobs().clear_completed_jobs(g.user["email"])
    return ok(message="Completed jobs cleared")


@app.get("/api/me/jobs/<job_id>")
def me_get_job(job_id):
    e = require_auth()
    if e:
        return e
    job = _jobs().get_job(job_id)
    if not job:
        return err("not_found", "Job not found", 404)
    if job.get("owner_email") != g.user["email"] and g.user.get("role") != "admin":
        return err("not_found", "Job not found", 404)
    return ok(job=job)

# ===========================================================================
# ADMIN — Users
# ===========================================================================
@app.get("/api/admin/users")
def admin_list_users():
    e = require_admin()
    if e:
        return e
    users = _auth().list_users()
    active = _auth().active_user_count()
    cap = _settings().get("user_cap", 25)
    return ok(users=users, active_count=active, cap=cap)

@app.post("/api/admin/users")
def admin_add_user():
    e = require_admin()
    if e:
        return e
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return err("invalid_param", "email is required")
    role = data.get("role", "member")
    enabled = bool(data.get("enabled", True))
    try:
        user = _auth().add_user(email, role=role, enabled=enabled)
        return ok(user=user), 201
    except ValueError as ex:
        return err("conflict", str(ex), 409)
    except PermissionError as ex:
        return err("cap_exceeded", str(ex), 403)

@app.patch("/api/admin/users/<email>")
def admin_patch_user(email):
    e = require_admin()
    if e:
        return e
    data = request.get_json(silent=True) or {}
    if "enabled" not in data:
        return err("invalid_param", "enabled field is required")
    try:
        user = _auth().patch_user(email.lower(), enabled=bool(data["enabled"]))
        return ok(user=user)
    except KeyError as ex:
        return err("not_found", str(ex), 404)

# ===========================================================================
# ADMIN — Sessions
# ===========================================================================
@app.get("/api/admin/sessions")
def admin_sessions():
    e = require_admin()
    if e:
        return e
    limit, offset, perr = _paginate()
    if perr:
        return perr
    email = request.args.get("email")
    include_revoked = request.args.get("include_revoked", "false").lower() == "true"
    revoked_by = request.args.get("revoked_by")
    revoke_reason = request.args.get("revoke_reason")
    sessions = _auth().list_sessions(
        email=email,
        include_revoked=include_revoked,
        revoked_by=revoked_by,
        revoke_reason=revoke_reason,
        limit=limit,
        offset=offset,
    )
    return ok(sessions=sessions)

@app.delete("/api/admin/sessions")
def admin_revoke_user_sessions():
    e = require_admin()
    if e:
        return e
    email = request.args.get("email", "").strip().lower()
    if not email:
        return err("invalid_param", "email query param is required")
    reason = request.args.get("reason")
    count = _auth().revoke_sessions_for_user(email, revoked_by="admin", reason=reason)
    return ok(revoked_count=count)

@app.delete("/api/admin/sessions/<token_id>")
def admin_revoke_session(token_id):
    e = require_admin()
    if e:
        return e
    reason = request.args.get("reason")
    try:
        _auth().revoke_session(token_id, revoked_by="admin", reason=reason)
        return ok(revoked=True)
    except KeyError as ex:
        return err("not_found", str(ex), 404)

# ===========================================================================
# ADMIN — Jobs
# ===========================================================================
@app.get("/api/admin/jobs")
def admin_list_jobs():
    e = require_admin()
    if e:
        return e
    limit, offset, perr = _paginate()
    if perr:
        return perr
    status_raw = request.args.get("status", "")
    status_filter = [s.strip() for s in status_raw.split(",") if s.strip()] or None
    owner_email = request.args.get("owner_email")
    include_public = request.args.get("include_public", "true").lower() == "true"
    jobs, total = _jobs().list_jobs(
        owner_email=owner_email,
        status_filter=status_filter,
        include_public=include_public,
        limit=limit,
        offset=offset,
    )
    return ok(jobs=jobs, total=total)

@app.get("/api/admin/jobs/<job_id>")
def admin_get_job(job_id):
    e = require_admin()
    if e:
        return e
    job = _jobs().get_job(job_id)
    if not job:
        return err("not_found", "Job not found", 404)
    return ok(job=job)

@app.delete("/api/admin/jobs/<job_id>")
def admin_delete_job(job_id):
    e = require_admin()
    if e:
        return e
    job = _jobs().get_job(job_id)
    if not job:
        return err("not_found", "Job not found", 404)
    _jobs().delete_job(job_id)
    return ok(deleted=True)

# ===========================================================================
# ADMIN — Metrics
# ===========================================================================
@app.get("/api/admin/metrics")
def admin_metrics():
    e = require_admin()
    if e:
        return e
    user_m = _auth().metrics()
    job_m = _jobs().metrics()
    file_m = _engine().file_metrics()
    return ok(
        users={"total": user_m["total"], "active": user_m["active"], "cap": user_m["cap"]},
        sessions=user_m["sessions"],
        jobs=job_m,
        files=file_m,
    )

@app.get("/api/admin/system/logs")
def admin_system_logs():
    e = require_admin()
    if e:
        return e
    
    from src.logger import get_log_file_path
    log_path = get_log_file_path()
    
    if not os.path.exists(log_path):
        return ok(logs=[], message="Log file not found yet.")
    
    try:
        # Get last 200 lines
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            logs = lines[-200:] if len(lines) > 200 else lines
            return ok(logs=[line.strip() for line in logs])
    except Exception as ex:
        return err("internal_error", f"Failed to read logs: {ex}", 500)

@app.post("/api/storage/upload")
def upload_file():
    optional_auth()
    if 'file' not in request.files:
        return err("invalid_param", "No file part in the request")
    file = request.files['file']
    if file.filename == '':
        return err("invalid_param", "No selected file")
    
    import uuid
    from werkzeug.utils import secure_filename
    ext = os.path.splitext(file.filename)[1]
    filename = secure_filename(f"{uuid.uuid4().hex}{ext}")

    if os.environ.get("SUPABASE_URL"):
        from src.supabase_store import get_supabase_client
        supabase = get_supabase_client()
        content = file.read()
        supabase.storage.from_("yotudrive-archives").upload(filename, content)
        return ok(
            path=filename,
            filename=file.filename,
            size=len(content),
            storage="supabase"
        ), 201

    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    
    return ok(
        path=os.path.abspath(path),
        filename=file.filename,
        size=os.path.getsize(path)
    ), 201

# ===========================================================================
# FILES (public/optional-auth)
# ===========================================================================
@app.get("/api/files")
def list_files():
    optional_auth()
    files = _engine().list_files()
    return ok(files=files, total=len(files))

@app.delete("/api/files/<file_id>")
def delete_file(file_id):
    optional_auth()
    user = g.user
    try:
        _engine().delete_file(
            file_id,
            requester_email=user["email"] if user else None,
            is_admin=user.get("role") == "admin" if user else False,
        )
        return ok(deleted=True)
    except KeyError:
        return err("not_found", "File not found", 404)
    except PermissionError as ex:
        return err("forbidden", str(ex), 403)

@app.post("/api/files/<file_id>/attach")
def attach_file(file_id):
    optional_auth()
    data = request.get_json(silent=True) or {}
    video_id = data.get("video_id", "").strip()
    if not video_id:
        return err("invalid_param", "video_id is required")
    entry = _engine().get_file(file_id)
    if not entry:
        return err("not_found", "File not found", 404)
    user = g.user
    owner = entry.get("owner_email")
    if owner and user and owner != user["email"] and user.get("role") != "admin":
        return err("forbidden", "You do not own this file", 403)
    updated = _engine().attach_video_reference(
        file_id, video_id,
        video_url=data.get("video_url"),
        owner_email=user["email"] if user else None,
    )
    return ok(file=updated)

@app.post("/api/upload/manual/register")
def manual_register():
    optional_auth()
    data = request.get_json(silent=True) or {}
    file_name = (data.get("file_name") or data.get("filename") or "").strip()
    video_id = (data.get("video_id") or "").strip()
    if not file_name or not video_id:
        return err("invalid_param", "file_name and video_id are required")
    file_size = int(data.get("file_size", 0))
    user = g.user
    file_id = _engine().register_file(
        file_name, video_id, file_size,
        metadata=data.get("metadata"),
        owner_email=user["email"] if user else None,
    )
    return ok(file_id=file_id), 201

# ===========================================================================
# SETTINGS
# ===========================================================================
@app.get("/api/settings")
def get_settings_route():
    return ok(settings=_settings().as_dict())

@app.put("/api/settings")
def put_settings():
    data = request.get_json(silent=True) or {}
    if not data:
        return err("invalid_param", "No settings provided")
    try:
        _settings().merge(data)
    except Exception as e:
        return err("invalid_param", str(e))
    return ok(settings=_settings().as_dict())

# ===========================================================================
# VERIFY & TOOLS
# ===========================================================================
@app.post("/api/verify")
def verify():
    data = request.get_json(silent=True) or {}
    video_path = (data.get("video_path") or "").strip()
    if not video_path:
        return err("invalid_param", "video_path is required")
    max_frames = data.get("max_frames", 10)
    try:
        max_frames = int(max_frames)
        if max_frames < 1:
            raise ValueError
    except (ValueError, TypeError):
        return err("invalid_param", "max_frames must be an integer >= 1")
    if not os.path.exists(video_path):
        return err("not_found", f"File not found: {video_path}", 404)
    try:
        report = _engine().verify_video(video_path, max_frames=max_frames)
        return ok(**report)
    except Exception as e:
        return err("verify_failed", str(e), 422)

@app.post("/api/tools/auto-join")
def auto_join():
    optional_auth()
    data = request.get_json(silent=True) or {}
    file_list = data.get("file_list", [])
    if not isinstance(file_list, list) or not file_list:
        return err("invalid_param", "file_list must be a non-empty array of paths")
    auto_cleanup = bool(data.get("auto_cleanup", True))
    try:
        result = _engine().auto_join(file_list, auto_cleanup=auto_cleanup)
        return ok(result_files=result)
    except Exception as e:
        return err("join_failed", str(e), 422)

@app.post("/api/youtube/playlist/inspect")
def playlist_inspect():
    data = request.get_json(silent=True) or {}
    playlist_url = (data.get("playlist_url") or "").strip()
    if not playlist_url:
        return err("invalid_param", "playlist_url is required")
    try:
        videos = _engine().inspect_playlist(playlist_url)
        return ok(videos=videos, count=len(videos))
    except Exception as e:
        return err("inspect_failed", str(e), 422)

# ===========================================================================
# ASYNC JOBS — polling
# ===========================================================================
@app.get("/api/jobs/<job_id>")
def get_job(job_id):
    optional_auth()
    job = _jobs().get_job(job_id)
    if not job:
        return err("not_found", "Job not found", 404)
    return ok(job=job)

@app.post("/api/jobs/<job_id>/cancel")
def cancel_job(job_id):
    optional_auth()
    job = _jobs().get_job(job_id)
    if not job:
        return err("not_found", "Job not found", 404)
    
    # Ownership check
    if g.user:
        if job.get("owner_email") != g.user["email"]:
            return err("forbidden", "You do not own this job", 403)
            
    success = _jobs().cancel_job(job_id)
    if success:
        return ok(message="Cancellation signal sent")
    else:
        return err("invalid_state", "Job is not running or already completed")

@app.patch("/api/jobs/<job_id>/claim")
def claim_job_api(job_id):
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id", "unnamed-worker")
    success = _jobs().claim_job(job_id, worker_id)
    if success:
        return ok(message=f"Job {job_id} claimed by {worker_id}")
    return err("conflict", "Job already claimed or not eligible for remote worker", 409)

@app.post("/api/jobs/<job_id>/update")
def update_job_api(job_id):
    # For now, permissive. In production, check worker_id or secret.
    data = request.get_json(silent=True) or {}
    success = _jobs().update_job(job_id, **data)
    if success:
        return ok(message="Job updated")
    return err("not_found", "Job not found", 404)

# ===========================================================================
# ENCODE / DECODE (raw)
# ===========================================================================
@app.post("/api/encode/start")
def encode_start():
    optional_auth()
    data = request.get_json(silent=True) or {}
    input_file = (data.get("input_file") or "").strip()
    output_dir = (data.get("output_dir") or "").strip()
    if not input_file or not output_dir:
        return err("invalid_param", "input_file and output_dir are required")
    if not os.path.exists(input_file):
        return err("not_found", f"input_file not found: {input_file}", 404)

    s = _settings()
    password = data.get("password")
    block_size = int(data.get("block_size", s.get("block_size", 2)))
    ecc_bytes = int(data.get("ecc_bytes", s.get("ecc_bytes", 32)))
    threads = int(data.get("threads", s.get("threads", 4)))

    owner = g.user["email"] if g.user else None
    managed = bool(data.get("managed", False))
    job = _jobs().create_job("encode", owner_email=owner, managed=managed)

    if managed:
        return ok(job_id=job["id"], managed=True), 202

    cancel = threading.Event()

    def run():
        _engine().encode_file(
            input_file, output_dir,
            password=password, block_size=block_size,
            ecc_bytes=ecc_bytes, threads=threads,
            progress_cb=_jobs().make_progress_callback(job["id"], "Encoding "),
            check_cancel=_jobs().make_cancel_check(cancel),
        )
        return {"frames_dir": output_dir}

    _jobs().submit(run, job["id"], cancel_event=cancel)
    return ok(job_id=job["id"]), 202

@app.post("/api/decode/start")
def decode_start():
    optional_auth()
    data = request.get_json(silent=True) or {}
    frames_dir = (data.get("frames_dir") or "").strip()
    output_path = (data.get("output_path") or "").strip()
    if not frames_dir or not output_path:
        return err("invalid_param", "frames_dir and output_path are required")
    if not os.path.exists(frames_dir):
        return err("not_found", f"frames_dir not found: {frames_dir}", 404)

    password = data.get("password")
    threads = int(data.get("threads", _settings().get("threads", 4)))
    owner = g.user["email"] if g.user else None
    job = _jobs().create_job("decode", owner_email=owner)
    cancel = threading.Event()

    def run():
        out = _engine().decode_source(
            frames_dir, output_path,
            password=password, threads=threads,
            progress_cb=_jobs().make_progress_callback(job["id"], "Decoding "),
            check_cancel=_jobs().make_cancel_check(cancel),
        )
        return {"output_path": out}

    _jobs().submit(run, job["id"], cancel_event=cancel)
    return ok(job_id=job["id"]), 202

# ===========================================================================
# PIPELINE — full encode + stitch
# ===========================================================================
@app.post("/api/pipeline/encode-video/start")
def pipeline_encode():
    optional_auth()
    data = request.get_json(silent=True) or {}
    input_file = (data.get("input_file") or "").strip()
    output_video = (data.get("output_video") or "").strip()
    if not input_file or not output_video:
        return err("invalid_param", "input_file and output_video are required")
    if not os.path.exists(input_file):
        return err("not_found", f"input_file not found: {input_file}", 404)

    s = _settings()
    password = data.get("password")
    overrides = data.get("overrides", {})
    block_size = int(overrides.get("block_size", s.get("block_size", 2)))
    ecc_bytes = int(overrides.get("ecc_bytes", s.get("ecc_bytes", 32)))
    threads = int(overrides.get("threads", s.get("threads", 4)))
    encoder = overrides.get("encoder", s.get("encoder", "libx264"))
    verify_roundtrip = bool(data.get("verify_roundtrip", False))
    register_in_db = bool(data.get("register_in_db", False))

    owner = g.user["email"] if g.user else None
    managed = bool(data.get("managed", False))
    job = _jobs().create_job("pipeline_encode", owner_email=owner, managed=managed)
    job_id = job["id"]

    if managed:
        return ok(job_id=job_id, managed=True), 202

    cancel = threading.Event()

    def run():
        import tempfile, os as _os
        frames_dir = _os.path.join(
            _os.path.dirname(output_video),
            f"_frames_{job_id[:8]}"
        )
        def stitch_cb(pct):
            # Scale 0-100% of stitching to 70-100% of total pipeline
            total_pct = 70 + (pct * 0.3)
            _jobs().update_job(job_id, progress=int(total_pct), message=f"Stitching {int(pct)}%")

        _engine().encode_file(
            input_file, frames_dir,
            password=password, block_size=block_size,
            ecc_bytes=ecc_bytes, threads=threads,
            progress_cb=_jobs().make_progress_callback(job_id, "Encoding "),
            check_cancel=_jobs().make_cancel_check(cancel),
        )
        _engine().stitch_frames(frames_dir, output_video, encoder=encoder,
                                progress_cb=stitch_cb,
                                check_cancel=_jobs().make_cancel_check(cancel))
        # Cleanup frames
        import shutil
        try: shutil.rmtree(frames_dir)
        except Exception: pass

        file_id = None
        if register_in_db:
            file_id = _engine().register_file(
                _os.path.basename(input_file),
                "pending",
                _os.path.getsize(input_file),
                owner_email=owner,
            )
        return {"output_video": output_video, "file_id": file_id}

    _jobs().submit(run, job_id, cancel_event=cancel)
    return ok(job_id=job_id), 202

@app.post("/api/pipeline/decode-video/start")
def pipeline_decode():
    optional_auth()
    data = request.get_json(silent=True) or {}
    video_path = (data.get("video_path") or "").strip()
    output_file = (data.get("output_file") or "").strip()
    if not video_path or not output_file:
        return err("invalid_param", "video_path and output_file are required")
    if not os.path.exists(video_path):
        return err("not_found", f"video_path not found: {video_path}", 404)

    password = data.get("password")
    overrides = data.get("overrides", {})
    threads = int(overrides.get("threads", _settings().get("threads", 4)))
    owner = g.user["email"] if g.user else None
    job = _jobs().create_job("pipeline_decode", owner_email=owner)
    cancel = threading.Event()
    job_id = job["id"]

    def run():
        import tempfile, os as _os, shutil
        frames_dir = _os.path.join(
            _os.path.dirname(output_file) or ".",
            f"_frames_{job_id[:8]}"
        )
        _engine().extract_from_video(video_path, frames_dir,
                                     check_cancel=_jobs().make_cancel_check(cancel))
        _jobs().update_job(job_id, progress=50, message="Decoding frames…")
        out = _engine().decode_source(
            frames_dir, output_file,
            password=password, threads=threads,
            progress_cb=_jobs().make_progress_callback(job_id, "Decoding "),
            check_cancel=_jobs().make_cancel_check(cancel),
        )
        try: shutil.rmtree(frames_dir)
        except Exception: pass
        return {"output_file": out}

    _jobs().submit(run, job_id, cancel_event=cancel)
    return ok(job_id=job_id), 202

# ===========================================================================
# OAUTH UPLOAD
# ===========================================================================
@app.post("/api/upload/oauth/start")
def oauth_upload_start():
    e = require_auth()
    if e:
        return e
    data = request.get_json(silent=True) or {}
    file_path = (data.get("file_path") or "").strip()
    title = (data.get("title") or "").strip()
    if not file_path or not title:
        return err("invalid_param", "file_path and title are required")
    if not os.path.exists(file_path):
        return err("not_found", f"file_path not found: {file_path}", 404)

    description = data.get("description", "")
    privacy_status = data.get("privacy_status", "unlisted")
    file_id = data.get("file_id")

    job = _jobs().create_job("oauth_upload", owner_email=g.user["email"])
    job_id = job["id"]

    def run():
        # Requires google-api-python-client + saved OAuth credentials
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.oauth2.credentials import Credentials
            import json as _json

            creds_file = os.environ.get("YOUTUBE_OAUTH_CREDS", "youtube_oauth.json")
            if not os.path.exists(creds_file):
                raise FileNotFoundError(
                    f"YouTube OAuth credentials not found at {creds_file}. "
                    "Run the OAuth flow once to generate this file."
                )
            with open(creds_file) as f:
                creds_data = _json.load(f)
            creds = Credentials(**creds_data)
            youtube = build("youtube", "v3", credentials=creds)

            media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
            request_obj = youtube.videos().insert(
                part="snippet,status",
                body={
                    "snippet": {"title": title, "description": description},
                    "status": {"privacyStatus": privacy_status},
                },
                media_body=media,
            )
            response = None
            while response is None:
                _, response = request_obj.next_chunk()
            video_id = response.get("id", "")
            if file_id:
                _engine().attach_video_reference(file_id, video_id,
                                                  owner_email=g.user["email"])
            return {"video_id": video_id, "file_id": file_id}
        except ImportError:
            raise RuntimeError(
                "google-api-python-client not installed. Run: pip install google-api-python-client"
            )

    _jobs().submit(run, job_id)
    return ok(job_id=job_id), 202

# ===========================================================================
# Static web app (serves Next.js build if present)
# ===========================================================================
WEB_OUT = os.path.join(os.path.dirname(__file__), "web", "out")

if os.path.exists(WEB_OUT):
    from flask import send_from_directory

    @app.get("/")
    @app.get("/<path:subpath>")
    def serve_web(subpath="index.html"):
        if subpath.startswith("api/"):
            return err("not_found", "API route not found", 404)
        target = os.path.join(WEB_OUT, subpath)
        if os.path.isdir(target):
            target = os.path.join(target, "index.html")
            subpath = os.path.join(subpath, "index.html")
        if os.path.exists(target):
            return send_from_directory(WEB_OUT, subpath)
        return send_from_directory(WEB_OUT, "index.html")

# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    flask_env = os.environ.get("FLASK_ENV", "development")
    print(f"YotuDrive API v{VERSION} — {flask_env} mode — http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
