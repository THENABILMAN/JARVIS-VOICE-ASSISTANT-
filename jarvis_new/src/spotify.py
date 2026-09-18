from __future__ import annotations

import base64
import json
import os
import threading
import time
import unicodedata
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

CLIENT_ID_ENV = "SPOTIFY_CLIENT_ID"
CLIENT_SECRET_ENV = "SPOTIFY_CLIENT_SECRET"
REDIRECT_URI = "http://127.0.0.1:8765/callback"
SCOPES = "user-read-playback-state user-modify-playback-state"
TOKEN_FILE = Path(__file__).resolve().parent.parent / ".spotify-token.json"


class SpotifyError(Exception):
    """A user-facing Spotify integration failure."""


def _request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            content = response.read()
            return json.loads(content) if content else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SpotifyError(f"Spotify API returned {exc.code}: {detail[:300]}") from exc
    except OSError as exc:
        raise SpotifyError("Spotify could not be reached.") from exc


def _credentials() -> tuple[str, str]:
    client_id = os.getenv(CLIENT_ID_ENV, "").strip()
    client_secret = os.getenv(CLIENT_SECRET_ENV, "").strip()
    if not client_id or not client_secret:
        raise SpotifyError(
            "Spotify is not configured. Add SPOTIFY_CLIENT_ID and "
            "SPOTIFY_CLIENT_SECRET to .env.local."
        )
    return client_id, client_secret


def _save_token(token: dict[str, Any]) -> None:
    TOKEN_FILE.write_text(json.dumps(token), encoding="utf-8")


def _load_token() -> dict[str, Any] | None:
    try:
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _refresh_token(token: dict[str, Any], client_id: str, client_secret: str) -> str:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urlencode(
        {"grant_type": "refresh_token", "refresh_token": token["refresh_token"]}
    ).encode()
    request = Request(
        "https://accounts.spotify.com/api/token",
        data=body,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            updated = json.loads(response.read())
    except (HTTPError, OSError) as exc:
        raise SpotifyError("Spotify authorization has expired; connect Spotify again.") from exc
    token.update(updated)
    token["expires_at"] = int(time.time()) + int(updated.get("expires_in", 3600))
    _save_token(token)
    return str(token["access_token"])


def _access_token() -> str | None:
    token = _load_token()
    if not token:
        return None
    if int(token.get("expires_at", 0)) > int(time.time()) + 60:
        return str(token["access_token"])
    client_id, client_secret = _credentials()
    return _refresh_token(token, client_id, client_secret)


def _authorization_code() -> str:
    client_id, _ = _credentials()
    state = uuid.uuid4().hex
    result: dict[str, str] = {}
    finished = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = parse_qs(urlparse(self.path).query)
            if query.get("state", [""])[0] != state:
                self.send_error(400, "Invalid OAuth state")
                return
            if query.get("error"):
                result["error"] = query["error"][0]
            else:
                result["code"] = query.get("code", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Spotify connected. You can close this window.")
            finished.set()

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 8765), CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    auth_url = "https://accounts.spotify.com/authorize?" + urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
        }
    )
    webbrowser.open(auth_url)
    if not finished.wait(timeout=180):
        server.server_close()
        raise SpotifyError("Spotify authorization timed out.")
    server.server_close()
    if result.get("error") or not result.get("code"):
        raise SpotifyError("Spotify authorization was cancelled.")
    return result["code"]


def connect() -> str:
    client_id, client_secret = _credentials()
    code = _authorization_code()
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urlencode(
        {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
    ).encode()
    request = Request(
        "https://accounts.spotify.com/api/token",
        data=body,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            token = json.loads(response.read())
    except (HTTPError, OSError) as exc:
        raise SpotifyError("Spotify authorization could not be completed.") from exc
    token["expires_at"] = int(time.time()) + int(token.get("expires_in", 3600))
    _save_token(token)
    return "Spotify is connected."


def play(query: str) -> dict[str, str]:
    query = query.strip()
    if not query:
        raise SpotifyError("Tell me the song title or artist to play.")
    _credentials()
    token = _access_token()
    if token is None:
        connect()
        token = _access_token()
    if token is None:
        raise SpotifyError("Spotify authorization did not complete.")
    headers = {"Authorization": f"Bearer {token}"}
    title, artist = _parse_track_request(query)
    search_query = _spotify_search_query(title, artist)
    results = _request_json(
        "https://api.spotify.com/v1/search?"
        + urlencode({"q": search_query, "type": "track", "limit": 10}),
        headers=headers,
    )
    tracks = results.get("tracks", {}).get("items", [])
    if not tracks:
        raise SpotifyError(f"I could not find {query!r} on Spotify.")
    track = _best_track(tracks, title, artist)
    devices = _request_json("https://api.spotify.com/v1/me/player/devices", headers=headers).get(
        "devices", []
    )
    active = next((device for device in devices if device.get("is_active")), None)
    device = active or (devices[0] if devices else None)
    if device is None:
        raise SpotifyError("Open Spotify on a device first so I have a player to control.")
    _request_json(
        "https://api.spotify.com/v1/me/player/play?" + urlencode({"device_id": device["id"]}),
        method="PUT",
        headers=headers,
        data={"uris": [track["uri"]]},
    )
    artists = ", ".join(artist["name"] for artist in track.get("artists", []))
    return {"song": track["name"], "artist": artists, "device": device["name"]}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return " ".join(
        "".join(character for character in normalized if character.isalnum() or character.isspace()).split()
    )


def _parse_track_request(query: str) -> tuple[str, str | None]:
    separator = query.casefold().find(" by ")
    if separator > 0:
        return query[:separator].strip(), query[separator + 4 :].strip()
    return query, None


def _spotify_search_query(title: str, artist: str | None) -> str:
    if artist:
        return f'track:"{title}" artist:"{artist}"'
    return title


def _best_track(
    tracks: list[dict[str, Any]], title: str, artist: str | None
) -> dict[str, Any]:
    wanted_title = _normalize(title)
    wanted_artist = _normalize(artist or "")

    def score(track: dict[str, Any]) -> tuple[int, int]:
        actual_title = _normalize(str(track.get("name", "")))
        actual_artists = _normalize(
            " ".join(item.get("name", "") for item in track.get("artists", []))
        )
        exact_title = int(actual_title == wanted_title)
        exact_artist = int(bool(wanted_artist) and wanted_artist in actual_artists)
        return exact_title + exact_artist, -len(actual_title)

    return max(tracks, key=score)
