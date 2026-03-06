import os
import json
import uuid
import time
from typing import Optional, Callable
import psycopg2
from psycopg2.extras import RealDictCursor
import threading

def get_pg_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def init_db():
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            # Users
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    email VARCHAR(255) PRIMARY KEY,
                    role VARCHAR(50) DEFAULT 'member',
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at FLOAT
                )
            """)
            # Sessions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token_id VARCHAR(255) PRIMARY KEY,
                    token_hash VARCHAR(255) UNIQUE,
                    user_email VARCHAR(255) REFERENCES users(email),
                    created_at FLOAT,
                    last_seen_at FLOAT,
                    created_from_ip VARCHAR(255),
                    user_agent TEXT,
                    revoked_by VARCHAR(255),
                    revoke_reason TEXT
                )
            """)
            # Jobs
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id VARCHAR(255) PRIMARY KEY,
                    kind VARCHAR(50),
                    status VARCHAR(50),
                    progress INT DEFAULT 0,
                    message TEXT,
                    result JSONB,
                    error TEXT,
                    owner_email VARCHAR(255),
                    public BOOLEAN DEFAULT FALSE,
                    created_at FLOAT,
                    updated_at FLOAT
                )
            """)
            # Files
            cur.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id VARCHAR(255) PRIMARY KEY,
                    file_name TEXT,
                    video_id VARCHAR(255),
                    file_size BIGINT,
                    upload_date FLOAT,
                    metadata JSONB,
                    owner_email VARCHAR(255)
                )
            """)
        conn.commit()
    finally:
        conn.close()

