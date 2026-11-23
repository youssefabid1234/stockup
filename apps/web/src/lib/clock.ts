import { setCategories } from "./labels";
/**
 * The ONE business clock of the web app.
 *
 * The data pack is anchored on a fixed day (`meta.today`, GET /api/meta) while the real clock may be
 * on another day. The API stamps new records with "meta.today + real wall-clock time" (UTC), so the
 * web app does the same: businessNow() = real now shifted by a whole number of days.
 *
 * Use businessNow() / businessToday() for anything relative ("il y a 3 min", "aujourd'hui", "J+2").
 * Plain elapsed-time measures (debounces, "flash for 4 s") can keep Date.now().
 */
import type { IsoDate } from "@kit/shared";
import { api } from "./api";

const DAY_MS = 86_400_000;
let offsetMs = 0;
let anchor: IsoDate | null = null;
let loading: Promise<void> | null = null;

const utcDayStart = (ms: number) => Math.floor(ms / DAY_MS) * DAY_MS;

/** Anchor the clock on the data pack day (idempotent). */
export function setBusinessToday(today: IsoDate | undefined | null) {
  if (!today || !/^\d{4}-\d{2}-\d{2}$/.test(today) || today === anchor) return;
  anchor = today;
  offsetMs = Date.parse(`${today}T00:00:00Z`) - utcDayStart(Date.now());
}

/** Load meta.today once (called before the first render; never throws). */
export function loadBusinessClock(): Promise<void> {
  loading ??= api
    .meta()
    .then((m) => { setBusinessToday(m.today); setCategories(m.categories); })
    .catch(() => undefined);
  return loading;
}

/** Offset (ms, whole days) between the business clock and the real clock. */
export const businessOffsetMs = () => offsetMs;

/** "Now" on the business clock: same wall-clock time, on the data pack day. */
export const businessNow = (): Date => new Date(Date.now() + offsetMs);

/** Business "today" as YYYY-MM-DD (= meta.today once loaded). */
export const businessToday = (): IsoDate => businessNow().toISOString().slice(0, 10);
