import json
import os
from typing import Optional


class YouTubeOAuthUploader:
    """Optional OAuth uploader integration for YouTube Data API v3."""

    def __init__(self, client_secrets_file: str = "client_secrets.json", token_file: str = "youtube_oauth_token.json"):
        self.client_secrets_file = client_secrets_file
        self.token_file = token_file

    def _load_token(self) -> Optional[dict]:
        if not os.path.exists(self.token_file):
            return None
        try:
            with open(self.token_file, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def authenticate(self):
        """Authenticate with installed-app OAuth flow and persist refreshable credentials."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:
            raise RuntimeError(
                "OAuth dependencies are not installed. Install google-auth-oauthlib and google-api-python-client."
            ) from exc

        scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        creds = None

        token_payload = self._load_token()
        if token_payload:
            creds = Credentials.from_authorized_user_info(token_payload, scopes=scopes)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_file, scopes)
            creds = flow.run_local_server(port=0)

        with open(self.token_file, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())
        return creds

    def upload_video(self, file_path: str, title: str, description: str = "", privacy_status: str = "unlisted") -> str:
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise RuntimeError(
                "YouTube API client dependencies are not installed. Install google-api-python-client."
            ) from exc

        creds = self.authenticate()
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title,
                "description": description,
            },
            "status": {
                "privacyStatus": privacy_status,
            },
        }

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True),
        )

        response = None
        while response is None:
            _, response = request.next_chunk()

        video_id = response.get("id")
        if not video_id:
            raise RuntimeError("Upload succeeded but no video id was returned")
        return video_id
