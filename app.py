import threading
import time
import uuid
import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from flask import Flask, jsonify, render_template, request, g

from src.core.engine import Engine
from src.file_utils import auto_join_restored_files
from src.youtube import YouTubeStorage
from src.youtube_api import YouTubeOAuthUploader


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_job(self, kind: str, payload: Dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        record = {
            "id": job_id,
            "kind": kind,
            "status": "queued",
            "progress": 0.0,
            "message": "Queued",
            "result": None,
            "error": None,
            "created_at": time.time(),
            "updated_at": time.time(),
            "payload": payload,
        }
        with self._lock:
            self._jobs[job_id] = record
        return job_id

    def update(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            if job_id not in self._jobs:
                return
            self._jobs[job_id].update(updates)
            self._jobs[job_id]["updated_at"] = time.time()

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None


def create_app(engine: Optional[Engine] = None) -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    logger = logging.getLogger("yotudrive.web")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    core = engine or Engine()
    jobs = JobManager()

    def request_id() -> str:
        return getattr(g, "request_id", "")

    def ok(payload: Dict[str, Any], status: int = 200):
        body = {"ok": True, "request_id": request_id(), **payload}
        return jsonify(body), status

    def err(error_code: str, message: str, status: int = 400, details: Any = None, job_id: Optional[str] = None):
        body: Dict[str, Any] = {
            "ok": False,
            "request_id": request_id(),
            "error": {
                "error_code": error_code,
                "message": message,
            },
        }
        if details is not None:
            body["error"]["details"] = details
        if job_id:
            body["error"]["job_id"] = job_id
        return jsonify(body), status

    @app.before_request
    def bind_request_id():
        incoming = request.headers.get("X-Request-ID", "").strip()
        g.request_id = incoming or str(uuid.uuid4())

    @app.after_request
    def emit_request_id(response):
        response.headers["X-Request-ID"] = request_id()
        return response

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        logger.exception("Unhandled server error request_id=%s", request_id())
        return err("internal_error", "An internal server error occurred.", status=500)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return ok({"service": "yotudrive-web"})

    @app.get("/api/files")
    def list_files():
        return ok({"files": core.list_files()})

    @app.delete("/api/files/<file_id>")
    def delete_file(file_id: str):
        removed = core.db.remove_file(file_id)
        return ok({"removed": bool(removed)})

    @app.post("/api/files/<file_id>/attach")
    def attach_video(file_id: str):
        payload = request.get_json(silent=True) or {}
        updated = core.attach_video_reference(
            file_id=file_id,
            video_id=str(payload.get("video_id", "")).strip(),
            video_url=str(payload.get("video_url", "")).strip() or None,
        )
        return ok({"updated": updated})

    @app.post("/api/upload/manual/register")
    def register_manual_upload():
        payload = request.get_json(silent=True) or {}
        file_id = payload.get("file_id")
        video_id = str(payload.get("video_id", "")).strip()
        video_url = str(payload.get("video_url", "")).strip() or None
        if not file_id or not video_id:
            return err("validation_error", "file_id and video_id are required", status=400)

        updated = core.attach_video_reference(file_id=file_id, video_id=video_id, video_url=video_url)
        return ok({"updated": updated, "file_id": file_id, "video_id": video_id})

    @app.post("/api/upload/oauth/start")
    def oauth_upload_start():
        payload = request.get_json(silent=True) or {}
        file_path = payload.get("file_path")
        title = payload.get("title")
        description = payload.get("description") or ""
        privacy_status = payload.get("privacy_status") or "unlisted"
        file_id = payload.get("file_id")

        if not file_path or not title:
            return err("validation_error", "file_path and title are required", status=400)

        job_id = jobs.create_job("oauth-upload", payload)
        req_id = request_id()

        def run_job():
            jobs.update(job_id, status="running", message="OAuth upload started")
            try:
                uploader = YouTubeOAuthUploader()
                video_id = uploader.upload_video(
                    file_path=file_path,
                    title=title,
                    description=description,
                    privacy_status=privacy_status,
                )

                if file_id:
                    core.attach_video_reference(
                        file_id=file_id,
                        video_id=video_id,
                        video_url=f"https://www.youtube.com/watch?v={video_id}",
                    )

                jobs.update(
                    job_id,
                    status="completed",
                    progress=100.0,
                    message="OAuth upload complete",
                    result={"video_id": video_id},
                )
            except Exception as exc:
                logger.exception("OAuth upload failed request_id=%s job_id=%s", req_id, job_id)
                jobs.update(job_id, status="failed", message="OAuth upload failed", error=str(exc))

        threading.Thread(target=run_job, daemon=True).start()
        return ok({"job_id": job_id})

    @app.post("/api/youtube/playlist/inspect")
    def inspect_playlist():
        payload = request.get_json(silent=True) or {}
        playlist_url = payload.get("playlist_url")
        if not playlist_url:
            return err("validation_error", "playlist_url is required", status=400)

        yt = YouTubeStorage()
        videos = yt.get_playlist_info(playlist_url)
        return ok({"count": len(videos), "videos": videos})

    @app.get("/api/settings")
    def get_settings():
        return ok(asdict(core.get_settings()))

    @app.put("/api/settings")
    def put_settings():
        payload = request.get_json(silent=True) or {}
        updated = core.update_settings(payload)
        return ok(asdict(updated))

    @app.post("/api/verify")
    def verify_video():
        payload = request.get_json(silent=True) or {}
        video_path = payload.get("video_path")
        max_frames = int(payload.get("max_frames", 5))
        if not video_path:
            return err("validation_error", "video_path is required", status=400)
        result = core.verify_video(video_path=video_path, max_frames=max_frames)
        return ok(result)

    @app.post("/api/tools/auto-join")
    def auto_join_tool():
        payload = request.get_json(silent=True) or {}
        files = payload.get("files") or []
        auto_cleanup = bool(payload.get("auto_cleanup", True))
        if not isinstance(files, list) or not files:
            return err("validation_error", "files must be a non-empty list", status=400)
        joined = auto_join_restored_files(files, auto_cleanup=auto_cleanup)
        return ok({"files": joined})

    @app.post("/api/encode/start")
    def encode_start():
        payload = request.get_json(silent=True) or {}
        input_file = payload.get("input_file")
        output_root = payload.get("output_root")
        password = payload.get("password")
        overrides = payload.get("overrides")

        if not input_file or not output_root:
            return err("validation_error", "input_file and output_root are required", status=400)

        job_id = jobs.create_job("encode", payload)
        req_id = request_id()

        def run_job():
            jobs.update(job_id, status="running", message="Encoding started")

            def progress_cb(pct: float):
                jobs.update(job_id, progress=float(pct), message=f"Encoding {pct:.1f}%")

            try:
                result = core.encode_file(
                    input_file=input_file,
                    output_root=output_root,
                    password=password,
                    overrides=overrides,
                    progress_callback=progress_cb,
                )
                jobs.update(
                    job_id,
                    status="completed",
                    progress=100.0,
                    message="Encoding complete",
                    result={
                        "source_file": result.source_file,
                        "split": result.split,
                        "parts": [asdict(p) for p in result.parts],
                    },
                )
            except Exception as exc:
                logger.exception("Encode failed request_id=%s job_id=%s", req_id, job_id)
                jobs.update(job_id, status="failed", message="Encoding failed", error=str(exc))

        threading.Thread(target=run_job, daemon=True).start()
        return ok({"job_id": job_id})

    @app.post("/api/decode/start")
    def decode_start():
        payload = request.get_json(silent=True) or {}
        frames_dir = payload.get("frames_dir")
        output_file = payload.get("output_file")
        password = payload.get("password")
        overrides = payload.get("overrides")

        if not frames_dir or not output_file:
            return err("validation_error", "frames_dir and output_file are required", status=400)

        job_id = jobs.create_job("decode", payload)
        req_id = request_id()

        def run_job():
            jobs.update(job_id, status="running", message="Decoding started")

            def progress_cb(pct: float):
                jobs.update(job_id, progress=float(pct), message=f"Decoding {pct:.1f}%")

            try:
                restored = core.decode_source(
                    frames_dir=frames_dir,
                    output_file=output_file,
                    password=password,
                    overrides=overrides,
                    progress_callback=progress_cb,
                )
                jobs.update(
                    job_id,
                    status="completed",
                    progress=100.0,
                    message="Decoding complete",
                    result={"output_file": restored},
                )
            except Exception as exc:
                logger.exception("Decode failed request_id=%s job_id=%s", req_id, job_id)
                jobs.update(job_id, status="failed", message="Decoding failed", error=str(exc))

        threading.Thread(target=run_job, daemon=True).start()
        return ok({"job_id": job_id})

    @app.post("/api/pipeline/encode-video/start")
    def encode_video_start():
        payload = request.get_json(silent=True) or {}
        input_file = payload.get("input_file")
        output_video = payload.get("output_video")
        password = payload.get("password")
        overrides = payload.get("overrides")
        verify_roundtrip = bool(payload.get("verify_roundtrip", True))
        register_in_db = bool(payload.get("register_in_db", True))

        if not input_file or not output_video:
            return err("validation_error", "input_file and output_video are required", status=400)

        job_id = jobs.create_job("encode-video-pipeline", payload)
        req_id = request_id()

        def run_job():
            jobs.update(job_id, status="running", message="Encode-to-video pipeline started")

            def progress_cb(pct: float, message: str):
                jobs.update(job_id, progress=float(pct), message=message)

            try:
                result = core.encode_to_video(
                    input_file=input_file,
                    output_video=output_video,
                    password=password,
                    overrides=overrides,
                    verify_roundtrip=verify_roundtrip,
                    progress_callback=progress_cb,
                    register_in_db=register_in_db,
                )
                jobs.update(
                    job_id,
                    status="completed",
                    progress=100.0,
                    message="Encode-to-video pipeline complete",
                    result=result,
                )
            except Exception as exc:
                logger.exception("Encode-video pipeline failed request_id=%s job_id=%s", req_id, job_id)
                jobs.update(job_id, status="failed", message="Encode-to-video pipeline failed", error=str(exc))

        threading.Thread(target=run_job, daemon=True).start()
        return ok({"job_id": job_id})

    @app.post("/api/pipeline/decode-video/start")
    def decode_video_start():
        payload = request.get_json(silent=True) or {}
        video_path = payload.get("video_path")
        output_file = payload.get("output_file")
        password = payload.get("password")
        overrides = payload.get("overrides")

        if not video_path or not output_file:
            return err("validation_error", "video_path and output_file are required", status=400)

        job_id = jobs.create_job("decode-video-pipeline", payload)
        req_id = request_id()

        def run_job():
            jobs.update(job_id, status="running", message="Decode-video pipeline started")

            def progress_cb(pct: float, message: str):
                jobs.update(job_id, progress=float(pct), message=message)

            try:
                result = core.decode_video_source(
                    video_path=video_path,
                    output_file=output_file,
                    password=password,
                    overrides=overrides,
                    progress_callback=progress_cb,
                )
                jobs.update(
                    job_id,
                    status="completed",
                    progress=100.0,
                    message="Decode-video pipeline complete",
                    result=result,
                )
            except Exception as exc:
                logger.exception("Decode-video pipeline failed request_id=%s job_id=%s", req_id, job_id)
                jobs.update(job_id, status="failed", message="Decode-video pipeline failed", error=str(exc))

        threading.Thread(target=run_job, daemon=True).start()
        return ok({"job_id": job_id})

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id: str):
        job = jobs.get(job_id)
        if not job:
            return err("not_found", "job not found", status=404, job_id=job_id)
        return ok({"job": job})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
