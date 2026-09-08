"""Vercel Connect token helper for Python (HTTP API).

Uses the deployment OIDC token (VERCEL_OIDC_TOKEN) to mint a short-lived
provider token. Locally, run `vercel env pull` after `vercel link`.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CONNECT_TOKEN_URL = "https://api.vercel.com/v1/connect/token/{connector}"


def oidc_token() -> str:
    return (os.getenv("VERCEL_OIDC_TOKEN") or "").strip()


def get_token(
    connector: Optional[str] = None,
    *,
    subject: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    name = (connector or "").strip()
    if not name:
        return None
    bearer = oidc_token()
    if not bearer:
        logger.info("Vercel Connect skipped: no VERCEL_OIDC_TOKEN")
        return None
    body: Dict[str, Any] = {"subject": subject or {"type": "app"}}
    req = urllib.request.Request(
        CONNECT_TOKEN_URL.format(connector=name),
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
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        logger.warning("Vercel Connect token failed (%s): %s", exc.code, detail)
        return None
    except Exception as exc:
        logger.warning("Vercel Connect token error: %s", exc)
        return None
    token = payload.get("token")
    return str(token) if token else None
