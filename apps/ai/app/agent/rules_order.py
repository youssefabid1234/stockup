"""
OWNER: Amine Khalil · switch TEAM_ORDER_RULES · contract: docs/team/interfaces.md §4

« La commande juste » : what the agent must understand and check so that the order in the ERP is exactly what the
caller meant. Real life: Lucie knows "10 de tradi" = 10 sacks of 25 kg, "comme d'hab" = the usual basket, never
confirms without reading the order back, never promises anything to a blocked client.

Two parts:
  1. ORDER_RULES: text added to the system prompt (voice + chat modes) when the switch is on.
  2. Deterministic helpers (quantities, units, dates): the brief says "du code déterministe pour ce qui n'a pas
     besoin d'un modèle". Faster and never wrong. Business rules that touch prices / stock / credit stay in the
     backend (AGENTS.md): read the ERP's order warnings (client_blocked, no_route…) instead of re-coding them.
     The dates are exposed to the model by the tool check_delivery_date (tools/delivery.py).

Decision (T0, see docs/team/status/amine-khalil.md): the ERP's delivery days are the truth. Some CRM notes say
"Fermé le mercredi" for clients the ERP delivers on Wednesdays — and the order history shows they ARE delivered on
Wednesdays after the note. So the agent never claims a client is closed; only the caller can say so.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

from app import team_flags

ORDER_RULES = """Règles « commande juste » (prise de commande au téléphone) :
- Ne pense jamais tout haut : pas de phrase de vérification avant ou entre les outils (« jeudi est bien un jour de livraison » est interdit). Tu parles une fois, à la fin.
- Unités : farines et sucre au sac (25 kg ; épeautre 10 kg), « 10 de tradi » = 10 sacs, jamais 10 kilos. Tourage, beurre, chocolat, fruits secs au kilo ; crème et lait au litre ; viennoiserie surgelée et emballages au carton ; levure au pain de 500 g ; œufs au plateau de 30. Dis les quantités avec leur unité (« douze sacs de tradi »).
- « Chocolatine » et « pain au chocolat » sont le même produit : ne corrige jamais le client.
- « Comme d'hab » = la commande habituelle de la fiche client (pas la dernière commande). Cite seulement les deux ou trois produits principaux avec leur quantité, puis demande « et le reste comme d'habitude ? ».
- Date : appelle check_delivery_date dès qu'un jour est dit (ou pour « au plus vite »). Si le jour n'est pas livré, propose le prochain jour possible qu'il renvoie. N'affirme jamais qu'un client est fermé : seul le client peut le dire ; s'il le dit, propose le jour livré suivant et mémorise-le (save_context).
- Dès que produits et quantités sont clairs, crée le brouillon (create_draft_order). Un changement d'avis (« finalement 12 », « enlève le seigle ») modifie la ligne existante : ne l'ajoute pas une deuxième fois.
- Avant confirm_order : relis produits, quantités et jour de livraison en une phrase, puis attends un oui. Après « oui », « c'est bon », « validez », appelle confirm_order tout de suite, sans tout revérifier.
- Compte bloqué : ne prends aucune commande et ne promets rien ; ne donne aucun détail comptable interne ; dis que la comptabilité (Sandrine) le rappelle, et enregistre la demande avec log_client_event (type call).
- Lis les alertes (warnings) de la commande : client bloqué, pas de tournée, stock insuffisant. S'il y en a, dis-les simplement au client, sans code technique ; s'il n'y en a pas, n'en parle pas."""


def order_rules_section() -> str:
    """What prompts.py adds to the system prompt. '' when the switch is off or the rules are empty."""
    return ORDER_RULES.strip() if team_flags.order_rules() else ""


# ── Deterministic helpers: pure functions, unit-tested in tests/test_rules_order.py ──

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAYS_FR = {"lundi": "mon", "mardi": "tue", "mercredi": "wed", "jeudi": "thu", "vendredi": "fri", "samedi": "sat", "dimanche": "sun"}  # fmt: skip
DAY_LABEL = {v: k for k, v in DAYS_FR.items()}
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]  # fmt: skip
ASAP = ("au plus vite", "des que possible", "le plus tot", "prochaine livraison", "rapidement", "vite")
CUTOFF_HOUR = 17  # order before 17h for next-morning delivery (02-journee-type.md)
CUTOFF_HOUR_LAURAGAIS = 12  # Lauragais-Tarn route: order the day before, before noon
LAURAGAIS_ZONE = "Lauragais & Tarn"


def _norm(s: str) -> str:
    """lower case, no accents, single spaces: "Après-Demain " → "apres-demain"."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


def can_deliver(today: date, delivery_days: list[str], d: date, now_hour: float = 6, cutoff_hour: float = CUTOFF_HOUR) -> bool:
    """True when `d` is a delivery day of the client, after today, and the order is still in time for it."""
    if d <= today or WEEKDAYS[d.weekday()] not in delivery_days:
        return False
    return d - timedelta(days=1) > today or now_hour < cutoff_hour


def first_possible(today: date, delivery_days: list[str], now_hour: float = 6, cutoff_hour: float = CUTOFF_HOUR) -> date | None:
    """The first date the client can be delivered (None if the client has no delivery day)."""
    return next(
        (today + timedelta(days=i) for i in range(1, 15) if can_deliver(today, delivery_days, today + timedelta(days=i), now_hour, cutoff_hour)),
        None,
    )


