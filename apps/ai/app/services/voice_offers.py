"""A small state machine for verified offers in the voice conversation."""

import asyncio
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date

from app.agent.rules_order import french_day, packaging, quote, say_quantity, short_name, to_selling_qty
from app.schemas import ChatMessage, ToolCall
from app.tools import ErpClient, ToolContext
from app.tools.erp import ErpError, enc
from app.tools.orders import summarize_order
from app.agent.loop import to_json

LOOKUP_BUDGET = 0.15
CONFIRM_QUESTION = re.compile(
    r"\s*(?:[Jj]e (?:vous )?(?:la |le )?(?:valide|confirme)(?: (?:la|cette|votre) commande)?|[Cc]'est bon pour vous)\s*\?$"
)
NO = re.compile(r"(?:non(?: merci| pas interesse(?:e)?)?|pas interesse(?:e)?|pas maintenant|une autre fois)")
YES = re.compile(r"(?:oui(?: allez y| je vous ecoute| bien sur| volontiers)?|allez y|je vous ecoute|d accord|volontiers|ok)")
PRICE = re.compile(r"\b(?:prix|combien|tarif|ca coute)\b")
WORDS = ("zero un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize").split()
ADD = re.compile(
    r"(?:oui )?(?P<verb>ajoutez|rajoutez|mettez|prends|prendrais|voudrais)(?P<pronoun> en| moi)? "
    r"(?P<qty>\d+|\w+)(?: (?P<tail>.*))?"
)
PACKS = {"carton", "plaque", "caisse", "boite", "sac", "seau", "brique", "bidon", "colis"}


