"""Admin pin and session tokens.

The pin lives in a file outside this project. Setup writes it once.
After that the app only reads the file. Change the pin by editing the file.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

DEFAULT_PIN = "654321"
DEMO_PIN = "123456"
LOCK_AFTER = 8
LOCK_SECONDS = 15 * 60
SESSION_SECONDS = 12 * 60 * 60

_failures = 0
_locked_until = 0.0
_sessions: dict[str, tuple[float, bool]] = {}


def pin_file_path() -> Path:
    override = (os.getenv("JARVIS_ADMIN_PIN_FILE") or "").strip()
    if override:
        return Path(override)
    return Path.home() / ".jarvis" / "admin_pin"


def ensure_pin_file() -> Path:
    """Create the pin file on first setup. Never overwrite an existing pin."""
    path = pin_file_path()
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_PIN + "\n", encoding="utf-8")
    return path


def read_pin() -> str:
    env_pin = (os.getenv("JARVIS_ADMIN_PIN") or "").strip()
    if env_pin:
        if len(env_pin) == 6 and env_pin.isdigit():
            return env_pin
        raise ValueError("JARVIS_ADMIN_PIN must be 6 digits.")
    path = ensure_pin_file()
    raw = path.read_text(encoding="utf-8").strip().splitlines()
    pin = raw[0].strip() if raw else ""
    if len(pin) != 6 or not pin.isdigit():
        raise ValueError("Admin pin file must contain one 6-digit pin.")
    return pin


def _six_digits(pin: str) -> bool:
    return len(pin) == 6 and pin.isdigit()


def unlock(offered: str) -> tuple[str, bool]:
    """Return a session token and whether this login is the demo pin."""
    global _failures, _locked_until
    now = time.time()
    if now < _locked_until:
        raise ValueError("Too many attempts. Try again in a few minutes.")
    try:
        expected = read_pin()
    except ValueError as exc:
        raise ValueError("Admin pin file needs a 6-digit pin.") from exc
    offered = (offered or "").strip()
    demo = False
    if _six_digits(offered) and secrets.compare_digest(offered, expected):
        demo = False
    elif (
        _six_digits(offered)
        and secrets.compare_digest(offered, DEMO_PIN)
        and not secrets.compare_digest(DEMO_PIN, expected)
    ):
        demo = True
    else:
        _failures += 1
        if _failures >= LOCK_AFTER:
            _locked_until = now + LOCK_SECONDS
            _failures = 0
        raise ValueError("That pin is not right.")
    _failures = 0
    token = secrets.token_urlsafe(32)
    _sessions[token] = (now + SESSION_SECONDS, demo)
    return token, demo


def _demo_key() -> bytes:
    return read_pin().encode("utf-8")


def open_demo_session() -> str:
    """Mint a demo-only session any server can check. It cannot write the live list."""
    expires = int(time.time()) + SESSION_SECONDS
    payload = f"demo.{expires}"
    signature = hmac.new(_demo_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _signed_demo(token: str | None) -> bool:
    if not token:
        return False
    kind, sep, rest = token.partition(".")
    if kind != "demo" or not sep:
        return False
    expires, sep, signature = rest.partition(".")
    if not sep or not expires.isdigit() or int(expires) < time.time():
        return False
    payload = f"demo.{expires}"
    try:
        expected = hmac.new(_demo_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    except ValueError:
        return False
    if len(signature) != len(expected):
        return False
    return secrets.compare_digest(signature, expected)


def session_ok(token: str | None) -> bool:
    if _signed_demo(token):
        return True
    if not token:
        return False
    row = _sessions.get(token)
    if not row or row[0] < time.time():
        _sessions.pop(token, None)
        return False
    return True


def session_is_demo(token: str | None) -> bool:
    if _signed_demo(token):
        return True
    if not session_ok(token):
        return False
    return bool(_sessions[token][1])


def drop_session(token: str | None) -> None:
    if token:
        _sessions.pop(token, None)
