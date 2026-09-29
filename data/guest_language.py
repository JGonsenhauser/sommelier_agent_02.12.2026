"""Guest language for voice and typed asks.

The wine matcher stays in English. Replies come back in the guest's language
when that language is Portuguese, English, Spanish, French, German, or Dutch.
"""
from __future__ import annotations

import json
import re
import urllib.request

ANSWER_LANGUAGES = ("pt", "en", "es", "fr", "de", "nl")
_LANGUAGE_NAME = {
    "pt": "Portuguese",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "nl": "Dutch",
}

# Distinctive words only. Shared crumbs such as "de" and "a" are left out.
_WORDS = {
    "pt": ("um", "uma", "quero", "vinho", "branco", "encorpado", "taca", "favor", "suave", "corpo"),
    "es": ("quiero", "vino", "blanco", "copa", "pescado", "cuerpo", "busco"),
    "fr": ("voudrais", "vin", "rouge", "blanc", "verre", "viande", "poisson", "corse"),
    "de": ("mochte", "wein", "weiss", "glas", "fleisch", "fisch", "trocken", "kraftig", "rotwein"),
    "nl": ("wijn", "rode", "witte", "vlees", "vis", "droog", "graag"),
    "en": ("wine", "steak", "something", "crisp", "body", "glass", "please", "want"),
}


def _fold(text: str) -> str:
    table = str.maketrans(
        "áàâãäåéèêëíìîïóòôõöúùûüçñß",
        "aaaaaaeeeeiiiiooooouuuucns",
    )
    return (text or "").lower().translate(table)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", _fold(text)))


def detect_language(text: str) -> str:
    """Best guess among the six guest languages. English when the text is unclear."""
    tokens = _tokens(text)
    if not tokens:
        return "en"
    scores = {
        code: sum(1 for word in words if word in tokens)
        for code, words in _WORDS.items()
    }
    best = max(scores, key=scores.get)
    if scores[best] <= 0:
        return "en"
    return best


def canonical_language(code: str | None) -> str | None:
    base = (code or "").strip().lower().replace("_", "-").split("-")[0]
    if base in ANSWER_LANGUAGES:
        return base
    return None


def answer_language(code: str | None, text: str) -> str:
    """Prefer a detected speech language, then the words the guest used."""
    hinted = canonical_language(code)
    guessed = detect_language(text)
    if hinted and guessed != "en" and hinted != guessed:
        return guessed
    return hinted or guessed


def _json_object(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else raw)
    except (json.JSONDecodeError, AttributeError):
        return {}
    return data if isinstance(data, dict) else {}


def _ask(system: str, user: str, timeout: float = 6.0) -> dict:
    from api.demo_api import _guest_grok_model, _xai_key

    key = _xai_key()
    if not key:
        return {}
    from openai import OpenAI

    client = OpenAI(api_key=key, base_url="https://api.x.ai/v1", timeout=timeout, max_retries=0)
    response = client.chat.completions.create(
        model=_guest_grok_model(),
        temperature=0,
        max_tokens=800,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return _json_object((response.choices[0].message.content or "").strip())


def prepare_search(guest_text: str | None, full_query: str, language: str | None) -> tuple[str, str]:
    """Return an English search line and the language to answer in."""
    guest = (guest_text or "").strip()
    full = (full_query or "").strip()
    lang = answer_language(language, guest or full)
    if lang == "en" or not guest:
        return full, lang
    try:
        payload = _ask(
            "Rewrite the guest's wine request in English for a search. "
            "Keep grape names, prices, and place names. Do not add bottles. JSON only.",
            f'Guest language: {_LANGUAGE_NAME[lang]}.\nGuest: "{guest}"\n'
            'JSON only: {"english":"their request in English"}',
            timeout=5,
        )
    except Exception:
        return full, lang
    english = str(payload.get("english") or "").strip().strip('"')
    if not english:
        return full, lang
    if full.startswith(guest):
        return (english + full[len(guest):]).strip(), lang
    return english, lang


def localize_answer(lang: str, intro: str | None, relaxed: str | None, wines: list) -> tuple[str | None, str | None, list]:
    """Rewrite the sommelier lines. Wine choice stays as it was."""
    if lang == "en" or lang not in _LANGUAGE_NAME:
        return intro, relaxed, wines
    lines = []
    for wine in wines:
        lines.append({
            "why": wine.get("why") or "",
            "note": wine.get("tasting_note") or "",
            "pairing": wine.get("food_pairing") or "",
        })
    try:
        payload = _ask(
            f"Rewrite these sommelier lines into {_LANGUAGE_NAME[lang]}. "
            "Do not change which wines were chosen. Keep producer names, vintages, "
            "regions, dish names, and prices exactly as written. Everyday words. JSON only.",
            json.dumps({
                "intro": intro or "",
                "relaxed": relaxed or "",
                "lines": lines,
            }, ensure_ascii=False),
            timeout=8,
        )
    except Exception:
        return intro, relaxed, wines
    new_intro = str(payload.get("intro") or "").strip()
    new_relaxed = str(payload.get("relaxed") or "").strip()
    new_lines = payload.get("lines") if isinstance(payload.get("lines"), list) else []
    if new_intro:
        intro = new_intro
    if relaxed and new_relaxed:
        relaxed = new_relaxed
    elif not relaxed:
        relaxed = None
    for wine, line in zip(wines, new_lines):
        if not isinstance(line, dict):
            continue
        why = str(line.get("why") or "").strip()
        note = str(line.get("note") or "").strip()
        pairing = str(line.get("pairing") or "").strip()
        if why:
            wine["why"] = why
        if note:
            wine["tasting_note"] = note
        if pairing:
            wine["food_pairing"] = pairing
    return intro, relaxed, wines


def transcribe_audio(audio: bytes, content_type: str, filename: str) -> dict:
    """Transcribe a short clip. Language is detected by the speech model."""
    from api.demo_api import _xai_key

    key = _xai_key()
    if not key:
        raise RuntimeError("Speech is not connected.")
    boundary = "jarvis-voice-boundary"
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "", filename or "") or "guest.wav"
    mime = content_type.split(";")[0].strip() or "audio/wav"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"grok-voice-transcribe-2.0\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        "https://api.x.ai/v1/stt",
        data=head + audio + tail,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    text = str(payload.get("text") or "").strip()
    return {
        "text": text,
        "language": answer_language(str(payload.get("language") or ""), text),
    }
