"""
YotuDrive API Smoke Tests
Tests every major route group against a live Flask test client.
"""
import json
import os
import sys
import unittest
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a temporary data directory so tests don't touch real data
_TMP = tempfile.mkdtemp(prefix="yotu_test_")
os.environ["YOTU_DATA_DIR"] = _TMP

import src.auth_store as _as_mod
import src.job_store as _js_mod
import src.settings as _se_mod

# Redirect store paths to tmp
_as_mod.AUTH_FILE = os.path.join(_TMP, "auth.json")
_js_mod.JOBS_FILE = os.path.join(_TMP, "jobs.json")
_se_mod.SETTINGS_FILE = os.path.join(_TMP, "settings.json")

# Reset module singletons
_as_mod._auth_store = None
_js_mod._job_store = None
_se_mod._settings = None


class TestAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Import app after path/env setup
        from app import app
        app.config["TESTING"] = True
        cls.client = app.test_client()
        cls.admin_token = None
        cls.admin_email = "admin@test.yotu"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP, ignore_errors=True)

    # ------------------------------------------------------------------
    def _post(self, path, data=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.post(path, data=json.dumps(data or {}), headers=headers)

    def _get(self, path, token=None, params=None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = path
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{path}?{qs}"
        return self.client.get(url, headers=headers)

    def _delete(self, path, token=None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.delete(path, headers=headers)

    # ------------------------------------------------------------------
    def test_01_health(self):
        resp = self._get("/api/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("version", body)

    def test_02_bootstrap_admin(self):
        resp = self._post("/api/auth/bootstrap-admin", {"email": self.admin_email})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("bearer", body["session"])
        TestAPI.admin_token = body["session"]["bearer"]

    def test_03_bootstrap_admin_second_time_fails(self):
        resp = self._post("/api/auth/bootstrap-admin", {"email": "other@test.yotu"})
        self.assertEqual(resp.status_code, 403)

    def test_04_dev_login_admin(self):
        resp = self._post("/api/auth/dev/login", {"email": self.admin_email})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])

    def test_05_dev_login_unknown_denied(self):
        resp = self._post("/api/auth/dev/login", {"email": "nobody@test.yotu"})
        self.assertEqual(resp.status_code, 403)

    def test_06_get_session(self):
        resp = self._get("/api/auth/session", token=self.admin_token)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["user"]["email"], self.admin_email)

    def test_07_no_token_unauthorized(self):
        resp = self._get("/api/auth/session")
        self.assertEqual(resp.status_code, 401)

    def test_08_google_status(self):
        resp = self._get("/api/auth/google/status")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("configured", body)

    def test_09_add_user(self):
        resp = self._post("/api/admin/users",
                          {"email": "user1@test.yotu", "role": "member"},
                          token=self.admin_token)
        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assertEqual(body["user"]["email"], "user1@test.yotu")

    def test_10_add_duplicate_user_conflict(self):
        resp = self._post("/api/admin/users",
                          {"email": "user1@test.yotu"},
                          token=self.admin_token)
        self.assertEqual(resp.status_code, 409)

    def test_11_list_users(self):
        resp = self._get("/api/admin/users", token=self.admin_token)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertGreaterEqual(len(body["users"]), 2)

    def test_12_patch_user(self):
        resp = self.client.patch(
            "/api/admin/users/user1@test.yotu",
            data=json.dumps({"enabled": False}),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.admin_token}",
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertFalse(body["user"]["enabled"])

    def test_13_disabled_user_cannot_login(self):
        resp = self._post("/api/auth/dev/login", {"email": "user1@test.yotu"})
        self.assertEqual(resp.status_code, 403)

    def test_14_me_sessions(self):
        resp = self._get("/api/me/sessions", token=self.admin_token)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIsInstance(body["sessions"], list)

    def test_15_get_settings(self):
        resp = self._get("/api/settings")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("settings", body)
        self.assertIn("block_size", body["settings"])

    def test_16_put_settings(self):
        resp = self.client.put(
            "/api/settings",
            data=json.dumps({"block_size": 4}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["settings"]["block_size"], 4)

    def test_17_admin_metrics(self):
        resp = self._get("/api/admin/metrics", token=self.admin_token)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("users", body)
        self.assertIn("jobs", body)
        self.assertIn("files", body)

    def test_18_list_files(self):
        resp = self._get("/api/files")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("files", body)

    def test_19_verify_missing_file(self):
        resp = self._post("/api/verify", {"video_path": "/nonexistent/video.mp4"})
        self.assertEqual(resp.status_code, 404)

    def test_20_auto_join_empty_list(self):
        resp = self._post("/api/tools/auto-join", {"file_list": []})
        self.assertEqual(resp.status_code, 400)

    def test_21_encode_start_missing_params(self):
        resp = self._post("/api/encode/start", {})
        self.assertEqual(resp.status_code, 400)

    def test_22_decode_start_missing_params(self):
        resp = self._post("/api/decode/start", {})
        self.assertEqual(resp.status_code, 400)

    def test_23_logout(self):
        # Create a new session to revoke
        login = self._post("/api/auth/dev/login", {"email": self.admin_email})
        token = login.get_json()["session"]["bearer"]
        resp = self._post("/api/auth/logout", token=token)
        self.assertEqual(resp.status_code, 200)
        # Revoked token should fail
        resp2 = self._get("/api/auth/session", token=token)
        self.assertEqual(resp2.status_code, 401)

    def test_24_admin_sessions(self):
        resp = self._get("/api/admin/sessions", token=self.admin_token)
        self.assertEqual(resp.status_code, 200)

    def test_25_non_admin_cannot_access_admin_routes(self):
        # Re-enable user1 and get a token
        self.client.patch(
            "/api/admin/users/user1@test.yotu",
            data=json.dumps({"enabled": True}),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.admin_token}",
            },
        )
        login = self._post("/api/auth/dev/login", {"email": "user1@test.yotu"})
        member_token = login.get_json()["session"]["bearer"]
        resp = self._get("/api/admin/users", token=member_token)
        self.assertEqual(resp.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
