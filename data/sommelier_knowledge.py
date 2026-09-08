"""Court-of-Master-Sommeliers style intent, with guest-plain language.

Tap chips and free text both parse into the same GuestIntent, so
'Dry & crisp' on a button is identical to typing 'crisp and clean'.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

CRISP_WORDS = (
    "crisp", "clean", "fresh", "zesty", "zippy", "bright", "mineral", "steely",
    "flinty", "linear", "taut", "racy", "saline", "citrus", "lemon", "lime",
    "green apple", "snappy", "piercing", "electric", "unoaked", "no oak",
    "not oaky", "not buttery", "bone dry", "bone-dry", "dry and crisp",
    "dry & crisp",
)
RICH_WHITE_WORDS = (
    "buttery", "oaky", "creamy", "toasty", "vanilla", "tropical",
    "opulent", "rich chardonnay",
)
LIGHT_BODY_WORDS = ("light-bodied", "light bodied", "light body")
MEDIUM_BODY_WORDS = ("medium-bodied", "medium bodied", "medium body")
FULL_BODY_WORDS = ("full-bodied", "full bodied", "full body")

LEAN_WHITE_REGIONS = (
    "chablis", "sancerre", "pouilly", "muscadet", "rias baixas", "albarino",
    "albariño", "alto adige", "alsace", "vouvray", "menetou",
    "quincy", "valdeorras", "santorini", "txakoli", "vinho verde",
    "finger lakes", "clare valley", "mosel", "saar", "ruwer", "wagram",
    "soave", "castelli di jesi", "matelica", "gavi", "etna", "campania",
    "marche", "umbria", "liguria", "gallura",
)
LEAN_WHITE_GRAPES = (
    "sauvignon", "pinot gris", "pinot grigio", "arneis", "riesling",
    "albariño", "albarino", "muscadet", "melon", "assyrtiko", "gruner",
    "grüner", "vermentino", "aligote", "aligoté", "glera",
    "garganega", "soave", "verdicchio", "pecorino", "cortese", "gavi",
    "fiano", "falanghina", "greco", "carricante", "trebbiano", "kerner",
    "silvaner", "grüner veltliner",
)
MED_LEAN_WHITES = (
    "soave", "garganega", "verdicchio", "vermentino", "pecorino", "gavi",
    "cortese", "arneis", "fiano", "falanghina", "greco", "carricante",
    "etna", "pigato",
)
OAKY_CHARD_PRODUCERS = (
    "kistler", "aubert", "rombauer", "cakebread", "ramey", "kongsgaard",
    "peter michael", "lewis", "far niente", "grgich",
)
OAKY_CHARD_REGIONS = (
    "napa", "sonoma coast", "sonoma", "russian river", "carneros",
    "knights valley", "oakville",
)
LIGHT_RED_MARKERS = (
    "pinot noir", "gamay", "beaujolais", "willamette", "dundee", "eola",
    "volnay", "chambolle", "sancerre rouge", "valpolicella classico",
)
FULL_RED_MARKERS = (
    "cabernet", "syrah", "shiraz", "malbec", "nebbiolo", "barolo",
    "barbaresco", "brunello", "sangiovese grosso", "zinfandel", "amarone",
    "pauillac", "saint-julien", "saint-estèphe", "margaux", "napa",
    "opus", "dominus",
)
EARTHY_MARKERS = (
    "burgundy", "chablis", "barolo", "barbaresco", "nebbiolo", "rioja",
    "gevreys", "morey", "nuits", "vosne", "chambolle", "volnay",
    "piedmont", "loire", "sancerre", "syrah", "cote-rotie", "côte-rôtie",
    "hermitage", "willamette", "eyrie",
)
FRUITY_MARKERS = (
    "zinfandel", "malbec", "moscato", "mclaren", "barossa", "caymus",
    "geyserville", "paso", "nuevo", "primitivo", "beaujolais", "dolcetto",
    "new zealand", "napa", "sonoma", "mendoza",
)
OFFDRY_MARKERS = (
    "moscato", "muscat", "d'asti", "brachetto", "late harvest", "spätlese",
    "spatlese", "kabinett", "demi-sec", "off-dry", "auslese", "gewurz",
    "gewürz",
)

# Chip copy a guest sees → the phrase the engine parses
BODY_CUES = [
    {"label": "Light", "query": "light-bodied"},
    {"label": "Medium", "query": "medium-bodied"},
    {"label": "Full", "query": "full-bodied"},
]
PROFILE_CUES = [
    {"label": "Fruity", "query": "fruity profile"},
    {"label": "Earthy", "query": "earthy profile"},
    {"label": "Dry & crisp", "query": "dry and crisp"},
    {"label": "Off-dry", "query": "off-dry"},
]
FOOD_CUES = [
    {"label": "Oysters", "query": "to drink with oysters"},
    {"label": "Steak", "query": "to drink with steak"},
    {"label": "Chicken", "query": "to drink with roast chicken"},
    {"label": "Branzino", "query": "to drink with branzino"},
    {"label": "Cream sauce", "query": "to drink with cream sauce"},
    {"label": "Tomato sauce", "query": "to drink with tomato sauce"},
    {"label": "Hard cheese", "query": "to drink with hard cheese"},
    {"label": "Soft cheese", "query": "to drink with soft cheese"},
]


@dataclass
class GuestIntent:
    color: Optional[str] = None
    lock_color: bool = False
    body: Optional[str] = None  # light, medium, full
    lock_body: bool = False
    oak: Optional[str] = None
    profile: List[str] = field(default_factory=list)
    lock_profile: bool = False
    food: Optional[str] = None
    raw: str = ""


def parse_intent(query: str) -> GuestIntent:
    q = (query or "").lower()
    intent = GuestIntent(raw=query or "")

    if any(w in q for w in ("champagne", "sparkling", "bubbly", "prosecco", "cava", "crémant", "cremant")):
        intent.color = "sparkling"
        intent.lock_color = True
    elif "rosé" in q or re.search(r"\brose\b", q):
        intent.color = "rose"
        intent.lock_color = True
    elif re.search(r"\bwhite\b", q) or "chardonnay" in q or "chablis" in q:
        intent.color = "white"
        intent.lock_color = True
    elif re.search(r"\bred\b", q):
        intent.color = "red"
        intent.lock_color = True

    if any(w in q for w in LIGHT_BODY_WORDS):
        intent.body = "light"
        intent.lock_body = True
    elif any(w in q for w in FULL_BODY_WORDS):
        intent.body = "full"
        intent.lock_body = True
    elif any(w in q for w in MEDIUM_BODY_WORDS):
        intent.body = "medium"
        intent.lock_body = True

    if "off-dry" in q or "off dry" in q:
        intent.profile.append("offdry")
        intent.lock_profile = True
        if intent.color is None:
            intent.color = "white"
            intent.lock_color = True
    if "fruity profile" in q or re.search(r"\bfruity\b", q):
        intent.profile.append("fruity")
        intent.lock_profile = True
    if "earthy profile" in q or re.search(r"\bearthy\b", q):
        intent.profile.append("earthy")
        intent.lock_profile = True

    crisp = any(w in q for w in CRISP_WORDS)
    if crisp:
        intent.profile.append("crisp")
        intent.lock_profile = True
        if intent.body is None:
            intent.body = "light"
        intent.oak = "none"
        if intent.color is None:
            intent.color = "white"
            intent.lock_color = True

    rich_white = any(w in q for w in RICH_WHITE_WORDS)
    if rich_white:
        intent.profile.append("rich_white")
        if intent.body is None:
            intent.body = "full"
        intent.oak = "new"
        if intent.color is None:
            intent.color = "white"
        intent.lock_color = True

    if any(w in q for w in ("oyster", "oysters")):
        intent.food = "oysters"
        if intent.color is None:
            intent.color = "white"
            intent.lock_color = True
        if intent.body is None:
            intent.body = "light"
    elif "branzino" in q or "sea bass" in q:
        intent.food = "branzino"
        if intent.color is None:
            intent.color = "white"
            intent.lock_color = True
        if intent.body is None:
            intent.body = "light"
    elif "steak" in q or "strip" in q:
        intent.food = "steak"
        if intent.color is None:
            intent.color = "red"
            intent.lock_color = True
        if intent.body is None:
            intent.body = "full"
    elif "cream sauce" in q or "cream" in q and "sauce" in q:
        intent.food = "cream"
        if intent.body is None:
            intent.body = "medium"
    elif "tomato sauce" in q or "tomato" in q:
        intent.food = "tomato"
        if intent.color is None:
            intent.color = "red"
            intent.lock_color = True
    elif "hard cheese" in q:
        intent.food = "hard_cheese"
    elif "soft cheese" in q:
        intent.food = "soft_cheese"
        if intent.color is None:
            intent.color = "white"
            intent.lock_color = True
    elif "chicken" in q:
        intent.food = "chicken"

    if intent.food is None:
        cooked = cook_profile_from_text(q)
        if cooked:
            intent.food = cooked
            if cooked in {"oysters", "branzino"} and intent.color is None:
                intent.color = "white"
                intent.lock_color = True
            if cooked == "steak" and intent.color is None:
                intent.color = "red"
                intent.lock_color = True
            if cooked == "tomato" and intent.color is None:
                intent.color = "red"
                intent.lock_color = True
            if cooked == "soft_cheese" and intent.color is None:
                intent.color = "white"
                intent.lock_color = True

    if re.search(r"\bpinot noir\b", q) and intent.color is None:
        intent.color = "red"
        if intent.body is None:
            intent.body = "light"

    # Deduplicate profile tags, keep order
    seen = set()
    intent.profile = [p for p in intent.profile if not (p in seen or seen.add(p))]
    return intent


def cook_profile_from_text(text: str) -> Optional[str]:
    """Map a menu dish (name + description) onto a pairing family."""
    t = (text or "").lower()
    if any(w in t for w in ("oyster", "oysters")):
        return "oysters"
    if any(w in t for w in ("chowder", "cream sauce", "cream", "bacon", "brioche")) and any(
        w in t for w in ("cod", "fish", "sauce", "chowder", "pasta", "tagliatelle")
    ):
        return "cream"
    if any(w in t for w in ("bordelaise", "strip", "steak", "beef tartare", "lamb")):
        return "steak"
    if any(w in t for w in ("tomato", "marinara", "pomodoro")):
        return "tomato"
    if any(w in t for w in ("burrata", "stracciatella", "brie", "burrata")):
        return "soft_cheese"
    if any(w in t for w in ("parmesan", "pecorino", "comte", "comté", "cheddar", "grana")):
        return "hard_cheese"
    if any(w in t for w in (
        "branzino", "crudo", "crudo", "yellowtail", "sea bass", "orata",
        "sole", "dover", "citrus", "olive oil", "grilled fish",
    )):
        return "branzino"
    if "chicken" in t:
        return "chicken"
    return None


def grape_family(wine: Dict) -> str:
    blob = _blob(wine)
    grapes = str(wine.get("grapes") or "").lower()
    hay = blob + " " + grapes
    if wine_color(wine) in {"sparkling", "champagne"} or "champagne" in hay:
        return "sparkling"
    if any(m in hay for m in MED_LEAN_WHITES):
        return "italian_lean"
    if "chablis" in hay or ("chardonnay" in hay and is_lean_white(wine)):
        return "chard_lean"
    if "chardonnay" in hay:
        return "chard_rich"
    if "sauvignon" in hay or "sancerre" in hay:
        return "sauvignon"
    if "pinot gris" in hay or "pinot grigio" in hay:
        return "gris"
    if "riesling" in hay:
        return "riesling"
    if "albari" in hay:
        return "albarino"
    if "muscadet" in hay:
        return "muscadet"
    if "pinot" in hay:
        return "pinot"
    if "sangiovese" in hay or "chianti" in hay:
        return "sangiovese"
    if "nebbiolo" in hay or "barolo" in hay:
        return "nebbiolo"
    if "cabernet" in hay:
        return "cabernet"
    return (grapes or hay)[:24]


def wine_key(wine: Dict) -> str:
    name = wine.get("wine_name") or wine.get("label") or ""
    return "|".join(
        str(x or "")
        for x in (wine.get("producer"), name, wine.get("vintage"))
    ).lower()


def complementary_picks(
    ranked: List[Dict],
    seen_ids: Optional[List[str]] = None,
    band: float = 2.0,
    query: str = "",
) -> List[Dict]:
    """Textbook first bottle, then a partner that stays on the same ask.

    If they named a grape (Chardonnay), stay on that grape with a different
    producer. Otherwise pick a different grape in the same color.
    """
    if not ranked:
        return []
    seen = set()
    for item in seen_ids or []:
        if isinstance(item, (list, tuple)):
            seen.update(str(x).lower() for x in item if x)
        elif item:
            seen.add(str(item).lower())
    score_of = lambda w: float(w.get("_score") if w.get("_score") is not None else w.get("score") or 0)
    top = score_of(ranked[0])
    banded = [w for w in ranked if score_of(w) >= top - band] or ranked[:6]

    def unseen(seq):
        return [w for w in seq if wine_key(w) not in seen and str(w.get("wine_id") or "") not in seen]

    pool = unseen(banded) or banded
    first = pool[0]
    fam = grape_family(first)
    first_color = wine_color(first)
    rest = [w for w in pool if wine_key(w) != wine_key(first)]
    same_color = [w for w in rest if wine_color(w) == first_color and wine_color(w) != "mixed"]
    q = (query or "").lower()
    named = None
    for needle, family in (
        ("chardonnay", "chard"),
        ("pinot noir", "pinot"),
        ("sauvignon", "sauvignon"),
        ("riesling", "riesling"),
        ("pinot gris", "gris"),
        ("malbec", "malbec"),
        ("cabernet", "cabernet"),
    ):
        if needle in q:
            named = family
            break
    if named:
        same_grape = [w for w in same_color if named in grape_family(w) or named in _blob(w)]
        if not same_grape:
            same_grape = [w for w in unseen(ranked) if wine_key(w) != wine_key(first) and wine_color(w) == first_color and (named in grape_family(w) or named in _blob(w))]
        if same_grape:
            return [first, same_grape[0]]
    second = next((w for w in same_color if grape_family(w) != fam), None)
    if second is None and same_color:
        second = same_color[0]
    return [first] + ([second] if second else [])


def menu_dish_cues(menu: List[Dict]) -> List[Dict[str, str]]:
    """Tonight chips from an uploaded menu, with the dish text so pairing can adapt."""
    cues = []
    skip = {"sweets", "dessert", "pastry"}
    for dish in menu or []:
        cat = str(dish.get("category") or "").lower()
        if cat in skip:
            continue
        name = (dish.get("name") or "").strip()
        if not name:
            continue
        desc = (dish.get("description") or "").strip()
        cues.append({
            "label": name,
            "query": f"to drink with {name}: {desc}".strip(": "),
        })
    return cues


def _blob(wine: Dict) -> str:
    return " ".join(
        str(wine.get(k) or wine.get("metadata", {}).get(k) or "")
        for k in (
            "producer", "wine_name", "label", "grapes", "region",
            "major_region", "country", "wine_type", "wine_style", "text",
        )
    ).lower()


_RED_GRAPES = (
    "cabernet sauvignon", "pinot noir", "nebbiolo", "sangiovese", "malbec",
    "syrah", "shiraz", "zinfandel", "merlot", "tempranillo",
)
_WHITE_GRAPES = (
    "chardonnay", "sauvignon blanc", "pinot gris", "pinot grigio", "arneis",
    "riesling", "viognier", "verdicchio", "garganega", "soave", "vermentino",
    "gavi", "cortese", "fiano", "albari", "chenin", "moscato", "semillon",
)


def wine_color(wine: Dict) -> str:
    grapes = str(wine.get("grapes") or "").lower()
    label = str(wine.get("wine_name") or wine.get("label") or "").lower()
    blob = grapes + " " + label
    has_red = any(g in blob for g in _RED_GRAPES)
    has_white = any(g in blob for g in _WHITE_GRAPES)
    if has_red and has_white:
        return "mixed"
    if has_red and "blanc" not in blob:
        return "red"
    if has_white and "pinot noir" not in blob:
        return "white"
    return str(
        wine.get("wine_style") or wine.get("wine_type") or
        (wine.get("metadata") or {}).get("wine_style") or
        (wine.get("metadata") or {}).get("wine_type") or ""
    ).lower()


def is_oaky_chardonnay(wine: Dict) -> bool:
    blob = _blob(wine)
    grapes = str(wine.get("grapes") or "").lower()
    if "chardonnay" not in grapes and "chardonnay" not in blob:
        return False
    if "chablis" in blob or "mâcon" in blob or "macon" in blob:
        return False
    if any(p in blob for p in OAKY_CHARD_PRODUCERS):
        return True
    if any(r in blob for r in OAKY_CHARD_REGIONS):
        return True
    if any(r in blob for r in ("meursault", "puligny")):
        return True
    if "california" in blob or "napa" in blob or "sonoma" in blob:
        return True
    return False


def is_lean_white(wine: Dict) -> bool:
    blob = _blob(wine)
    grapes = str(wine.get("grapes") or "").lower()
    if wine_color(wine) not in {"white", "sparkling", "champagne"}:
        return False
    if "chablis" in blob:
        return True
    if any(g in grapes or g in blob for g in LEAN_WHITE_GRAPES):
        return True
    if any(r in blob for r in LEAN_WHITE_REGIONS):
        return True
    if "mâcon" in blob or "macon" in blob or "saint-aubin" in blob or "st-aubin" in blob:
        return True
    return False


def is_light_red(wine: Dict) -> bool:
    if wine_color(wine) != "red":
        return False
    blob = _blob(wine)
    if any(m in blob for m in FULL_RED_MARKERS) and "pinot" not in blob:
        return False
    return any(m in blob for m in LIGHT_RED_MARKERS) or "pinot" in blob


def is_full_red(wine: Dict) -> bool:
    if wine_color(wine) != "red":
        return False
    blob = _blob(wine)
    if "pinot noir" in blob or "pinot" in str(wine.get("grapes") or "").lower():
        if not any(m in blob for m in ("napa", "cabernet")):
            return False
    return any(m in blob for m in FULL_RED_MARKERS)


def is_off_dry(wine: Dict) -> bool:
    blob = _blob(wine)
    return any(m in blob for m in OFFDRY_MARKERS)


def is_earthy(wine: Dict) -> bool:
    blob = _blob(wine)
    return any(m in blob for m in EARTHY_MARKERS)


def is_fruity(wine: Dict) -> bool:
    blob = _blob(wine)
    if is_earthy(wine) and not any(m in blob for m in ("zinfandel", "malbec", "moscato", "caymus", "geyserville")):
        return False
    return any(m in blob for m in FRUITY_MARKERS) or is_off_dry(wine)


def is_tannic(wine: Dict) -> bool:
    blob = _blob(wine)
    return any(
        m in blob
        for m in ("cabernet", "barolo", "brunello", "nebbiolo", "syrah", "tannat", "malbec", "opus")
    ) and wine_color(wine) == "red"


def is_sangiovese(wine: Dict) -> bool:
    blob = _blob(wine)
    grapes = str(wine.get("grapes") or "").lower()
    return any(m in blob or m in grapes for m in ("sangiovese", "chianti", "brunello", "nobile", "morellino"))


def sommelier_score(query: str, wine: Dict, base: float = 0.0) -> float:
    intent = parse_intent(query)
    score = base
    color = wine_color(wine)
    blob = _blob(wine)

    if color == "mixed":
        return -10.0

    q = (intent.raw or "").lower()
    if "france" in q or "french" in q:
        if any(m in blob for m in ("france", "burgundy", "bordeaux", "loire", "rhone", "rhône", "alsace", "champagne", "chablis", "pauillac", "puligny", "meursault")):
            score += 2.2
        else:
            score -= 2.5
    if "chardonnay" in q:
        chard = "chardonnay" in blob or "chablis" in blob or "puligny" in blob or "meursault" in blob or "montrachet" in blob
        if chard:
            score += 3.0
        else:
            score -= 8.0

    if "rich_white" in intent.profile:
        if color != "white":
            score -= 8.0
        if is_oaky_chardonnay(wine) or any(m in blob for m in ("meursault", "puligny", "montrachet", "corton")):
            score += 3.2
        if "chablis" in blob:
            score -= 2.5

    if intent.color:
        wanted = {intent.color}
        if intent.color == "white" and "crisp" not in intent.profile:
            wanted.add("sparkling")
        if intent.color == "sparkling":
            wanted.update({"sparkling", "champagne"})
        if intent.color == "rose":
            wanted.update({"rose", "rosé"})
        if color not in wanted:
            if intent.lock_color:
                return -10.0
            score -= 0.8

    if "crisp" in intent.profile:
        if color == "red" and intent.color != "red":
            score -= 8.0
        if is_oaky_chardonnay(wine):
            score -= 6.0
        if is_off_dry(wine):
            score -= 4.0
        if is_lean_white(wine):
            score += 2.2
        if "chablis" in blob:
            score += 1.5
        if any(g in blob for g in ("sauvignon", "pinot gris", "arneis")):
            score += 1.0

    if "offdry" in intent.profile:
        if is_off_dry(wine):
            score += 4.0
        else:
            score -= 8.0

    if "fruity" in intent.profile:
        if is_fruity(wine):
            score += 2.0
        if is_earthy(wine) and not is_fruity(wine):
            score -= 1.5
        if "barolo" in blob or "brunello" in blob:
            score -= 1.2
        white_ask = intent.color == "white" or color in {"white", "sparkling"}
        if white_ask:
            if is_off_dry(wine) and "offdry" not in intent.profile:
                score -= 3.5
            if is_oaky_chardonnay(wine):
                score -= 3.0
            if any(m in blob for m in ("sauvignon", "viognier", "torrontes", "pinot gris", "chenin", "albari", "fiano")):
                score += 1.8
        else:
            if any(m in blob for m in ("zinfandel", "malbec", "caymus", "geyserville")):
                score += 1.2

    if "earthy" in intent.profile:
        if is_earthy(wine):
            score += 2.2
        if is_fruity(wine) and not is_earthy(wine):
            score -= 1.8
        if any(m in blob for m in ("caymus", "rombauer", "moscato", "opus")):
            score -= 2.0
        if any(m in blob for m in ("burgundy", "barolo", "chablis", "rioja", "nebbiolo", "barbaresco")):
            score += 1.2
        if intent.body == "full" and color == "red":
            if any(m in blob for m in ("barolo", "barbaresco", "brunello", "rioja", "nebbiolo")):
                score += 2.5
            if ("napa" in blob or "cabernet" in blob) and not is_earthy(wine):
                score -= 2.0

    if intent.body == "light":
        if is_full_red(wine) or is_oaky_chardonnay(wine):
            score -= 5.0
        if is_lean_white(wine) or is_light_red(wine):
            score += 2.0
        if "pinot gris" in blob or "arneis" in blob or "chablis" in blob:
            score += 0.8
    elif intent.body == "full":
        if is_lean_white(wine) and intent.color != "white":
            score -= 3.0
        if is_light_red(wine) and not is_full_red(wine):
            score -= 3.0
        if is_full_red(wine) or is_oaky_chardonnay(wine):
            score += 2.0
        if any(m in blob for m in ("cabernet", "barolo", "brunello", "syrah", "malbec")):
            score += 0.8
    elif intent.body == "medium":
        if is_oaky_chardonnay(wine) or (is_full_red(wine) and "cabernet" in blob and "napa" in blob):
            score -= 0.8
        if is_lean_white(wine) and "chablis" not in blob:
            score += 0.4
        if "chianti" in blob or "rioja" in blob or "pinot" in blob:
            score += 1.0

    food = intent.food
    if food == "oysters":
        if is_lean_white(wine) or "chablis" in blob or color in {"sparkling", "champagne"}:
            score += 3.0
        if is_oaky_chardonnay(wine) or is_full_red(wine):
            score -= 6.0
        if "chablis" in blob or "muscadet" in blob:
            score += 0.6
        if "sauvignon" in blob and "pessac" not in blob and "bordeaux" not in blob:
            score += 0.5
        if "pessac" in blob or "sauternes" in blob:
            score -= 1.0
    elif food == "branzino":
        # Principle: lean, high-acid, no oak. Any grape that does that is in play —
        # Soave, Verdicchio, dry Riesling, Albariño, Muscadet, Chablis, Pinot Gris.
        if is_lean_white(wine):
            score += 2.8
        if is_oaky_chardonnay(wine) or color == "red":
            score -= 6.0
        if any(m in blob for m in MED_LEAN_WHITES):
            score += 1.6  # Mediterranean fish loves Italian coastal whites
        if any(m in blob for m in ("chablis", "riesling", "albari", "pinot gris", "sauvignon", "muscadet")):
            score += 0.5
    elif food == "steak":
        if is_full_red(wine):
            score += 3.0
        if is_lean_white(wine) or is_off_dry(wine):
            score -= 5.0
        if any(m in blob for m in ("cabernet", "syrah", "malbec", "bordeaux", "pauillac")):
            score += 1.5
    elif food == "chicken":
        if is_light_red(wine) or (color == "white" and not is_off_dry(wine)):
            score += 2.0
        if is_tannic(wine) and "cabernet" in blob:
            score -= 2.0
        if "pinot" in blob or "chardonnay" in blob:
            score += 1.0
    elif food == "cream":
        # Fat needs acid or modest oak; tannin turns metallic with cream.
        if is_tannic(wine):
            score -= 5.0
        if color == "white" or is_light_red(wine):
            score += 2.2
        if "chardonnay" in blob or "pinot" in blob or "meursault" in blob:
            score += 1.5
        if is_oaky_chardonnay(wine):
            score -= 1.8
        if is_lean_white(wine) and "chablis" in blob:
            score += 0.6
    elif food == "tomato":
        # Tomato acid wants acid, not oak or heavy tannin.
        if is_sangiovese(wine) or "chianti" in blob:
            score += 3.5
        if "chianti" in blob:
            score += 2.0
        if "brunello" in blob:
            score -= 1.5
        if color == "red" and not is_oaky_chardonnay(wine):
            score += 1.0
        if is_oaky_chardonnay(wine) or ("cabernet" in blob and "napa" in blob):
            score -= 3.0
        if is_off_dry(wine):
            score -= 4.0
    elif food == "hard_cheese":
        if is_full_red(wine) or "rioja" in blob or color in {"sparkling", "champagne"}:
            score += 2.0
        if is_off_dry(wine) or (is_lean_white(wine) and "chablis" not in blob):
            score -= 1.2
        if any(m in blob for m in ("barolo", "rioja", "chianti", "champagne")):
            score += 2.2
        if "cabernet" in blob and "napa" in blob:
            score -= 0.5
    elif food == "soft_cheese":
        if is_tannic(wine):
            score -= 5.0
        if is_lean_white(wine) or color in {"sparkling", "champagne", "white"}:
            score += 2.2
        if "sauvignon" in blob or "chablis" in blob or "champagne" in blob:
            score += 1.4

    return score


def passes_color_lock(query: str, wine: Dict) -> bool:
    intent = parse_intent(query)
    if not intent.lock_color or not intent.color:
        return True
    color = wine_color(wine)
    if intent.color == "white":
        if "crisp" in intent.profile or "offdry" in intent.profile:
            return color == "white"
        return color in {"white", "sparkling", "champagne"}
    if intent.color == "sparkling":
        return color in {"sparkling", "champagne"}
    if intent.color == "rose":
        return color in {"rose", "rosé"}
    if intent.color == "red":
        return color == "red"
    return True


def passes_profile(query: str, wine: Dict) -> bool:
    intent = parse_intent(query)
    color = wine_color(wine)
    if "crisp" in intent.profile:
        if is_oaky_chardonnay(wine):
            return False
        if color == "red" and intent.color != "red":
            return False
        if is_off_dry(wine):
            return False
    if "offdry" in intent.profile and not is_off_dry(wine):
        return False
    if intent.lock_body and intent.body == "light":
        if is_full_red(wine) or is_oaky_chardonnay(wine):
            return False
    if intent.lock_body and intent.body == "full":
        if is_lean_white(wine):
            return False
        if is_light_red(wine) and not is_full_red(wine):
            return False
    food = intent.food
    if food in {"oysters", "branzino"}:
        if color == "red" or is_oaky_chardonnay(wine):
            return False
    if food in {"cream", "soft_cheese"} and is_tannic(wine) and is_full_red(wine):
        return False
    if food == "tomato" and (is_off_dry(wine) or is_oaky_chardonnay(wine)):
        return False
    return True


def approachable_note(wine: Dict, query: str) -> Tuple[str, str]:
    intent = parse_intent(query)
    producer = wine.get("producer") or ""
    name = wine.get("wine_name") or wine.get("label") or ""
    region = wine.get("region") or ""
    grapes = wine.get("grapes") or ""
    blob = _blob(wine)

    if intent.food == "oysters":
        return (
            "Oysters want salt, lemon, and a cold white — never oak, never tannin.",
            f"{producer} {name} stays bright and mineral. It tastes like the sea more than like butter.",
        )
    if intent.food == "branzino":
        return (
            "Delicate fish wants a lean, high-acid white with no oak — Soave, Verdicchio, dry Riesling, Chablis, Pinot Gris: whatever this list actually has.",
            f"{producer} {name} from {region} stays light and dry so the fish leads.",
        )
    if intent.food == "steak":
        return (
            "Steak wants grip. Tannin and body stand up to the meat.",
            f"{producer} {name} has the weight for a strip — fruit and structure, not a light sip.",
        )
    if intent.food == "cream":
        return (
            "Cream needs acid, not tannin — tannin plus cream tastes metallic.",
            f"{producer} {name} is round enough for a cream sauce and still fresh.",
        )
    if intent.food == "tomato":
        return (
            "Tomato is acid. The wine needs acid too — classically Chianti, not Napa Cab.",
            f"{producer} {name} from {region} has enough snap for tomato sauce.",
        )
    if intent.food == "hard_cheese":
        return (
            "Aged hard cheese can take a more serious bottle — structure, not sugar.",
            f"{producer} {name} has the backbone for Parmesan or an aged cheddar.",
        )
    if intent.food == "soft_cheese":
        return (
            "Soft cheese is fat and mild. High-acid white or bubbles, not a tannic red.",
            f"{producer} {name} stays bright so the cheese does not feel heavy.",
        )
    if intent.food == "chicken":
        return (
            "Roast chicken sits in the middle — Pinot or a calm white.",
            f"{producer} {name} will not overpower the bird.",
        )

    if "offdry" in intent.profile:
        why = "Off-dry means a little sweetness — not dessert, just softer on the edges."
        note = (
            f"{producer} {name} from {region} has ripe fruit and a gentle finish. "
            "Easy if you do not want something bone-dry."
        )
        return why, note
    if "crisp" in intent.profile:
        if "chablis" in blob:
            why = "This is the crisp, clean white a sommelier reaches for — high acid, no oak, no butter."
            note = (
                f"{producer} Chablis tastes like lemon, wet stone, and a cold glass. "
                "It finishes dry and tidy, the opposite of a rich California Chardonnay."
            )
            return why, note
        if "pinot gris" in blob:
            why = "Pinot Gris from a cool place stays light and snappy — that dry-and-crisp feeling."
            note = (
                f"{producer} {name} is pale, a little pear, a little citrus, and gone in a fresh way. "
                "Nothing heavy, nothing oaky."
            )
            return why, note
        if is_lean_white(wine):
            why = "Lean, high-acid white — what people mean by dry and crisp."
            note = (
                f"{producer} from {region} stays tight and refreshing. "
                "Think citrus and minerals rather than butter or vanilla."
            )
            return why, note
    if "earthy" in intent.profile:
        why = "Earthy here means forest floor, stone, or savory — not jammy fruit."
        note = (
            f"{producer} {name} from {region} is more savory than sweet. "
            "It tastes like the place more than like ripe fruit."
        )
        return why, note
    if "fruity" in intent.profile:
        why = "Fruity means you taste the grape first — ripe, open, easy."
        note = (
            f"{producer} {name} leads with fruit, not oak or earth. "
            "Straightforward in the glass."
        )
        return why, note
    if intent.body == "light":
        why = "Light-bodied: it will not sit heavy. Think silk, not a blanket."
        note = (
            f"{producer} from {region} stays on its toes"
            f"{' — ' + grapes if grapes else ''}. Easy with food or without."
        )
        return why, note
    if intent.body == "full":
        why = "Full-bodied: more weight, more grip, a bigger sip."
        note = (
            f"{producer} {name} from {region} fills the glass. "
            "This is the richer side of the list."
        )
        return why, note

    why = f"From {region}, this sits in the style you asked for."
    grape_bit = f" {grapes}." if grapes else "."
    note = (
        f"{producer} {name} is a {wine_color(wine) or 'wine'} from {region}.{grape_bit} "
        "Straightforward, and true to the place."
    )
    return why, note


def guest_intro(query: str) -> str:
    intent = parse_intent(query)
    food_intro = {
        "oysters": "Oysters with a mineral white — Chablis, not oaky Chardonnay.",
        "branzino": "Delicate fish: a lean, unoaked white from this list — not always Chablis.",
        "steak": "Steak with something that has grip.",
        "cream": "Cream sauce with acid, not tannin.",
        "tomato": "Tomato sauce with a high-acid red — think Chianti.",
        "hard_cheese": "Hard cheese can take a more structured bottle.",
        "soft_cheese": "Soft cheese with a bright white, not a tannic red.",
        "chicken": "Chicken is versatile — Pinot or a calm white.",
    }
    if intent.food and intent.food in food_intro:
        return food_intro[intent.food]
    if "offdry" in intent.profile:
        return "Off-dry is a little softness, not a dessert wine. Two from the list."
    if "crisp" in intent.profile:
        return "Dry and crisp means a lean white — high acid, no oak. Here are two from the list."
    if "earthy" in intent.profile:
        return "Earthy, savory bottles — more forest and stone than jam."
    if "fruity" in intent.profile:
        return "Open, fruit-forward bottles from the list."
    if intent.body == "light":
        return "Light on its feet — nothing heavy."
    if intent.body == "full":
        return "The fuller side of the list — more weight in the glass."
    return "Two from the list for what you asked."


def grok_system_prompt(restaurant_name: str) -> str:
    return (
        f"You are the house sommelier at {restaurant_name}, trained to the standard of "
        "the Court of Master Sommeliers. Think like a Master Sommelier. Write like a kind "
        "person at the table.\n\n"
        "The guest may tap buttons or type. Treat these as identical:\n"
        "- Light / light-bodied: Pinot Noir, Gamay, Pinot Gris, Chablis, Arneis. "
        "Never Napa Cab, Barolo, or Kistler-style Chardonnay.\n"
        "- Medium: Chianti, Rioja, village Burgundy, Oregon Pinot, Mâcon.\n"
        "- Full: Cabernet, Syrah, Malbec, Barolo, Brunello, oaky California Chardonnay.\n"
        "- Fruity: ripe, open fruit (Zin, Malbec, New World). Not tarry Barolo.\n"
        "- Earthy: forest, stone, savory (Burgundy, Barolo, Chablis, traditional Rioja). Not jam.\n"
        "- Dry & crisp / crisp / clean: high-acid unoaked WHITE (Chablis, Sancerre, Pinot Gris). "
        "Never Kistler, Aubert, Rombauer, Cakebread. Never red unless they also tapped Red.\n"
        "- Off-dry: a little sugar (Moscato d'Asti, Kabinett Riesling). Not bone-dry Cab.\n"
        "- Infer color from language. Guests will not always say 'white'.\n"
        "Food (classic table rules):\n"
        "- Oysters / branzino: ANY lean, high-acid, unoaked white on THIS list "
        "(Soave, Verdicchio, dry Riesling, Albariño, Muscadet, Chablis, Pinot Gris, Vermentino). "
        "Do not default to Chablis every time. Pick two different grapes. Never oaky Chard or red.\n"
        "- If a menu dish is named, pair to how it is cooked: lemon/olive/grilled fish = lean white; "
        "chowder/butter/bacon = richer white or Pinot; tomato = Sangiovese; steak/bordelaise = Cab.\n"
        "- Steak: tannic full red (Cabernet, Syrah, Bordeaux). Not Pinot Gris.\n"
        "- Cream sauce: Chardonnay, Pinot, high-acid white. Never Cab/Barolo (tannin + cream is metallic).\n"
        "- Tomato sauce: Sangiovese / Chianti. Acid with acid. Not Napa Cab, not Moscato.\n"
        "- Hard cheese: structured red or Champagne. Soft cheese: Sancerre, Chablis, Champagne — not tannic red.\n"
        "- Chicken: Pinot Noir or moderate white.\n"
        "- Only choose from the numbered list. Never invent a bottle, vintage, or price.\n\n"
        "Voice: two short everyday sentences. No jargon, scores, or 'notes of'. "
        "The why must echo their buttons or words.\n"
        "JSON only."
    )
