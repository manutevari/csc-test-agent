import os
import re
import sqlite3
from datetime import datetime

import streamlit as st


PERSONAL_DATA_PATTERNS = (
    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)"),
    re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE),
    re.compile(r"\b(?:account|a/c|acct)[\s:.-]*(?:no\.?|number)?[\s:.-]*\d{9,18}\b", re.IGNORECASE),
)


def _secret(name, default=""):

    try:
        value = st.secrets.get(name, None)
    except Exception:
        value = None

    if value:
        return str(value).strip()

    return os.getenv(name, default).strip()


def _queue_path():

    configured = _secret("HITL_QUEUE_DB_PATH", "")
    if configured:
        return configured

    return os.path.join(os.path.dirname(__file__), "csc_human_review_queue.sqlite3")


def _redact(text):

    safe = text or ""
    for pattern in PERSONAL_DATA_PATTERNS:
        safe = pattern.sub("[REDACTED_PERSONAL_DATA]", safe)
    return safe


def _connect():

    path = _queue_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS human_review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            reason TEXT NOT NULL,
            confidence REAL NOT NULL,
            query TEXT NOT NULL,
            retrieved_context TEXT,
            draft_response TEXT,
            operator_note TEXT,
            resolved_at TEXT
        )
        """
    )
    return conn


def queue_human_review(query, retrieved_context="", draft_response="", reason="", confidence=0.0):

    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO human_review_queue (
                    created_at, status, reason, confidence, query, retrieved_context, draft_response
                )
                VALUES (?, 'pending', ?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    reason or "Needs human review",
                    float(confidence or 0.0),
                    _redact(query)[:4000],
                    _redact(retrieved_context)[:12000],
                    _redact(draft_response)[:8000],
                ),
            )
            return cursor.lastrowid
    except Exception:
        return None


def list_pending_reviews(limit=5):

    try:
        with _connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, created_at, reason, confidence, query, retrieved_context, draft_response
                FROM human_review_queue
                WHERE status = 'pending'
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def resolve_review(review_id, operator_note="Reviewed"):

    try:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE human_review_queue
                SET status = 'resolved', operator_note = ?, resolved_at = ?
                WHERE id = ?
                """,
                (
                    operator_note or "Reviewed",
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    int(review_id),
                ),
            )
            return True
    except Exception:
        return False
