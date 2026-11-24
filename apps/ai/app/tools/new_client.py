"""
OWNER: Youssef · a NEW client on the phone becomes a real prospect in the ERP (registered with TEAM_PRELOAD).

Real life: a bakery that has never ordered calls the switchboard. Lucie takes down the business, the contact, the
phone, the delivery address and what they want; she does not take the order (the account must be opened first: terms,
credit, delivery round), but nothing is lost: the prospect card and the request are in the ERP, and the team calls back.

register_new_client:
  - never a duplicate: the phone (any contact of any client) or the exact business name → the existing client is
    returned instead (an active / blocked client is handled as a known client; a prospect is completed);
  - the business type → the ERP's client type and tags (a bakery gets the bakeries' tag, so their price rules apply);
  - the city → the delivery zone: the ERP's zone sheets (communes, quartiers, postal codes), else the zone most of the
    ERP's clients of that city have; the zone's round gives the weekdays; else « hors zone », said honestly;
  - the request (products, quantities, wished day) → an « onboarding » event on the prospect, for the team.
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections import Counter

from pydantic import Field

from .erp import enc
from .registry import ToolContext, tool

# what the caller says → the ERP's client type (the kit names bakeries "fishmonger") and the tags price rules use
KINDS = {
    "boulangerie": ("fishmonger", ["boulangeries"]),
    "patisserie": ("fishmonger", ["patisseries"]),
    "chocolatier": ("fishmonger", ["patisseries"]),
    "salon de the": ("fishmonger", ["patisseries"]),
    "restaurant": ("restaurant", ["chr"]),
    "brasserie": ("brasserie", ["chr"]),
    "snack": ("brasserie", ["chr"]),
    "traiteur": ("caterer", []),
    "hotel": ("hotel", []),
    "cantine": ("canteen", []),
    "collectivite": ("canteen", []),
    "supermarche": ("supermarket", []),
}
DAYS_FR = {"mon": "lundi", "tue": "mardi", "wed": "mercredi", "thu": "jeudi", "fri": "vendredi", "sat": "samedi", "sun": "dimanche"}
_cache: tuple[float, dict] | None = None


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def digits(phone: str | None) -> str:
    d = re.sub(r"\D", "", phone or "")
    return "0" + d[2:] if d.startswith("33") and len(d) == 11 else d


def kind_of(kind: str | None) -> tuple[str, list[str]]:
    k = norm(kind)
    for word, value in KINDS.items():
        if word in k:
            return value
    return ("fishmonger", ["boulangeries"]) if not k else ("restaurant", [])  # the wholesaler's main trade first


def communes(entries: list[dict]) -> dict[str, str]:
    """« Zone X » context sheets (« Communes / quartiers : Toulouse (Capitole) (31000), Blagnac (31700)… ») →
    {"toulouse capitole": X, "capitole": X, "toulouse": X (the zone with most of its quartiers), "31000": X, …}."""
    out: dict[str, str] = {}
    base: dict[str, Counter] = {}
    for e in entries:
        title, body = e.get("title") or "", e.get("body") or ""
        if not title.startswith("Zone ") or "Communes" not in body:
            continue
        zone = title[5:].strip()
        listed = body.split(":", 1)[1].split(". Livr")[0]
        for item in re.split(r",\s*", listed):
            m = re.match(r"\s*(.+?)\s*\((\d{5})\)\s*$", item)
            if not m:
                continue
            name, postal = m.groups()
            out[norm(name)] = out[postal] = zone
            if q := re.match(r"(.+?)\s*\((.+)\)$", name):  # Toulouse (Capitole): the quartier alone, and the city
                out.setdefault(norm(q.group(2)), zone)
                base.setdefault(norm(q.group(1)), Counter())[zone] += 1
    for city, zones in base.items():
        out.setdefault(city, zones.most_common(1)[0][0])
    out["__cities__"] = " ".join(base)  # cities split in quartiers: a quartier said with them wins
    return out


async def _directory(erp) -> dict:
    """Clients (for duplicates), place → zone (zone sheets, then the ERP's clients) and zone → round weekdays. 60 s cache."""
    global _cache
    if _cache and time.monotonic() - _cache[0] < 60:
        return _cache[1]
    clients = await erp.get("/api/clients", {"limit": 1000})
    clients = clients.get("items", clients) if isinstance(clients, dict) else clients

    async def optional(path, query=None):
        try:
            d = await erp.get(path, query)
            return d.get("items", d) if isinstance(d, dict) else d
        except Exception:
            return []

    routes, entries = await optional("/api/routes"), await optional("/api/context", {"entityType": "company", "limit": 1000})
    places = communes(entries or [])
    by_city: dict[str, Counter] = {}
    for c in clients:
        if c.get("city") and c.get("zone"):
            by_city.setdefault(norm(re.sub(r"\s*\(.*\)", "", c["city"])), Counter())[c["zone"]] += 1
    for city, zones in by_city.items():
        places.setdefault(city, zones.most_common(1)[0][0])
    zone_days: dict[str, set] = {}
    for r in routes or []:
        if r.get("zone"):
            zone_days.setdefault(r["zone"], set()).update(r.get("days") or [])
    d = {"clients": clients, "places": places, "zone_days": zone_days}
    _cache = (time.monotonic(), d)
    return d


def clear_cache() -> None:
    global _cache
    _cache = None


def find_existing(clients: list[dict], name: str | None, phone: str | None) -> dict | None:
    """The client with this phone (any contact), else with exactly this business name (accents, case ignored)."""
    p = digits(phone)
    if len(p) >= 9:
        for c in clients:
            if any(digits(x.get("phone")) == p for x in c.get("contacts") or []):
                return c
    n = norm(name)
    if n:
        return next((c for c in clients if norm(c.get("name")) == n), None)
    return None


def zone_for(directory: dict, city: str | None) -> tuple[str | None, list[str]]:
    """« Colomiers », « toulouse, quartier des Minimes », « 31170 », « Saint-Jean » → (zone, round weekdays)."""
    places, c = directory["places"], norm(city)
    zone = None
    if c:
        postal = re.search(r"\b\d{5}\b", c)
        zone = (places.get(postal.group()) if postal else None) or places.get(c)
        if not zone:  # the longest known place said inside the words (a quartier before its city)
            split = set(places.get("__cities__", "").split())
            hits = [k for k in places if k[0].isalpha() and k != "__cities__" and re.search(rf"\b{re.escape(k)}\b", c)]
            zone = places[max(hits, key=lambda k: (k not in split, len(k)))] if hits else None
    days = sorted(directory["zone_days"].get(zone, set()), key=list(DAYS_FR).index) if zone else []
    return zone, days


@tool
async def register_new_client(
    ctx: ToolContext,
    company_name: str = Field(description="Nom de l'établissement, ex. « Boulangerie du Canal »"),
    request: str = Field(description="Ce qu'il veut, en français : produits, quantités, jour souhaité (ex. « 10 sacs de tradi pour jeudi »)"),
    city: str | None = Field(None, description="Ville (ou quartier, code postal) de livraison, vide si pas encore dite"),
    contact_name: str | None = Field(None, description="Nom de la personne au téléphone"),
    phone: str | None = Field(None, description="Téléphone du client"),
    address: str | None = Field(None, description="Adresse de livraison si donnée"),
    kind: str | None = Field(None, description="Type d'établissement : boulangerie, pâtisserie, restaurant, traiteur, hôtel, cantine…"),
) -> dict:
    """
    NOUVEAU CLIENT uniquement : crée sa fiche prospect dans l'ERP et enregistre sa demande pour l'équipe (aucune commande).
    À appeler une fois que tu as le nom de l'établissement, la ville et sa demande ; rappelle-le pour compléter (même
    téléphone = même fiche, jamais de doublon). S'il existe déjà, renvoie le client existant. Register a new prospect.
    """
    directory = await _directory(ctx.erp)
    existing = find_existing(directory["clients"], company_name, phone)
    if existing and existing.get("status") != "prospect":
        return {
            "existing": True, "clientId": existing["id"], "name": existing.get("name"), "status": existing.get("status"),
            "next": "Ce n'est pas un nouveau client : il est déjà dans l'ERP. Traite-le comme un client connu (son id ci-dessus)"
                    + (" ; son compte est BLOQUÉ : ne promets rien, la comptabilité le rappelle." if existing.get("status") == "blocked" else "."),
        }  # fmt: skip

    known = existing or {}
    city = city or known.get("city") or None  # a prospect calling back: what its card already says counts
    zone, days = zone_for(directory, city)
    ctype, tags = kind_of(kind)
    if existing:  # a prospect already (same phone or name): complete it, one card only
        cid, created = existing["id"], False
        patch = {k: v for k, v in {"address": address, "city": city, "zone": zone}.items() if v and not known.get(k)}
        if "zone" in patch:
            patch["deliveryDays"] = days
        if patch:
            await ctx.erp.patch(f"/api/clients/{enc(cid)}", patch)
            clear_cache()
        events = await ctx.erp.get(f"/api/clients/{enc(cid)}/events")
        events = events.get("items", events) if isinstance(events, dict) else events
        said_before = [e.get("description") or "" for e in events or [] if e.get("type") == "onboarding"]
    else:
        body = {
            "name": company_name.strip(),
            "type": ctype,
            "status": "prospect",
            "contacts": [{"name": contact_name or company_name, "role": "Contact (premier appel)", "phone": phone}] if (contact_name or phone) else None,
            "address": address,
            "city": city,
            "zone": zone,
            "deliveryDays": days,  # its sector's round ([] out of zone, not the ERP's default); the team adjusts it
            "tags": tags or None,
            "preferences": "Prospect enregistré par l'assistante vocale lors de son premier appel : compte à ouvrir par l'équipe.",
        }  # fmt: skip
        client = await ctx.erp.post("/api/clients", {k: v for k, v in body.items() if v is not None})
        cid, created, said_before = client["id"], True, []
        clear_cache()

    repeated = already_said(request, said_before, f"{address or ''} {city or ''}")
    if not repeated:  # the same request sent again (the model repeating itself) is not a new event for the team
        note = request.strip() + (f" · contact : {contact_name}" if contact_name else "") + (f" · tél. {phone}" if phone else "")
        title = "première demande à valider" if not said_before else "complément de demande"
        await ctx.erp.post(f"/api/clients/{enc(cid)}/events", {
            "type": "onboarding", "title": f"Nouveau client : {title} ({company_name.strip()})", "description": note,
        })  # fmt: skip

    if zone:
        when = {"zone": zone, "deliveryDays": [DAYS_FR[d] for d in days]}
        where = f" Son secteur est livré : {', '.join(when['deliveryDays']) or 'à confirmer'} (jour exact confirmé par l'équipe)."
    elif city:
        when = {"zone": None, "outOfZone": True}
        where = " Sa ville n'est dans aucune de nos zones de livraison : dis-le honnêtement, l'équipe verra ce qui est possible."
    else:
        when = {"zone": None, "cityUnknown": True}
        where = " Demande-lui sa ville de livraison, puis rappelle cet outil avec."
    card = {k: v for k, v in {"city": city, "address": address or known.get("address")}.items() if v}
    return {
        "registered": True, "created": created, "clientId": cid, "name": company_name.strip(), **card, **when,
        **({"requestAlreadyNoted": True} if repeated else {}),
        "next": ("Sa fiche et sa demande sont enregistrées (dis-le, sans répéter ce que tu as déjà dit) ; l'équipe le rappelle "
                 "pour ouvrir son compte et valider sa première commande ; ne confirme aucune commande. Ce qui est sur sa "
                 "fiche (ville, adresse) est connu : ne le redemande pas. Tu peux donner la disponibilité et le prix "
                 "catalogue, indicatif (avec ce clientId)." + where),
    }  # fmt: skip


FILLER = set(
    "de du des d la le les l un une et a au aux en pour par sur avec chez son sa ses votre vos il elle on nous je "
    "souhaite souhaitee voudrait veut demande demandee adresse livraison livrer nouveau nouvelle client premier contact "
    "aussi ajout ajouter precedente".split()
)


def words(s: str) -> set[str]:
    return set(norm(s).split()) - FILLER


def already_said(request: str, before: list[str], known: str = "") -> bool:
    """Nothing new in `request` (once the earlier requests and the card's address / city are taken out): the model is
    repeating itself. « 10 sacs de tradi pour jeudi. Adresse : 3 rue des Lilas » after « 10 sacs de tradi pour jeudi »
    → True; « et aussi du beurre » → False."""
    if not before:
        return False
    said = words(request)
    new = said - words(" ".join(b.split(" · contact")[0].split(" · tél.")[0] for b in before)) - words(known)
    return not new or len(new) / max(1, len(said)) <= 0.25
