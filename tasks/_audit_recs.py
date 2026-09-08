"""Enumerate guest chip/query combinations and flag Court-of-MS violations."""
from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest_winelist_temp import parse_list
from data.sommelier_knowledge import (
    BODY_CUES,
    FOOD_CUES,
    PROFILE_CUES,
    parse_intent,
    sommelier_score,
    passes_color_lock,
    passes_profile,
    complementary_picks,
    wine_color,
    is_oaky_chardonnay,
    is_off_dry,
    is_full_red,
    is_lean_white,
    is_tannic,
    is_sangiovese,
    grape_family,
    is_burgundy_grand_cru,
    is_super_tuscan,
)
from restaurants.restaurant_config import MAASS_CONFIG

CATALOG = parse_list((ROOT / "data" / "winelist_temp.md").read_text(encoding="utf-8"))
OUT = ROOT / "tasks" / "_audit_out.json"

COLORS = [
    {"label": "White", "query": "white wine"},
    {"label": "Red", "query": "red wine"},
    {"label": "Rosé", "query": "rosé wine"},
    {"label": "Champagne", "query": "champagne, sparkling"},
]
PRICES = MAASS_CONFIG.price_bands
MENU = MAASS_CONFIG.load_menu()
TYPED = [
    "oaky Chardonnay from France",
    "white crisp and clean",
    "crisp and clean",
    "fruity white wine",
    "earthy red",
    "light-bodied pinot noir",
    "full-bodied cabernet",
    "something quiet",
    "bubbly",
    "dry Riesling",
    "Sancerre",
    "Barolo",
    "grand cru burgundy",
    "supertuscan red",
    "Super Tuscan",
]


def compose(parts):
    bits = [p for p in parts if p]
    extra = ", ".join(bits)
    return extra + "." if extra else ""


def price_filter(query: str):
    q = query.lower()
    m = re.search(r"between\s*\$?(\d+)\s*and\s*\$?(\d+)", q)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return min(a, b), max(a, b)
    m = re.search(r"under\s*\$?(\d+)", q)
    if m:
        return None, int(m.group(1))
    if "cellar" in q or "splurge" in q:
        return 250, None
    return None, None


def recommend(query: str):
    lo, hi = price_filter(query)

    def consider(wine, ignore_price=False):
        price = int(wine["price"])
        if not ignore_price:
            if lo is not None and price < lo:
                return None
            if hi is not None and price > hi:
                return None
        if not passes_color_lock(query, wine) or not passes_profile(query, wine):
            return None
        item = dict(wine)
        item["_score"] = sommelier_score(query, wine, base=0.0)
        if ignore_price and hi is not None:
            item["_score"] -= abs(price - hi) / 500.0
        return item

    pool = [w for w in (consider(wine) for wine in CATALOG) if w]
    if len(pool) < 2 and hi and not lo:
        pool = [w for w in (consider(wine, ignore_price=True) for wine in CATALOG) if w]
    pool.sort(key=lambda w: w["_score"], reverse=True)
    ranked = [w for w in pool if w["_score"] > -1]
    picked = complementary_picks(ranked, query=query)
    return picked


def bottle(w):
    return {
        "vintage": w.get("vintage"),
        "producer": w.get("producer"),
        "label": w.get("label"),
        "grapes": w.get("grapes"),
        "region": w.get("region"),
        "country": w.get("country"),
        "price": w.get("price"),
        "color": wine_color(w),
        "family": grape_family(w),
        "score": round(float(w.get("_score") or 0), 2),
    }


