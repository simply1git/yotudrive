import os
import tempfile
import time
import unittest
from unittest.mock import patch

from app import create_app
from src.core.engine import Engine


class WebApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings_path = os.path.join(self.temp_dir.name, "settings.json")
        self.db_path = os.path.join(self.temp_dir.name, "db.json")
        engine = Engine(settings_path=self.settings_path, db_path=self.db_path)
        app = create_app(engine)
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.engine = engine

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_health_and_settings(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("ok"))

        res = self.client.get("/api/settings")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("block_size", data)

        res = self.client.put("/api/settings", json={"block_size": 4, "threads": 2})
        self.assertEqual(res.status_code, 200)
        updated = res.get_json()
        self.assertEqual(updated["block_size"], 4)

    def test_files_list_attach_delete(self):
        file_id = self.engine.db.add_file("demo.bin", "pending_upload", 123, {"frames_dir": "x"})

        res = self.client.get("/api/files")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json().get("files", [])), 1)

        res = self.client.post(f"/api/files/{file_id}/attach", json={"video_id": "abc123"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("updated"))

        res = self.client.post("/api/upload/manual/register", json={"file_id": file_id, "video_id": "xyz999"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("updated"))

        res = self.client.delete(f"/api/files/{file_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("removed"))

    def test_verify_requires_video_path(self):
        res = self.client.post("/api/verify", json={})
        self.assertEqual(res.status_code, 400)

    def test_encode_video_pipeline_job(self):
        with patch.object(self.engine, "encode_to_video", return_value={"video_file": "x.mp4", "verified": True}):
            res = self.client.post(
                "/api/pipeline/encode-video/start",
                json={"input_file": "a.bin", "output_video": "b.mp4", "verify_roundtrip": True},
            )
            self.assertEqual(res.status_code, 200)
            job_id = res.get_json().get("job_id")
            self.assertTrue(job_id)

            status = None
            for _ in range(20):
                poll = self.client.get(f"/api/jobs/{job_id}")
                self.assertEqual(poll.status_code, 200)
                status = (poll.get_json().get("job") or {}).get("status")
                if status in ("completed", "failed"):
                    break
                time.sleep(0.02)

            self.assertEqual(status, "completed")

    def test_decode_video_pipeline_job(self):
        with patch.object(self.engine, "decode_video_source", return_value={"output_file": "restored.bin"}):
            res = self.client.post(
                "/api/pipeline/decode-video/start",
                json={"video_path": "video.mp4", "output_file": "restored.bin"},
            )
            self.assertEqual(res.status_code, 200)
            job_id = res.get_json().get("job_id")
            self.assertTrue(job_id)

            status = None
            for _ in range(20):
                poll = self.client.get(f"/api/jobs/{job_id}")
                self.assertEqual(poll.status_code, 200)
                status = (poll.get_json().get("job") or {}).get("status")
                if status in ("completed", "failed"):
                    break
                time.sleep(0.02)

            self.assertEqual(status, "completed")


if __name__ == "__main__":
    unittest.main()