def parse_asked_day(today: date, asked: str | None) -> date | None | str:
    """What the caller said → a date, "asap", or None when it is not understood / not a future day.
    "demain", "après-demain", "jeudi", "jeudi prochain", "26/11", "le 26", "2026-11-26", "au plus vite"."""
    if asked is None or not asked.strip():
        return "asap"
    a = _norm(asked)
    if any(k in a for k in ASAP):
        return "asap"
    if "apres-demain" in a or "apres demain" in a:
        return today + timedelta(days=2)
    if "demain" in a:
        return today + timedelta(days=1)
    if "aujourd" in a or "ce matin" in a or "ce midi" in a:
        return today
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", a):
        return date(int(m[1]), int(m[2]), int(m[3]))
    if m := re.search(r"\b(\d{1,2})\s*/\s*(\d{1,2})\b", a):
        return _future(today, int(m[1]), int(m[2]))
    for name, code in DAYS_FR.items():
        if re.search(rf"\b{name}\b", a):
            ahead = (WEEKDAYS.index(code) - today.weekday()) % 7 or 7  # "mardi" said on a Tuesday = next Tuesday
            return today + timedelta(days=ahead)
    if m := re.search(r"\b(?:le\s+)?(\d{1,2})\b", a):
        return _future(today, int(m[1]), today.month)
    return None


def _future(today: date, day: int, month: int) -> date | None:
    """Day/month without a year: the next occurrence from today."""
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= today:
            return d
    return None


def next_delivery_date(
    today: date, delivery_days: list[str], asked: str | None = None, now_hour: float = 6, cutoff_hour: float = CUTOFF_HOUR
) -> date | None:
    """
    The delivery date for "jeudi", "demain", "au plus vite"… given the client's delivery days and the order cut-off
    (17h for the next morning; 12h the day before for the Lauragais-Tarn route).
    Use the ERP's business date (GET /api/meta → today), never the real clock.
    Returns None if the asked day is not delivered for this client, already gone, or too late to order for.
    """
    wanted = parse_asked_day(today, asked)
    if wanted == "asap":
        return first_possible(today, delivery_days, now_hour, cutoff_hour)
    if not isinstance(wanted, date):
        return None
    return wanted if can_deliver(today, delivery_days, wanted, now_hour, cutoff_hour) else None


def french_day(d: date) -> str:
    """date(2026, 11, 26) → "jeudi 26 novembre"."""
    return f"{DAY_LABEL[WEEKDAYS[d.weekday()]]} {d.day} {MONTHS_FR[d.month - 1]}"


def delivery_answer(
    today: date, delivery_days: list[str], asked: str | None, now_hour: float = 6, zone: str | None = None
) -> dict:
    """Everything the agent needs to answer about a delivery day, as small JSON (used by check_delivery_date)."""
    cutoff = CUTOFF_HOUR_LAURAGAIS if zone == LAURAGAIS_ZONE else CUTOFF_HOUR
    days_fr = [DAY_LABEL[d] for d in WEEKDAYS if d in delivery_days]
    nxt = first_possible(today, delivery_days, now_hour, cutoff)
    wanted = parse_asked_day(today, asked)
    out: dict = {"deliveryDays": days_fr}
    if wanted == "asap" or (date_ok := next_delivery_date(today, delivery_days, asked, now_hour, cutoff)) is not None:
        d = nxt if wanted == "asap" else date_ok
        if d is None:
            return {**out, "ok": False, "reason": "aucun jour de livraison connu pour ce client"}
        return {**out, "ok": True, "date": d.isoformat(), "say": french_day(d)}
    if not isinstance(wanted, date):
        reason = f"jour non compris : « {asked} »"
    elif wanted <= today:
        reason = "les tournées du jour sont parties (dépannage possible au dépôt)"
    elif WEEKDAYS[wanted.weekday()] not in delivery_days:
        reason = f"le client n'est pas livré le {DAY_LABEL[WEEKDAYS[wanted.weekday()]]} (tournée : {', '.join(days_fr)})"
    else:
        limit = "la veille avant 12h" if cutoff == CUTOFF_HOUR_LAURAGAIS else "avant 17h la veille"
        reason = f"trop tard pour ce jour : commande {limit}"
    return {
        **out,
        "ok": False,
        "asked": french_day(wanted) if isinstance(wanted, date) else asked,
        "reason": reason,
        **({"nextPossible": nxt.isoformat(), "sayNext": french_day(nxt)} if nxt else {}),
    }


UNIT_ALIASES = {
    "kg": ("kg", "kilo", "kilos", "kilogramme", "kilogrammes"),
    "l": ("l", "litre", "litres"),
    "g": ("g", "gramme", "grammes"),
}


def _said(unit: str | None) -> str | None:
    if not unit:
        return None
    u = _norm(unit).rstrip(".")
    return next((k for k, aliases in UNIT_ALIASES.items() if u in aliases), u)


def sacks_from_words(product_unit: str, qty: float, said_unit: str | None) -> float:
    """
    Convert what was said into the product's selling unit, e.g. "10 de tradi" → 10 sacks, "50 kilos de tradi" → 2.
    `product_unit` is the package the product is sold by ("sac 25 kg", "plaque 2 kg", "carton 140"…); a product sold
    by weight or volume passes "kg" / "l" and the quantity stays as said.
    No unit said ("10 de tradi") = packages. A weight said for a weighed package = weight / package weight
    (may be fractional: the agent then asks, e.g. 40 kg of 25 kg sacks).
    """
    said = _said(said_unit)
    pu = _norm(product_unit)
    if pu in ("kg", "l", "litre", "kilo"):
        return qty
    if said is None or said in ("sac", "sacs", "carton", "cartons", "plaque", "plaques", "piece", "pieces"):
        return qty
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|l|g)\b", pu)
    if not m:
        return qty
    size, size_unit = float(m[1].replace(",", ".")), m[2]
    if said == "g" and size_unit == "kg":
        qty, said = qty / 1000, "kg"
    if said != size_unit:
        return qty
    return round(qty / size, 3)
