"""SQLite CRM: recommendation events and email leads."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
import os
DB_PATH = Path("/tmp/crm.sqlite") if os.getenv("VERCEL") else (ROOT / "data" / "crm.sqlite")

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _lock:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS recommendations (
                    id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    restaurant_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    intro TEXT,
                    relaxed TEXT,
                    wine_ids TEXT NOT NULL,
                    wines_json TEXT NOT NULL,
                    scores_json TEXT,
                    latency_ms INTEGER,
                    channel TEXT
                );
                CREATE TABLE IF NOT EXISTS email_leads (
                    id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    restaurant_id TEXT NOT NULL,
                    recommendation_id TEXT,
                    email TEXT NOT NULL,
                    wine_ids TEXT NOT NULL,
                    wines_json TEXT NOT NULL,
                    sent INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_rec_rest_ts
                    ON recommendations(restaurant_id, ts);
                CREATE INDEX IF NOT EXISTS idx_lead_rest_ts
                    ON email_leads(restaurant_id, ts);
                """
            )
            conn.commit()
        finally:
            conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_recommendation(
    restaurant_id: str,
    query: str,
    wines: List[Dict[str, Any]],
    intro: str = "",
    relaxed: str = "",
    latency_ms: Optional[int] = None,
    channel: str = "pwa",
) -> str:
    rec_id = uuid.uuid4().hex
    wine_ids = [w.get("wine_id") for w in wines if w.get("wine_id")]
    scores = {w.get("wine_id"): w.get("score") for w in wines if w.get("wine_id")}
    public = [_public_wine(w) for w in wines]
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO recommendations
                (id, ts, restaurant_id, query, intro, relaxed, wine_ids, wines_json, scores_json, latency_ms, channel)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id,
                    _now(),
                    restaurant_id,
                    query,
                    intro or "",
                    relaxed or "",
                    json.dumps(wine_ids),
                    json.dumps(public),
                    json.dumps(scores),
                    latency_ms,
                    channel,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return rec_id


def recent_wine_keys(restaurant_id: str, limit: int = 6) -> List[str]:
    """Wine ids shown recently, so the next ask can rotate inside the same style."""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT wine_ids, wines_json FROM recommendations
                WHERE restaurant_id = ?
                ORDER BY ts DESC LIMIT ?
                """,
                (restaurant_id, limit),
            ).fetchall()
        finally:
            conn.close()
    keys: List[str] = []
    for row in rows:
        for wid in json.loads(row["wine_ids"] or "[]"):
            if wid:
                keys.append(str(wid))
        for wine in json.loads(row["wines_json"] or "[]"):
            name = wine.get("wine_name") or wine.get("label") or ""
            keys.append(
                "|".join(
                    str(x or "")
                    for x in (wine.get("producer"), name, wine.get("vintage"))
                ).lower()
            )
    return keys


def get_recommendation(rec_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM recommendations WHERE id = ?", (rec_id,)
            ).fetchone()
        finally:
            conn.close()
    return dict(row) if row else None


def log_email_lead(
    restaurant_id: str,
    email: str,
    wines: List[Dict[str, Any]],
    recommendation_id: Optional[str] = None,
    sent: bool = False,
    error: str = "",
) -> str:
    lead_id = uuid.uuid4().hex
    wine_ids = [w.get("wine_id") for w in wines if w.get("wine_id")]
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO email_leads
                (id, ts, restaurant_id, recommendation_id, email, wine_ids, wines_json, sent, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lead_id,
                    _now(),
                    restaurant_id,
                    recommendation_id or "",
                    email.strip().lower(),
                    json.dumps(wine_ids),
                    json.dumps([_public_wine(w) for w in wines]),
                    1 if sent else 0,
                    error or "",
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return lead_id


def report(restaurant_id: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    where = "WHERE restaurant_id = ?" if restaurant_id else ""
    args: List[Any] = [restaurant_id] if restaurant_id else []
    with _lock:
        conn = _connect()
        try:
            recs = conn.execute(
                f"SELECT * FROM recommendations {where} ORDER BY ts DESC LIMIT ?",
                [*args, limit],
            ).fetchall()
            leads = conn.execute(
                f"SELECT * FROM email_leads {where} ORDER BY ts DESC LIMIT ?",
                [*args, limit],
            ).fetchall()
        finally:
            conn.close()
    rec_rows = [dict(r) for r in recs]
    counts: Dict[str, int] = {}
    for row in rec_rows:
        for wine_id in json.loads(row.get("wine_ids") or "[]"):
            if wine_id:
                counts[str(wine_id)] = counts.get(str(wine_id), 0) + 1
    top = [
        {"wine_id": wine_id, "n": n}
        for wine_id, n in sorted(counts.items(), key=lambda item: -item[1])[:20]
    ]
    return {
        "recommendations": rec_rows,
        "leads": [dict(r) for r in leads],
        "top_wines": top,
    }


def _public_wine(wine: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "wine_id",
        "producer",
        "wine_name",
        "region",
        "country",
        "vintage",
        "price",
        "grapes",
        "wine_type",
        "tasting_note",
        "why",
        "food_pairing",
    )
    return {k: wine.get(k, "") for k in keys}
