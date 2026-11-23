/** French formatters (Intl fr-FR). Use the <Money/Qty/DateLabel> components in JSX; these for strings. */
import type { Unit } from "@kit/shared";
import { businessNow, businessToday } from "./clock";

const eur = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const eur0 = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const num = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
const pct = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 0 });

export const fmtMoney = (v: number | null | undefined, opts?: { compact?: boolean }) =>
  v == null || Number.isNaN(v) ? "—" : (opts?.compact ? eur0 : eur).format(v);
export const fmtNumber = (v: number | null | undefined) => (v == null || Number.isNaN(v) ? "—" : num.format(v));
export const fmtPercent = (v: number | null | undefined) => (v == null || Number.isNaN(v) ? "—" : pct.format(v));

export const UNIT_LABEL: Record<Unit, string> = { kg: "kg", piece: "pce", box: "colis", dozen: "douz.", liter: "L" };
export const fmtQty = (v: number | null | undefined, unit?: Unit | string) =>
  v == null ? "—" : `${num.format(v)}${unit ? ` ${UNIT_LABEL[unit as Unit] ?? unit}` : ""}`;

/** Parse "YYYY-MM-DD" as a LOCAL date (not UTC) and full ISO normally. */
export function parseDate(d: string | Date): Date {
  if (d instanceof Date) return d;
  if (/^\d{4}-\d{2}-\d{2}$/.test(d)) {
    const [y, m, day] = d.split("-").map(Number);
    return new Date(y, m - 1, day);
  }
  return new Date(d);
}

const dShort = new Intl.DateTimeFormat("fr-FR", { weekday: "short", day: "numeric", month: "short" });
const dLong = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const dNum = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
const tShort = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });

/** Formats a date, "—" when missing or invalid (a bad `?date=` in a URL must never crash a page). */
const safe = (f: Intl.DateTimeFormat, d?: string | null) => {
  if (!d) return "—";
  const v = parseDate(d);
  return Number.isNaN(v.getTime()) ? "—" : f.format(v);
};
/** "lun. 23 nov." */
export const fmtDate = (d?: string | null) => safe(dShort, d);
export const fmtDateLong = (d?: string | null) => safe(dLong, d);
export const fmtDateNum = (d?: string | null) => safe(dNum, d);
export const fmtTime = (d?: string | null) => safe(tShort, d);
/** "lun. 23 nov. · 08:42" */
export const fmtDateTime = (d?: string | null) => (d ? `${fmtDate(d)} · ${fmtTime(d)}` : "—");

const rtf = new Intl.RelativeTimeFormat("fr-FR", { numeric: "auto" });
/** "il y a 3 min", "hier", "dans 2 jours" */
export function fmtRelative(d?: string | null, now = businessNow()): string {
  if (!d) return "—";
  const date = parseDate(d);
  const diffS = (date.getTime() - now.getTime()) / 1000;
  const abs = Math.abs(diffS);
  if (abs < 45) return "à l'instant";
  if (abs < 3600) return rtf.format(Math.round(diffS / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diffS / 3600), "hour");
  if (abs < 86400 * 30) return rtf.format(Math.round(diffS / 86400), "day");
  return fmtDate(d);
}

/** Business "today" (data pack day), YYYY-MM-DD. */
export const todayIso = () => businessToday();
