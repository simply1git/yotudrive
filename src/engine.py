from __future__ import annotations

"""
Core YotuDrive engine.

This module exposes a high-level, UI-agnostic API that:
- Encodes files into frame directories and MP4 videos using the robust Encoder.
- Optionally splits large files into multiple parts.
- Registers encoded artifacts in the FileDatabase.
- Restores files from YouTube (or local videos) using the Decoder.

Web (Flask) and desktop GUI layers should call into this engine rather than using
Encoder/Decoder/FFmpeg/YouTube primitives directly.
"""

import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from .config_manager import config_manager
from .db import FileDatabase
from .encoder import Encoder
from .decoder import Decoder
from .ffmpeg_utils import stitch_frames
from .youtube import YouTubeStorage
from .utils import (
    ErrorCodes,
    FileValidator,
    NamingConvention,
    ValidationError,
    YotuDriveException,
    ensure_directory_exists,
)


ProgressCallback = Optional[Callable[[float], None]]
CancelCallback = Optional[Callable[[], None]]


@dataclass
class EncodeSettings:
    """High-level settings for an encode operation."""

    password: Optional[str] = None
    compression: str = "deflate"  # deflate | lzma | bzip2 | store
    block_size: Optional[int] = None
    ecc_bytes: Optional[int] = None
    threads: Optional[int] = None
    split_size_mb: int = 0  # 0 = no auto-splitting
    hw_encoder: Optional[str] = None  # libx264 / h264_nvenc / hevc_nvenc / qsv / amf / etc.


@dataclass
class EncodePartResult:
    """Result for a single encoded part (may be a whole file if not split)."""

    part_index: int
    total_parts: int
    source_path: str
    frames_dir: str
    video_path: str
    db_id: Optional[str]
    logical_file_name: str
    file_size: int


@dataclass
class EncodeResult:
    """Aggregate result for a full encode request (possibly multi-part)."""

    parts: List[EncodePartResult]
    upload_session_id: Optional[str]


@dataclass
class DecodeSettings:
    password: Optional[str] = None
    threads: Optional[int] = None


@dataclass
class DecodeResult:
    output_path: str


