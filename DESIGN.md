# Design system — Voice ERP kit

Calm, dense, Linear-like.
Every screen uses the tokens and components in `apps/web/src/ui/` — no ad-hoc colors, radii or font sizes.

## Principles
- **Hairlines, not boxes.** 1px `border` lines separate things; shadows only on floating layers (popover, side panel).
- **Small radii.** 4px default (`rounded-[4px]`), 3px for chips/badges, 6px max for panels. Never `rounded-lg/xl`.
- **Dense type.** Base 13px. Table rows 34px. Section labels 10.5px uppercase, `tracking-[.08em]`, muted.
- **Full width.** Pages use the whole width (no narrow centered column); must not break 1024–1728px.
- **Header row + optional filter bar.** Row 1 (48px): title (never truncated) + inline tabs + primary action + shell tools.
  Row 2 (40px, hairline, only on lists): search, Selects, DatePickers, "Effacer les filtres" — `PageHeader filters`
  renders it as `<FilterBar>`. Tabs that don't fit fold into a "+N" menu; the shell tools drop their shortcut hints, then
  their labels, before anything clips. Secondary table columns give way at narrow widths (`hideBelow`). No duplicate titles.
- **Focus is always visible.** Keyboard focus = 2px `ring/70` (global `:focus-visible` outline, or `ring-2 ring-ring/70`
  on custom controls); inputs use `border-ring` + `ring-ring/20`. Never a fainter per-page ring.
- **Inline edits and side panels, no modal dialogs.** Detail opens in a right side panel or a detail page.
- **Status = dot + word.** A 6px colored dot followed by the label, never a loud filled pill.
- **Numbers tabular.** `tabular-nums`, right-aligned in tables, € with French formatting (`1 234,50 €`).
- **French UI copy.** Short, plain. Dates `lun. 23 nov.`.
- **Light and dark**, same tokens (`.dark` on `<html>`), toggle persisted in localStorage, default = system.

## Tokens (HSL triplets, used as `hsl(var(--token))`)
Font: Inter (Google Fonts), `font-feature-settings: "cv11","ss01"`; mono: JetBrains Mono for ids/SKUs.

| Token | Light | Dark |
|---|---|---|
| background | 150 25% 99% | 155 22% 7% |
| foreground | 155 18% 12% | 150 12% 92% |
| card | 0 0% 100% | 155 20% 9% |
| muted | 150 16% 96% | 155 13% 17% |
| muted-foreground | 155 8% 42% | 150 8% 63% |
| secondary-foreground | 155 15% 24% | 150 12% 90% |
| border | 150 14% 90% | 155 14% 18% |
| border-hover | 150 14% 82% | 155 12% 34% |
| input | 150 14% 88% | 155 14% 20% |
| primary | 148 70% 28% | 150 58% 46% |
| primary-hover | 148 70% 22% | 150 58% 40% |
| primary-foreground | 150 30% 98% | 155 30% 8% |
| ring | 148 70% 28% | 150 58% 46% |
| row-selected | 148 35% 93% | 150 32% 20% |
| success | 142 66% 36% | 150 55% 45% |
| warning | 38 92% 50% | 40 90% 56% |
| destructive | 0 74% 52% | 0 72% 60% |
| info | 214 84% 49% | 213 82% 62% |
| violet (AI/voice accent) | 262 83% 58% | 258 90% 66% |
| chart-1..5 | 148 68% 38% · 175 55% 40% · 38 90% 52% · 224 64% 56% · 342 68% 56% | 150 58% 52% · 175 50% 52% · 40 88% 60% · 224 62% 66% · 342 66% 64% |

Shadows: `--shadow-sm: 0 1px 3px 0 #24423317, 0 1px 2px -1px #24423314`, side panel `-8px 0 24px -8px #0000001f` (dark: `#03070580`).

## Status colors
- Orders: draft = muted, confirmed = info, prepared = violet, delivered = success, invoiced = foreground/60, cancelled = destructive.
- Invoices: issued = info, partially_paid = warning, paid = success, overdue = destructive, draft/cancelled = muted.
- Purchase orders: draft = muted, sent = info, partially_received = warning, received = success, cancelled = destructive.
- Stock: available ≤ 0 destructive, low warning, expiring ≤ 2 days warning.

## Components (apps/web/src/ui)
`Button` (default | primary | ghost | danger; md 32px / sm 26px), `IconButton`, `Input`, `Select`, `Textarea`,
`Badge`/`StatusDot`, `Table` (sticky header, 34px rows, hover row, selected row = row-selected),
`PageHeader` (title + tabs + actions, `filters` → `FilterBar` row), `FilterBar`, `Tabs` (underline, inline, "+N" overflow menu), `SidePanel` (right, 480px, hairline),
`Section` (10.5px uppercase label + content), `KeyValue` list, `Stat` (KPI), `EmptyState`, `Skeleton`,
`Toaster` + `toast()`, `CommandK` (search palette on ⌘K using /api/search), `ThemeToggle`, `Money`, `Qty`, `DateLabel`.
`DatePicker`: never use a native `<input type=date>` (`<DatePicker value onChange min max size presets clearable/>`, popover calendar, fr-FR, business today; `scripts/check-no-native-date.sh` enforces it).
`Select`: never use a native `<select>` (`<Select value onChange options placeholder size filterable/>`, Input-like trigger + anchored listbox: hairline, 4px radius, shadow-pop, 13px rows, check on selected, muted hint, group headings, filter field above 8 options, full keyboard; `scripts/check-no-native-controls.sh` enforces it with the date rule).
Icons: lucide-react, 14–16px, stroke 1.75.

## Layout
- Left sidebar 232px: workspace name, ⌘K search, nav groups (Ventes, Achats & stock, Finance, Logistique, IA, then Activité and Groupes), live-feed status and theme toggle at the bottom. Resizable; ⌘\ or ⌘B collapses it to a 56px rail.
- Main: PageHeader 48px (+ FilterBar 40px on lists), then content scrolling.
- Right: Assistant panel (AI chat) toggled with ⌘J, 400px (resizable), pushes content.
- Activity feed: live events (SSE) with actor icon — voice/AI events tinted violet so the ERP visibly updates during a call.
