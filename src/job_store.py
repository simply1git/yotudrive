"""
YotuDrive Job Store
Persistent async job tracking backed by data/jobs.json.
Background ThreadPoolExecutor runs codec pipelines and updates job state.
"""
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
JOBS_FILE = os.path.join(DATA_DIR, "jobs.json")

VALID_STATUSES = ("pending", "running", "done", "failed", "cancelled")
VALID_KINDS = (
    "encode", "decode",
    "pipeline_encode", "pipeline_decode",
    "oauth_upload",
)


class JobStore:
    def __init__(self, path: str = JOBS_FILE, max_workers: int = 4):
        self._path = path
        self._lock = threading.Lock()
        self._data: dict = {}  # job_id -> job_dict
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="yotu-job")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._load()
        self.prune()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self):
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            if os.path.exists(self._path):
                os.remove(self._path)
            os.rename(tmp, self._path)
        except Exception as e:
            print(f"[JobStore] Save error: {e}")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def create_job(self, kind: str, owner_email: str = None, public: bool = False) -> dict:
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "kind": kind if kind in VALID_KINDS else "encode",
            "status": "pending",
            "progress": 0,
            "message": "",
            "result": None,
            "error": None,
            "owner_email": owner_email,
            "public": public,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        with self._lock:
            self._data[job_id] = job
            self._save()
        return dict(job)

    def update_job(self, job_id: str, **kwargs):
        allowed = {"status", "progress", "message", "result", "error"}
        with self._lock:
            job = self._data.get(job_id)
            if not job:
                return
            for k, v in kwargs.items():
                if k in allowed:
                    job[k] = v
            job["updated_at"] = time.time()
            self._save()

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._lock:
            j = self._data.get(job_id)
            return dict(j) if j else None

    def delete_job(self, job_id: str):
        with self._lock:
            if job_id in self._data:
                del self._data[job_id]
                self._save()

    def list_jobs(
        self,
        owner_email: str = None,
        status_filter: list = None,
        include_public: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple:
        """Returns (jobs_list, total_count)."""
        with self._lock:
            all_jobs = list(self._data.values())

        result = []
        for j in all_jobs:
            if owner_email:
                if j.get("owner_email") != owner_email:
                    if not (include_public and j.get("public")):
                        continue
            if status_filter:
                if j.get("status") not in status_filter:
                    continue
            result.append(dict(j))

        result.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        total = len(result)
        return result[offset: offset + limit], total

    # ------------------------------------------------------------------
    # Background Execution
    # ------------------------------------------------------------------
    def submit(self, fn: Callable, job_id: str, *args, **kwargs):
        """
        Submit a callable to the thread pool.
        Auto-sets job status to running/done/failed.
        """
        self.update_job(job_id, status="running", message="Starting…")

        def wrapper():
            try:
                result = fn(*args, **kwargs)
                self.update_job(job_id, status="done", progress=100,
                                message="Completed", result=result)
            except Exception as e:
                if "cancelled" in str(e).lower() or "process cancelled" in str(e).lower():
                    self.update_job(job_id, status="cancelled", message="Cancelled by user")
                else:
                    self.update_job(job_id, status="failed", message=str(e), error=str(e))

        self._executor.submit(wrapper)

    def make_progress_callback(self, job_id: str, message_prefix: str = "") -> Callable:
        """Returns a progress_callback(pct) suitable for Encoder/Decoder."""
        def cb(pct):
            msg = f"{message_prefix}{int(pct)}%" if message_prefix else f"{int(pct)}%"
            self.update_job(job_id, progress=int(pct), message=msg)
        return cb

    def make_cancel_check(self, cancel_event: threading.Event) -> Callable:
        """Returns a check_cancel() that raises on cancel_event."""
        def check():
            if cancel_event.is_set():
                raise Exception("Process Cancelled")
        return check

    # ------------------------------------------------------------------
    # Pruning
    # ------------------------------------------------------------------
    def prune(self):
        """Remove jobs beyond max_age_days or max_records."""
        try:
            from src.settings import get_settings
            s = get_settings()
            max_age = s.get("job_max_age_days", 30) * 86400
            max_records = s.get("job_max_records", 500)
        except Exception:
            max_age = 30 * 86400
            max_records = 500

        now = time.time()
        with self._lock:
            # Remove old terminal jobs
            to_delete = [
                jid for jid, j in self._data.items()
                if j.get("status") in ("done", "failed", "cancelled")
                and (now - j.get("updated_at", 0)) > max_age
            ]
            for jid in to_delete:
                del self._data[jid]

            # Trim if still over limit
            all_sorted = sorted(self._data.values(), key=lambda x: x.get("created_at", 0))
            while len(all_sorted) > max_records:
                victim = all_sorted.pop(0)
                del self._data[victim["id"]]

            if to_delete or len(self._data) < len(all_sorted):
                self._save()

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def metrics(self) -> dict:
        with self._lock:
            jobs = list(self._data.values())
        by_status = {}
        for j in jobs:
            st = j.get("status", "unknown")
            by_status[st] = by_status.get(st, 0) + 1
        return {"total": len(jobs), "by_status": by_status}


# Module-level singleton
_job_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    global _job_store
    if _job_store is None:
        if os.environ.get("DATABASE_URL"):
            from src.pg_store import PGJobStore
            _job_store = PGJobStore()
        else:
            _job_store = JobStore()
    return _job_store