class YotuDriveEngine:
    """
    Main engine used by both web and desktop frontends.
    """

    def __init__(
        self,
        db: Optional[FileDatabase] = None,
        uploads_dir: str = "uploads",
        temp_dir: str = "temp",
        downloads_dir: str = "downloads",
    ) -> None:
        self.db = db or FileDatabase()
        self.uploads_dir = ensure_directory_exists(uploads_dir)
        self.temp_dir = ensure_directory_exists(temp_dir)
        self.downloads_dir = ensure_directory_exists(downloads_dir)

    # -------------------------------------------------------------------------
    # Public API – Encoding
    # -------------------------------------------------------------------------
    def encode_file(
        self,
        input_path: str,
        *,
        owner_id: Optional[str] = None,
        upload_session_id: Optional[str] = None,
        settings: Optional[EncodeSettings] = None,
        progress_callback: ProgressCallback = None,
        check_cancel: CancelCallback = None,
    ) -> EncodeResult:
        """
        Encode a single file into one or more MP4 videos using the robust Encoder pipeline.

        - Validates the input file.
        - Optionally splits large files into parts.
        - For each part:
          - Generates frames into a dedicated frames directory.
          - Stitches frames into an MP4 using FFmpeg.
          - Registers the result in the FileDatabase.
        """
        settings = settings or EncodeSettings()

        # Resolve effective settings from config + overrides
        encoding_cfg = config_manager.encoding
        perf_cfg = config_manager.performance
        video_cfg = config_manager.video

        block_size = settings.block_size or encoding_cfg.block_size
        ecc_bytes = settings.ecc_bytes or encoding_cfg.ecc_bytes
        threads = settings.threads or perf_cfg.threads
        hw_encoder = settings.hw_encoder or video_cfg.encoder

        # Validate paths and file
        validated_path, file_size = FileValidator.validate_file(
            input_path, max_size=config_manager.security.max_file_size
        )
        source_path = Path(validated_path)

        # Decide whether to split
        split_size_mb = max(0, int(settings.split_size_mb))
        if split_size_mb > 0:
            split_size_bytes = split_size_mb * 1024 * 1024
        else:
            split_size_bytes = 0

        if split_size_bytes and file_size > split_size_bytes:
            part_paths = list(
                self._split_file_streaming(source_path, split_size_bytes)
            )
        else:
            part_paths = [source_path]

        total_parts = len(part_paths)
        parts_results: List[EncodePartResult] = []

        for idx, part_path in enumerate(part_paths, start=1):
            if check_cancel:
                check_cancel()

            logical_name = part_path.name
            frames_dir = NamingConvention.generate_frames_dir_name(
                os.path.join(self.temp_dir, "frames"), logical_name
            )
            ensure_directory_exists(frames_dir)

            # Run robust encoder (frames only)
            encoder = Encoder(
                str(part_path),
                frames_dir,
                password=settings.password,
                progress_callback=progress_callback,
                block_size=block_size,
                ecc_bytes=ecc_bytes,
                threads=threads,
                check_cancel=check_cancel,
                compression=settings.compression,
            )
            # Current Encoder implementation exposes run(); we alias encode() there.
            if hasattr(encoder, "encode"):
                encoder.encode()
            else:
                encoder.run()

            # Stitch into video
            video_name = NamingConvention.generate_video_name(logical_name)
            video_path = os.path.join(self.uploads_dir, video_name)
            stitch_frames(
                frames_dir,
                video_path,
                framerate=video_cfg.fps,
                encoder=hw_encoder,
                preset=video_cfg.preset,
            )

            video_size = os.path.getsize(video_path)

            metadata = {
                "owner_id": owner_id,
                "upload_session": upload_session_id,
                "video_path": video_path,
                "original_filename": logical_name,
                "part": idx,
                "total_parts": total_parts,
            }

            db_id = self.db.add_file(
                file_name=logical_name,
                video_id="",  # Video not yet uploaded to YouTube
                file_size=video_size,
                metadata=metadata,
            )

            parts_results.append(
                EncodePartResult(
                    part_index=idx,
                    total_parts=total_parts,
                    source_path=str(part_path),
                    frames_dir=frames_dir,
                    video_path=video_path,
                    db_id=db_id,
                    logical_file_name=logical_name,
                    file_size=video_size,
                )
            )

        return EncodeResult(parts=parts_results, upload_session_id=upload_session_id)

    # -------------------------------------------------------------------------
    # Public API – Decoding / Recovery
    # -------------------------------------------------------------------------
    def recover_from_youtube(
        self,
        youtube_url: str,
        *,
        settings: Optional[DecodeSettings] = None,
        cookies_browser: Optional[str] = None,
        cookies_file: Optional[str] = None,
        progress_callback: ProgressCallback = None,
        check_cancel: CancelCallback = None,
    ) -> DecodeResult:
        """
        Download a video from YouTube (or a playlist entry), extract frames, and
        restore the original file using the robust Decoder.

        This is a high-level wrapper around YouTubeStorage + Decoder.
        """
        settings = settings or DecodeSettings()
        threads = settings.threads or config_manager.performance.threads

        # Prepare working directories
        frames_dir = ensure_directory_exists(
            os.path.join(self.temp_dir, f"frames_recover_{uuid.uuid4().hex}")
        )

        yt = YouTubeStorage(temp_dir=self.temp_dir)
        ok = yt.download(
            youtube_url,
            frames_dir,
            cookies_browser=cookies_browser,
            cookies_file=cookies_file,
            check_cancel=check_cancel,
        )
        if not ok:
            raise YotuDriveException(
                f"Failed to download YouTube video: {youtube_url}",
                ErrorCodes.DOWNLOAD_FAILED,
            )

        # Decide output path – decoder will refine extension based on header/content
        base_output = os.path.join(
            self.downloads_dir, f"recovered_{uuid.uuid4().hex}"
        )

        decoder = Decoder(
            frames_dir,
            base_output,
            password=settings.password,
            progress_callback=progress_callback,
            threads=threads,
            check_cancel=check_cancel,
        )
        decoder.run()

        return DecodeResult(output_path=decoder.output_file)

    def recover_any(
        self,
        youtube_url: str,
        *,
        settings: Optional[DecodeSettings] = None,
        cookies_browser: Optional[str] = None,
        cookies_file: Optional[str] = None,
        progress_callback: ProgressCallback = None,
        check_cancel: CancelCallback = None,
    ) -> DecodeResult:
        """
        Recover from either a single YouTube video URL or a playlist URL.
        """
        # Heuristic: treat URLs containing 'list=' or '/playlist' as playlists
        if "list=" in youtube_url or "playlist" in youtube_url:
            return self.recover_from_playlist(
                youtube_url,
                settings=settings,
                cookies_browser=cookies_browser,
                cookies_file=cookies_file,
                progress_callback=progress_callback,
                check_cancel=check_cancel,
            )
        # Fallback to single-video recovery
        return self.recover_from_youtube(
            youtube_url,
            settings=settings,
            cookies_browser=cookies_browser,
            cookies_file=cookies_file,
            progress_callback=progress_callback,
            check_cancel=check_cancel,
        )

    def recover_from_playlist(
        self,
        playlist_url: str,
        *,
        settings: Optional[DecodeSettings] = None,
        cookies_browser: Optional[str] = None,
        cookies_file: Optional[str] = None,
        progress_callback: ProgressCallback = None,
        check_cancel: CancelCallback = None,
    ) -> DecodeResult:
        """
        Restore a sequence of split files from a single YouTube playlist URL
        and auto-join them into the original file.
        """
        yt = YouTubeStorage(temp_dir=self.temp_dir)
        entries = yt.get_playlist_info(playlist_url)
        if not entries:
            raise YotuDriveException(
                f"Playlist is empty or cannot be read: {playlist_url}",
                ErrorCodes.DOWNLOAD_FAILED,
            )

        # Decode each playlist entry in order
        part_files: List[Path] = []
        for entry in entries:
            if check_cancel:
                check_cancel()
            url = entry.get("url")
            if not url:
                continue
            result = self.recover_from_youtube(
                url,
                settings=settings,
                cookies_browser=cookies_browser,
                cookies_file=cookies_file,
                progress_callback=progress_callback,
                check_cancel=check_cancel,
            )
            part_files.append(Path(result.output_path))

        final_path = self._auto_join_parts(part_files)
        return DecodeResult(output_path=str(final_path))

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------
    def _split_file_streaming(
        self, path: Path, split_size_bytes: int
    ) -> Iterable[Path]:
        """
        Stream-split a file into sequential numbered parts of approximately
        split_size_bytes each without loading the entire file into memory.
        """
        if split_size_bytes <= 0:
            yield path
            return

        parent = path.parent
        stem = path.stem
        ext = path.suffix

        part_index = 1
        bytes_written = 0
        out_file: Optional[Path] = None
        out_fh = None

        try:
            with path.open("rb") as src:
                while True:
                    chunk = src.read(4 * 1024 * 1024)
                    if not chunk:
                        break

                    if out_fh is None or bytes_written >= split_size_bytes:
                        if out_fh is not None:
                            out_fh.close()
                        part_name = f"{stem}.part{part_index:03d}{ext}"
                        out_file = parent / part_name
                        out_fh = out_file.open("wb")
                        bytes_written = 0
                        part_index += 1

                    out_fh.write(chunk)
                    bytes_written += len(chunk)

            # Close last handle
            if out_fh is not None:
                out_fh.close()

            # Yield created parts
            for i in range(1, part_index):
                part_name = f"{stem}.part{i:03d}{ext}"
                yield parent / part_name

        except OSError as e:
            raise YotuDriveException(
                f"Failed to split file {path}: {e}",
                ErrorCodes.FILE_NOT_READABLE,
                e,
            )