# ------------------------------------------------------------------
# PG Auth Store
# ------------------------------------------------------------------
class PGAuthStore:
    def __init__(self):
        self._oauth_states: dict = {}
        init_db()

    def _get_user_cap(self) -> int:
        try:
            from src.settings import get_settings
            return get_settings().get("user_cap", 25)
        except Exception:
            return 25
            
    def _hash_token(self, raw_token: str) -> str:
        import hashlib
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def bootstrap_admin(self, email: str) -> dict:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as c FROM users")
                if cur.fetchone()["c"] > 0:
                    raise PermissionError("bootstrap_admin can only be called on an empty user store")
                user = {
                    "email": email, "role": "admin", 
                    "enabled": True, "created_at": time.time()
                }
                cur.execute(
                    "INSERT INTO users (email, role, enabled, created_at) VALUES (%s, %s, %s, %s)",
                    (email, user["role"], user["enabled"], user["created_at"])
                )
            conn.commit()
            return user
        finally:
            conn.close()

    def add_user(self, email: str, role: str = "member", enabled: bool = True) -> dict:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as c FROM users WHERE enabled = TRUE")
                if cur.fetchone()["c"] >= self._get_user_cap():
                    raise PermissionError(f"User cap of {self._get_user_cap()} reached")
                
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    raise ValueError(f"User {email!r} already exists")
                    
                user = {
                    "email": email, "role": role if role in ("admin", "member") else "member",
                    "enabled": enabled, "created_at": time.time()
                }
                cur.execute(
                    "INSERT INTO users (email, role, enabled, created_at) VALUES (%s, %s, %s, %s)",
                    (email, user["role"], user["enabled"], user["created_at"])
                )
            conn.commit()
            return user
        finally:
            conn.close()

    def patch_user(self, email: str, enabled: bool) -> dict:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET enabled = %s WHERE email = %s RETURNING *", (enabled, email))
                row = cur.fetchone()
                if not row:
                    raise KeyError(f"User {email!r} not found")
            conn.commit()
            return dict(row)
        finally:
            conn.close()

    def get_user(self, email: str) -> Optional[dict]:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def check_membership(self, email: str) -> Optional[dict]:
        u = self.get_user(email)
        return u if u and u.get("enabled") else None

    def list_users(self) -> list:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users ORDER BY created_at DESC")
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def active_user_count(self) -> int:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as c FROM users WHERE enabled = TRUE")
                return cur.fetchone()["c"]
        finally:
            conn.close()

    def create_session(self, email: str, ip: str = None, user_agent: str = None) -> tuple:
        import secrets, uuid
        token_id = str(uuid.uuid4())
        raw_token = secrets.token_urlsafe(48)
        token_hash = self._hash_token(raw_token)
        now = time.time()
        
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sessions (token_id, token_hash, user_email, created_at, last_seen_at, created_from_ip, user_agent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (token_id, token_hash, email, now, now, ip, user_agent))
            conn.commit()
            return token_id, raw_token
        finally:
            conn.close()

    def validate_token(self, raw_token: str) -> tuple:
        token_hash = self._hash_token(raw_token)
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sessions WHERE token_hash = %s", (token_hash,))
                sess = cur.fetchone()
                if not sess:
                    raise ValueError("Invalid token")
                if sess.get("revoked_by") is not None:
                    raise ValueError("Token has been revoked")
                
                cur.execute("SELECT * FROM users WHERE email = %s", (sess["user_email"],))
                user = cur.fetchone()
                if not user or not user.get("enabled"):
                    raise ValueError("User not found or disabled")
                
                cur.execute("UPDATE sessions SET last_seen_at = %s WHERE token_id = %s", (time.time(), sess["token_id"]))
                conn.commit()
                return dict(sess), dict(user)
        finally:
            conn.close()

    def revoke_session(self, token_id: str, revoked_by: str = "user", reason: str = None):
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE sessions SET revoked_by = %s, revoke_reason = %s WHERE token_id = %s", (revoked_by, reason, token_id))
                if cur.rowcount == 0:
                    raise KeyError(f"Session {token_id!r} not found")
            conn.commit()
        finally:
            conn.close()

    def revoke_sessions_for_user(self, email: str, keep_current_id: str = None,
                                  revoked_by: str = "user", reason: str = None) -> int:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                q = "UPDATE sessions SET revoked_by = %s, revoke_reason = %s WHERE user_email = %s AND revoked_by IS NULL"
                params = [revoked_by, reason, email]
                if keep_current_id:
                    q += " AND token_id != %s"
                    params.append(keep_current_id)
                cur.execute(q, params)
                c = cur.rowcount
            conn.commit()
            return c
        finally:
            conn.close()

    def list_sessions(self, email: str = None, include_revoked: bool = False,
                      revoked_by: str = None, revoke_reason: str = None,
                      limit: int = 50, offset: int = 0) -> list:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                q = "SELECT * FROM sessions WHERE 1=1"
                params = []
                if email:
                    q += " AND user_email = %s"; params.append(email)
                if not include_revoked:
                    q += " AND revoked_by IS NULL"
                if revoked_by:
                    q += " AND revoked_by = %s"; params.append(revoked_by)
                if revoke_reason:
                    q += " AND revoke_reason = %s"; params.append(revoke_reason)
                
                q += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(q, params)
                rows = cur.fetchall()
                for r in rows:
                    r.pop("token_hash", None)
                return [dict(r) for r in rows]
        finally:
            conn.close()

    def store_oauth_state(self, state: str, ttl_seconds: int = 600):
        self._oauth_states[state] = {"expiry": time.time() + ttl_seconds}

    def validate_oauth_state(self, state: str) -> bool:
        entry = self._oauth_states.pop(state, None)
        return False if not entry else entry["expiry"] > time.time()

    def metrics(self) -> dict:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as t, SUM(CASE WHEN enabled THEN 1 ELSE 0 END) as a FROM users")
                u = cur.fetchone()
                
                cur.execute("SELECT COUNT(*) as t, SUM(CASE WHEN revoked_by IS NULL THEN 1 ELSE 0 END) as a, SUM(CASE WHEN revoked_by IS NOT NULL THEN 1 ELSE 0 END) as r FROM sessions")
                s = cur.fetchone()
                
            return {
                "total": u["t"] or 0, "active": u["a"] or 0, "cap": self._get_user_cap(),
                "sessions": {
                    "total": s["t"] or 0, "active": s["a"] or 0, "revoked": s["r"] or 0,
                }
            }
        finally:
            conn.close()

