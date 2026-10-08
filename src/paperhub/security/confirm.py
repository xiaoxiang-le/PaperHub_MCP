import hashlib
import json
import secrets
import time
from typing import Any

from paperhub.core.db import Database
from paperhub.errors import PaperHubError


def fingerprint(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


class Confirmations:
    def __init__(self, db: Database, ttl: int = 300):
        self.db, self.ttl = db, ttl

    def verify(
        self, action: str, payload: Any, token: str | None, summary: str, **preview: Any
    ) -> None:
        payload_hash = fingerprint(payload)
        now = time.time()
        with self.db.connect() as conn:
            conn.execute("DELETE FROM confirmation WHERE expires < ?", (now,))
            if token:
                token_hash = fingerprint(token)
                row = conn.execute(
                    "SELECT * FROM confirmation WHERE token_hash=?", (token_hash,)
                ).fetchone()
                if row and row["action"] == action and row["payload_hash"] == payload_hash:
                    conn.execute("DELETE FROM confirmation WHERE token_hash=?", (token_hash,))
                    return
            issued = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO confirmation VALUES(?,?,?,?)",
                (fingerprint(issued), action, payload_hash, now + self.ttl),
            )
        raise PaperHubError(
            "E_CONFIRM_REQUIRED",
            summary,
            "向用户展示预览，获得同意后携带 confirm_token 再次调用",
            confirm_token=issued,
            expires_in=self.ttl,
            preview=preview,
        )
