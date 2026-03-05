import os
import hashlib
import shutil
import tempfile
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.db import FileDatabase
from src.decoder import Decoder
from src.encoder import Encoder
from src.ffmpeg_utils import extract_frames, stitch_frames
from src.file_utils import split_file
from src.settings import EngineSettings, load_settings, merge_settings, save_settings


ProgressCallback = Optional[Callable[[float], None]]


@dataclass
class EncodePartResult:
    part_path: str
    frames_dir: str
    db_id: Optional[str]


@dataclass
class EncodeResult:
    source_file: str
    parts: List[EncodePartResult]
    split: bool


class Engine:
    def __init__(self, settings_path: str = "settings.json", db_path: str = "yotudrive.json"):
        self.settings_path = settings_path
        self.db = FileDatabase(db_path)
        self.settings = load_settings(settings_path)

    def get_settings(self) -> EngineSettings:
        self.settings = load_settings(self.settings_path)
        return self.settings

    def update_settings(self, overrides: Dict[str, Any]) -> EngineSettings:
        self.settings = merge_settings(self.get_settings(), overrides)
        save_settings(self.settings, self.settings_path)
        return self.settings

    def list_files(self) -> List[dict]:
        return self.db.list_files()

    def encode_file(
        self,
        input_file: str,
        output_root: str,
        password: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
        progress_callback: ProgressCallback = None,
        check_cancel: Optional[Callable[[], None]] = None,
        register_in_db: bool = True,
    ) -> EncodeResult:
        cfg = merge_settings(self.get_settings(), overrides)
        source_size = os.path.getsize(input_file)
        os.makedirs(output_root, exist_ok=True)

        split = cfg.split_enabled and cfg.split_threshold_bytes > 0 and source_size > cfg.split_threshold_bytes
        parts = [input_file]
        if split:
            split_dir = os.path.join(output_root, "split_parts")
            os.makedirs(split_dir, exist_ok=True)
            parts = split_file(input_file, cfg.split_threshold_bytes, output_dir=split_dir)

        results: List[EncodePartResult] = []
        multipart_group_id = None
        if split and register_in_db:
            multipart_group_id = self.db.add_multipart_file(
                file_name=os.path.basename(input_file),
                file_size=source_size,
                total_parts=len(parts),
                metadata={"source_file": os.path.abspath(input_file)},
            )

        for idx, part in enumerate(parts, start=1):
            part_name = os.path.basename(part)
            part_dir = os.path.join(output_root, f"frames_part_{idx:03d}") if split else output_root
            os.makedirs(part_dir, exist_ok=True)

            encoder = Encoder(
                input_file=part,
                output_dir=part_dir,
                password=password,
                progress_callback=progress_callback,
                block_size=cfg.block_size,
                ecc_bytes=cfg.ecc_bytes,
                threads=cfg.threads,
                check_cancel=check_cancel,
            )
            encoder.run()

            metadata = {
                "frames_dir": part_dir,
                "part_index": idx,
                "total_parts": len(parts),
                "split": split,
                "compression": cfg.compression,
                "kdf_iterations": cfg.kdf_iterations,
                "encryption_chunk_size": cfg.encryption_chunk_size,
            }
            if multipart_group_id:
                metadata["multipart_group_id"] = multipart_group_id

            db_id = None
            if register_in_db:
                db_id = self.db.add_file(part_name, "pending_upload", os.path.getsize(part), metadata)
                if multipart_group_id and db_id:
                    self.db.add_part_to_group(multipart_group_id, db_id, idx)

            results.append(EncodePartResult(part_path=part, frames_dir=part_dir, db_id=db_id))

        return EncodeResult(source_file=input_file, parts=results, split=split)

    def decode_source(
        self,
        frames_dir: str,
        output_file: str,
        password: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
        progress_callback: ProgressCallback = None,
        check_cancel: Optional[Callable[[], None]] = None,
    ) -> str:
        cfg = merge_settings(self.get_settings(), overrides)
        decoder = Decoder(
            input_dir=frames_dir,
            output_file=output_file,
            password=password,
            progress_callback=progress_callback,
            threads=cfg.threads,
            check_cancel=check_cancel,
        )
        decoder.run()
        return decoder.output_file

    def decode_video_source(
        self,
        video_path: str,
        output_file: str,
        password: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        check_cancel: Optional[Callable[[], None]] = None,
        temp_root: Optional[str] = None,
        auto_cleanup: bool = True,
    ) -> Dict[str, Any]:
        cfg = merge_settings(self.get_settings(), overrides)

        def emit(pct: float, message: str) -> None:
            if progress_callback:
                progress_callback(pct, message)

        base_tmp = temp_root or tempfile.mkdtemp(prefix="yotudrive_decode_")
        created_base_tmp = temp_root is None
        frames_dir = os.path.join(base_tmp, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        try:
            emit(0.0, "Extracting frames...")
            extract_frames(video_path, frames_dir, check_cancel=check_cancel)

            emit(35.0, "Decoding...")
            restored = self.decode_source(
                frames_dir=frames_dir,
                output_file=output_file,
                password=password,
                overrides={"threads": cfg.threads},
                progress_callback=lambda pct: emit(35.0 + (pct * 0.65), f"Decoding... {pct:.1f}%"),
                check_cancel=check_cancel,
            )

            emit(100.0, "Decode pipeline complete")
            return {"output_file": restored, "frames_dir": frames_dir}
        finally:
            if auto_cleanup:
                try:
                    if os.path.isdir(frames_dir):
                        shutil.rmtree(frames_dir)
                except OSError:
                    pass
                if created_base_tmp:
                    try:
                        if os.path.isdir(base_tmp):
                            shutil.rmtree(base_tmp)
                    except OSError:
                        pass

    def encode_to_video(
        self,
        input_file: str,
        output_video: str,
        password: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
        verify_roundtrip: bool = True,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        check_cancel: Optional[Callable[[], None]] = None,
        temp_root: Optional[str] = None,
        auto_cleanup: bool = True,
        register_in_db: bool = True,
    ) -> Dict[str, Any]:
        cfg = merge_settings(self.get_settings(), overrides)

        def emit(pct: float, message: str) -> None:
            if progress_callback:
                progress_callback(pct, message)

        base_tmp = temp_root or tempfile.mkdtemp(prefix="yotudrive_pipeline_")
        created_base_tmp = temp_root is None
        frames_dir = os.path.join(base_tmp, "frames")
        verify_frames_dir = os.path.join(base_tmp, "verify_frames")
        verify_output = os.path.join(base_tmp, "verify_output.bin")

        os.makedirs(frames_dir, exist_ok=True)

        try:
            emit(0.0, "Encoding...")
            self.encode_file(
                input_file=input_file,
                output_root=frames_dir,
                password=password,
                overrides={
                    "block_size": cfg.block_size,
                    "ecc_bytes": cfg.ecc_bytes,
                    "threads": cfg.threads,
                    "split_enabled": False,
                },
                progress_callback=lambda pct: emit(pct * 0.5, f"Encoding... {pct:.1f}%"),
                check_cancel=check_cancel,
                register_in_db=register_in_db,
            )

            emit(50.0, "Stitching...")
            stitch_frames(frames_dir, output_video, encoder=cfg.encoder, check_cancel=check_cancel)

            result = {
                "video_file": output_video,
                "verified": False,
                "restored_file": None,
            }

            if verify_roundtrip:
                emit(60.0, "Extracting for verification...")
                os.makedirs(verify_frames_dir, exist_ok=True)
                extract_frames(output_video, verify_frames_dir, check_cancel=check_cancel)

                restored = self.decode_source(
                    frames_dir=verify_frames_dir,
                    output_file=verify_output,
                    password=password,
                    overrides={"threads": cfg.threads},
                    progress_callback=lambda pct: emit(60.0 + (pct * 0.35), f"Verifying... {pct:.1f}%"),
                    check_cancel=check_cancel,
                )

                if self._file_md5(input_file) != self._file_md5(restored):
                    raise ValueError("Roundtrip verification failed: checksum mismatch")

                result["verified"] = True
                result["restored_file"] = restored

            emit(100.0, "Pipeline complete")
            return result
        finally:
            if auto_cleanup:
                try:
                    if os.path.isdir(frames_dir):
                        shutil.rmtree(frames_dir)
                except OSError:
                    pass
                try:
                    if os.path.isdir(verify_frames_dir):
                        shutil.rmtree(verify_frames_dir)
                except OSError:
                    pass
                try:
                    if os.path.isfile(verify_output):
                        os.remove(verify_output)
                except OSError:
                    pass
                if created_base_tmp:
                    try:
                        if os.path.isdir(base_tmp):
                            shutil.rmtree(base_tmp)
                    except OSError:
                        pass

    @staticmethod
    def _file_md5(path: str) -> str:
        md5 = hashlib.md5(usedforsecurity=False)
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(4 * 1024 * 1024), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def verify_video(self, video_path: str, max_frames: int = 5) -> Dict[str, Any]:
        if not os.path.exists(video_path):
            return {"valid": False, "reason": "Video file does not exist"}

        with tempfile.TemporaryDirectory(prefix="yotudrive_verify_") as temp_dir:
            extract_frames(video_path, temp_dir, limit=max_frames)
            decoder = Decoder(temp_dir, os.path.join(temp_dir, "unused.bin"))
            frames = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.lower().endswith(".png")]
            frames.sort()
            if not frames:
                return {"valid": False, "reason": "No frames extracted"}
            try:
                block_size, ecc_bytes, header_copies, version = decoder.detect_config(frames)
                return {
                    "valid": True,
                    "block_size": block_size,
                    "ecc_bytes": ecc_bytes,
                    "header_copies": header_copies,
                    "version": version,
                }
            except Exception as exc:
                return {"valid": False, "reason": str(exc)}

    def attach_video_reference(self, file_id: str, video_id: str, video_url: Optional[str] = None) -> bool:
        return self.db.attach_video(file_id=file_id, video_id=video_id, video_url=video_url)
