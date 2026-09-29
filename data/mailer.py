"""Send a branded wine note to a guest."""
from __future__ import annotations

import base64
import html
import json
import logging
import os
import re
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)
OUTBOX = Path(__file__).resolve().parent / "outbox"
SENDER = "jonathan@agenthaus.io"
GMAIL_CONNECTOR = "gmail/jarvis-gmail"
GMAIL_SUBJECT = "ni25XOsoNbhVfcdoM2MfX3lW"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send", "email", "openid"]


def _format_wine_text(wine: Dict) -> str:
    title = " ".join(
        p
        for p in (
            str(wine.get("vintage") or ""),
            str(wine.get("producer") or ""),
            str(wine.get("wine_name") or ""),
        )
        if p
    ).strip()
    lines = [title or "Wine from the list"]
    region = wine.get("region") or ""
    if region:
        lines.append(str(region))
    if wine.get("why"):
        lines.append(str(wine["why"]))
    if wine.get("tasting_note"):
        lines.append(str(wine["tasting_note"]))
    if wine.get("food_pairing"):
        lines.append(f"With tonight's menu: {wine['food_pairing']}")
    return "\n".join(lines)


TEMPLATE = Path(__file__).resolve().parent / "email_template.txt"


def load_template() -> Tuple[str, str]:
    """Read the guest email each send, so an edit is what the next message says."""
    subject = "Your wines from Jarvis"
    fallback = (
        "{{wines}}\n\n"
        "Thank you for using our digital Sommelier,\n\n"
        "· Built by Agenthaus"
    )
    try:
        raw = TEMPLATE.read_text(encoding="utf-8")
    except OSError:
        return subject, fallback
    kept = []
    for line in raw.splitlines():
        if line.startswith("#"):
            continue
        if line.lower().startswith("subject:"):
            found = line.split(":", 1)[1].strip()
            if found:
                subject = found
            continue
        kept.append(line)
    body = "\n".join(kept).strip()
    if "{{wines}}" not in body:
        return subject, fallback
    return subject, body


def build_body(restaurant_name: str, wines: List[Dict]) -> str:
    _subject, body = load_template()
    bottles = "\n\n".join(_format_wine_text(w) for w in wines)
    return body.replace("{{wines}}", bottles)


def _copy_html(chunk: str) -> str:
    blocks = []
    for block in re.split(r"\n\s*\n", (chunk or "").strip()):
        text = block.strip()
        if not text:
            continue
        blocks.append(
            '<p style="font-size:15px;line-height:1.55;color:#6B645C;margin:0 0 16px;">'
            + html.escape(text).replace("\n", "<br>")
            + "</p>"
        )
    return "".join(blocks)


def build_html(restaurant_name: str, wines: List[Dict]) -> str:
    cards = []
    for wine in wines:
        title = html.escape(
            " ".join(
                p
                for p in (
                    str(wine.get("vintage") or ""),
                    str(wine.get("producer") or ""),
                    str(wine.get("wine_name") or ""),
                )
                if p
            ).strip()
            or "Wine from the list"
        )
        meta = html.escape(str(wine.get("region") or ""))
        why = html.escape(str(wine.get("why") or ""))
        note = html.escape(str(wine.get("tasting_note") or ""))
        pair = html.escape(str(wine.get("food_pairing") or ""))
        pair_html = (
            f'<p style="font-size:13px;color:#6B645C;margin:10px 0 0;">'
            f'<span style="letter-spacing:.12em;text-transform:uppercase;font-size:10px;color:#7A8A78;">Tonight</span><br>{pair}</p>'
            if pair
            else ""
        )
        cards.append(
            f"""
            <div style="border-top:1px solid #DDD4C8;padding:20px 0;">
              <p style="font-family:Georgia,serif;font-size:22px;margin:0 0 6px;color:#1C1A16;">{title}</p>
              {f'<p style="font-size:13px;color:#6B645C;margin:0 0 12px;">{meta}</p>' if meta else ""}
              {"<p style='font-size:15px;line-height:1.5;margin:0 0 8px;color:#1C1A16;'>" + why + "</p>" if why else ""}
              {"<p style='font-size:14px;line-height:1.55;margin:0;color:#3A3530;'>" + note + "</p>" if note else ""}
              {pair_html}
            </div>
            """
        )
    inner = "".join(cards)
    _subject, body = load_template()
    before, after = (body.split("{{wines}}", 1) + [""])[:2]
    return f"""<!DOCTYPE html>
<html><body style="margin:0;background:#F3EEE6;color:#1C1A16;">
  <div style="max-width:520px;margin:0 auto;padding:32px 20px;font-family:Georgia,serif;">
    <h1 style="font-size:28px;font-weight:600;margin:0 0 18px;">Jarvis</h1>
    {_copy_html(before)}
    {inner}
    {_copy_html(after)}
  </div>
</body></html>"""


