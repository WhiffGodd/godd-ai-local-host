"""Per-browser YouTube authorization and resumable video uploads."""

import hmac
import os
import re
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit

import requests


CALLBACK_PATH = "/api/youtube/callback"
SESSION_AGE = 86400
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_URL = "https://www.googleapis.com/youtube/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPES = ("https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly")
CHUNK_BYTES = 4 * 1024 * 1024


class YouTubeUploadError(RuntimeError):
    """A message safe to return to the uploader."""


def upload_metadata(payload):
    title = payload.get("title")
    description = payload.get("description", "")
    privacy = payload.get("privacy", "private")
    kids = payload.get("made_for_kids")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100 or re.search(r"[<>\r\n]", title):
        raise ValueError("Enter a YouTube title between 1 and 100 characters without angle brackets.")
    if not isinstance(description, str) or len(description.encode("utf-8")) > 5000 or re.search(r"[<>]", description):
        raise ValueError("Enter a YouTube description under 5,000 bytes without angle brackets.")
    if privacy not in ("private", "unlisted", "public"):
        raise ValueError("Choose Private, Unlisted or Public.")
    if type(kids) is not bool:
        raise ValueError("Choose whether this clip is made for kids.")
    return {"snippet": {"title": title.strip(), "description": description, "categoryId": "22"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": kids}}


class YouTubeConnections:
    def __init__(self):
        self.client_id = os.environ.get("YOUTUBE_OAUTH_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.environ.get("YOUTUBE_OAUTH_REDIRECT_URI", "").strip()
        try:
            uri = urlsplit(self.redirect_uri)
        except ValueError:
            uri = urlsplit("")
        valid_scheme = uri.scheme == "https" or (
            uri.scheme == "http" and uri.hostname in ("localhost", "127.0.0.1", "::1"))
        self.enabled = bool(self.client_id and self.client_secret and valid_scheme and uri.netloc
                            and not (uri.username or uri.password or uri.query or uri.fragment)
                            and uri.path == CALLBACK_PATH)
        self.origin = f"{uri.scheme}://{uri.netloc}" if self.enabled else ""
        self.sessions = {}
        self.lock = threading.Lock()

    def begin(self, session_id, ai_studio=False):
        with self.lock:
            now = time.monotonic()
            for key, session in list(self.sessions.items()):
                if now >= session["expires"]:
                    del self.sessions[key]
            if (ai_studio, session_id) not in self.sessions:
                if len(self.sessions) >= 128:
                    raise YouTubeUploadError("Too many YouTube connections. Please try again later.")
                session_id = secrets.token_urlsafe(32)
            state = ("ai." if ai_studio else "") + secrets.token_urlsafe(32)
            self.sessions[ai_studio, session_id] = {"expires": now + SESSION_AGE, "state": state, "state_expires": now + 600}
        params = {"client_id": self.client_id, "redirect_uri": self.redirect_uri,
                  "response_type": "code", "scope": " ".join(SCOPES), "state": state,
                  "access_type": "offline", "prompt": "consent select_account"}
        return session_id, "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)

    def _session(self, session_id, ai_studio):
        session = self.sessions.get((ai_studio, session_id))
        if session and time.monotonic() < session["expires"]:
            return session
        return None

    def _token(self, **params):
        try:
            response = requests.post(TOKEN_URL, data={**params, "client_id": self.client_id,
                                                       "client_secret": self.client_secret}, timeout=15)
            response.raise_for_status()
            data = response.json()
            return {"access": data["access_token"], "refresh": data.get("refresh_token"),
                    "token_expires": time.monotonic() + int(data.get("expires_in", 3600))}
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            raise YouTubeUploadError("YouTube authorization expired or failed. Connect your channel again.") from error

    def complete(self, session_id, state, code, *, ai_studio=False):
        with self.lock:
            session = self._session(session_id, ai_studio)
            if not session or time.monotonic() >= session["state_expires"] or not hmac.compare_digest(
                    session.get("state", "").encode(), state.encode()) or not state:
                raise YouTubeUploadError("This sign-in link expired. Return to the studio and connect again.")
            del session["state"]
        if not code:
            raise YouTubeUploadError("YouTube sign-in was cancelled. Return to the studio to try again.")
        token = self._token(grant_type="authorization_code", code=code, redirect_uri=self.redirect_uri)
        try:
            response = requests.get(API_URL + "/channels", params={"part": "snippet", "mine": "true"},
                                    headers={"Authorization": f"Bearer {token['access']}"}, timeout=15)
            response.raise_for_status()
            items = response.json()["items"]
            if not items:
                raise YouTubeUploadError("This Google account has no YouTube channel. Choose an account with a channel.")
            if len(items) != 1:
                raise YouTubeUploadError("Select a single YouTube channel during Google sign-in.")
            channel = {"id": items[0]["id"], "title": items[0]["snippet"]["title"]}
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            raise YouTubeUploadError("Could not find your YouTube channel. Check the account you selected.") from error
        with self.lock:
            if self._session(session_id, ai_studio) is not session:
                raise YouTubeUploadError("This sign-in session expired. Connect again from the studio.")
            session.update(token, channel=channel)

    def channel(self, session_id, *, ai_studio=False):
        with self.lock:
            return (self._session(session_id, ai_studio) or {}).get("channel")

    def disconnect(self, session_id, *, ai_studio=False):
        with self.lock:
            # Revoking the shared Google project grant would also revoke the other studio.
            self.sessions.pop((ai_studio, session_id), None)

    def access_token(self, session_id, channel_id, *, ai_studio=False):
        with self.lock:
            session = self._session(session_id, ai_studio)
            if not session or session.get("channel", {}).get("id") != channel_id:
                raise YouTubeUploadError("Connect the original YouTube channel again before uploading.")
            if time.monotonic() + 60 < session["token_expires"]:
                return session["access"]
            refresh = session.get("refresh")
        if not refresh:
            raise YouTubeUploadError("YouTube authorization expired. Disconnect and reconnect your channel.")
        token = self._token(grant_type="refresh_token", refresh_token=refresh)
        with self.lock:
            if self._session(session_id, ai_studio) is not session:
                raise YouTubeUploadError("The YouTube channel was disconnected.")
            token["refresh"] = token["refresh"] or refresh
            session.update(token)
            return session["access"]


def _upload_error(response):
    try:
        reason = response.json()["error"]["errors"][0]["reason"]
    except (ValueError, KeyError, IndexError, TypeError):
        reason = ""
    if response.status_code == 401:
        return YouTubeUploadError("YouTube authorization expired. Disconnect and reconnect your channel.")
    if reason in ("quotaExceeded", "dailyLimitExceeded", "uploadLimitExceeded"):
        return YouTubeUploadError("YouTube's upload limit has been reached. Try again later.")
    if response.status_code == 403:
        return YouTubeUploadError("YouTube denied the upload. Check your channel permissions and API setup.")
    return YouTubeUploadError(f"YouTube could not finish the upload (HTTP {response.status_code}). Check YouTube Studio before retrying.")


def set_video_thumbnail(video_id, token, image, wait_seconds=120):
    """Wait for Shorts processing before setting the thumbnail on the existing upload."""
    auth = {"Authorization": f"Bearer {token}"}
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        try:
            response = requests.get(API_URL + "/videos",
                                    params={"part": "processingDetails", "id": video_id},
                                    headers=auth, timeout=10)
            if response.status_code == 200:
                items = response.json().get("items", [])
                status = items[0].get("processingDetails", {}).get("processingStatus") if items else None
                if status == "succeeded":
                    upload = requests.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
                                           params={"videoId": video_id, "uploadType": "media"},
                                           headers={**auth, "Content-Type": "image/jpeg"},
                                           data=image, timeout=20, allow_redirects=False)
                    if upload.ok:
                        return None
                    if upload.status_code == 403:
                        return "YouTube did not allow a custom thumbnail on this channel. Check thumbnail eligibility in YouTube Studio."
                    if upload.status_code < 500 and upload.status_code != 429:
                        return "YouTube declined the thumbnail. You can add the JPG in YouTube Studio."
                elif status in ("failed", "terminated"):
                    return "YouTube could not finish processing the video. Check YouTube Studio."
            elif response.status_code < 500 and response.status_code != 429:
                return "Could not check processing status. You can add the thumbnail in YouTube Studio."
        except (requests.RequestException, ValueError):
            pass
        time.sleep(min(6, max(0, deadline - time.monotonic())))
    return "YouTube was still processing the video. You can add the thumbnail in YouTube Studio when it finishes."


def upload_video(path, token, metadata):
    """Resume within the same Google upload session after a network error."""
    total = os.path.getsize(path)
    if not total:
        raise YouTubeUploadError("The rendered clip is empty.")
    auth = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
                                 headers={**auth, "X-Upload-Content-Type": "video/mp4",
                                          "X-Upload-Content-Length": str(total)}, json=metadata,
                                 timeout=(10, 30), allow_redirects=False)
    except requests.RequestException as error:
        raise YouTubeUploadError("Could not start the YouTube upload. Please try again.") from error
    if response.status_code not in (200, 201):
        raise _upload_error(response)
    location = response.headers.get("Location", "")
    parsed = urlsplit(location)
    if parsed.scheme != "https" or parsed.netloc not in ("www.googleapis.com", "upload.youtube.com"):
        raise YouTubeUploadError("YouTube did not return a valid upload session.")

    offset, failures, probe = 0, 0, False
    with open(path, "rb") as video:
        while failures < 4:
            video.seek(offset)
            chunk = b"" if probe else video.read(CHUNK_BYTES)
            content_range = f"bytes {offset}-{offset + len(chunk) - 1}/{total}" if chunk else f"bytes */{total}"
            try:
                response = requests.put(location, data=chunk,
                                        headers={**auth, "Content-Type": "video/mp4", "Content-Range": content_range,
                                                 "Content-Length": str(len(chunk))},
                                        timeout=(10, 60), allow_redirects=False)
            except requests.RequestException:
                response = None
            if response is not None and response.status_code in (200, 201):
                try:
                    uploaded = response.json()
                    video_id = uploaded["id"]
                    if re.fullmatch(r"[\w-]{11}", video_id, flags=re.ASCII):
                        return {"video_id": video_id,
                                "privacy": uploaded.get("status", {}).get("privacyStatus", "unknown")}
                except (ValueError, KeyError, TypeError):
                    pass
                raise YouTubeUploadError("YouTube accepted the upload. Check YouTube Studio for the new clip.")
            if response is not None and response.status_code == 308:
                received = re.fullmatch(r"bytes=0-(\d+)", response.headers.get("Range", ""))
                next_offset = int(received[1]) + 1 if received else 0
                if next_offset > total:
                    break
                failures = 0 if next_offset > offset else failures + 1
                offset, probe = next_offset, next_offset == total
                continue
            if response is not None and response.status_code < 500 and response.status_code != 429:
                raise _upload_error(response)
            failures += 1
            probe = True
            retry_after = response.headers.get("Retry-After", "") if response is not None else ""
            time.sleep(min(20, int(retry_after)) if retry_after.isdigit() else 2 ** failures)
    raise YouTubeUploadError("The upload was interrupted. Check YouTube Studio before retrying to avoid duplicates.")
