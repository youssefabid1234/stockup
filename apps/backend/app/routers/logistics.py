"""/api/routes (tournées) and /api/route-runs (one route on one date)."""

from fastapi import APIRouter, Query

from app import crud
from app.core.activity import today
from app.core.listing import ListDep, Page, respond
from app.dependencies import CtxDep, data, iso_date_query
from app.schemas.domain import Route
from app.schemas.inputs import PlanInput, ReorderStopsInput
from app.schemas.views import RouteRunDetail
from app.services import routing

routes = APIRouter(prefix="/api/routes", tags=["logistics"])
route_runs = APIRouter(prefix="/api/route-runs", tags=["logistics"])


@routes.get("", response_model=list[Route] | Page[Route])
async def list_routes(lq: ListDep):
    return respond(crud.routes.all(), lq)


@route_runs.get("", response_model=list[RouteRunDetail] | Page[RouteRunDetail])
async def list_route_runs(lq: ListDep, date: str | None = Query(None, description="YYYY-MM-DD"), route_id: str | None = Query(None, alias="routeId")):
    """Newest date first, then by route."""
    return routing.list_route_runs(iso_date_query(date), lq, route_id=route_id or None)


@route_runs.post("/plan", response_model=list[RouteRunDetail])
async def plan_day(ctx: CtxDep, body: PlanInput | None = None):
    """Puts the confirmed/prepared orders of the date (default today) on the runs of their zones."""
    return routing.plan_day(ctx, data(body).get("date") or today())


@route_runs.patch("/{id}/stops", response_model=RouteRunDetail)
async def reorder_stops(id: str, body: ReorderStopsInput, ctx: CtxDep):
    return routing.reorder_stops(ctx, id, body.order_ids)
