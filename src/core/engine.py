"""
YotuDrive Core Engine Facade
Single entry-point used by all clients (Flask API, future integrations).
Delegates to the existing src/* modules — nothing here re-implements codec logic.
"""
import os
import threading
from typing import Callable, Optional


class Engine:
    """
    Shared engine facade. Instantiate once and reuse across requests.
    All methods are thread-safe (they delegate to thread-safe modules or
    create independent objects per call).
    """

    # ------------------------------------------------------------------
    # Encode / Decode
    # ------------------------------------------------------------------
    def encode_file(
        self,
        input_path: str,
        output_dir: str,
        *,
        password: str = None,
        block_size: int = 2,
        ecc_bytes: int = 32,
        threads: int = None,
        check_cancel: Callable = None,
        progress_cb: Callable = None,
    ):
        """Encode a file into PNG frames in output_dir."""
        from src.encoder import Encoder
        enc = Encoder(
            input_path,
            output_dir,
            password=password,
            block_size=block_size,
            ecc_bytes=ecc_bytes,
            threads=threads,
            progress_callback=progress_cb,
            check_cancel=check_cancel,
        )
        enc.run()

    def decode_source(
        self,
        frames_dir: str,
        output_path: str,
        *,
        password: str = None,
        threads: int = None,
        check_cancel: Callable = None,
        progress_cb: Callable = None,
    ):
        """Decode PNG frames from frames_dir into output_path."""
        from src.decoder import Decoder
        dec = Decoder(
            frames_dir,
            output_path,
            password=password,
            threads=threads,
            progress_callback=progress_cb,
            check_cancel=check_cancel,
        )
        dec.run()
        return dec.output_file

    # ------------------------------------------------------------------
    # Video utilities
    # ------------------------------------------------------------------
    def verify_video(self, video_path: str, max_frames: int = 10) -> dict:
        """Quick header-only verify of a YotuDrive archive video."""
        from src.verifier import verify_video
        return verify_video(video_path)

    def stitch_frames(
        self,
        frames_dir: str,
        output_video: str,
        *,
        encoder: str = "libx264",
        framerate: int = 30,
        check_cancel: Callable = None,
        progress_cb: Callable = None,
    ):
        """Stitch PNG frames into a video file (for full pipeline)."""
        from src.ffmpeg_utils import stitch_frames
        stitch_frames(frames_dir, output_video, framerate=framerate,
                      encoder=encoder, check_cancel=check_cancel, progress_cb=progress_cb)

    def extract_from_video(
        self,
        video_path: str,
        frames_dir: str,
        *,
        limit: int = None,
        check_cancel: Callable = None,
    ):
        """Extract frames from a video file using FFmpeg."""
        from src.ffmpeg_utils import extract_frames
        extract_frames(video_path, frames_dir, limit=limit, check_cancel=check_cancel)

    # ------------------------------------------------------------------
    # YouTube
    # ------------------------------------------------------------------
    def download_from_youtube(
        self,
        video_id_or_url: str,
        frames_dir: str,
        *,
        cookies_file: str = None,
        cookies_browser: str = None,
        check_cancel: Callable = None,
    ) -> bool:
        """Download a YouTube video and extract frames into frames_dir."""
        from src.youtube import YouTubeStorage
        yt = YouTubeStorage()
        return yt.download(
            video_id_or_url,
            frames_dir,
            cookies_file=cookies_file,
            cookies_browser=cookies_browser,
            check_cancel=check_cancel,
        )

    def inspect_playlist(self, playlist_url: str) -> list:
        """Return list of {url, id, title} dicts from a playlist."""
        from src.youtube import YouTubeStorage
        yt = YouTubeStorage()
        return yt.get_playlist_info(playlist_url)

    # ------------------------------------------------------------------
    # File Database
    # ------------------------------------------------------------------
    def list_files(self, owner_email: str = None, include_legacy: bool = False) -> list:
        """Return file records, optionally filtered by owner."""
        from src.db import FileDatabase
        db = FileDatabase()
        files = db.list_files()
        if owner_email is not None:
            result = []
            for f in files:
                if f.get("owner_email") == owner_email:
                    result.append(f)
                elif include_legacy and not f.get("owner_email"):
                    result.append(f)
            return result
        return files

    def attach_video_reference(
        self,
        file_id: str,
        video_id: str,
        *,
        video_url: str = None,
        owner_email: str = None,
    ) -> dict:
        """Link a file record to a YouTube video ID."""
        from src.db import FileDatabase
        db = FileDatabase()
        entry = db.get_file(file_id)
        if not entry:
            raise KeyError(f"File {file_id!r} not found")
        entry["video_id"] = video_id
        if video_url:
            entry["video_url"] = video_url
        if owner_email:
            entry["owner_email"] = owner_email
        db.data[file_id] = entry
        db.save()
        return dict(entry)

    def register_file(
        self,
        file_name: str,
        video_id: str,
        file_size: int,
        metadata: dict = None,
        owner_email: str = None,
    ) -> str:
        """Register a new file record. Returns the UUID."""
        from src.db import FileDatabase
        db = FileDatabase()
        meta = metadata or {}
        if owner_email:
            meta["owner_email"] = owner_email
        file_id = db.add_file(file_name, video_id, file_size, meta)
        # Also store owner_email at top level for easy querying
        if owner_email:
            db.data[file_id]["owner_email"] = owner_email
            db.save()
        return file_id

    def delete_file(self, file_id: str, requester_email: str = None, is_admin: bool = False):
        """Delete a file record. Enforces ownership unless admin."""
        from src.db import FileDatabase
        db = FileDatabase()
        entry = db.get_file(file_id)
        if not entry:
            raise KeyError(f"File {file_id!r} not found")
        if not is_admin and requester_email:
            owner = entry.get("owner_email")
            if owner and owner != requester_email:
                raise PermissionError("You do not own this file")
            if not owner:
                raise PermissionError("Legacy records can only be managed by admins")
        db.remove_file(file_id)

    def get_file(self, file_id: str) -> Optional[dict]:
        from src.db import FileDatabase
        db = FileDatabase()
        entry = db.get_file(file_id)
        return dict(entry) if entry else None

    def file_metrics(self) -> dict:
        from src.db import FileDatabase
        db = FileDatabase()
        files = db.list_files()
        owned = sum(1 for f in files if f.get("owner_email"))
        return {"total": len(files), "owned": owned, "legacy": len(files) - owned}

    # ------------------------------------------------------------------
    # File splitting / joining
    # ------------------------------------------------------------------
    def split_file(self, file_path: str, chunk_size: int, output_dir: str = None) -> list:
        from src.file_utils import split_file
        return split_file(file_path, chunk_size, output_dir)

    def auto_join(self, file_list: list, *, auto_cleanup: bool = True,
                  log_cb: Callable = None) -> list:
        from src.file_utils import auto_join_restored_files
        return auto_join_restored_files(file_list, log_callback=log_cb, auto_cleanup=auto_cleanup)


# Module-level singleton
_engine: Optional[Engine] = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine
