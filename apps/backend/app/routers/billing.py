"""/api/invoices, /api/payments, /api/receivables."""

from fastapi import APIRouter, Query

from app.core.listing import ListDep, Page
from app.dependencies import CtxDep
from app.schemas.inputs import PaymentInput
from app.schemas.views import InvoiceDetail, InvoiceSummary, PaymentSummary, Receivables
from app.services import invoices as invoice_service
from app.services import payments as payment_service
from app.services import receivables as receivable_service

invoices = APIRouter(prefix="/api/invoices", tags=["billing"])
payments = APIRouter(prefix="/api/payments", tags=["billing"])
receivables = APIRouter(prefix="/api/receivables", tags=["billing"])


@invoices.get("", response_model=list[InvoiceSummary] | Page[InvoiceSummary])
async def list_invoices(
    lq: ListDep,
    status: str | None = Query(None, description="Comma list (overdue is computed); also accepts the pseudo-status `open`"),
    client_id: str | None = Query(None, alias="clientId"),
    q: str | None = Query(None, description="Invoice number or client name"),
):
    """Newest first. sort: number | client | issued | due | ttc | paid | balance | status.
    Envelope extras: counts (per status, ignoring `status`), sums (totalTtc, amountPaid, balance), sumsByStatus."""
    return invoice_service.list_invoices(lq, status=status or None, client_id=client_id or None, q=q or None)


@invoices.get("/{id}", response_model=InvoiceDetail)
async def get_invoice(id: str):
    return invoice_service.invoice_detail(id)


@payments.get("", response_model=list[PaymentSummary] | Page[PaymentSummary])
async def list_payments(
    lq: ListDep,
    client_id: str | None = Query(None, alias="clientId"),
    method: str | None = Query(None, description="Comma list of payment methods"),
    q: str | None = Query(None, description="Client name, reference or allocated invoice number"),
):
    """Newest first. sort: date | client | method | ref | amount. Envelope extras: sums.amount."""
    return payment_service.list_payments(lq, client_id=client_id or None, method=method or None, q=q or None)


@payments.post("", response_model=PaymentSummary, status_code=201)
async def record_payment(body: PaymentInput, ctx: CtxDep):
    """Auto-allocates to the oldest open invoices when `allocations` is omitted."""
    return payment_service.record_payment(ctx, body.data())


@receivables.get("", response_model=Receivables)
async def get_receivables(
    q: str | None = None,
    tag: str | None = None,
    rep: str | None = None,
    zone: str | None = None,
    only_overdue: str | None = Query(None, alias="onlyOverdue", description="true | 1"),
):
    """Aged balance per client, as of business today."""
    return receivable_service.receivables(q=q, tag=tag, rep=rep, zone=zone, only_overdue=only_overdue)
