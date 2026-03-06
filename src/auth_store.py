"""
YotuDrive Auth Store
JSON-backed store for users, sessions, and membership management.
Separate from yotudrive.json — stored at data/auth.json.
"""
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
AUTH_FILE = os.path.join(DATA_DIR, "auth.json")


class AuthStore:
    def __init__(self, path: str = AUTH_FILE):
        self._path = path
        self._lock = threading.Lock()
        # In-memory OAuth state: {state_str: {"email": ..., "expiry": float}}
        self._oauth_states: dict = {}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._data: dict = {"users": {}, "sessions": {}}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self):
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                self._data.setdefault("users", {})
                self._data.setdefault("sessions", {})
        except Exception:
            self._data = {"users": {}, "sessions": {}}

    def _save(self):
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            if os.path.exists(self._path):
                os.remove(self._path)
            os.rename(tmp, self._path)
        except Exception as e:
            print(f"[AuthStore] Save error: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _hash_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def _get_user_cap(self) -> int:
        try:
            from src.settings import get_settings
            return get_settings().get("user_cap", 25)
        except Exception:
            return 25

    # ------------------------------------------------------------------
    # Admin Bootstrap
    # ------------------------------------------------------------------
    def bootstrap_admin(self, email: str) -> dict:
        """One-time admin seeding. Fails if any user already exists."""
        with self._lock:
            if self._data["users"]:
                raise PermissionError("bootstrap_admin can only be called on an empty user store")
            user = {
                "email": email,
                "role": "admin",
                "enabled": True,
                "created_at": time.time(),
            }
            self._data["users"][email] = user
            self._save()
            return dict(user)

    # ------------------------------------------------------------------
    # Users / Membership
    # ------------------------------------------------------------------
    def add_user(self, email: str, role: str = "member", enabled: bool = True) -> dict:
        with self._lock:
            if email in self._data["users"]:
                raise ValueError(f"User {email!r} already exists")
            active = sum(1 for u in self._data["users"].values() if u.get("enabled"))
            if active >= self._get_user_cap():
                raise PermissionError(f"User cap of {self._get_user_cap()} reached")
            user = {
                "email": email,
                "role": role if role in ("admin", "member") else "member",
                "enabled": enabled,
                "created_at": time.time(),
            }
            self._data["users"][email] = user
            self._save()
            return dict(user)

    def patch_user(self, email: str, enabled: bool) -> dict:
        with self._lock:
            if email not in self._data["users"]:
                raise KeyError(f"User {email!r} not found")
            self._data["users"][email]["enabled"] = enabled
            self._save()
            return dict(self._data["users"][email])

    def get_user(self, email: str) -> Optional[dict]:
        with self._lock:
            u = self._data["users"].get(email)
            return dict(u) if u else None

    def check_membership(self, email: str) -> Optional[dict]:
        """Returns user dict if email is allowlisted and enabled, else None."""
        u = self.get_user(email)
        if u and u.get("enabled"):
            return u
        return None

    def list_users(self) -> list:
        with self._lock:
            return [dict(u) for u in self._data["users"].values()]

    def active_user_count(self) -> int:
        with self._lock:
            return sum(1 for u in self._data["users"].values() if u.get("enabled"))

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------
    def create_session(self, email: str, ip: str = None, user_agent: str = None) -> tuple:
        """Returns (token_id, raw_bearer_token). raw token is only returned once."""
        token_id = str(uuid.uuid4())
        raw_token = secrets.token_urlsafe(48)
        token_hash = self._hash_token(raw_token)
        session = {
            "token_id": token_id,
            "token_hash": token_hash,
            "user_email": email,
            "created_at": time.time(),
            "last_seen_at": time.time(),
            "created_from_ip": ip,
            "user_agent": user_agent,
            "revoked_by": None,
            "revoke_reason": None,
        }
        with self._lock:
            self._data["sessions"][token_id] = session
            self._save()
        return token_id, raw_token

    def validate_token(self, raw_token: str) -> tuple:
        """Returns (session_dict, user_dict) or raises ValueError."""
        token_hash = self._hash_token(raw_token)
        with self._lock:
            for sess in self._data["sessions"].values():
                if sess.get("token_hash") == token_hash:
                    if sess.get("revoked_by") is not None:
                        raise ValueError("Token has been revoked")
                    email = sess["user_email"]
                    user = self._data["users"].get(email)
                    if not user or not user.get("enabled"):
                        raise ValueError("User not found or disabled")
                    # Update last_seen
                    sess["last_seen_at"] = time.time()
                    self._save()
                    return dict(sess), dict(user)
        raise ValueError("Invalid token")

    def revoke_session(self, token_id: str, revoked_by: str = "user", reason: str = None):
        with self._lock:
            sess = self._data["sessions"].get(token_id)
            if not sess:
                raise KeyError(f"Session {token_id!r} not found")
            sess["revoked_by"] = revoked_by
            sess["revoke_reason"] = reason
            self._save()

    def revoke_sessions_for_user(self, email: str, keep_current_id: str = None,
                                  revoked_by: str = "user", reason: str = None) -> int:
        count = 0
        with self._lock:
            for sess in self._data["sessions"].values():
                if sess["user_email"] == email and sess.get("revoked_by") is None:
                    if keep_current_id and sess["token_id"] == keep_current_id:
                        continue
                    sess["revoked_by"] = revoked_by
                    sess["revoke_reason"] = reason
                    count += 1
            if count:
                self._save()
        return count

    def list_sessions(self, email: str = None, include_revoked: bool = False,
                      revoked_by: str = None, revoke_reason: str = None,
                      limit: int = 50, offset: int = 0) -> list:
        with self._lock:
            sessions = list(self._data["sessions"].values())

        result = []
        for s in sessions:
            if email and s["user_email"] != email:
                continue
            if not include_revoked and s.get("revoked_by") is not None:
                continue
            if revoked_by and s.get("revoked_by") != revoked_by:
                continue
            if revoke_reason and s.get("revoke_reason") != revoke_reason:
                continue
            # Expose token_id, NOT raw token
            safe = {k: v for k, v in s.items() if k != "token_hash"}
            result.append(safe)

        result.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return result[offset: offset + limit]

    # ------------------------------------------------------------------
    # Google OAuth State (in-memory with TTL)
    # ------------------------------------------------------------------
    def store_oauth_state(self, state: str, ttl_seconds: int = 600):
        self._oauth_states[state] = {"expiry": time.time() + ttl_seconds}

    def validate_oauth_state(self, state: str) -> bool:
        entry = self._oauth_states.pop(state, None)
        if not entry:
            return False
        return entry["expiry"] > time.time()

    def cleanup_oauth_states(self):
        now = time.time()
        self._oauth_states = {k: v for k, v in self._oauth_states.items() if v["expiry"] > now}

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def metrics(self) -> dict:
        with self._lock:
            users = self._data["users"]
            sessions = self._data["sessions"]
            return {
                "total": len(users),
                "active": sum(1 for u in users.values() if u.get("enabled")),
                "cap": self._get_user_cap(),
                "sessions": {
                    "total": len(sessions),
                    "active": sum(1 for s in sessions.values() if s.get("revoked_by") is None),
                    "revoked": sum(1 for s in sessions.values() if s.get("revoked_by") is not None),
                },
            }


# Module-level singleton
_auth_store: Optional[AuthStore] = None


def get_auth_store() -> AuthStore:
    global _auth_store
    if _auth_store is None:
        if os.environ.get("DATABASE_URL"):
            from src.pg_store import PGAuthStore
            _auth_store = PGAuthStore()
        else:
            _auth_store = AuthStore()
    return _auth_store
