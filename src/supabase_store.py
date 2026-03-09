import os
import json
import uuid
import time
from typing import Optional, List, Dict, Any
from supabase import create_client, Client

def get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
    return create_client(url, key)

# ------------------------------------------------------------------
# Supabase Auth Store
# ------------------------------------------------------------------
class SupaAuthStore:
    def __init__(self):
        self._supabase = get_supabase_client()
        self._oauth_states: Dict[str, Dict[str, float]] = {}

    def _get_user_cap(self) -> int:
        try:
            from src.settings import get_settings
            return get_settings().get("user_cap", 25)
        except Exception:
            return 25

    def bootstrap_admin(self, email: str) -> dict:
        # Check if users table is empty
        res = self._supabase.table("users").select("count", count="exact").execute()
        if res.count > 0:
            raise PermissionError("bootstrap_admin can only be called on an empty user store")
        
        user = {
            "email": email,
            "role": "admin",
            "enabled": True,
            "created_at": time.time()
        }
        self._supabase.table("users").insert(user).execute()
        return user

    def add_user(self, email: str, role: str = "member", enabled: bool = True) -> dict:
        res = self._supabase.table("users").select("count", count="exact").filter("enabled", "eq", True).execute()
        if res.count >= self._get_user_cap():
            raise PermissionError(f"User cap of {self._get_user_cap()} reached")
            
        # Check if user exists
        res = self._supabase.table("users").select("*").filter("email", "eq", email).execute()
        if res.data:
            raise ValueError(f"User {email!r} already exists")
            
        user = {
            "email": email,
            "role": role if role in ("admin", "member") else "member",
            "enabled": enabled,
            "created_at": time.time()
        }
        self._supabase.table("users").insert(user).execute()
        return user

    def patch_user(self, email: str, enabled: bool) -> dict:
        res = self._supabase.table("users").update({"enabled": enabled}).filter("email", "eq", email).execute()
        if not res.data:
            raise KeyError(f"User {email!r} not found")
        return res.data[0]

    def get_user(self, email: str) -> Optional[dict]:
        res = self._supabase.table("users").select("*").filter("email", "eq", email).execute()
        return res.data[0] if res.data else None

    def check_membership(self, email: str) -> Optional[dict]:
        u = self.get_user(email)
        return u if u and u.get("enabled") else None

    def list_users(self) -> list:
        res = self._supabase.table("users").select("*").order("created_at", desc=True).execute()
        return res.data

    def active_user_count(self) -> int:
        res = self._supabase.table("users").select("count", count="exact").filter("enabled", "eq", True).execute()
        return res.count

    def create_session(self, email: str, ip: str = None, user_agent: str = None) -> tuple:
        import secrets
        token_id = str(uuid.uuid4())
        raw_token = secrets.token_urlsafe(48)
        
        # We'll use Supabase Auth for real tokens later, but for backward compatibility
        # we still store our custom sessions in a 'sessions' table.
        import hashlib
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        now = time.time()
        
        session = {
            "token_id": token_id,
            "token_hash": token_hash,
            "user_email": email,
            "created_at": now,
            "last_seen_at": now,
            "created_from_ip": ip,
            "user_agent": user_agent
        }
        self._supabase.table("sessions").insert(session).execute()
        return token_id, raw_token

    def validate_token(self, raw_token: str) -> tuple:
        import hashlib
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        res = self._supabase.table("sessions").select("*").filter("token_hash", "eq", token_hash).execute()
        if not res.data:
            raise ValueError("Invalid token")
        sess = res.data[0]
        
        if sess.get("revoked_by") is not None:
            raise ValueError("Token has been revoked")
            
        user = self.get_user(sess["user_email"])
        if not user or not user.get("enabled"):
            raise ValueError("User not found or disabled")
            
        self._supabase.table("sessions").update({"last_seen_at": time.time()}).filter("token_id", "eq", sess["token_id"]).execute()
        return sess, user

    def revoke_session(self, token_id: str, revoked_by: str = "user", reason: str = None):
        res = self._supabase.table("sessions").update({
            "revoked_by": revoked_by,
            "revoke_reason": reason
        }).filter("token_id", "eq", token_id).execute()
        if not res.data:
            raise KeyError(f"Session {token_id!r} not found")

    def revoke_sessions_for_user(self, email: str, keep_current_id: str = None,
                                  revoked_by: str = "user", reason: str = None) -> int:
        query = self._supabase.table("sessions").update({
            "revoked_by": revoked_by,
            "revoke_reason": reason
        }).filter("user_email", "eq", email).filter("revoked_by", "is", "null")
        
        if keep_current_id:
            query = query.filter("token_id", "neq", keep_current_id)
            
        res = query.execute()
        return len(res.data)

    def list_sessions(self, email: str = None, include_revoked: bool = False,
                      revoked_by: str = None, revoke_reason: str = None,
                      limit: int = 50, offset: int = 0) -> list:
        query = self._supabase.table("sessions").select("*")
        if email:
            query = query.filter("user_email", "eq", email)
        if not include_revoked:
            query = query.filter("revoked_by", "is", "null")
        if revoked_by:
            query = query.filter("revoked_by", "eq", revoked_by)
        if revoke_reason:
            query = query.filter("revoke_reason", "eq", revoke_reason)
            
        res = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        for r in res.data:
            r.pop("token_hash", None)
        return res.data

    def store_oauth_state(self, state: str, ttl_seconds: int = 600):
        self._oauth_states[state] = {"expiry": time.time() + ttl_seconds}

    def validate_oauth_state(self, state: str) -> bool:
        entry = self._oauth_states.pop(state, None)
        return False if not entry else entry["expiry"] > time.time()

    def metrics(self) -> dict:
        u_total = self._supabase.table("users").select("count", count="exact").execute().count
        u_active = self._supabase.table("users").select("count", count="exact").filter("enabled", "eq", True).execute().count
        
        s_total = self._supabase.table("sessions").select("count", count="exact").execute().count
        s_active = self._supabase.table("sessions").select("count", count="exact").filter("revoked_by", "is", "null").execute().count
        
        return {
            "total": u_total or 0, "active": u_active or 0, "cap": self._get_user_cap(),
            "sessions": {
                "total": s_total or 0, "active": s_active or 0, "revoked": s_total - s_active
            }
        }

