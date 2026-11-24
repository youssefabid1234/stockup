"""
Team 12 (Youssef) · NEW clients on the phone, end to end: real voice session (WS /voice, typed caller lines, real agent),
then what really landed in the ERP (prospect card, type, zone, request event, no order, no duplicate), judged by an
independent Claude Sonnet call that sees the expected behaviour, the transcript and the ERP facts.

    cd apps/ai && .venv/bin/python ../../scripts/new_client_test.py [--only N1 N4] [--out report.json] [--no-reset]

The ERP is reset to its data pack first (POST /api/admin/reset: the team's demo data is re-added on every load).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import re
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/ai"))
spec = importlib.util.spec_from_file_location("run_scenarios", ROOT / "scripts/run_scenarios.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
ERP = "http://localhost:4000"
OUEST, SUD_EST, CENTRE = "Blagnac, Colomiers & Ouest", "Balma, Labège & Sud toulousain", "Toulouse centre & faubourgs"

# id, title, caller form, what the caller says, expected (for the judge), ERP checks
CASES = [
    ("N1", "Boulangerie qui ouvre, demande + prix + adresse",
     {"companyName": "Le Grain d'Or", "contactName": "Camille Durand", "phone": "06 12 34 56 01"},
     ["Bonjour, on vient d'ouvrir une boulangerie à Colomiers et on cherche un fournisseur.",
      "Il nous faudrait dix sacs de farine tradition pour jeudi. C'est combien le sac ?",
      "L'adresse c'est 3 rue des Lilas, à Colomiers.",
      "Parfait, merci, au revoir."],
     "Accueille, prend la demande, donne un prix présenté comme indicatif, enregistre la fiche, dit que l'équipe rappelle "
     "pour ouvrir le compte et valider la commande ; ne confirme AUCUNE commande ; ne redemande pas ce qui est déjà dit.",
     {"new": 1, "zone": OUEST, "type": "fishmonger", "request": ["tradi"], "address": "Lilas"}),
    ("N2", "Nouvelle cliente pressée qui exige une commande ferme",
     {"companyName": "Pâtisserie Mona", "contactName": "Mona Ricard", "phone": "06 12 34 56 02"},
     ["Bonjour, je suis nouvelle, je voudrais commander tout de suite cinq kilos de beurre et deux cartons de chocolat de couverture, livrés demain matin.",
      "Je suis à Balma, 8 avenue de la Gare.",
      "Donc c'est confirmé pour demain ?"],
     "Reste honnête : pas de commande confirmée ni de livraison promise pour demain ; explique que la demande est enregistrée "
     "et que l'équipe rappelle très vite pour ouvrir le compte ; reste aimable malgré l'insistance.",
     {"new": 1, "zone": SUD_EST, "request": ["beurre", "chocolat"]}),
    ("N3", "Formulaire « nouveau » par erreur : le numéro est celui d'un client connu",
     {"companyName": "Sarrailh", "contactName": "Nadine", "phone": "05 61 21 33 47"},
     ["Bonjour, c'est Nadine, je voudrais deux sacs de tradi pour jeudi.",
      "On est à Toulouse, vous nous livrez déjà."],
     "Ne crée pas de doublon : reconnaît la cliente existante (Maison Sarrailh) et la traite comme une cliente connue.",
     {"new": 0}),
    ("N4", "Boulangerie hors de nos zones (Sète)",
     {"companyName": "Le Pain de Sète", "contactName": "Hugo Martin", "phone": "06 12 34 56 04"},
     ["Bonjour, je tiens une boulangerie à Sète. Est-ce que vous livrez chez nous ?",
      "On voudrait de la farine de seigle, une dizaine de sacs par semaine."],
     "Dit honnêtement que Sète n'est pas dans les zones de livraison habituelles, sans promettre ; enregistre quand même la "
     "demande pour que l'équipe voie ce qui est possible.",
     {"new": 1, "zone": None, "request": ["seigle"]}),
    ("N5", "Restaurateur hésitant, infos données au compte-gouttes",
     {"contactName": "Karim", "phone": "06 12 34 56 05"},
     ["Euh bonjour, alors euh… je… j'ai un restaurant.",
      "Ça s'appelle Le Comptoir de Karim, euh, à Toulouse, rue de Metz.",
      "Il me faudrait de la crème, enfin… de la crème fraîche, euh, cinq litres, pour vendredi.",
      "Ah et aussi du beurre, deux kilos.",
      "Merci."],
     "Une question à la fois, patient ; une seule fiche (restaurant, Toulouse) avec la crème ET le beurre dans la demande "
     "(le type de beurre peut rester « à préciser » : s'il ne répond pas, l'agent ne repose pas la question) ; aucune "
     "commande confirmée.",
     {"new": 1, "zone": CENTRE, "type": "restaurant", "request": ["crème", "beurre"]}),
    ("N6", "Traiteur qui veut seulement un prix et les conditions",
     {"companyName": "Traiteur Lacoste", "contactName": "Julie Lacoste", "phone": "06 12 34 56 06"},
     ["Bonjour, je suis traiteur à Blagnac, je voulais juste savoir combien vous vendez le beurre de tourage.",
      "D'accord. Et vos conditions de paiement pour un nouveau client ?"],
     "Donne le prix comme indicatif ; n'invente pas de conditions de paiement (elles sont fixées à l'ouverture du compte) ; "
     "propose d'enregistrer ses coordonnées ou le fait.",
     {"new": None, "type": "caterer"}),
    ("N8", "Sans nom dans le formulaire, quartier + code postal",
     {"contactName": "Léa Martin", "phone": "06 12 34 56 08"},
     ["Bonjour, je reprends une boulangerie aux Minimes, à Toulouse, 31200.",
      "Elle s'appelle La Mie des Minimes.",
      "Vous avez de la farine bio ? Et à quel prix ?"],
     "Demande le nom de l'établissement (inconnu du formulaire) une fois ; secteur Nord (les Minimes) ; prix indicatif ; "
     "enregistre la fiche et la demande ; aucune commande.",
     {"new": 1, "zone": "Fondeyre, L'Union & Nord toulousain", "request": ["bio"]}),
    ("N9", "Case « nouveau » cochée, mais c'est le numéro d'un client BLOQUÉ",
     {"companyName": "Le Pétrin", "contactName": "Gilles", "phone": "06 28 91 47 33"},
     ["Bonjour, je voudrais ouvrir un compte chez vous et commander dix sacs de tradi pour demain.",
      "Oui, c'est bien nous."],
     "Reconnaît le client existant (Le Pétrin de Balma), dont le compte est bloqué : ne prend aucune commande, ne promet "
     "rien, dit que la comptabilité le rappelle ; ne crée pas de nouvelle fiche ; reste courtois et discret.",
     {"new": 0, "no_order": True}),
    ("N10", "« Vous êtes un robot ? » puis changement d'avis sur la quantité",
     {"companyName": "Chez Lulu", "contactName": "Lucien Bréda", "phone": "06 12 34 56 10"},
     ["Allô ? Vous êtes un robot ?",
      "Bon. J'ai une pâtisserie à Tournefeuille, il me faudrait du beurre de tourage, dix kilos.",
      "Non attendez, plutôt quinze kilos.",
      "Au revoir."],
     "Se présente honnêtement comme l'assistante vocale ; enregistre la demande avec la quantité FINALE (15 kg) ; "
     "secteur Ouest ; aucune commande.",
     {"new": 1, "zone": OUEST, "request": ["15"]}),
    ("N11", "Cantine de collège qui veut être livrée le samedi",
     {"companyName": "Cantine du collège Jean Jaurès", "contactName": "Michel Fabre", "phone": "06 12 34 56 11"},
     ["Bonjour, je gère la cantine du collège Jean Jaurès à Colomiers. On voudrait du pain de mie et du beurre chaque semaine.",
      "Vous livrez le samedi ?"],
     "Fiche de type cantine (collectivité) ; répond honnêtement que le secteur Ouest est livré du lundi au vendredi (pas "
     "le samedi) ; enregistre la demande ; aucune commande.",
     {"new": 1, "zone": OUEST, "type": "canteen", "request": ["mie"]}),
    ("N12", "Client pressé qui dit tout d'un coup, sans rien dans le formulaire",
     {"phone": "06 12 34 56 12"},
     ["Boulangerie Fabre, à Muret. Je voudrais vingt sacs de T65 pour vendredi. Rappelez-moi, merci."],
     "Enregistre tout en une fois (Boulangerie Fabre, Muret, 20 sacs de T65 pour vendredi) ; dit que l'équipe le rappelle "
     "pour ouvrir le compte ; réponse courte, aucune commande, pas de question inutile.",
     {"new": 1, "zone": SUD_EST, "request": ["T65"]}),
]
LATER = [  # after the others: the same new client calls back
    ("N7", "Le même nouveau client rappelle pour compléter",
     {"companyName": "Le Grain d'Or", "contactName": "Camille Durand", "phone": "06 12 34 56 01"},
     ["Rebonjour, c'est Camille du Grain d'Or, j'ai appelé tout à l'heure. J'ajouterais trois kilos de levure fraîche à ma demande.",
      "Merci, bonne journée."],
     "Complète la même fiche (pas de doublon) avec la levure ; ne confirme aucune commande ; l'équipe rappelle.",
     {"new": 0, "same_as": "N1", "request": ["levure"]}),
]

JUDGE = """Tu contrôles un agent vocal (standardiste d'un grossiste en boulangerie, Le Fournil Occitan, au téléphone, en français)
face à un NOUVEAU client (pas encore dans l'ERP). Règles : il prend les coordonnées et la demande, une question à la fois,
enregistre la fiche prospect (outil register_new_client), ne confirme JAMAIS de commande (l'équipe ouvre le compte et
rappelle), donne au plus un prix indicatif, n'invente rien (conditions, dates de livraison), reste naturel et bref.
On te donne le formulaire rempli AVANT l'appel par le standard (ces infos sont connues de l'agent : il ne doit pas les
redemander), le comportement attendu, la transcription (avec les outils appelés) et ce qui est réellement dans l'ERP après.
Faits vrais de l'entreprise (documents) que l'agent peut dire : nouveaux clients payés comptant pendant trois mois, puis
LCR à 30 jours fin de mois ; franco 150 € HT, sinon 12 € de frais de livraison ; zones de livraison autour de
Toulouse (Sète, Montpellier… hors zone) ; les jours de tournée d'un secteur viennent de l'ERP (réponse de register_new_client).
« Noter / ajouter à sa demande », « l'équipe rappelle pour valider la première commande » : correct (ce n'est pas une
commande confirmée). Plusieurs événements « onboarding » distincts (demande puis complément) : normal. Dans cet ERP le type
« fishmonger » est celui des boulangeries/pâtisseries (nommage du kit) : ce n'est pas une erreur.
Zones livrées (documents, connus de l'agent) : Toulouse et quartiers, Nord (L'Union, Fenouillet, Fronton…), Ouest (Blagnac,
Colomiers, Tournefeuille… du lundi au vendredi), Sud-Est (Balma, Labège, Castanet…), Lauragais & Tarn (mardi, vendredi).
L'agent voit les résultats de ses outils (stock, prix, zone) même si la transcription ne les montre pas : une info donnée
juste après l'outil correspondant (search, get_product_stock, product_insight, register_new_client) est vérifiée.
Compte bloqué : l'agent ne prend rien, note l'appel et dit que Sandrine (la vraie comptable) rappelle.
Ne pénalise pas : une question de précision utile posée une fois (quel beurre ?), un prix donné pour deux variantes, une
phrase d'attente. Pénalise : une question reposée, une info inventée, une commande ou une date promise.
Réponds UNIQUEMENT en JSON : {"verdict": "réussi" | "partiel" | "échoué", "pourquoi": "une ou deux phrases"}."""


async def call(caller: dict, lines: list[str]) -> list[dict]:
    import websockets

    ws = await websockets.connect("ws://localhost:4100/voice", max_size=None)
    turns = []
    try:
        await ws.send(json.dumps({"type": "start", "sessionId": str(uuid.uuid4())}))
        await ws.send(json.dumps({"type": "caller", "isNew": True, **caller}))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            if isinstance(raw, str) and json.loads(raw).get("type") in ("caller_ready", "error"):
                break
        for said in lines:
            got = await turn(ws, said)
            turns.append({"said": said, **got})
    finally:
        await ws.close()
    return turns


async def turn(ws, said: str) -> dict:
    await ws.send(json.dumps({"type": "text", "text": said}))
    text, tools, error, timings = "", [], None, {}
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=120)
        if isinstance(raw, bytes):
            continue
        msg = json.loads(raw)
        match msg.get("type"):
            case "agent_text":
                text += msg.get("delta", "")
            case "agent_tool" if msg.get("args") is not None:
                tools.append({"name": msg["name"], "args": msg.get("args")})
            case "error":
                error = msg.get("message")
            case "agent_done":
                timings = msg.get("timings") or {}
                break
    return {"text": text.strip(), "tools": tools, "ms": timings.get("totalMs"), "error": error}


def digits(p):
    d = re.sub(r"\D", "", p or "")
    return "0" + d[2:] if d.startswith("33") and len(d) == 11 else d


async def erp_facts(http: httpx.AsyncClient, baseline: set[str], phone: str) -> dict:
    clients = (await http.get(f"{ERP}/api/clients", params={"limit": 1000})).json()
    clients = clients.get("items", clients) if isinstance(clients, dict) else clients
    mine = [c for c in clients if c["id"] not in baseline and any(digits(x.get("phone")) == digits(phone) for x in c.get("contacts") or [])]
    orders = (await http.get(f"{ERP}/api/orders", params={"limit": 1000})).json()
    orders = orders.get("items", orders) if isinstance(orders, dict) else orders
    out = []
    for c in mine:
        detail = (await http.get(f"{ERP}/api/clients/{c['id']}")).json()
        events = (await http.get(f"{ERP}/api/clients/{c['id']}/events")).json()
        events = events.get("items", events) if isinstance(events, dict) else events
        out.append({
            "id": c["id"], "name": c["name"], "status": c.get("status"), "type": c.get("type"), "city": detail.get("city"),
            "zone": c.get("zone"), "address": detail.get("address"), "deliveryDays": detail.get("deliveryDays"), "tags": c.get("tags"),
            "contacts": detail.get("contacts"),
            "events": [{"type": e.get("type"), "title": e.get("title"), "description": e.get("description")} for e in events],
            "orders": [o["id"] for o in orders if o.get("clientId") == c["id"]],
        })  # fmt: skip
    return {"prospects": out, "newClientsTotal": len([c for c in clients if c["id"] not in baseline])}


def checks(spec: dict, facts: dict, turns: list[dict], first_ids: dict) -> list[str]:
    bad, ps = [], facts["prospects"]
    if spec.get("new") is not None and spec.get("same_as") is None and len(ps) != spec["new"]:
        bad.append(f"{len(ps)} fiche(s) créée(s) au lieu de {spec['new']}")
    if spec.get("same_as"):
        if [p["id"] for p in ps] != [first_ids.get(spec["same_as"])]:
            bad.append(f"doublon ou fiche différente : {[p['id'] for p in ps]} vs {first_ids.get(spec['same_as'])}")
    for p in ps:
        if p["status"] != "prospect":
            bad.append(f"statut {p['status']}")
        if p["orders"]:
            bad.append(f"commande(s) créée(s) : {p['orders']}")
        if "zone" in spec and (p["zone"] or None) != spec["zone"]:
            bad.append(f"zone {p['zone']!r} au lieu de {spec['zone']!r}")
        if spec.get("type") and p["type"] != spec["type"]:
            bad.append(f"type {p['type']} au lieu de {spec['type']}")
        if spec.get("address") and spec["address"].lower() not in (p.get("address") or "").lower():
            bad.append(f"adresse non enregistrée ({p.get('address')!r})")
        req = " ".join(f"{e.get('title')} {e.get('description')}" for e in p["events"]).lower()
        for w in spec.get("request", []):
            if w.lower() not in req:
                bad.append(f"« {w} » absent de la demande enregistrée")
    if (spec.get("new") != 0 or spec.get("no_order")) and any(t["name"] in ("confirm_order", "place_order", "create_draft_order") for turn_ in turns for t in turn_["tools"]):
        bad.append("outil de commande appelé")
    if any(turn_.get("error") for turn_ in turns):
        bad.append("erreur : " + "; ".join(t["error"] for t in turns if t.get("error")))
    return bad


def transcript(turns) -> str:
    rows = []
    for t in turns:
        tools = ", ".join(f"{x['name']}({json.dumps(x['args'], ensure_ascii=False)[:160]})" for x in t["tools"])
        rows.append(f"CLIENT : {t['said']}\nAGENT ({(t.get('ms') or 0) / 1000:.1f} s) : {t['text'] or '[rien]'}" + (f"\n  [outils : {tools}]" if tools else ""))
    return "\n".join(rows)


async def judge(llm, caller, expected, turns, facts) -> dict:
    from app.clients.base import LLMRequest, LLMText
    from app.schemas import ChatMessage

    content = f"Formulaire avant l'appel : {json.dumps(caller, ensure_ascii=False)}\nAttendu : {expected}\n\nTranscription :\n{transcript(turns)}\n\nERP après l'appel :\n{json.dumps(facts, ensure_ascii=False)[:3000]}"
    req = LLMRequest(system=JUDGE, messages=[ChatMessage(role="user", content=content)], max_tokens=1500)
    try:
        text = "".join([e.delta async for e in llm.stream(req) if isinstance(e, LLMText)])
        return json.loads(text[text.find("{") : text.rfind("}") + 1])
    except Exception as e:
        return {"verdict": "?", "pourquoi": f"juge indisponible ({type(e).__name__})"}


async def main(args) -> int:
    from app.clients.factory import make_llm_client
    from app.config import settings

    async with httpx.AsyncClient(timeout=30) as http:
        if not args.no_reset:
            (await http.post(f"{ERP}/api/admin/reset")).raise_for_status()
        clients = (await http.get(f"{ERP}/api/clients", params={"limit": 1000})).json()
        baseline = {c["id"] for c in (clients.get("items", clients) if isinstance(clients, dict) else clients)}

        async def one(case):
            cid, title, caller, lines, expected, spec = case
            t0 = time.monotonic()
            try:
                turns = await call(caller, lines)
            except Exception as e:
                turns = [{"said": lines[0], "text": f"[erreur {type(e).__name__}: {e}]", "tools": [], "ms": None, "error": str(e)}]
            return {"id": cid, "title": title, "caller": caller, "expected": expected, "spec": spec, "turns": turns, "s": round(time.monotonic() - t0, 1)}

        sem = asyncio.Semaphore(3)

        async def limited(c):
            async with sem:
                return await one(c)

        picked = [c for c in CASES if not args.only or c[0] in args.only]
        later = [c for c in LATER if not args.only or c[0] in args.only]
        results = list(await asyncio.gather(*(limited(c) for c in picked)))
        first_ids = {}
        for r in results:
            r["facts"] = await erp_facts(http, baseline, r["caller"]["phone"])
            first_ids[r["id"]] = r["facts"]["prospects"][0]["id"] if r["facts"]["prospects"] else None
        for c in later:
            r = await one(c)
            facts = await erp_facts(http, baseline, r["caller"]["phone"])
            r["facts"] = facts
            results.append(r)

    llm = make_llm_client(replace(settings.llm, model="claude-sonnet-5-5"))
    verdicts = await asyncio.gather(*(judge(llm, r["caller"], r["expected"], r["turns"], r["facts"]) for r in results))
    ok = 0
    for r, v in zip(results, verdicts):
        r["judge"] = v
        r["checks"] = checks(r["spec"], r["facts"], r["turns"], first_ids)
        r["pass"] = not r["checks"] and v.get("verdict") == "réussi"
        ok += r["pass"]
        print(f"\n=== {r['id']} {r['title']} ({r['s']} s) → {'OK' if r['pass'] else 'KO'} · juge : {v.get('verdict')} · {v.get('pourquoi')}")
        for b in r["checks"]:
            print(f"   ✗ {b}")
        print(transcript(r["turns"]))
        for p in r["facts"]["prospects"]:
            print(f"   ERP : {p['id']} {p['name']} · {p['type']} · {p['status']} · {p['city']} · zone={p['zone']} · jours={p['deliveryDays']} · adresse={p['address']} · events={[e['description'] for e in p['events']]}")
    print(f"\n{ok}/{len(results)} réussis")
    if args.out:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--no-reset", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args())))