def _smtp_value(name: str, default: str = "") -> str:
    env = (os.getenv(name) or "").strip()
    if env:
        return env
    try:
        from config import settings
        return str(getattr(settings, name.lower(), default) or default).strip()
    except Exception:
        return default


def _send_via_gmail_connect(msg: EmailMessage, oidc: str = "") -> str:
    """Return an empty string when Gmail accepted the message, otherwise why it did not."""
    connector = (os.getenv("JARVIS_GMAIL_CONNECTOR") or GMAIL_CONNECTOR).strip()
    if not connector:
        return "gmail: no connector"
    from data.vercel_connect import get_token_detail

    token, reason = get_token_detail(
        connector,
        subject={"type": "user", "id": GMAIL_SUBJECT},
        bearer=oidc,
        scopes=GMAIL_SCOPES,
    )
    if not token:
        return f"gmail: {reason}"
    raw = base64.urlsafe_b64encode(bytes(msg)).decode("ascii").rstrip("=")
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": raw}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if 200 <= resp.status < 300:
                logger.info("Sent wine email via Vercel Connect Gmail")
                return ""
        return f"gmail: HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:180].decode("utf-8", errors="replace")
        logger.warning("Gmail Connect send failed (%s): %s", exc.code, detail)
        return f"gmail: HTTP {exc.code} {detail}"
    except Exception as exc:
        logger.warning("Gmail Connect send error: %s", exc)
        return f"gmail: {_public_error(exc)}"


def _public_error(exc: Exception) -> str:
    text = str(exc)
    for name in ("SMTP_PASSWORD", "SMTP_USER", "SMTP_FROM"):
        secret = _smtp_value(name)
        if secret:
            text = text.replace(secret, "[redacted]")
    return text[:240]


def send_wine_email(
    to_email: str,
    restaurant_name: str,
    wines: List[Dict],
    oidc: str = "",
) -> Tuple[bool, str]:
    subject, _body = load_template()
    text = build_body(restaurant_name, wines)
    html_body = build_html(restaurant_name, wines)

    from_addr = f"Jarvis <{SENDER}>"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")

    gmail_reason = _send_via_gmail_connect(msg, oidc)
    if not gmail_reason:
        return True, "sent"

    host = _smtp_value("SMTP_HOST")
    if not host or not from_addr:
        try:
            OUTBOX.mkdir(parents=True, exist_ok=True)
            safe = to_email.replace("@", "_at_").replace("/", "_")
            path = OUTBOX / f"{safe}.txt"
            path.write_text(f"To: {to_email}\nSubject: {subject}\n\n{text}", encoding="utf-8")
            logger.info("SMTP not configured; wrote outbox %s", path)
        except OSError as exc:
            logger.warning("SMTP not configured and outbox is read-only: %s", exc)
        return False, "saved"

    port = int(_smtp_value("SMTP_PORT", "587") or 587)
    user = _smtp_value("SMTP_USER")
    password = _smtp_value("SMTP_PASSWORD")
    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True, "sent"
    except Exception as exc:
        logger.error("SMTP send failed: %s", exc)
        try:
            OUTBOX.mkdir(parents=True, exist_ok=True)
            safe = to_email.replace("@", "_at_").replace("/", "_")
            (OUTBOX / f"{safe}.txt").write_text(
                f"To: {to_email}\nSubject: {subject}\nError: {exc}\n\n{text}",
                encoding="utf-8",
            )
        except OSError:
            pass
        return False, f"{gmail_reason}; smtp: {_public_error(exc)}"
