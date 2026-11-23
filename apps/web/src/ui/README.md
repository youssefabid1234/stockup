# UI kit — `@/ui`

Import everything from `@/ui`. Tokens only (no hex, no `rounded-lg`, no ad-hoc font sizes). Icons: lucide 14–16px, `strokeWidth={1.75}`.
Reference pages to copy: `src/pages/clients` (list), `src/pages/client-detail` (detail), `src/pages/activity` (feed).

## Page layout
- `Page`: `<Page><PageHeader/><PageBody/></Page>`. Every page uses it, and it is `relative` so a SidePanel can float inside it.
- `PageHeader`: `title`, `breadcrumb=[{label,to}]`, `count`, `meta` (status / id), `tabs`, `filters`, `actions`. A 48px row (title · tabs · actions · shell tools) and, when `filters` is set, a 40px `FilterBar` row under it. The page gets no other title.
  - The title never truncates (detail names only past 420px); `meta` is clipped first; tabs that don't fit fold into a "+N" menu (the active tab stays visible); then the shell tools lose their shortcut hints, then their labels.
- `FilterBar`: the slim hairline strip under the header (40px). Put every list filter there via `PageHeader filters` (search first, then Selects / DatePickers, `className="ml-auto"` for "Effacer les filtres"). It scrolls horizontally rather than clipping.
- `PageBody`: the scroll area. `flush` removes the padding; use it for full-bleed tables so the header stays sticky.
- `Tabs`: `<Tabs value onChange items={[{id,label,count}]}/>` gives inline underline tabs. Put them in `PageHeader.tabs`. They measure themselves and fold the overflow into a "+N" menu.
- `SidePanel`: `<SidePanel title subtitle onClose actions footer>` is a 480px right panel with no backdrop; Esc closes it. Use it for create/edit forms and quick views. There are no modals.
- `Section`: `<Section title count actions>` adds a 10.5px uppercase label above its content. `SECTION_LABEL` is the same style as a class string.
- `Card`: a hairline box with a 6px radius.

## Data display
- `DataTable`: `<DataTable columns rows getRowId onRowClick selectedId loading empty footer defaultSort inset paginate pageKey server/>`.
  - **Big lists are paginated by the server** (orders, invoices, payments, stock, clients…): `const list = useServerList({ defaultSort })`
    (page + sort in the URL: `?page=`, `?sort=-date`), fetch ONE page with the `use…Page` hook (`{ ...filters, ...list.params }` →
    `{ items, total, counts, sums… }`), then `<DataTable server={{ list, total: data?.total }} rows={data?.items} />`. Columns sort
    through `sortKey` (an API sort field) instead of `sortValue`; tab counts, filter options and footer totals come from the Page
    extras, never from the page rows. Reference: `pages/clients/index.tsx`. Small bounded lists keep the client-side mode below.
  - Columns are `{id, header, cell, numeric?, mono?, muted?, width?, sortValue?, hideBelow?}`. `hideBelow` (px) hides a secondary column while the table is narrower than that, so lists fit 1024–1440 without a horizontal scroll. `numeric` gives right-aligned tabular numbers. `sortValue` lets the user sort by clicking the header.
  - `loading` (with no rows yet) shows skeleton rows. `rows=[]` shows `empty`. Rows flash violet when a live event touches their id.
  - `inset` frames the table for use inside a Section on a detail page (12px padding, no sticky header).
  - Pagination is built in: above `PAGE_SIZE` rows it shows pages of 100 with a footer bar. Sorting applies to the whole list before slicing. `footer` is computed by the page from the whole filtered list (counts, totals), never from the visible page, and it moves into the left side of the pagination bar. `pageKey` gives the table its own URL param when a screen has several paginated tables (`ordersPage`, `invoicesPage`…). Set `paginate={false}` for small embedded tables (order lines, lots of a PO).
