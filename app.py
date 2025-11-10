from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

BASE_DIR = Path(__file__).parent.resolve()
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "sentences.sqlite3"


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sentences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                author TEXT NOT NULL,
                created_at TEXT NOT NULL,
                client_id TEXT NOT NULL
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sentences)")}
        if "client_id" not in columns:
            conn.execute(
                "ALTER TABLE sentences ADD COLUMN client_id TEXT NOT NULL DEFAULT ''"
            )
        conn.commit()


def get_latest_sentence() -> Optional[Dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT text, author, created_at FROM sentences ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return {
            "text": row["text"],
            "author": row["author"],
            "created_at": row["created_at"],
        }


def save_sentence(sentence: str, author: str, client_id: str) -> Dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO sentences (text, author, created_at, client_id)
            VALUES (?, ?, ?, ?)
            """,
            (sentence, author, timestamp, client_id),
        )
        conn.commit()
    return {
        "text": sentence,
        "author": author,
        "created_at": timestamp,
    }


def has_submitted_today(client_id: str) -> bool:
    start_of_day = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM sentences
            WHERE client_id = ?
              AND created_at >= ?
            LIMIT 1
            """,
            (client_id, start_of_day.isoformat()),
        ).fetchone()
    return row is not None


class SentenceRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, directory: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def ensure_client_id(self) -> str:
        if hasattr(self, "_client_id"):
            return self._client_id

        cookie_header = self.headers.get("Cookie")
        client_id: Optional[str] = None

        if cookie_header:
            cookie = SimpleCookie()
            cookie.load(cookie_header)
            morsel = cookie.get("story_client_id")
            if morsel:
                client_id = morsel.value

        if not client_id:
            client_id = uuid.uuid4().hex
            self._should_set_client_cookie = True
        else:
            self._should_set_client_cookie = False

        self._client_id = client_id
        return client_id

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if getattr(self, "_should_set_client_cookie", False):
            self.send_header(
                "Set-Cookie",
                f"story_client_id={self._client_id}; Path=/; Max-Age=31536000; SameSite=Lax",
            )
        super().end_headers()

    def send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def send_json_error(self, status: HTTPStatus, message: str) -> None:
        self.send_json(status, {"error": message})

    def do_OPTIONS(self) -> None:
        self.ensure_client_id()
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        self.ensure_client_id()
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/api/sentence":
            self.handle_get_sentence()
        else:
            if parsed_path.path == "/":
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self) -> None:
        client_id = self.ensure_client_id()
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/api/sentence":
            self.handle_post_sentence(client_id)
        else:
            self.send_json_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def handle_get_sentence(self) -> None:
        payload = get_latest_sentence() or {
            "text": "Add the very first sentence to start the story!",
            "author": "System",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.send_json(HTTPStatus.OK, payload)

    def handle_post_sentence(self, client_id: str) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            self.send_json_error(HTTPStatus.BAD_REQUEST, "Empty request body")
            return

        try:
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json_error(HTTPStatus.BAD_REQUEST, "Invalid JSON payload")
            return

        sentence = (data.get("sentence") or "").strip()
        name = (data.get("name") or "").strip()
        anonymous = bool(data.get("anonymous"))
        is_test_user = not anonymous and name.upper() == "Z3US"

        if not sentence:
            self.send_json_error(HTTPStatus.BAD_REQUEST, "Sentence is required")
            return

        if not is_test_user and has_submitted_today(client_id):
            self.send_json_error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "You can only contribute one sentence per day. Please come back tomorrow!",
            )
            return

        author = "Anonymous" if anonymous or not name else name
        record = save_sentence(sentence, author, client_id)

        self.send_json(HTTPStatus.CREATED, record)


def main() -> None:
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", 8000), SentenceRequestHandler)
    print("Server running at http://localhost:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