def violations(query: str, wines: list) -> list[str]:
    intent = parse_intent(query)
    q = query.lower()
    flags = []
    if len(wines) < 2:
        if "offdry" in intent.profile:
            flags.append("catalog_thin_offdry")
        elif intent.named == "burgundy_gc" and not wines:
            flags.append("catalog_thin_named")
        elif intent.named and not wines:
            flags.append("named_empty")
        else:
            flags.append("fewer_than_two")
        return flags
    colors = [wine_color(w) for w in wines]
    if "mixed" in colors:
        flags.append("mixed_color_row")
    if any("range" in str(w.get("vintage") or "").lower() or "etc" in str(w.get("label") or "").lower() for w in wines):
        flags.append("junk_list_row")
    if intent.lock_color and intent.color == "white":
        if any(c not in {"white", "sparkling", "champagne"} for c in colors):
            flags.append("white_lock_broken")
    if intent.lock_color and intent.color == "red":
        if any(c != "red" for c in colors):
            flags.append("red_lock_broken")
    if intent.lock_color and intent.color == "sparkling":
        if any(c not in {"sparkling", "champagne"} for c in colors):
            flags.append("sparkling_lock_broken")
    if intent.lock_color and intent.color == "rose":
        if any(c not in {"rose", "rosé"} for c in colors):
            flags.append("rose_lock_broken")
    if colors[0] != colors[1] and intent.lock_color:
        allowed_mix = {colors[0], colors[1]} <= {"white", "sparkling", "champagne"} and intent.color in {
            "white",
            "sparkling",
        }
        rose_ok = {colors[0], colors[1]} <= {"rose", "rosé", "sparkling"} and intent.color in {"rose", "sparkling"}
        if not allowed_mix and not rose_ok:
            flags.append("pair_color_mismatch")
    if "crisp" in intent.profile:
        if any(is_oaky_chardonnay(w) for w in wines):
            flags.append("crisp_got_oaky_chard")
        if intent.color != "red" and any(wine_color(w) == "red" for w in wines):
            flags.append("crisp_got_red")
        if intent.color == "red" and any(is_full_red(w) for w in wines):
            flags.append("crisp_red_got_full")
        if any(is_off_dry(w) for w in wines):
            flags.append("crisp_got_offdry")
    if "sancerre" in q:
        if any("sancerre" not in f"{w.get('label','')} {w.get('region','')} {w.get('major_region','')}".lower() for w in wines):
            flags.append("named_sancerre_miss")
    if "barolo" in q:
        if any("barolo" not in f"{w.get('label','')} {w.get('region','')} {w.get('major_region','')}".lower() for w in wines):
            flags.append("named_barolo_miss")
    if "grand cru" in q and "burgundy" in q:
        if wines:
            flags.append("gc_burgundy_should_be_empty")
        if any(not is_burgundy_grand_cru(w) for w in wines):
            flags.append("named_gc_burgundy_miss")
    if "super tuscan" in q or "supertuscan" in q:
        if not wines:
            flags.append("super_tuscan_empty")
        elif any(not is_super_tuscan(w) for w in wines):
            flags.append("named_super_tuscan_miss")
    if "champagne" in q:
        if any("champagne" not in f"{w.get('region','')} {w.get('major_region','')} {w.get('label','')}".lower() for w in wines):
            flags.append("named_champagne_miss")
    if "chardonnay" in q:
        for w in wines:
            blob = f"{w.get('label','')} {w.get('grapes','')} {w.get('region','')}".lower()
            if "chardonnay" not in blob and "chablis" not in blob and "puligny" not in blob and "meursault" not in blob and "montrachet" not in blob:
                flags.append("named_chardonnay_miss")
                break
    if ("france" in q or "french" in q) and "chardonnay" in q:
        if any("france" not in str(w.get("country") or "").lower() and "burgundy" not in str(w.get("region") or "").lower() for w in wines):
            flags.append("french_chard_left_france")
    if intent.food == "steak" and intent.color not in {"white", "sparkling", "rose"}:
        if any(wine_color(w) != "red" for w in wines):
            flags.append("steak_not_red")
    if intent.food in {"oysters", "branzino"} and intent.color != "red":
        if any(wine_color(w) == "red" or is_oaky_chardonnay(w) for w in wines):
            flags.append("lean_fish_got_red_or_oak")
    if intent.food == "cream":
        if any(is_tannic(w) and is_full_red(w) for w in wines):
            flags.append("cream_got_tannic_red")
    if intent.food == "tomato":
        if any(is_off_dry(w) for w in wines):
            flags.append("tomato_got_offdry")
        if intent.color not in {"white", "sparkling", "rose", "champagne"} and not any(is_sangiovese(w) for w in wines):
            flags.append("tomato_no_sangiovese")
    if "offdry" in intent.profile:
        if any(not is_off_dry(w) for w in wines):
            flags.append("offdry_got_bone_dry")
    if "fruity" in intent.profile and intent.color == "white" and "offdry" not in intent.profile:
        if any(is_off_dry(w) for w in wines):
            flags.append("fruity_white_got_moscato")
        if any(wine_color(w) not in {"white", "sparkling", "champagne"} for w in wines):
            flags.append("fruity_white_not_white")
    if intent.body == "light":
        if any(is_full_red(w) for w in wines):
            flags.append("light_got_full_red")
    return flags