def normalized(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


def product_caliber(offer: dict) -> str:
    caliber = offer.get("caliber") or ""
    return re.sub(r"^carton of (\d+) sheets of ", r"carton \1 plaques de ", caliber)


def amount_requested(text: str, offer: dict) -> float | None:
    if not (match := ADD.fullmatch(text)):
        return None
    number = match["qty"]
    qty = int(number) if number.isdigit() and len(number) <= 6 else WORDS.index(number) if number in WORDS else 0
    if not qty:
        return None
    unit, _, rest = (match["tail"] or "").partition(" ")
    unit = unit.rstrip("s") if unit != "colis" else unit
    name = normalized(short_name(offer["productName"]))
    if unit and unit not in PACKS | {"kilo", "kg", "litre", "l", "piece", "unite"}:
        rest, unit = match["tail"], ""
    rest = re.sub(r"^(?:de |du |d |le |la )", "", rest)
    if (rest and rest != name) or (not unit and not rest and match["pronoun"] != " en"):
        return None
    product_unit, caliber = offer["unit"], product_caliber(offer)
    if not unit:
        return qty * offer["quantity"]
    if unit in PACKS:
        if product_unit in {"kg", "liter"} and unit not in {word for word, _ in packaging(product_unit, caliber, offer["productName"])}:
            return None
        if product_unit not in {"kg", "liter"} and unit != normalized(caliber).split(" ")[0] and not (
            product_unit == "box" and unit in {"boite", "carton", "caisse"}
        ):
            return None
    elif unit in {"kilo", "kg", "litre", "l"} and product_unit not in ({"kg"} if unit in {"kilo", "kg"} else {"liter"}):
        # The standard conversion also handles sacks sold by unit with an explicit kg caliber.
        if unit not in {"kilo", "kg"} or "kg" not in caliber.lower():
            return None
    return to_selling_qty(qty, unit, product_unit, caliber, offer["productName"])


@dataclass
class Handled:
    text: str
    order: dict | None = None
    review: dict | None = None

    def remember(self, history: list[ChatMessage]) -> None:
        for name, result in (("get_order", self.order), ("review_order", self.review)):
            if not result:
                continue
            call = ToolCall(id=uuid.uuid4().hex, name=name, arguments={"orderId": result.get("id") or result["orderId"]})
            history.extend([
                ChatMessage(role="assistant", tool_calls=[call]),
                ChatMessage(role="tool", tool_call_id=call.id, name=name, content=to_json(result)),
            ])


class CallOffers:
    def __init__(self, client_id: str, session_id: str, outbound: dict | None = None):
        self.client_id = client_id
        self.session_id = session_id
        self.outbound = outbound
        self.erp = ErpClient("voice_agent")
        self.draft: str | None = None
        self.offered = bool(outbound)
        self.pending: dict | None = None
        self.permission = bool(outbound)
        self.quoted = False

    async def complete(self) -> None:
        if self.outbound:
            try:
                async with asyncio.timeout(1):
                    await self.erp.post(f"/api/outbound-demo/attempts/{enc(self.outbound['id'])}/complete", {"sessionId": self.session_id})
            except (ErpError, TimeoutError):
                pass  # the server also closes abandoned calls

    async def respond(self, heard: str) -> Handled | None:
        text = normalized(heard)
        outbound_offer = self.outbound["offer"] if self.outbound else None
        if self.permission:
            self.permission = False
            if YES.fullmatch(text) or PRICE.search(text):
                if not (offer := await self._check(outbound_offer)):
                    return Handled("L’offre vient de changer. Merci de m’avoir répondu, bonne journée.")
                self.pending = offer
                self.quoted = True
                reason = "Vous en commandez régulièrement. " if offer["purchaseCount"] >= 2 else "C’est une nouveauté du catalogue. "
                return Handled(f"Je vous appelais pour le produit {short_name(offer['productName'])}. {reason}{self._price(offer)}")
            if NO.fullmatch(text):
                await self._decline(outbound_offer)
                return Handled("Bien sûr. Merci de m’avoir répondu, bonne journée.")
            self.permission = True
            return Handled("C’est l’assistant vocal du Fournil Occitan. Est-ce que je peux vous présenter l’offre ?")

        if not (offer := self.pending):
            return None
        if NO.fullmatch(text):
            self.pending = None
            await self._decline(offer)
            return Handled(await self._readback("Bien sûr."))
        if YES.fullmatch(text) or PRICE.search(text):
            if not (fresh := await self._check(offer)):
                self.pending = None
                return Handled(await self._readback("L’offre vient de changer."))
            self.pending = fresh
            self.quoted = True
            return Handled(self._price(fresh))
        request = text
        if self.quoted and re.fullmatch(r"(?:\d+|\w+)(?: (?:cartons?|plaques?|sacs?|caisses?|boites?|kilos?|kg|litres?|unites?|pieces?))?", text):
            request = f"ajoutez en {text}"
        if qty := amount_requested(request, offer):
            try:
                order = await self.erp.post(f"/api/recommendations/{enc(self.client_id)}/accept", {
                    "offer": offer, "quantity": qty, "orderId": self.draft, "requestId": self.session_id,
                })
            except ErpError:
                self.pending = None
                return Handled(await self._readback("Je dois revérifier le tarif et le stock de cette offre."))
            self.pending = None
            self.draft = order["id"]
            spoken = f"J’ai ajouté {say_quantity(qty, offer['unit'], product_caliber(offer))} de {short_name(offer['productName'])}."
            review = await self._review()
            return Handled(self._recap(spoken, review), summarize_order(order), review)
        if ADD.match(text) and (" en " in f" {text} " or " moi " in f" {text} " or normalized(short_name(offer["productName"])) in text):
            return Handled("Pouvez-vous me préciser la quantité et le conditionnement pour ce produit ?")
        if re.match(r"^(?:oui|d accord|ok)\b", text):
            return Handled("Souhaitez-vous modifier la commande ou en savoir plus sur cette offre ?")
        if re.search(r"\b(?:validez|confirmez) (?:la commande|le panier)\b", text):
            self.pending = None
            return Handled(await self._readback("Je vous relis la commande."))
        self.pending = None
        return None  # another explicit need: resume the standard order conversation

    def observe_order(self, name: str, result: object) -> None:
        if not isinstance(result, dict):
            return
        if name == "place_order" and result.get("written") and result.get("orderId"):
            self.draft = result["orderId"]
        elif name in {"create_draft_order", "add_order_line", "update_order_line", "remove_order_line", "change_delivery_date", "place_order"}:
            if result.get("status") == "draft" and result.get("id"):
                self.draft = result["id"]
        elif name in {"confirm_order", "cancel_draft_order"} and (result.get("confirmed") or result.get("status") in {"confirmed", "cancelled"}):
            self.draft = None

    async def propose(self, text: str, reply: str, review: dict | None) -> tuple[str, dict | None]:
        if self.offered or not self.draft or not review or review.get("orderId") != self.draft or not review.get("canConfirm"):
            return reply, None
        if any(review.get(key) for key in ("alerts", "askFirst", "duplicateDrafts", "sameDayOrders")):
            return reply, None
        if not reply or re.search(r"\b(?:reclamation|abime|manquant|en retard|urgent|rupture|merci|c est tout)\b", normalized(text)):
            return reply, None
        cleaned = CONFIRM_QUESTION.sub("", reply.replace("’", "'")).strip()
        if "?" in cleaned:
            return reply, None
        # Do not delay ordinary calls when this read is slow or unavailable.
        try:
            async with asyncio.timeout(LOOKUP_BUDGET):
                offers = await self.erp.get("/api/recommendations", {"clientId": self.client_id, "orderId": self.draft})
        except (ErpError, TimeoutError):
            return reply, None
        if not offers:
            return reply, None
        offer = offers[0]
        product = short_name(offer["productName"])
        if offer["kind"] == "promo":
            line = f"Au fait, il y a une promo sur le produit {product}, que vous prenez régulièrement. Je vous donne le prix ?"
        elif offer["kind"] == "new":
            line = f"Au fait, on vient de référencer {product}, dans la même gamme que vos achats habituels. Je vous en parle ?"
        else:
            line = f"Vous prenez aussi souvent {product} avec cette commande. Vous souhaitez en ajouter ?"
        return f"{cleaned} {line}".strip(), offer

    async def _check(self, offer: dict) -> dict | None:
        try:
            async with asyncio.timeout(1):
                offers = await self.erp.get("/api/recommendations", {"clientId": self.client_id, "orderId": self.draft})
        except (ErpError, TimeoutError):
            return None
        return next((o for o in offers if o["id"] == offer["id"]), None)

    async def _decline(self, offer: dict) -> None:
        try:
            async with asyncio.timeout(1):
                await self.erp.post(f"/api/recommendations/{enc(self.client_id)}/decline", offer)
        except (ErpError, TimeoutError):
            pass  # the conversation still honours the refusal

    @staticmethod
    def _price(offer: dict) -> str:
        price = quote(1, offer["unit"], product_caliber(offer), offer["productName"], offer["unitPrice"])["say"]
        until = offer.get("validUntil")
        deadline = f" jusqu’au {french_day(date.fromisoformat(until))}" if until else ""
        return f"C’est {price} hors taxes{deadline}. Quelle quantité souhaitez-vous ?"

    async def _review(self) -> dict | None:
        if self.draft:
            from app.tools.order_review import review_for

            try:
                async with asyncio.timeout(2):
                    return await review_for(ToolContext(self.erp, "voice_agent"), self.draft)
            except (ErpError, TimeoutError):
                pass
        return None

    async def _readback(self, prefix: str) -> str:
        return self._recap(prefix, await self._review())

    @staticmethod
    def _recap(prefix: str, review: dict | None) -> str:
        if not review:
            return prefix
        recap = review["readback"].replace(" ; ", ". ")
        alerts = " ".join(f"{a.rstrip('.')}." for a in review.get("alerts", []))
        if not review["canConfirm"]:
            return f"{prefix} {alerts}".strip()
        if review.get("duplicateDrafts") or review.get("sameDayOrders"):
            return f"{prefix} J’ai aussi une autre commande pour ce jour. Souhaitez-vous vérifier les deux avant de confirmer ?"
        if review.get("askFirst"):
            return f"{prefix} Pouvez-vous me confirmer cette quantité inhabituelle, {review['askFirst'][0]} ?"
        delivery_fee = review.get("franco")
        fee = f" {delivery_fee.rstrip('.')}." if delivery_fee else ""
        return f"{prefix} Je récapitule, {recap}.{fee} Je vous valide la commande ?"
