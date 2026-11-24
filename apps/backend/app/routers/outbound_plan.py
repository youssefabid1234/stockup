"""Team 12 (Youssef) · Lucie's planned outbound calls (who, why, when) and « call now ». Same switch as the simulated calls."""

from fastapi import APIRouter, Depends

from app.services import outbound_plan

from .outbound_calls import require_enabled

router = APIRouter(prefix="/api/outbound-plan", tags=["outbound-demo"], dependencies=[Depends(require_enabled)])


@router.get("")
async def planned_calls():
    return outbound_plan.current()


@router.post("/refresh")
async def replan():
    return outbound_plan.build()


@router.post("/{plan_id}/call")
async def call_now(plan_id: str):
    return outbound_plan.call_now(plan_id)