def queries():
    colors = [None] + COLORS
    bodies = [None] + BODY_CUES
    profiles = [None] + PROFILE_CUES
    foods = [None] + FOOD_CUES
    prices = [None] + [p for p in PRICES if p.get("query")]
    seen = set()
    # singles + pairs + color×body×profile + color×food + typed
    for c, b, p in itertools.product(colors, bodies, profiles):
        parts = [x["query"] for x in (c, b, p) if x]
        if not parts:
            continue
        q = compose(parts)
        if q not in seen:
            seen.add(q)
            yield q, {
                "color": (c or {}).get("label"),
                "body": (b or {}).get("label"),
                "profile": (p or {}).get("label"),
            }
    for c, f in itertools.product(colors, foods):
        parts = [x["query"] for x in (c, f) if x]
        if not parts:
            continue
        q = compose(parts)
        if q not in seen:
            seen.add(q)
            yield q, {"color": (c or {}).get("label"), "food": (f or {}).get("label")}
    for f, p in itertools.product(FOOD_CUES, PROFILE_CUES):
        q = compose([f["query"], p["query"]])
        if q not in seen:
            seen.add(q)
            yield q, {"food": f["label"], "profile": p["label"]}
    for pr in prices:
        if not pr:
            continue
        q = compose([pr["query"], "red wine"])
        yield q, {"price": pr["label"], "color": "Red"}
        q = compose([pr["query"], "white wine"])
        yield q, {"price": pr["label"], "color": "White"}
    for dish in MENU:
        if dish.get("category") == "Sweets":
            continue
        q = f"to drink with {dish['name']}: {dish.get('description','')}"
        yield q, {"menu": dish["name"]}
    for q in TYPED:
        yield q, {"typed": True}


def main():
    rows = []
    fails = []
    for query, meta in queries():
        wines = recommend(query)
        flags = violations(query, wines)
        row = {
            "query": query,
            "meta": meta,
            "intent": parse_intent(query).__dict__,
            "picks": [bottle(w) for w in wines],
            "flags": flags,
        }
        rows.append(row)
        real = [f for f in flags if f not in {"catalog_thin_offdry", "catalog_thin_named"}]
        if real:
            fails.append(row)
    OUT.write_text(json.dumps({"total": len(rows), "fail": len(fails), "rows": rows, "fails": fails}, indent=2), encoding="utf-8")
    print(f"total={len(rows)} fail={len(fails)} catalog={len(CATALOG)} out={OUT}")
    by = {}
    for f in fails:
        for flag in f["flags"]:
            by[flag] = by.get(flag, 0) + 1
    for k, v in sorted(by.items(), key=lambda kv: -kv[1]):
        print(f"  {v:4d}  {k}")
    print("--- sample fails ---")
    for f in fails[:25]:
        picks = " | ".join(f"{p['producer']} {p['label']} ({p['color']})" for p in f["picks"])
        print(f"* {f['flags']} :: {f['query'][:80]} :: {picks}")


if __name__ == "__main__":
    main()