- `Table`, `THead`, `TBody`, `TR` (`selected`, `liveId`), `TH`, `TD` (`numeric`, `mono`, `muted`), `TableFrame`: the raw primitives, for custom tables.
- Pagination, for lists that are not a DataTable (such as the Activité feed). It lives in `pagination.tsx`.
  - `PAGE_SIZE` = 100. It is the only place the number lives, and every list uses it.
  - `usePagination(rows, { key?, resetKey?, enabled?, server?, total? })` takes rows that are already filtered and sorted
    (`server: true` + `total`: `rows` is already the current page, fetched with `useServerList().params`). It returns `{ rows, page, pageCount, total, from, to, setPage, anchorRef }`, where `rows` is the current page.
    - The page lives in the URL (`?page=`, or `?<key>=`), so it survives reloads, back/forward and links. It is clamped when the list shrinks.
    - It goes back to page 1 when a filter, tab or search changes: every `useUrlState` setter clears the page params. Setters are same-tick safe (`setQ(""); setType("")` both apply); for several params at once use `useUrlPatch()` (`patch({ tab: "sim", rule: "" })`), both from `@/lib/url-state`. Pass `{ keepPage: true }` for params that only open a panel (`?new=1`, `?p=<id>`). It also goes back to page 1 when `resetKey` changes, for state that is not in the URL, such as the sort.
    - Put `anchorRef` on the top of the list: on a page change it is scrolled back into view.
  - `<Pagination pagination={pg} sticky inset>{summary}</Pagination>` is the footer bar: hairline top, 13px, muted. It reads `1–100 sur 2 192`, with previous/next buttons and page numbers (`1 … 9 10 11 … 22`). It renders nothing when everything fits on one page. `sticky` pins it to the bottom of a full-bleed page and `inset` is for inside a TableFrame.
- `KeyValue`: `<KeyValue items={[{label, value, mono?}]} labelWidth={140}/>`.
- `Stat` and `StatGrid`: `<StatGrid><Stat label value hint icon tone onClick/></StatGrid>` is a row of KPIs separated by hairlines.
- `EmptyState`: `<EmptyState icon title description action compact/>`. `ErrorState`: `<ErrorState onRetry/>`.
- `Skeleton`: `<Skeleton className="h-3 w-24"/>`.

## Status
- `StatusDot`: `<StatusDot kind="order|invoice|purchaseOrder|client|routeRun|stop" value={x.status}/>` renders a dot plus a French word. It also takes a free form: `<StatusDot tone="warning" label="Stock bas"/>`.
- `Dot`: `<Dot tone pulse/>` is the bare 6px dot. `Badge`: `<Badge tone="violet">Agent vocal</Badge>` is a 3px chip for tags and counts, never statuses.
- Status maps (`ORDER_STATUS`, `INVOICE_STATUS`, `PO_STATUS`, `CLIENT_STATUS`, `ROUTE_RUN_STATUS`, `STOP_STATUS`) live in `status.tsx`. To add a status, add one `{label, tone}` entry there. `statusOptions("order")` builds the options for a filter Select.
- `Tone` is one of muted, info, violet, success, warning, destructive or foreground. `TONE_TEXT`/`TONE_DOT` map a tone to its class.
- `ActorIcon`: `<ActorIcon actor="voice_agent"/>`. `isAiActor(a)` is true for AI and voice actors, which are tinted violet.

## Formatting (fr-FR)
- `Money`: `<Money value compact zeroMuted tone/>` gives `1 234,50 €`.
- `Qty`: `<Qty value unit="kg"/>` gives `12,5 kg`, with the unit muted.
- `DateLabel`: `<DateLabel date format="short|long|datetime|relative"/>` gives `lun. 23 nov.` or `il y a 3 min`.
- `Mono`: `<Mono>CMD-2026-000123</Mono>` for ids, SKUs and document numbers.
- The same formatters exist as strings in `@/lib/format`: `fmtMoney`, `fmtQty`, `fmtDate`, `fmtDateTime`, `fmtRelative`, `fmtPercent`, `todayIso`. Enum labels are in `@/lib/labels`: `CLIENT_TYPE_LABEL`, `CATEGORY_LABEL`, `SOURCE_LABEL`, `PAYMENT_METHOD_LABEL`, `MOVEMENT_REASON_LABEL`, `WEEKDAY_LABEL`, `ACTOR_LABEL`.

## Inputs
- `Button`: `<Button variant="default|primary|ghost|danger" size="md|sm" icon={Plus} loading kbd="⌘↵">`. Sizes are 32px (md) and 26px (sm). Each header gets at most one primary button.
- `IconButton`: `<IconButton icon={X} label="Fermer" size="sm"/>`. It is ghost by default and `label` is required.
- `Input`: `<Input size leading={<Icon/>}/>`.
- `SearchInput`: `<SearchInput value onChange placeholder/>`, a compact 28px header search with a clear button.
- `Select`: `<Select value onChange options placeholder="Tous les …" size="sm"/>`, a Stockline listbox (see Select at the end). `placeholder` adds an empty option.
- `Textarea`: a standard textarea.
- `Field`: `<Field label hint><Input/></Field>`.
- `Segmented`: `<Segmented value onChange options={[{id,label}]}/>`.
- `Kbd` and `Spinner`: small helpers.

