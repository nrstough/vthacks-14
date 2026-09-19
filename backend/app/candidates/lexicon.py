"""Turn a merchant string into a category.

Statement descriptors are shouted, abbreviated and full of store numbers, so
matching is on whole tokens rather than substrings: `KROGER #382`, `kroger 0382`
and `KROGER*382` all reduce to a token sequence beginning `KROGER`, while `GYM`
does not match `GYMBOREE`.

Two rules earn their keep, and both come from real statement lines:

1. **Protected categories are checked first.** `GAP INSURANCE PREMIUM` is an
   insurance payment, not a clothing purchase, and offering to skip it would be
   worse than offering nothing.
2. **A lone generic word is never a phrase.** `CLUB` would make `SAM'S CLUB` a
   gym, `WATER` would make `WATER ST TAVERN` a utility, and `POWER` would make
   `CORE POWER YOGA` one. Those words appear only inside longer phrases.

Everything here is a tuple. A set would let iteration order vary with
PYTHONHASHSEED, and the matched phrase picks the brand name that reaches the
screen, so the same account could render different words in two processes.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")


def normalise(text: str) -> tuple[str, ...]:
    """Uppercase, split on anything that is not a letter or digit.

    Accents are decomposed and their marks discarded rather than left to the
    regex, so an accented merchant name classifies the same whichever Unicode
    form the caller sends and does not break in half. Left composed, `CAFÉ`
    loses its É and becomes CAF; decomposed but not stripped, `MÉLANGE` splits
    into ME and LANGE. Both spellings now reduce to CAFE MELANGE.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in decomposed if not unicodedata.combining(c))
    return tuple(_NON_ALNUM.sub(" ", folded.upper()).split())


# Categories that never yield a candidate. Rent, the card payment and the power
# bill are not discretionary, and a product that offers to skip them is not one
# anybody should trust with their money.
PROTECTED: tuple[str, ...] = (
    "card_payment",
    "housing",
    "loan",
    "insurance",
    "utilities",
    "phone",
    "medical",
    "tuition",
    "transfer",
    "atm_cash",
)

# Match order. Protected first, then the changeable categories most likely to be
# shadowed by a broader one: delivery before rideshare so UBER EATS is a meal,
# streaming before shopping so AMAZON PRIME VIDEO is a subscription.
PRIORITY: tuple[str, ...] = PROTECTED + (
    "food_delivery",
    "rideshare",
    "coffee",
    "groceries",
    "fuel",
    "restaurant",
    "streaming",
    "gym",
    "software",
    "shopping",
    "entertainment",
    "personal_care",
)

UNKNOWN_CATEGORY = "unknown"

# Words too generic to stand alone as a phrase. Each one here misclassified a
# real statement line during review.
_GENERIC: tuple[str, ...] = (
    "CLUB", "MARKET", "WATER", "POWER", "GAP", "BP", "QT", "FUEL", "GIANT",
    "PILOT", "GAS", "STORE", "SHOP", "BANK", "ONLINE", "PAYMENT", "SERVICE",
    "SERVICES", "INC", "LLC", "CO", "THE", "OF", "AND", "US", "USA",
)

# Single tokens of three characters or fewer that are specific enough anyway.
_SHORT_OK: tuple[str, ...] = ("ATM", "HOA", "WSJ", "REI", "AMC", "TST", "BBQ", "SPA", "GYM", "HBO")