# ------------------------------------------------------------------
# PG Job Store
# ------------------------------------------------------------------
class PGJobStore:
    def __init__(self, max_workers: int = 4):
        from concurrent.futures import ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="yotu-job")
        init_db()

    def create_job(self, kind: str, owner_email: str = None, public: bool = False) -> dict:
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id, "kind": kind, "status": "pending", "progress": 0,
            "message": "", "result": None, "error": None, "owner_email": owner_email,
            "public": public, "created_at": time.time(), "updated_at": time.time()
        }
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO jobs (id, kind, status, progress, message, owner_email, public, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (job["id"], job["kind"], job["status"], job["progress"], job["message"],
                     job["owner_email"], job["public"], job["created_at"], job["updated_at"])
                )
            conn.commit()
            return job
        finally:
            conn.close()

    def update_job(self, job_id: str, **kwargs):
        allowed = {"status", "progress", "message", "result", "error"}
        updates = []
        params = []
        for k, v in kwargs.items():
            if k in allowed:
                updates.append(f"{k} = %s")
                params.append(json.dumps(v) if k == "result" else v)
        
        if not updates:
            return
            
        updates.append("updated_at = %s")
        params.extend([time.time(), job_id])
        
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = %s", params)
            conn.commit()
        finally:
            conn.close()

    def get_job(self, job_id: str) -> Optional[dict]:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def delete_job(self, job_id: str):
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
            conn.commit()
        finally:
            conn.close()

    def list_jobs(self, owner_email: str = None, status_filter: list = None,
                  include_public: bool = False, limit: int = 50, offset: int = 0) -> tuple:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                q = "SELECT * FROM jobs WHERE 1=1"
                params = []
                
                if owner_email:
                    if include_public:
                        q += " AND (owner_email = %s OR public = TRUE)"; params.append(owner_email)
                    else:
                        q += " AND owner_email = %s"; params.append(owner_email)
                if status_filter:
                    q += " AND status = ANY(%s)"; params.append(status_filter)
                
                cur.execute(q.replace("SELECT *", "SELECT COUNT(*) as c"), params)
                total = cur.fetchone()["c"]
                
                q += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(q, params)
                return [dict(r) for r in cur.fetchall()], total
        finally:
            conn.close()

    def submit(self, fn: Callable, job_id: str, *args, **kwargs):
        self.update_job(job_id, status="running", message="Starting…")
        def wrapper():
            try:
                result = fn(*args, **kwargs)
                self.update_job(job_id, status="done", progress=100, message="Completed", result=result)
            except Exception as e:
                self.update_job(job_id, status="failed", message=str(e), error=str(e))
        self._executor.submit(wrapper)

    def make_progress_callback(self, job_id: str, message_prefix: str = "") -> Callable:
        def cb(pct):
            msg = f"{message_prefix}{int(pct)}%" if message_prefix else f"{int(pct)}%"
            self.update_job(job_id, progress=int(pct), message=msg)
        return cb

    def make_cancel_check(self, cancel_event: threading.Event) -> Callable:
        def check():
            if cancel_event.is_set(): raise Exception("Process Cancelled")
        return check

    def metrics(self) -> dict:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as t FROM jobs")
                total = cur.fetchone()["t"]
                cur.execute("SELECT status, COUNT(*) as c FROM jobs GROUP BY status")
                by_status = {r["status"]: r["c"] for r in cur.fetchall()}
            return {"total": total, "by_status": by_status}
        finally:
            conn.close()

# ------------------------------------------------------------------
# PG File Database
# ------------------------------------------------------------------
class PGFileDatabase:
    def __init__(self):
        init_db()

    def add_file(self, file_name: str, video_id: str, file_size: int, metadata: dict = None, owner_email: str = None) -> str:
        new_id = str(uuid.uuid4())
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO files (id, file_name, video_id, file_size, upload_date, metadata, owner_email)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (new_id, file_name, video_id, file_size, time.time(), json.dumps(metadata or {}), owner_email))
            conn.commit()
            return new_id
        finally:
            conn.close()

    def get_file(self, file_id: str) -> Optional[dict]:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM files WHERE id = %s", (file_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def list_files(self, owner_email: str = None) -> list:
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                q = "SELECT * FROM files"
                params = []
                if owner_email:
                    q += " WHERE owner_email = %s"
                    params.append(owner_email)
                q += " ORDER BY upload_date DESC"
                cur.execute(q, params)
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def remove_file(self, file_id: str):
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM files WHERE id = %s", (file_id,))
            conn.commit()
        finally:
            conn.close()