## Global
- `toast`: `toast.success|error|warning|info(title, description?)` works anywhere. API errors already toast, so don't toast them again.
- `Toaster`, `CommandK` and `ThemeToggle` are mounted once by the shell. `useTheme()` returns `{theme, resolved, setTheme}`.
- `searchResultPath(result)` returns the route for a search hit. `entityPath(entity, id)` in `@/lib/links` does the same for any entity.
- `DatePicker`: `<DatePicker value={iso} onChange={setIso} min max placeholder size="md|sm" presets={[{label,days}]|false} clearable disabled variant="field|inline"/>`. It is the only date input: never use a native `<input type="date">` (guarded by `scripts/check-no-native-date.sh`). Value is ISO `YYYY-MM-DD`, today = business today, the popover floats above SidePanels.
- `AnchoredPopover` / `useAnchoredPosition`: `<AnchoredPopover anchorRef={ref} open matchWidth maxHeight={320}>…</AnchoredPopover>`. Use for every dropdown/autocomplete attached to an input: it portals to `<body>` with `position: fixed`, flips above when there is no room below and follows scroll/resize, so `overflow-hidden` frames (tables, Sections, SidePanels) never clip it. Never use an `absolute` dropdown inside a scrolling or rounded frame.
- Shell chrome (don't rebuild per page): every `PageHeader` ends with the global Assistant toggle (⌘J) after a hairline, injected by the shell through `PageHeaderSlot`; when the row is too narrow, tabs fold into "+N" and the shell tools compact so actions + toggle never move. Sidebar (⌘\ or ⌘B → icon rail), Assistant and every `SidePanel` are resizable via `useResizableWidth(key, def, min, max)` + `<ResizeHandle r edge="left|right"/>` (width saved in `kit-w:<key>`, double-click resets). `SidePanel` takes an optional `id` for its saved width.
- `Select`: `<Select value onChange={(v)=>…} options={[{value,label,hint?,group?,disabled?}]} placeholder size="md|sm" filterable name disabled className/>`. It is the only choice dropdown: never use a native `<select>` (guarded by `scripts/check-no-native-controls.sh`, which also covers native date inputs). The trigger looks like `Input` (32px md / 26px sm, sized to the widest option unless `className` sets a width); the list is an `AnchoredPopover` (works in SidePanels), with a check on the selected item. `hint` renders muted after the label and defaults to the part after " · " (`"Bigouden Marée · Le Guilvinec"`); consecutive options with the same `group` get a heading. A filter field appears above 8 options (`filterable` forces it on/off). Keyboard: Enter/Space/↑/↓ open, ↑↓ Home End PgUp PgDn move, typing jumps (or filters), Enter selects, Esc closes and refocuses, Tab closes. `name` adds a hidden input for native forms.

## Groups (tags) — `tags.tsx`
Groups are `TagDef`s per scope (`client` | `product` | `supplier`), stored as `tags: string[]` on the entity. Managed on `/groups`; used by price rules (`/prices`).
- `TagChip`: `<TagChip tag={def}/>` or `<TagChip scope="client" id="gastro"/>` (label/color resolved from the cached `GET /tags`). 20px, 3px radius, colored dot + label; `onRemove` adds an ×, `onClick` makes it a button.
- `TagList`: `<TagList scope="product" tags={p.tags} max={2} empty="—"/>`, read-only chips with a `+N` overflow (full list in its title).
- `TagEditor`: `<TagEditor scope="client" value={c.tags} entityId={c.id}/>` saves itself (`PATCH /clients/:id {tags}`) and refreshes lists, groups and prices; or controlled with `onChange={(tags) => …}` (may return a promise). Chips with ×, then a dashed "+ Groupe" button opening an `AnchoredPopover`: search, check/uncheck, ↑↓ Enter, and "Créer le groupe « … »" (POST /tags, slug from the label via `tagSlug`).
- `TagDot`, `TagColorPicker`, `TAG_COLORS`, `TAG_DOT` (color → token class: green=chart-1, teal=chart-2, amber=chart-3, blue=chart-4, rose=chart-5, violet, gray=muted), `TAG_SCOPE_LABEL`, `useTagDefs(scope)` (Map id → def).
- Data: `useTags(scope?)`, `useTagMembers(scope, tag)` and `api.tags.{list,create,update,remove,members,setOn}` in `@/lib`.
