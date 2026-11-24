"""Small helpers shared by every service: money, dates, text, sorting, French formatting.

Several helpers reproduce JavaScript behaviour on purpose (rounding, number-to-text, string
collation) so that this API returns exactly what the original TypeScript API returned.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import cmp_to_key, lru_cache
from typing import Any, Callable, Iterable, TypeVar

T = TypeVar("T")

# ───────── Numbers ─────────


def js_round(x: float) -> int:
    """JavaScript Math.round: nearest integer, ties go up (2.5 → 3, -2.5 → -2)."""
    r = math.floor(x)
    return int(r + 1) if x - r >= 0.5 else int(r)


EPSILON = 2.220446049250313e-16  # JavaScript Number.EPSILON


def round2(n: float) -> float:
    """Round to 2 decimals (cents), avoiding the 1.005 → 1.00 float trap."""
    return js_round((n + EPSILON) * 100) / 100


def round3(n: float) -> float:
    """Quantities keep 3 decimals (grams for kg products)."""
    return js_round((n + EPSILON) * 1000) / 1000


def js_number(value: Any) -> float:
    """JavaScript Number(value) for a query string: "" → 0, garbage → NaN."""
    if value is None:
        return math.nan
    s = str(value).strip()
    if s == "":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return math.nan


def js_str(n: float | int) -> str:
    """A number as JavaScript prints it in a template string: 8.0 → "8", 1.5 → "1.5"."""
    if isinstance(n, float) and n.is_integer():
        return str(int(n))
    return str(n)


def int_param(value: str | None, default: int) -> int:
    """Positive integer query param, else the default (same rule as the TS intParam)."""
    n = js_number(value)
    return math.floor(n) if value and math.isfinite(n) and n > 0 else default


def total(xs: Iterable[float]) -> float:
    """Sum left to right (same float result as JavaScript reduce)."""
    s: float = 0
    for x in xs:
        s += x
    return s


# ───────── French formatting ─────────

NNBSP = " "  # narrow no-break space: the French thousands separator


def _decimal(n: float, min_frac: int, max_frac: int) -> str:
    value = Decimal(n).quantize(Decimal(1).scaleb(-max_frac), rounding=ROUND_HALF_UP)
    integer, _, fraction = f"{value:,.{max_frac}f}".partition(".")
    fraction = fraction.rstrip("0").ljust(min_frac, "0")
    return f"{integer}.{fraction}" if fraction else integer

def fmt_eur(n: float) -> str:
    return f"€{_decimal(round2(n), 2, 2)}"

def fr_money(n: float) -> str:
    return _decimal(n, 2, 2)

def fr_num(n: float) -> str:
    return _decimal(n, 0, 3)

def fr_day(iso: str) -> str:
    day = date.fromisoformat(iso[:10])
    return f"{day:%a} {day.day} {day:%b}"


# ───────── Dates (ISO strings) ─────────

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def add_days(iso: str, days: int) -> str:
    return (date.fromisoformat(iso[:10]) + timedelta(days=days)).isoformat()


def days_between(a: str, b: str) -> int:
    """Whole days from a to b (b - a)."""
    return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days


def weekday_of(iso: str) -> str:
    return WEEKDAYS[date.fromisoformat(iso[:10]).weekday()]


def add_minutes(hhmm: str, minutes: int) -> str:
    """"05:30" + 42 min → "06:12"."""
    h, m = (int(x) for x in hhmm.split(":"))
    t = (h * 60 + m + minutes) % (24 * 60)
    return f"{t // 60:02d}:{t % 60:02d}"


def to_date(iso_datetime: str) -> str:
    return iso_datetime[:10]


# ───────── Text ─────────


@lru_cache(maxsize=1 << 18)
def normalize(s: str) -> str:
    """Lowercase, strip accents and punctuation: "Saint-Jacques Écosse" → "saint jacques ecosse".
    Memoised: list searches normalise the same names / numbers / titles on every request."""
    s = unicodedata.normalize("NFD", s)
    s = re.sub("[̀-ͯ]", "", s).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i]
        for j in range(1, len(b) + 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (0 if a[i - 1] == b[j - 1] else 1)))
        prev = cur
    return prev[len(b)]


# ───────── Sorting ─────────
# JavaScript sorts text with localeCompare (Unicode collation): case and accents only break ties,
# spaces/punctuation sort before digits, digits before letters. collate_key() approximates that.

_PUNCT_ORDER = "_-,;:!?.'‘’\"«»()[]{}§¶@*/\\&#%`^+<=>|~$€"
_EXPANSIONS = {"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE", "ß": "ss"}
# Secondary (accent) weights, in Unicode collation order.
_ACCENTS = {"́": 1, "̀": 2, "̆": 3, "̂": 4, "̌": 5, "̊": 6, "̈": 7, "̃": 8, "̧": 9}


@lru_cache(maxsize=1 << 16)
def collate_key(s: str) -> tuple:
    """Sort key close to JavaScript `a.localeCompare(b)` (ICU root collation)."""
    primary: list[tuple[int, int]] = []
    secondary: list[int] = []
    tertiary: list[int] = []
    for ch in unicodedata.normalize("NFD", "".join(_EXPANSIONS.get(c, c) for c in s)):
        if ch in _ACCENTS or unicodedata.combining(ch):
            if secondary:
                secondary[-1] = _ACCENTS.get(ch, 10)
            continue
        if ch.isspace():
            primary.append((0, 0))
        elif ch.isdigit():
            primary.append((2, ord(ch)))
        elif ch.isalpha():
            primary.append((3, ord(ch.lower())))
        else:
            i = _PUNCT_ORDER.find(ch)
            primary.append((1, i if i >= 0 else 100 + ord(ch)))
        secondary.append(0)
        tertiary.append(1 if ch.isupper() else 0)
    return (primary, secondary, tertiary)


def locale_cmp(a: str, b: str) -> int:
    """a.localeCompare(b) → -1 / 0 / 1."""
    ka, kb = collate_key(a), collate_key(b)
    return (ka > kb) - (ka < kb)


def cmp(a: Any, b: Any) -> int:
    """Plain comparison → -1 / 0 / 1 (numbers, ISO dates, ids)."""
    return (a > b) - (a < b)


def sort_by(items: Iterable[T], compare: Callable[[T, T], int]) -> list[T]:
    """Stable sort with a JavaScript-style comparator: sort_by(xs, lambda a, b: cmp(a["x"], b["x"]))."""
    return sorted(items, key=cmp_to_key(compare))


def compact(d: dict) -> dict:
    """Drop None values, so optional fields stay absent from stored documents."""
    return {k: v for k, v in d.items() if v is not None}
