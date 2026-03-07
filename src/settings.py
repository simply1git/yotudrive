"""
YotuDrive Settings Manager
Wraps settings.json with schema defaults, validation, and merge utilities.
"""
import json
import os
import threading

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")

# Environment detection
IS_RENDER = "RENDER" in os.environ or "RENDER_SERVICE_ID" in os.environ
RENDER_MAX_THREADS = 2

def get_default_threads():
    count = max(1, (os.cpu_count() or 4) - 1)
    if IS_RENDER:
        return min(count, RENDER_MAX_THREADS)
    return count

DEFAULTS = {
    # Encoding
    "block_size": 2,
    "ecc_bytes": 32,
    "threads": get_default_threads(),
    "auto_cleanup": True,
    "encoder": "libx264",
    "theme": "cosmo",
    "compression": "Fast (Deflate)",
    "split_size": "No Split",
    # API-only additions
    "user_cap": 25,
    "job_max_age_days": 30,
    "job_max_records": 500,
}

VALID_ENCODERS = ["libx264", "h264_nvenc", "h264_qsv", "h264_amf"]
VALID_COMPRESSIONS = ["Store (No Compression)", "Fast (Deflate)", "Best (LZMA)", "BZIP2"]
VALID_SPLIT_SIZES = ["No Split", "100 MB", "500 MB", "1 GB", "5 GB", "10 GB"]


class Settings:
    """Thread-safe settings manager backed by settings.json."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, path: str = SETTINGS_FILE):
        self._path = path
        self._lock = threading.Lock()
        self._data: dict = {}
        self.load()

    # ------------------------------------------------------------------
    # Singleton-style factory (optional convenience)
    # ------------------------------------------------------------------
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------
    def load(self):
        """Load from disk, fall back to defaults on any error."""
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    on_disk = json.load(f)
                # Merge: disk values override defaults
                merged = dict(DEFAULTS)
                merged.update({k: v for k, v in on_disk.items() if k in DEFAULTS})
                with self._lock:
                    self._data = merged
                return
        except Exception:
            pass
        with self._lock:
            self._data = dict(DEFAULTS)

    def save(self):
        """Persist current settings to disk atomically."""
        tmp = self._path + ".tmp"
        try:
            with self._lock:
                snapshot = dict(self._data)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=4)
            if os.path.exists(self._path):
                os.remove(self._path)
            os.rename(tmp, self._path)
        except Exception as e:
            print(f"[Settings] Save error: {e}")
            try:
                os.remove(tmp)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key: str, value):
        if key not in DEFAULTS:
            raise KeyError(f"Unknown setting: {key!r}")
        with self._lock:
            self._data[key] = value
        self.save()

    def merge(self, updates: dict):
        """Merge a dict of updates (unknown keys are ignored)."""
        with self._lock:
            for k, v in updates.items():
                if k in DEFAULTS:
                    self._data[k] = v
        self.save()

    def as_dict(self) -> dict:
        with self._lock:
            return dict(self._data)

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)


# Module-level convenience instance
_settings = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
