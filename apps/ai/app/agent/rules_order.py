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
- Tout texte que tu écris est prononcé au client. N'écris donc rien avant ou entre tes appels d'outils : ni analyse, ni note pour toi (« quantité inhabituelle, je crée le brouillon… », « jeudi est bien un jour de livraison » sont interdits). Tu parles une fois, à la fin.
- Unités : farines et sucre au sac (25 kg ; épeautre 10 kg), « 10 de tradi » = 10 sacs, jamais 10 kilos. Tourage, beurre, chocolat, fruits secs au kilo ; crème et lait au litre ; viennoiserie surgelée et emballages au carton ; levure au pain de 500 g ; œufs au plateau de 30. Dis les quantités avec leur unité (« douze sacs de tradi »).
- « Chocolatine » et « pain au chocolat » sont le même produit : ne corrige jamais le client.
- À l'oral, nomme le produit comme le client (« tradi », « gruau », « tourage AOP », « crème »), jamais le nom complet du catalogue ni sa référence (pas de « farine de blé T55 tradition française »).
- Commande : dès que des produits et des quantités sont dits, appelle place_order en UN SEUL appel, avec chaque produit tel que dit (« said »), sa quantité, l'unité dite et le jour dit. Il vérifie le jour, trouve le produit (même ambigu), convertit les unités, crée ou modifie la commande et renvoie la relecture : n'appelle pas en plus check_delivery_date, resolve_product, create_draft_order ni review_order. S'il renvoie « next », rien n'est écrit : pose cette question au client (jour impossible → propose le jour qu'il donne).
- Une seule commande par appel : un changement d'avis (« finalement 12 », « enlève le seigle », « plutôt vendredi ») = place_order avec order_id de la commande en cours et seulement ce qui change (quantité 0 = retirer) ; ne crée jamais une deuxième commande. Si le client renonce, cancel_draft_order.
- « Comme d'hab » = la commande habituelle de la fiche client (pas la dernière commande). Cite seulement les deux ou trois produits principaux avec leur quantité, puis demande « et le reste comme d'habitude ? ».
- Les jours de livraison de l'ERP font foi : ignore les notes « Fermé le … » des fiches (périmées), n'en parle pas. Seul le client peut annoncer une fermeture ; s'il le fait, propose le jour livré suivant et mémorise-le (save_context).
- Relecture parlée comme une personne, pas une liste : les mots du client pour les produits, puis « et vous serez livrés mercredi 25 », puis le total dans sa propre phrase (« Ça fait 99 euros hors taxes, plus 12 euros de livraison. »), puis une question (exemple : « C'est noté, cinq sacs de tradi, et vous serez livrés mercredi 25 novembre. Ça fait 99 euros hors taxes, plus 12 euros de livraison. Je vous la confirme ? »). Jamais « livrés mercredi, plus 12 euros » collés en fin de liste ; pas d'adresse ni de prix unitaire sauf si on te les demande.
- Avec le résultat de place_order (ou de review_order) : relis sa phrase « readback » (produits, quantités, jour) ; dis ses « alerts » et sa remarque « franco » s'il y en a, simplement, sans code technique ni chiffre interne. Si « askFirst » n'est pas vide, fais confirmer cette quantité inhabituelle. Si « duplicateDrafts » n'est pas vide (autres brouillons de l'agent pour ce client) : un brouillon « sameAsThis » est un doublon, abandonne-le (cancel_draft_order) sans en parler ; un autre (resté d'un appel précédent), relis son « readback » et pose une question fermée : « Il restait aussi … non validé : je l'ajoute à cette commande ? » (oui = ajout, non = annulation), puis fais-le. Ne laisse jamais deux commandes ouvertes par l'agent pour le même client. Si « sameDayOrders » n'est pas vide, le client a déjà une commande pour ce jour : pose UNE question fermée, à laquelle « oui » répond sans ambiguïté : « Vous avez déjà une livraison mercredi : je l'ajoute dedans ? » (oui = ajout, non = commande à part). Jamais « A ou B ? ». Puis attends sa réponse.
- Prix : pour dire un prix ou un total, appelle quote_line et répète ses phrases « say » et « total » ; ne calcule jamais toi-même un prix au carton, à la plaque ou un total.
- Dès que le client répond à ta relecture, appelle confirm_order tout de suite (sans tout revérifier) avec client_answer = sa réponse mot pour mot et read_back = ta relecture : un vérificateur décide si c'est un vrai oui. Si confirmed=false, suis « next » (ne dis pas que c'est validé). Si canConfirm=false, ne confirme pas et dis pourquoi.
- Compte bloqué : ne prends aucune commande et ne promets rien ; ne donne aucun détail comptable interne ; dis que la comptabilité (Sandrine) le rappelle, et enregistre la demande avec log_client_event (type call).
- « À quelle heure vous passez ? », « quand arrive le camion ? » : delivery_eta, puis dis sa phrase « say » telle quelle, sans rien promettre de plus.
- Réclamation sur une livraison (manquant, abîmé, erreur, qualité) : report_delivery_issue d'abord (il retrouve la vraie livraison, le montant, et l'enregistre) ; s'il renvoie « next » sans l'avoir enregistrée, pose sa question. Excuse-toi en une phrase, propose ses options, puis settle_delivery_issue avec le choix du client (order_id = la commande en cours s'il y en a une). Ne fais jamais payer un manquant : jamais de commande payante pour le remplacer, jamais de geste au-delà de ce que l'outil propose."""


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


# ── T3 / T4: read the order back, the ERP's warnings, franco, unusual quantities (used by tools/order_review.py) ──

FRANCO_HT = 150.0  # « Franco de port 150 € HT ; en dessous, 12 € de livraison » (01-entreprise.md)
DELIVERY_FEE_HT = 12.0
UNUSUAL_RATIO = 5  # a line at 5× (or more) the client's usual quantity is read back and confirmed first

# What the caller may hear for each ERP warning code. None = internal, never said to the caller.
# `blocks` = the order must not be confirmed while it is there.
WARNINGS_FOR_CALLER: dict[str, tuple[str | None, bool]] = {
    "client_blocked": ("votre compte est bloqué : je ne peux pas valider de commande, la comptabilité vous rappelle", True),
    "credit_limit": ("cette commande dépasse votre plafond de crédit : la comptabilité doit la valider avant", True),
    "no_route": ("aucune tournée ne passe chez vous ce jour-là", True),
    "insufficient_stock": (None, True),  # said per product below, with what is left
    "expiring_soon": (None, False),  # said per product below, with the date (idée 3, Amine K.)
    "price_below_cost": (None, False),  # margin: internal
}


def fr_number(x: float) -> str:
    """12.0 → "12", 1.5 → "1,5"."""
    return f"{x:g}".replace(".", ",")


def _plural(word: str, n: float) -> str:
    if n <= 1 or word.endswith(("s", "x")):
        return word
    return word + ("x" if word.endswith("eau") else "s")


def say_quantity(qty: float, unit: str | None, caliber: str | None = None) -> str:
    """How a quantity is said: (12, piece, "sac 25 kg") → "12 sacs", (40, kg) → "40 kilos", (4, box, "carton 140") → "4 cartons"."""
    if unit == "kg":
        return f"{fr_number(qty)} {'kilo' if qty <= 1 else 'kilos'}"
    if unit in ("liter", "l"):
        return f"{fr_number(qty)} {'litre' if qty <= 1 else 'litres'}"
    word = (caliber or "").split()[0] if caliber else ("carton" if unit == "box" else "pièce")
    return f"{fr_number(qty)} {_plural(word, qty)}"


def short_name(product_name: str) -> str:
    """"Farine de blé T55 tradition française (sac 25 kg)" → "Farine de blé T55 tradition française"."""
    return product_name.split(" (")[0].strip()


def franco_note(total_ht: float) -> str | None:
    """Below 150 € HT there is a 12 € delivery fee: worth saying, with what is missing."""
    if total_ht >= FRANCO_HT or total_ht <= 0:
        return None
    missing = FRANCO_HT - total_ht
    return (f"la commande fait {fr_number(round(total_ht))} euros hors taxes : en dessous de 150 euros, il y a 12 euros de "
            f"livraison ; il manque environ {fr_number(round(missing))} euros pour être livré gratuitement")


def unusual_lines(lines: list[dict], usual: list[dict], ratio: float = UNUSUAL_RATIO) -> list[dict]:
    """Lines at `ratio`× or more of the client's usual quantity for that product (a « 100 » heard for « 10 »…)."""
    avg = {u["productId"]: u.get("avgQty") or 0 for u in usual}
    out = []
    for line in lines:
        usual_qty = avg.get(line["productId"]) or 0
        if usual_qty > 0 and line["qty"] >= ratio * usual_qty:
            out.append({"productId": line["productId"], "qty": line["qty"], "usualQty": round(usual_qty, 1)})
    return out


_FR_MONTH_ABBR = ("janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc")


def expiry_alert(warning: dict, order: dict) -> str | None:
    """ERP « Levure fraîche… (pain de 500 g) : le lot lot_014289 expire le ven. 27 nov. » → « la levure fraîche… que je
    vous livrerais est à utiliser avant le vendredi 27 novembre, juste après la livraison : ça vous va pour votre
    production ? » (None if the message cannot be read: then nothing is said, as before)."""
    m = re.search(r"expire le \S+ (\d{1,2}) (\S+?)\.?$", warning.get("message") or "")
    line = next((li for li in order.get("lines", []) if li.get("productId") == warning.get("productId")), None)
    if not m or not line or not order.get("deliveryDate"):
        return None
    month = next((i for i, a in enumerate(_FR_MONTH_ABBR, 1) if m.group(2).lower().startswith(a[:3])), None)
    if not month:
        return None
    delivered = date.fromisoformat(order["deliveryDate"][:10])
    year = delivered.year + (1 if month < delivered.month else 0)
    try:
        expires = date(year, month, int(m.group(1)))
    except ValueError:
        return None
    name = short_name(line.get("productName", "")).lower()
    return (f"le lot de {name} que je vous livrerais est à utiliser avant le {french_day(expires)}, juste après la "
            "livraison : demande-lui si ça lui va pour sa production, ou s'il en veut moins")


def review(order: dict, products: dict[str, dict], usual: list[dict], client_orders: list[dict] | None = None) -> dict:
    """
    Everything to read back before confirm_order, deterministic:
      readback   : "12 sacs de Farine de blé T55 tradition française, … ; livraison jeudi 26 novembre"
      alerts     : what to tell the caller (ERP warnings translated, internal ones dropped)
      franco     : the 12 € fee note when the order is below 150 € HT
      askFirst   : unusual quantities to have confirmed
      canConfirm : False when a warning blocks (client blocked, credit limit, no route, missing stock)
      duplicateDrafts / sameDayOrders : see other_open_orders (`client_orders` = the client's order list)
    """
    parts = []
    for line in order["lines"]:
        p = products.get(line["productId"]) or {}
        free = " offerts (réclamation)" if line.get("unitPrice") == 0 else ""
        parts.append(f"{say_quantity(line['qty'], line.get('unit') or p.get('unit'), p.get('caliber'))} de {short_name(line.get('productName') or p.get('name', ''))}{free}")
    when = french_day(date.fromisoformat(order["deliveryDate"][:10])) if order.get("deliveryDate") else None
    readback = ", ".join(parts) + (f" ; livraison {when}" if when else "")

    alerts: list[str] = []
    blocking: list[str] = []
    for w in order.get("warnings") or []:
        said, blocks = WARNINGS_FOR_CALLER.get(w.get("code"), (None, False))
        if w.get("code") == "insufficient_stock":
            line = next((li for li in order["lines"] if li["productId"] == w.get("productId")), None)
            if line:
                p = products.get(line["productId"]) or {}
                left = max(0.0, line.get("available") or 0)
                said = (f"{short_name(line.get('productName', ''))} : il n'en reste que "
                        f"{say_quantity(left, line.get('unit') or p.get('unit'), p.get('caliber'))}") if left > 0 else \
                    f"{short_name(line.get('productName', ''))} : en rupture"
        if w.get("code") == "expiring_soon":  # idée 3: a short date is the caller's business too (FEFO lot served)
            said = expiry_alert(w, order)
        if said and said not in alerts:
            alerts.append(said)
        if blocks:
            blocking.append(w.get("code"))

    unusual = unusual_lines(order["lines"], usual)
    ask_first = []
    for u in unusual:
        p = products.get(u["productId"]) or {}
        name = short_name(p.get("name", u["productId"]))
        ask_first.append(f"{say_quantity(u['qty'], p.get('unit'), p.get('caliber'))} de {name}, alors que d'habitude c'est "
                         f"environ {say_quantity(u['usualQty'], p.get('unit'), p.get('caliber'))}")
    out = {
        "orderId": order.get("id"),
        "readback": readback,
        "totalHt": order.get("totalHt"),
        "canConfirm": not blocking,
        "alerts": alerts,
        "askFirst": ask_first,
    }
    if note := franco_note(order.get("totalHt") or 0):
        out["franco"] = note
    if blocking:
        out["blockedBy"] = sorted(set(blocking))
    duplicates, same_day = other_open_orders(order, client_orders or [], products)
    if duplicates:
        out["duplicateDrafts"] = duplicates
    if same_day:
        out["sameDayOrders"] = same_day
    return out


OPEN = ("draft", "confirmed", "prepared")


def other_open_orders(order: dict, client_orders: list[dict], products: dict[str, dict] | None = None) -> tuple[list[dict], list[dict]]:
    """
    The client's other orders that matter before confirming `order`:
      duplicates : other DRAFTS created by the voice agent (a draft left behind when the agent re-created the order
                   instead of editing it: the very bug seen in S31 v1) → to cancel before confirm_order.
      same_day   : other open orders for the same delivery day (e.g. a WhatsApp draft the client sent last night)
                   → to mention: « vous avez déjà une commande pour mercredi, je l'ajoute dedans ? ».
    Drafts from other channels (WhatsApp, e-mail, portal) are never duplicates: the team confirms those.
    """
    duplicates, same_day = [], []
    for o in client_orders:
        if o.get("id") == order.get("id") or o.get("status") not in OPEN:
            continue
        brief = {"orderId": o["id"], "number": o.get("number"), "status": o["status"], "deliveryDate": o.get("deliveryDate"),
                 "source": o.get("source"), "totalHt": o.get("totalHt")}
        if o["status"] == "draft" and o.get("source") == "voice_agent":
            if o.get("lines") is not None:  # detail given by the tool: say what it holds, and whether it is the same order
                brief["readback"] = ", ".join(_line_words(li, products or {}) for li in o["lines"])
                brief["sameAsThis"] = _qty_by_product(o["lines"]) == _qty_by_product(order["lines"])
            duplicates.append(brief)
        elif o.get("deliveryDate") == order.get("deliveryDate"):
            same_day.append(brief)
    return duplicates, same_day


def _qty_by_product(lines: list[dict]) -> dict[str, float]:
    acc: dict[str, float] = {}
    for li in lines:
        acc[li["productId"]] = acc.get(li["productId"], 0) + li["qty"]
    return acc


def _line_words(line: dict, products: dict[str, dict]) -> str:
    p = products.get(line["productId"]) or {}
    return f"{say_quantity(line['qty'], line.get('unit') or p.get('unit'), p.get('caliber'))} de {short_name(line.get('productName') or p.get('name', ''))}"


# ── Prices said out loud (S05 recording: « 92 euros la plaque de 2 kilos… pardon, 18 euros 40 ») ──
# The model multiplied in its head and got it wrong on the phone. The arithmetic is done here, the model only says it.

_FR_WORD_UNITS = {"kg": "kilo", "l": "litre"}


def fr_money(x: float) -> str:
    """9.2 → "9 euros 20", 92.0 → "92 euros", 0.5 → "50 centimes", 1.05 → "1 euro 05"."""
    cents = round(x * 100)
    e, c = divmod(cents, 100)
    if e == 0:
        return f"{c} centimes"
    euros = f"{e} euro{'s' if e > 1 else ''}"
    return f"{euros} {c:02d}" if c else euros


def packaging(unit: str, caliber: str, product_name: str = "") -> list[tuple[str, float]]:
    """
    The packages a weighed / liquid product is handled in, biggest first, with their size in the selling unit:
      kg, "carton 5 plaques de 2 kg"                       → [("carton", 10), ("plaque", 2)]
      kg, "plaquette 1 kg" (name "… (carton 10 × 1 kg)")  → [("carton", 10), ("plaquette", 1)]
      liter, "carton 6 × 1 L" (name "… (brique 1 L)")     → [("carton", 6), ("brique", 1)]
      kg, "sac 5 kg"                                       → [("sac", 5)]
    Products sold by the piece / box (sacs de farine, cartons de viennoiserie) return [] : the unit IS the package.
    """
    if unit not in ("kg", "liter", "l"):
        return []
    out: list[tuple[str, float]] = []

    def num(s: str) -> float:
        return float(s.replace(",", "."))

    texts = [_norm(t.replace("×", "x")) for t in [caliber, *re.findall(r"\(([^)]*)\)", product_name)]]  # _norm drops "×"
    for t in texts:
        if m := re.match(r"^(\w+)\s+(\d+)\s+(\w+?)s?\s+de\s+(\d+(?:[.,]\d+)?)\s*(kg|l)\b", t):  # carton 5 plaques de 2 kg
            out += [(m[1], int(m[2]) * num(m[4])), (m[3], num(m[4]))]
        elif m := re.match(r"^(\w+)\s+(\d+)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(kg|l)\b", t):  # carton 6 × 1 L
            out.append((m[1], int(m[2]) * num(m[3])))
        elif m := re.match(r"^(\w+)\s+(\d+(?:[.,]\d+)?)\s*(kg|l)\b", t):  # sac 5 kg, brique 1 L
            out.append((m[1], num(m[2])))
    seen, uniq = set(), []
    for word, size in sorted(out, key=lambda p: -p[1]):
        if word not in seen:
            seen.add(word)
            uniq.append((word, size))
    return uniq


def to_selling_qty(qty: float, said_unit: str | None, unit: str, caliber: str, product_name: str = "") -> float:
    """What the caller said → quantity in the product's selling unit: 3 cartons of tourage → 30 (kg), 50 kg of flour → 2 sacks."""
    said = _said(said_unit)
    if unit in ("kg", "liter", "l"):
        if said is None or said in ("kg", "l"):
            return qty
        word = said.rstrip("sx") if said.endswith(("s", "x")) and said not in ("colis",) else said
        for w, size in packaging(unit, caliber, product_name):
            if w == word or w == said:
                return round(qty * size, 3)
        return qty
    return sacks_from_words(caliber, qty, said_unit)


def quote(qty: float, unit: str, caliber: str, product_name: str, unit_price: float, said_unit: str | None = None) -> dict:
    """
    Price sentences ready to be said, computed (never by the model):
      say       : "9 euros 20 le kilo, soit 92 euros le carton de 10 kilos (18 euros 40 la plaque de 2 kilos)"
      total     : "276 euros hors taxes pour 30 kilos, soit 3 cartons"
    """
    q = to_selling_qty(qty, said_unit, unit, caliber, product_name)
    word = _FR_WORD_UNITS.get("l" if unit == "liter" else unit)
    packs = packaging(unit, caliber, product_name)
    if word:
        say = f"{fr_money(unit_price)} le {word}"
        if packs:
            big, size = packs[0]
            say += f", soit {fr_money(unit_price * size)} le {big} de {fr_number(size)} {word}s"
            if len(packs) > 1 and packs[1][1] != 1:  # « 4 euros 10 la brique de 1 litre » = the litre price again
                small, s2 = packs[1]
                say += f" ({fr_money(unit_price * s2)} {'la' if small.endswith('e') else 'le'} {small} de {fr_number(s2)} {word}{'s' if s2 > 1 else ''})"
    else:
        noun = (caliber or "").split()[0] if caliber else "pièce"
        size = " ".join(caliber.split()[1:]) if caliber else ""
        size = re.sub(r"(\d)\s*kg\b", r"\1 kilos", re.sub(r"(\d)\s*g\b", r"\1 grammes", re.sub(r"(\d)\s*L\b", r"\1 litres", size)))
        say = f"{fr_money(unit_price)} {'la' if noun.endswith('e') else 'le'} {noun}" + (f" de {size}" if size else "")
    total = unit_price * q
    qty_words = say_quantity(q, unit, caliber)
    if word and packs and (n := q / packs[0][1]) == int(n) and n >= 1:
        qty_words += f", soit {fr_number(n)} {_plural(packs[0][0], n)}"
    return {
        "qty": q,
        "unitPrice": unit_price,
        "say": say,
        "total": f"{fr_money(total)} hors taxes pour {qty_words}",
        "totalHt": round(total, 2),
    }


# ── Jev (decision model): "is that a real yes?" and "which product?" (tools/order_jev.py) ──
# Calibrated on 12 real caller answers (mar. 24/11, 113–229 ms each): plain yeses score 0.89–0.96 on « accord »;
# « oui mais… », « et rajoutez… », « attendez », questions score ≤ 0.14, with « change » 0.59–0.93.

YES_MIN = 0.8  # « accord » at or above (and « change » below CHANGE_MIN): confirm
SURE_YES = 0.9  # « accord » at or above: confirm whatever « change » says
NO_MAX = 0.3  # « accord » at or below: do not confirm
CHANGE_MIN = 0.5  # « change » at or above (with no accord): the caller wants something modified
PICK_MIN = 0.6  # Jev's confidence needed to pick a product without asking

# Words the product glossary (03-glossaire-produits.md, « Alias ambigus ») says must be clarified: never settled by an
# alias alone, always by the client's habits (Jev) or by asking.
AMBIGUOUS_WORDS = {"tourage", "lait", "poudre", "farine", "chocolat", "creme"}
_ARTICLES = re.compile(r"^(?:(?:du|de la|des|de|le|la|les|un|une)\s+|de l'|d'|l')")  # not the "de" of « demi-sel »


def _singular(s: str) -> str:
    return " ".join(w[:-1] if len(w) > 3 and w.endswith(("s", "x")) else w for w in s.split())


def alias_match(said: str, products: dict[str, dict]) -> str | None:
    """
    « pains de levure » → prd_0011 when the words are exactly one product's catalogue alias (or name before the
    parenthesis), singular/plural and accents ignored. None when no alias matches, when several products share it, or
    when it is one of the glossary's ambiguous words (« tourage », « poudre »…): those need the client's habits.
    """
    core = _singular(_ARTICLES.sub("", _norm(said)))
    if not core or core in AMBIGUOUS_WORDS:
        return None
    hits = {
        pid
        for pid, p in products.items()
        if p.get("active", True)
        and any(_singular(_ARTICLES.sub("", _norm(a))) == core for a in [*(p.get("aliases") or []), p.get("name", "").split(" (")[0]])
    }
    return next(iter(hits)) if len(hits) == 1 else None

JEV_YES_QUESTIONS = {
    "accord": {"type": "noul", "instructions": "Le client accepte la commande telle qu'elle a été relue, sans rien changer."},
    "change": {"type": "noul", "instructions": "Le client demande une modification, un ajout ou pose une question avant de valider."},
}


def classify_answer(accord: float, change: float) -> str:
    """Jev's two probabilities → "yes" | "change" | "no" | "unsure"."""
    # A very clear yes wins: « C'est bon, validez » right after a price question scored accord 0.95 / change 0.55
    # (the question nudges « change » up). A real « oui mais… » never scored accord above 0.14 in the calibration.
    if accord >= SURE_YES or (accord >= YES_MIN and change < CHANGE_MIN):
        return "yes"
    if accord <= NO_MAX:
        return "change" if change >= CHANGE_MIN else "no"
    return "unsure"


NEXT_STEP = {
    "change": "Le client veut modifier ou demande quelque chose : réponds-lui, modifie la commande (update_order_line…), relis, puis redemande son accord.",
    "no": "Le client ne valide pas : ne confirme pas, demande-lui ce qu'il souhaite (modifier, reporter ou abandonner : cancel_draft_order).",
    "unsure": "Réponse ambiguë : ne confirme pas, redemande simplement « je vous la valide ? ».",
}