# ------------------------------------------------------------------
# Supabase Job Store
# ------------------------------------------------------------------
class SupaJobStore:
    def __init__(self, max_workers: int = 4):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="yotu-job")
        self._lock = threading.Lock()
        self._active_events = {}
        self._supabase = get_supabase_client()
        self.recover()

    def recover(self):
        """Mark interrupted jobs as failed upon server restart."""
        try:
            now = time.time()
            self._supabase.table("jobs").update({
                "status": "failed",
                "error": "System interrupted (restart detected)",
                "message": "Interrupted. Please restart the job manually.",
                "updated_at": now
            }).filter("status", "in", ("running", "pending")).filter("managed", "eq", False).execute()
        except Exception as e:
            print(f"[SupaJobStore] Recovery error: {e}")

    def create_job(self, kind: str, owner_email: str = None, public: bool = False, managed: bool = False) -> dict:
        job_id = str(uuid.uuid4())
        now = time.time()
        job = {
            "id": job_id, "kind": kind, "status": "pending", "progress": 0,
            "message": "", "result": None, "error": None, "owner_email": owner_email,
            "public": public, "managed": managed, "created_at": now, "updated_at": now
        }
        self._supabase.table("jobs").insert(job).execute()
        return job

    def claim_job(self, job_id: str, worker_id: str) -> bool:
        now = time.time()
        res = self._supabase.table("jobs").update({
            "status": "running",
            "worker_id": worker_id,
            "claimed_at": now,
            "updated_at": now,
            "message": "Claimed by Nebula Worker"
        }).filter("id", "eq", job_id).filter("status", "eq", "pending").filter("managed", "eq", True).execute()
        return len(res.data) > 0

    def update_job(self, job_id: str, **kwargs):
        allowed = {"status", "progress", "message", "result", "error"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = time.time()
        self._supabase.table("jobs").update(updates).filter("id", "eq", job_id).execute()

    def get_job(self, job_id: str) -> Optional[dict]:
        res = self._supabase.table("jobs").select("*").filter("id", "eq", job_id).execute()
        return res.data[0] if res.data else None

    def delete_job(self, job_id: str):
        self._supabase.table("jobs").delete().filter("id", "eq", job_id).execute()

    def cancel_job(self, job_id: str):
        with self._lock:
            evt = self._active_events.get(job_id)
            if evt:
                evt.set()
                return True
        return False

    def list_jobs(self, owner_email: str = None, status_filter: list = None,
                  include_public: bool = False, limit: int = 50, offset: int = 0) -> tuple:
        query = self._supabase.table("jobs").select("*", count="exact")
        if owner_email:
            if include_public:
                # Supabase OR filter
                query = query.or_(f"owner_email.eq.{owner_email},public.eq.true")
            else:
                query = query.filter("owner_email", "eq", owner_email)
        
        if status_filter:
            query = query.filter("status", "in", tuple(status_filter))
            
        res = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        return res.data, res.count

    def clear_completed_jobs(self, owner_email: str):
        self._supabase.table("jobs").delete().filter("owner_email", "eq", owner_email).filter("status", "in", ("done", "failed", "cancelled")).execute()

    def submit(self, fn: Any, job_id: str, *args, **kwargs):
        import threading
        cancel_event = kwargs.pop('cancel_event', None) or threading.Event()
        with self._lock:
            self._active_events[job_id] = cancel_event
        self.update_job(job_id, status="running", message="Starting…")
        
        def wrapper():
            try:
                result = fn(*args, **kwargs)
                self.update_job(job_id, status="done", progress=100, message="Completed", result=result)
            except Exception as e:
                msg = str(e)
                if "cancelled" in msg.lower() or "process cancelled" in msg.lower():
                    self.update_job(job_id, status="cancelled", message="Cancelled by user")
                else:
                    self.update_job(job_id, status="failed", message=msg, error=msg)
            finally:
                with self._lock:
                    if job_id in self._active_events:
                        del self._active_events[job_id]
        self._executor.submit(wrapper)
        return cancel_event

    def make_progress_callback(self, job_id: str, message_prefix: str = "") -> Any:
        def cb(pct):
            msg = f"{message_prefix}{int(pct)}%" if message_prefix else f"{int(pct)}%"
            self.update_job(job_id, progress=int(pct), message=msg)
        return cb

    def make_cancel_check(self, cancel_event: Any) -> Any:
        def check():
            if cancel_event.is_set(): raise Exception("Process Cancelled")
        return check

    def metrics(self) -> dict:
        res = self._supabase.table("jobs").select("status").execute()
        by_status = {}
        for r in res.data:
            s = r["status"]
            by_status[s] = by_status.get(s, 0) + 1
        return {"total": len(res.data), "by_status": by_status}

# ------------------------------------------------------------------
# Supabase File Database
# ------------------------------------------------------------------
class SupaFileDatabase:
    def __init__(self):
        self._supabase = get_supabase_client()

    def add_file(self, file_name: str, video_id: str, file_size: int, metadata: dict = None, owner_email: str = None) -> str:
        new_id = str(uuid.uuid4())
        file = {
            "id": new_id,
            "file_name": file_name,
            "video_id": video_id,
            "file_size": file_size,
            "upload_date": time.time(),
            "metadata": metadata or {},
            "owner_email": owner_email
        }
        self._supabase.table("files").insert(file).execute()
        return new_id

    def get_file(self, file_id: str) -> Optional[dict]:
        res = self._supabase.table("files").select("*").filter("id", "eq", file_id).execute()
        return res.data[0] if res.data else None

    def list_files(self, owner_email: str = None) -> list:
        query = self._supabase.table("files").select("*")
        if owner_email:
            query = query.filter("owner_email", "eq", owner_email)
        res = query.order("upload_date", desc=True).execute()
        return res.data

    def remove_file(self, file_id: str):
        self._supabase.table("files").delete().filter("id", "eq", file_id).execute()