# (category, display, phrases). `display` is the brand a label may name; None
# means the category's brand-less template is used instead. Protected categories
# never reach a template, so their display is always None.
ENTRIES: tuple[tuple[str, str | None, tuple[str, ...]], ...] = (
    ("card_payment", None, (
        "CHASE CARD", "CARD EPAY", "CAPITAL ONE", "AMEX", "AMERICAN EXPRESS",
        "DISCOVER", "CITI CARD", "CREDIT CARD", "CRD PMT", "CARDMEMBER",
        "SYNCHRONY", "BARCLAYCARD", "APPLE CARD",
    )),
    ("housing", None, (
        "RENT", "MORTGAGE", "APARTMENT", "APARTMENTS", "APTS", "PROPERTY MGMT",
        "PROPERTIES", "LEASING", "HOA", "GUARANTEED RATE", "ROCKET MORTGAGE",
    )),
    ("loan", None, (
        "LOAN", "NELNET", "SALLIE MAE", "NAVIENT", "MOHELA", "AUTO PMT",
        "CAR PMT", "TOYOTA FIN", "HONDA FIN", "FORD CREDIT", "AFFIRM",
        "KLARNA", "AFTERPAY", "UPSTART", "SOFI",
    )),
    ("insurance", None, (
        "INSURANCE", "GEICO", "PROGRESSIVE", "STATE FARM", "ALLSTATE", "USAA",
        "GAP INSURANCE", "LEMONADE",
    )),
    ("utilities", None, (
        "ELECTRIC", "DOMINION ENERGY", "APPALACHIAN POWER", "DUKE ENERGY",
        "POWER CO", "POWER COMPANY", "WATER BILL", "WATER AUTH", "WATER DEPT",
        "WATER WORKS", "SEWER", "UTILITY", "UTILITIES", "COLUMBIA GAS",
        "GAS CO", "GAS COMPANY", "WASTE MGMT", "COMCAST", "XFINITY",
        "COX COMM", "SPECTRUM", "FIOS", "INTERNET",
    )),
    ("phone", None, (
        "VERIZON", "T MOBILE", "TMOBILE", "AT T", "ATT WIRELESS", "SPRINT",
        "MINT MOBILE", "VISIBLE", "CRICKET", "WIRELESS",
    )),
    ("medical", None, (
        "PHARMACY", "MEDICAL", "HEALTHCARE", "HEALTH SYSTEM", "CLINIC",
        "DENTAL", "HOSPITAL", "URGENT CARE", "TARGET OPTICAL", "BP MONITOR",
    )),
    ("tuition", None, ("TUITION", "BURSAR", "UNIVERSITY", "COLLEGE", "VIRGINIA TECH")),
    ("transfer", None, ("TRANSFER", "ZELLE", "VENMO", "CASH APP", "PAYPAL", "XFER")),
    ("atm_cash", None, ("ATM", "WITHDRAWAL", "CASH WITHDRAWAL")),

    ("food_delivery", "DoorDash", ("DOORDASH",)),
    ("food_delivery", "Uber Eats", ("UBER EATS", "UBEREATS")),
    ("food_delivery", "Grubhub", ("GRUBHUB",)),
    ("food_delivery", "Instacart", ("INSTACART",)),
    ("food_delivery", "Postmates", ("POSTMATES",)),

    ("rideshare", "Uber", ("UBER",)),
    ("rideshare", "Lyft", ("LYFT",)),

    ("coffee", None, ("STARBUCKS", "DUNKIN", "PEET", "DUTCH BROS", "COFFEE", "CAFE", "TIM HORTONS")),

    ("groceries", None, (
        "KROGER", "HARRIS TEETER", "FOOD LION", "PUBLIX", "WALMART", "WAL MART",
        "ALDI", "LIDL", "TRADER JOE", "WHOLE FOODS", "WHOLEFDS", "SAFEWAY",
        "GIANT FOOD", "GIANT EAGLE", "WEGMANS", "COSTCO", "SAMS CLUB",
        "SAM S CLUB", "BJ S WHOLESALE", "GROCERY", "SUPERMARKET", "FRESH MARKET",
        "FARMERS MARKET", "H E B", "MEIJER", "WINN DIXIE", "SPROUTS", "FOOD CITY",
    )),
    ("fuel", None, (
        "SHELL OIL", "SHELL SERVICE", "EXXON", "MOBIL", "CHEVRON", "SUNOCO",
        "WAWA", "SHEETZ", "7 ELEVEN", "CIRCLE K", "SPEEDWAY", "MARATHON PETRO",
        "CITGO", "VALERO", "RACETRAC", "QUIKTRIP", "PILOT TRAVEL", "FLYING J",
        "LOVES TRAVEL", "TEXACO", "GAS STATION",
    )),

    ("restaurant", "Chipotle", ("CHIPOTLE",)),
    ("restaurant", "McDonald's", ("MCDONALD",)),
    ("restaurant", "Chick-fil-A", ("CHICK FIL A",)),
    ("restaurant", "Taco Bell", ("TACO BELL",)),
    ("restaurant", "Wendy's", ("WENDY",)),
    ("restaurant", "Burger King", ("BURGER KING",)),
    ("restaurant", "Panera", ("PANERA",)),
    ("restaurant", "Subway", ("SUBWAY",)),
    ("restaurant", "Domino's", ("DOMINO",)),
    ("restaurant", "Papa John's", ("PAPA JOHN",)),
    ("restaurant", "Five Guys", ("FIVE GUYS",)),
    ("restaurant", "Cook Out", ("COOK OUT",)),
    ("restaurant", "Bojangles", ("BOJANGLES",)),
    ("restaurant", "Zaxby's", ("ZAXBY",)),
    ("restaurant", "Raising Cane's", ("RAISING CANE",)),
    ("restaurant", "Total Wine", ("TOTAL WINE",)),
    ("restaurant", None, (
        "PIZZA", "RESTAURANT", "GRILL", "BISTRO", "DINER", "SUSHI", "WINGS",
        "BBQ", "TAVERN", "BREWERY", "ABC STORE", "TST",
    )),

    ("streaming", "Netflix", ("NETFLIX",)),
    ("streaming", "Spotify", ("SPOTIFY",)),
    ("streaming", "Hulu", ("HULU",)),
    ("streaming", "Disney+", ("DISNEY PLUS", "DISNEYPLUS")),
    ("streaming", "HBO", ("HBO", "MAX COM")),
    ("streaming", "Paramount+", ("PARAMOUNT",)),
    ("streaming", "Peacock", ("PEACOCK",)),
    ("streaming", "Apple", ("APPLE COM BILL",)),
    ("streaming", "Apple Music", ("APPLE MUSIC",)),
    ("streaming", "YouTube Premium", ("YOUTUBE PREMIUM",)),
    ("streaming", "Audible", ("AUDIBLE",)),
    ("streaming", "Prime Video", ("PRIME VIDEO",)),
    ("streaming", "Crunchyroll", ("CRUNCHYROLL",)),
    ("streaming", "SiriusXM", ("SIRIUS",)),
    ("streaming", "Pandora", ("PANDORA",)),
    ("streaming", "Tidal", ("TIDAL",)),

    ("gym", None, (
        "PLANET FIT", "PLANET FITNESS", "LA FITNESS", "ANYTIME FITNESS",
        "GOLD S GYM", "YMCA", "CRUNCH FITNESS", "ORANGETHEORY", "EQUINOX",
        "GYM", "CLUB FEES", "PELOTON", "CORE POWER YOGA", "FUEL FITNESS",
    )),

    ("software", "Adobe", ("ADOBE",)),
    ("software", "Microsoft", ("MICROSOFT",)),
    ("software", "Google One", ("GOOGLE ONE", "GOOGLE STORAGE")),
    ("software", "iCloud", ("ICLOUD",)),
    ("software", "Dropbox", ("DROPBOX",)),
    ("software", "ChatGPT", ("CHATGPT", "OPENAI")),
    ("software", "Notion", ("NOTION",)),
    ("software", "GitHub", ("GITHUB",)),
    ("software", "Patreon", ("PATREON",)),
    ("software", "Substack", ("SUBSTACK",)),
    ("software", "the Times", ("NYTIMES", "NY TIMES")),
    ("software", "the Journal", ("WSJ",)),
    ("software", "the Post", ("WASHINGTON POST",)),

    ("shopping", "Amazon", ("AMZN", "AMAZON")),
    ("shopping", "Target", ("TARGET",)),
    ("shopping", "Best Buy", ("BEST BUY", "BESTBUY")),
    ("shopping", "eBay", ("EBAY",)),
    ("shopping", "Etsy", ("ETSY",)),
    ("shopping", "Wayfair", ("WAYFAIR",)),
    ("shopping", "IKEA", ("IKEA",)),
    ("shopping", "Home Depot", ("HOME DEPOT",)),
    ("shopping", "Lowe's", ("LOWE S", "LOWES")),
    ("shopping", "Apple", ("APPLE STORE",)),
    ("shopping", "Nike", ("NIKE",)),
    ("shopping", "Zara", ("ZARA",)),
    ("shopping", "H&M", ("H M",)),
    ("shopping", "Old Navy", ("OLD NAVY",)),
    ("shopping", "TJ Maxx", ("TJ MAXX", "TJMAXX")),
    ("shopping", "Marshalls", ("MARSHALLS",)),
    ("shopping", "Ross", ("ROSS STORES",)),
    ("shopping", "Kohl's", ("KOHL",)),
    ("shopping", "Macy's", ("MACY",)),
    ("shopping", "Nordstrom", ("NORDSTROM",)),
    ("shopping", "Shein", ("SHEIN",)),
    ("shopping", "Temu", ("TEMU",)),
    ("shopping", "GameStop", ("GAMESTOP",)),
    ("shopping", "Steam", ("STEAM GAMES",)),
    ("shopping", "PlayStation", ("PLAYSTATION",)),
    ("shopping", "Xbox", ("XBOX",)),
    ("shopping", "Nintendo", ("NINTENDO",)),
    ("shopping", "Ulta", ("ULTA",)),
    ("shopping", "Sephora", ("SEPHORA",)),
    ("shopping", "Dick's", ("DICK S SPORTING",)),
    ("shopping", "REI", ("REI",)),

    ("entertainment", "AMC", ("AMC",)),
    ("entertainment", "Regal", ("REGAL",)),
    ("entertainment", "Cinemark", ("CINEMARK",)),
    ("entertainment", "Ticketmaster", ("TICKETMASTER",)),
    ("entertainment", "StubHub", ("STUBHUB",)),
    ("entertainment", "Eventbrite", ("EVENTBRITE",)),
    ("entertainment", "Topgolf", ("TOPGOLF",)),
    ("entertainment", "Dave & Buster's", ("DAVE BUSTER",)),
    ("entertainment", None, ("THEATRE", "THEATER", "CINEMA")),

    ("personal_care", "Supercuts", ("SUPERCUTS",)),
    ("personal_care", "Great Clips", ("GREAT CLIPS",)),
    ("personal_care", None, ("SALON", "BARBER", "NAILS", "SPA", "MASSAGE")),
)


