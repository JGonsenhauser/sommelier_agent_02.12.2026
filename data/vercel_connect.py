"""Vercel Connect token helper for Python (HTTP API).

Uses the deployment OIDC token (VERCEL_OIDC_TOKEN) to mint a short-lived
provider token. Locally, run `vercel env pull` after `vercel link`.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CONNECT_TOKEN_URL = "https://api.vercel.com/v1/connect/token/{connector}"


def oidc_token() -> str:
    return (os.getenv("VERCEL_OIDC_TOKEN") or "").strip()


def get_token_detail(
    connector: Optional[str] = None,
    *,
    subject: Optional[Dict[str, Any]] = None,
    bearer: Optional[str] = None,
    scopes: Optional[list] = None,
) -> tuple[Optional[str], str]:
    name = (connector or "").strip()
    if not name:
        return None, "no connector"
    bearer = (bearer or oidc_token() or "").strip()
    if not bearer:
        return None, "no bearer"
    body: Dict[str, Any] = {"subject": subject or {"type": "app"}}
    if scopes:
        body["scopes"] = scopes
    req = urllib.request.Request(
        CONNECT_TOKEN_URL.format(connector=urllib.parse.quote(name, safe="")),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:240]
        logger.warning("Vercel Connect token failed (%s): %s", exc.code, detail)
        return None, f"HTTP {exc.code} {detail}"
    except Exception as exc:
        logger.warning("Vercel Connect token error: %s", exc)
        return None, type(exc).__name__
    token = payload.get("token")
    if not token:
        return None, "empty token"
    return str(token), ""


def get_token(
    connector: Optional[str] = None,
    *,
    subject: Optional[Dict[str, Any]] = None,
    bearer: Optional[str] = None,
    scopes: Optional[list] = None,
) -> Optional[str]:
    token, _reason = get_token_detail(connector, subject=subject, bearer=bearer, scopes=scopes)
    return token
