"""Send a branded wine note to a guest."""
from __future__ import annotations

import base64
import html
import json
import logging
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)
OUTBOX = Path(__file__).resolve().parent / "outbox"


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
    price = wine.get("price") or ""
    meta = " · ".join(p for p in (region, f"${price}" if price else "") if p)
    if meta:
        lines.append(meta)
    if wine.get("why"):
        lines.append(str(wine["why"]))
    if wine.get("tasting_note"):
        lines.append(str(wine["tasting_note"]))
    if wine.get("food_pairing"):
        lines.append(f"With tonight's menu: {wine['food_pairing']}")
    return "\n".join(lines)


def build_body(restaurant_name: str, wines: List[Dict]) -> str:
    bottles = "\n\n".join(_format_wine_text(w) for w in wines)
    return (
        f"From Jarvis, your sommelier.\n\n"
        f"{bottles}\n\n"
        "Ask your server when you would like to order.\n"
        "— Jarvis · Agenthaus\n"
    )


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
        meta = html.escape(
            " · ".join(
                p
                for p in (
                    str(wine.get("region") or ""),
                    f"${wine['price']}" if wine.get("price") else "",
                )
                if p
            )
        )
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
              <p style="font-size:13px;color:#6B645C;margin:0 0 12px;">{meta}</p>
              {"<p style='font-size:15px;line-height:1.5;margin:0 0 8px;color:#1C1A16;'>" + why + "</p>" if why else ""}
              {"<p style='font-size:14px;line-height:1.55;margin:0;color:#3A3530;'>" + note + "</p>" if note else ""}
              {pair_html}
            </div>
            """
        )
    inner = "".join(cards)
    return f"""<!DOCTYPE html>
<html><body style="margin:0;background:#F3EEE6;color:#1C1A16;">
  <div style="max-width:520px;margin:0 auto;padding:32px 20px;font-family:Georgia,serif;">
    <p style="letter-spacing:.2em;text-transform:uppercase;font-size:11px;color:#7A8A78;margin:0 0 8px;">Agenthaus</p>
    <h1 style="font-size:28px;font-weight:600;margin:0 0 8px;">Jarvis</h1>
    <p style="font-size:15px;color:#6B645C;margin:0 0 24px;">Two bottles from the list, for you.</p>
    {inner}
    <p style="font-size:13px;color:#6B645C;margin:28px 0 0;">Ask your server when you would like to order.</p>
    <p style="font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#7A8A78;margin:24px 0 0;">Jarvis · Agenthaus</p>
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


def _send_via_gmail_connect(msg: EmailMessage) -> bool:
    connector = (os.getenv("CONNECT_GOOGLE") or "").strip()
    if not connector:
        return False
    from data.vercel_connect import get_token

    user = _smtp_value("SMTP_USER") or "jonathan@agenthaus.io"
    token = get_token(connector, subject={"type": "user", "id": user})
    if not token:
        token = get_token(connector, subject={"type": "app"})
    if not token:
        return False
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
                return True
    except urllib.error.HTTPError as exc:
        logger.warning("Gmail Connect send failed (%s): %s", exc.code, exc.read()[:300])
    except Exception as exc:
        logger.warning("Gmail Connect send error: %s", exc)
    return False


def send_wine_email(
    to_email: str,
    restaurant_name: str,
    wines: List[Dict],
) -> Tuple[bool, str]:
    subject = "Your wines from Jarvis"
    text = build_body(restaurant_name, wines)
    html_body = build_html(restaurant_name, wines)

    from_addr = _smtp_value("SMTP_FROM") or "Jarvis <jonathan@agenthaus.io>"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")

    if _send_via_gmail_connect(msg):
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
        return False, str(exc)