@dataclass(frozen=True)
class Match:
    category: str
    display: str | None


UNKNOWN = Match(UNKNOWN_CATEGORY, None)


def _build_index() -> dict[str, tuple[tuple[tuple[str, ...], int, str, str | None], ...]]:
    """Group phrases by their first token, best match first.

    Without this every row would be compared against every phrase; with it a row
    costs O(its own tokens). Each bucket is sorted by (priority, longest first),
    so the first phrase in it that matches is that bucket's best and the scan can
    stop there.
    """
    seen: dict[tuple[str, ...], str] = {}
    buckets: dict[str, list[tuple[tuple[str, ...], int, str, str | None]]] = {}

    for category, display, phrases in ENTRIES:
        if category not in PRIORITY:
            raise ValueError(f"{category} is not in PRIORITY")
        if category in PROTECTED and display is not None:
            raise ValueError(f"protected category {category} carries a display name")
        rank = PRIORITY.index(category)
        for phrase in phrases:
            tokens = normalise(phrase)
            if not tokens:
                raise ValueError(f"{category}: empty phrase {phrase!r}")
            if tokens in seen and seen[tokens] != category:
                raise ValueError(f"phrase {phrase!r} is in both {seen[tokens]} and {category}")
            if len(tokens) == 1:
                token = tokens[0]
                if token in _GENERIC:
                    raise ValueError(f"{token!r} is too generic to stand alone as a phrase")
                if len(token) <= 3 and token not in _SHORT_OK:
                    raise ValueError(f"{token!r} is too short to stand alone; add it to _SHORT_OK")
            seen[tokens] = category
            buckets.setdefault(tokens[0], []).append((tokens, rank, category, display))

    return {
        token: tuple(sorted(entries, key=lambda e: (e[1], -len(e[0]), e[0])))
        for token, entries in buckets.items()
    }


_INDEX = _build_index()


def classify(description: str) -> Match:
    """First phrase to match, by category priority then by length."""
    tokens = normalise(description)
    best: tuple[int, int, tuple[str, ...]] | None = None
    found = UNKNOWN

    for i, token in enumerate(tokens):
        for phrase, rank, category, display in _INDEX.get(token, ()):
            if tokens[i : i + len(phrase)] == phrase:
                key = (rank, -len(phrase), phrase)
                if best is None or key < best:
                    best, found = key, Match(category, display)
                # The bucket is sorted, so nothing after this can beat it.
                break

    return found
