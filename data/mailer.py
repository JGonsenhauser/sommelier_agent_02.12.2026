"""Send a branded wine note to a guest."""
from __future__ import annotations

import html
import logging
import smtplib
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


def send_wine_email(
    to_email: str,
    restaurant_name: str,
    wines: List[Dict],
) -> Tuple[bool, str]:
    subject = "Your wines from Jarvis"
    text = build_body(restaurant_name, wines)
    html_body = build_html(restaurant_name, wines)
    from config import settings

    host = (getattr(settings, "smtp_host", None) or "").strip()
    from_addr = (getattr(settings, "smtp_from", None) or "").strip()
    if not host or not from_addr:
        OUTBOX.mkdir(parents=True, exist_ok=True)
        safe = to_email.replace("@", "_at_").replace("/", "_")
        path = OUTBOX / f"{safe}.txt"
        path.write_text(f"To: {to_email}\nSubject: {subject}\n\n{text}", encoding="utf-8")
        logger.info("SMTP not configured; wrote outbox %s", path)
        return False, "saved"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")

    port = int(getattr(settings, "smtp_port", 587) or 587)
    user = (getattr(settings, "smtp_user", None) or "").strip()
    password = getattr(settings, "smtp_password", None) or ""
    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True, "sent"
    except Exception as exc:
        logger.error("SMTP send failed: %s", exc)
        OUTBOX.mkdir(parents=True, exist_ok=True)
        safe = to_email.replace("@", "_at_").replace("/", "_")
        (OUTBOX / f"{safe}.txt").write_text(
            f"To: {to_email}\nSubject: {subject}\nError: {exc}\n\n{text}",
            encoding="utf-8",
        )
        return False, str(exc)
