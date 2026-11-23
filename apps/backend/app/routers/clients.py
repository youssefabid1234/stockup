"""/api/clients: list, detail, usual basket, history, negotiated prices, create/update/notes."""

from fastapi import APIRouter, Query

from app.core.listing import ListDep, Page
from app.dependencies import CtxDep, data
from app.schemas.domain import Client, ClientEvent, ClientPrice
from app.schemas.inputs import ClientEventInput, ClientInput, ClientNoteInput, ClientPatch, ClientPriceInput
from app.schemas.views import ClientDetail, ClientEventSummary, ClientSummary, Ok, UsualBasketLine
from app.services import client_events, clients, pricing

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("", response_model=list[ClientSummary] | Page[ClientSummary])
async def list_clients(
    lq: ListDep,
    q: str | None = Query(None, description="Name, code, city or contact"),
    type: str | None = Query(None, description="Comma list of client types"),
    zone: str | None = Query(None, description="Comma list of zones"),
    status: str | None = Query(None, description="Comma list of statuses"),
    tag: str | None = None,
):
    """By name. sort: name | code | type | tags | zone | rep | city | outstanding | overdue | last | revenue30d | status.
    Envelope extras: counts (per status, ignoring `status`), facets.zone, facets.salesRep."""
    return clients.list_clients(lq, q=q or None, type=type, zone=zone, status=status, tag=tag or None)


@router.get("/{id}", response_model=ClientDetail)
async def get_client(id: str):
    return clients.client_detail(id)


@router.get("/{id}/usual", response_model=list[UsualBasketLine])
async def client_usual(id: str):
    """"The usual": what this client typically orders (last 60 days)."""
    return clients.usual_basket(id)


@router.get("/{id}/events", response_model=list[ClientEventSummary] | Page[ClientEventSummary])
async def client_history(
    id: str,
    lq: ListDep,
    type: str | None = Query(None, description="Comma list of event types"),
    status: str | None = Query(None, description="open | resolved"),
    q: str | None = None,
):
    """Relationship history of one client, newest first. sort: at | type | status | open (open issues first, then newest).
    Envelope extras: counts (per type, ignoring `type`)."""
    return client_events.list_client_events(lq, id, type=type or None, status=status or None, q=q or None)


@router.post("/{id}/events", response_model=ClientEvent, status_code=201)
async def add_client_event(id: str, body: ClientEventInput, ctx: CtxDep):
    return client_events.create_client_event(ctx, id, body.data())


@router.put("/{id}/prices/{product_id}", response_model=ClientPrice)
async def set_client_price(id: str, product_id: str, body: ClientPriceInput, ctx: CtxDep):
    """Negotiated price (upsert)."""
    return pricing.set_client_price(ctx, id, product_id, body.price)


@router.delete("/{id}/prices/{product_id}", response_model=Ok)
async def delete_client_price(id: str, product_id: str, ctx: CtxDep):
    return pricing.delete_client_price(ctx, id, product_id)


@router.post("", response_model=Client, status_code=201)
async def create_client(body: ClientInput, ctx: CtxDep):
    return clients.create_client(ctx, body.data())


@router.patch("/{id}", response_model=Client)
async def update_client(id: str, ctx: CtxDep, body: ClientPatch | None = None):
    return clients.update_client(ctx, id, data(body))


@router.post("/{id}/notes", response_model=Client, status_code=201)
async def add_client_note(id: str, body: ClientNoteInput, ctx: CtxDep):
    return clients.add_client_note(ctx, id, body.text, body.author)
