# FASTag Frontend Architecture

## Frontend model

FASTag uses server-rendered Jinja templates with plain HTML, CSS, and
JavaScript. There is no SPA framework or frontend build step. Templates receive
initial state from Flask, then use `fetch()` polling to refresh live state. The
browser is therefore a thin observability and control client over the Flask API;
authorization remains server-side.

## 1. SaaS Design Token System (`static/css/theme.css`)

### Sky/Ice Blue palette

The root token set establishes a consistent SaaS visual language:

| Token family | Examples |
|---|---|
| Canvas/surface | `--bg: #f0f7ff`, `--surface: #fff`, `--surface-alt: #f8fafc` |
| Brand | `--primary: #0284c7`, `--primary-hover: #0369a1`, `--primary-soft: #e0f2fe` |
| Text | dark slate `--text`, muted slate `--text-muted`, faint `--text-faint` |
| Status | green success, red danger, amber warning and matching backgrounds |
| Terminal | `--editor-bg: #0f172a`, `--editor-header: #020617`, light editor text |

Pages use an ice-blue gradient at the top of the viewport, white bordered
cards, and sky-blue focus/active states. These tokens make the live operations,
regional, SQL, DDBMS, and owner views visually coherent without a component
framework.

### Typography, elevation, and reusable primitives

* **Space Grotesk** (`--font-display`) supplies headings and metric values.
* **Inter** (`--font-body`) supplies readable interface text.
* **JetBrains Mono** (`--font-mono`) supplies SQL, paths, IDs, and numeric
  telemetry.
* `--shadow-sm`, `--shadow-md`, and `--shadow-lg` provide progressively deeper
  elevation; cards transition from small to medium shadow on hover.
* `--radius`, `--radius-sm`, and `--radius-pill` standardize cards, controls,
  and status pills.
* `.saas-badge-*` classes create compact success, danger, primary, PK, and FK
  badges. Existing pages also use local `.tag-badge` variants for RFID and
  payment status.
* `.saas-table th` is sticky (`top: 0`) inside scrollable table containers,
  keeping column context visible on long ledgers and query results.

```css
:root {
  --primary: #0284c7;
  --primary-soft: #e0f2fe;
  --editor-bg: #0f172a;
  --shadow-md: 0 4px 12px rgba(2, 132, 199, .07);
  --radius-pill: 9999px;
  --font-display: 'Space Grotesk', sans-serif;
  --font-body: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
.saas-table th { position: sticky; top: 0; z-index: 1; }
```

The stylesheet also supplies responsive grid breakpoints, focus-visible
outlines, buttons, form inputs, callouts, and reduced-motion support.

## 2. Multi-Tier Portal Architecture

The login portal is unified, but the post-login experience is role-specific:

| Role | Route | Experience |
|---|---|---|
| Vehicle Owner | `/portal/<user>` | Personal wallet, vehicles/tags, and own journey ledger |
| City Station Officer | `/city/<city>` | One regional node, local plazas, edge cache, and local SQL |
| Operations Admin | `/dashboard` | Nationwide telemetry, deduplication, SQL, and DDBMS tools |

`app.py` performs redirect and ownership checks before rendering. The frontend
does not hide privileged functionality as its security mechanism; unauthorized
requests are redirected or return HTTP 403 from Flask. Admin navigation exposes
the SQL ledger, global SQL console, DDBMS explorer, raw stream, batch output,
and station summary. City users can access regional views and DDBMS tools, but
not owner data or other cities.

## 3. Live Operations Dashboard (`templates/dashboard.html`)

### Metrics and charts

The dashboard presents four animated metric cards:

* total raw pings;
* cumulative clean deduplicated journeys;
* last-window deduplication ratio;
* current pings per second.

Chart.js renders a filled, tensioned line chart from
`/api/stats/throughput?buckets=30` and a doughnut gauge whose two slices are
“Duplicates Filtered” and “Clean Journeys.” The gauge center shows the current
ratio and a raw-to-journey subtitle.

```javascript
async function pollStats() {
  const d = await (await fetch('/api/stats')).json();
  counters.totalPings.target = d.total_raw_pings || 0;
  counters.totalJourneys.target = d.total_deduplicated_journeys || 0;
  counters.dedupRatio.target = d.dedup_ratio || 0;
  counters.pps.target = d.pings_per_second || 0;
}
```

Counters ease toward targets with `requestAnimationFrame`, avoiding abrupt
number changes. The page polls stats every 500 ms, throughput every second,
plaza data every two seconds, and health every five seconds.

### Ten-city India radar map

The “map” is a custom DOM/canvas-style overlay container backed by
`/static/india_map_transparent.png`. Ten positioned city markers represent
Delhi, Jaipur, Ahmedabad, Surat, Mumbai, Pune, Hyderabad, Bengaluru, Chennai,
and Kolkata. Plaza totals are aggregated into city totals. Active cities turn
red, scale with traffic, and use a pulsing glow animation; click handlers show
total pings, unique tags, and duplicates in a tooltip. This provides pulse-wave
visual feedback without a mapping SDK.

### Sortable plaza table and controls

The plaza breakdown table is generated from `/api/stats/plaza`, supports sorting
by plaza, pings, unique tags, duplicates, or region, and highlights the busiest
row. Sticky headers preserve context in the 340px scrolling panel. Controls
include a dedup interval slider (`PUT /api/dedup/config`) and a manual trigger
(`POST /api/dedup/trigger`). Health status reports storage backend, worker state,
and server health. Chaos state is exposed by the backend and consumed by the
generator; the dashboard keeps the live operational view intentionally light.

## 4. City Station Dashboard and Local Node SQL Terminal (`templates/city_dashboard.html`)

### Regional edge experience

The page is rendered with city data: city key/name, highway, plaza metadata,
journey counts, revenue, successful/failed totals, recent local journeys, and
raw edge pings. A 2.5-second polling loop calls
`/api/city/<city>/data`, refreshing metrics, financial passage rows, and raw
ping rows without a full page reload.

### Vertical edge fragment

The `Edge_Tags_Cache` section calls the city SQL endpoint with:

```sql
SELECT * FROM Edge_Tags_Cache LIMIT 15;
```

It renders returned columns dynamically, showing tag ID, registration, class,
status, home region, and synchronization timestamp. The callout explains that
the edge cache is operational and intentionally excludes financial PII. The
local plaza table shows the three city plazas and base rates; the local journey
table shows status and deduction badges.

### Local node terminal

The terminal offers chips for `Journeys_Local`, `Toll_Plazas_Local`,
`Edge_Tags_Cache`, and grouped payment totals. `runNodeQuery()` posts the
editor text to `/api/city/<city>/sql`; Flask enforces that the caller is admin
or the matching city officer, and `ddbms_manager.execute_node_query()` accepts
only read-oriented SQL prefixes.

```javascript
async function runNodeQuery() {
  const query = document.getElementById('node-sql').value.trim();
  const response = await fetch('/api/city/{{ city.city_key.lower() }}/sql', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query})
  });
  renderQueryTable(await response.json());
}
```

The UI displays node latency, returned row count, dynamic headers, escaped cell
values, errors, and a Ctrl/Cmd+Enter shortcut. “Direct execution” means direct
execution against the selected node by the backend API; the browser never
opens the SQLite file itself.

## 5. Global Distributed SQL Console (`templates/sql_console.html`)

The console uses a two-column layout: a schema sidebar and a dark slate editor.
The schema sidebar is populated by `/api/sql/schema` and displays the six
central tables and live row counts. Clicking a table creates a starter query.

### Target selector and presets

`<select id="target-node">` supports `COORDINATOR`, `FEDERATED`, and all ten
city keys. Presets demonstrate federated revenue, Chennai predicate pruning,
scatter-gather journeys, reconciliation, balances/vehicles, plaza revenue,
failed-tag audits, and a five-table audit trail. The editor uses JetBrains Mono,
sticky result headers, and Ctrl/Cmd+Enter execution.

### DQP execution-plan visualizer

The browser posts `{query, target}` to `/api/ddbms/query`. For successful
distributed responses, the visualizer renders:

* strategy name;
* active-node pills;
* red pruned-node pills;
* the four DQP steps (localize, push predicates, scatter, gather);
* per-node latency pills.

```javascript
const target = document.getElementById('target-node').value;
const data = await (await fetch('/api/ddbms/query', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({query, target})
})).json();
renderExecutionPlan(data.execution_plan, data.latency_ms);
```

Results are rendered as escaped dynamic tables, with status badges for elapsed
time and row count. Although the central SQL reader has a read-only guard, the
template contains legacy DML-result rendering; the DDBMS and city endpoints
remain explicitly read-only.

## 6. DDBMS Architecture and Fragmentation Explorer (`templates/ddbms_architecture.html`)

This page is an architecture observability view rather than a static diagram.
`/api/ddbms/catalog` supplies the coordinator, ten regional node cards, paths,
status, row counts, disk sizes, plaza counts, and partition predicates.

### Topology and fragmentation catalog

The topology card identifies `COORDINATOR_MASTER_01` and each
`data/nodes/<city>_node.db`. The horizontal fragmentation table displays
`Journeys_CITY`, `σ(region='CITY')`, `Journeys_Local`, physical path, and live
row count. Completeness and disjointness formulas are shown as callouts.

### Lossless join widget

The Edge and Central fragment cards list their attributes and privacy roles. The
“Verify Lossless Join Reconstruction” button calls
`/api/ddbms/reconstruct?limit=15`, then renders tag, registration, class,
status, owner, phone, and wallet balance rows. A success label and join-key
message make the edge-to-central reconstruction viva-ready.

```javascript
const result = await (await fetch('/api/ddbms/reconstruct?limit=15')).json();
if (result.success) {
  document.getElementById('reconstruct-result').classList.remove('hidden');
  renderProfiles(result.reconstructed_relation);
}
```

### Four-phase DQP visualizer

Four cards explain the execution pipeline: **01 Decompose & Localize**, **02
Push Predicates**, **03 Scatter in Parallel**, and **04 Gather & Merge**. A
three-second catalog loop updates node status and journey counts, while the
reconstruction action is on-demand.

## 7. Vehicle Owner Portal (`templates/user_dashboard.html`)

The owner portal is intentionally narrower than the operations UI. It displays
the owner profile, phone number, a personal wallet gradient card, and an ACID
Protected indicator. Top-up buttons call the wallet endpoint with fixed ₹500 or
₹200 amounts and immediately update the displayed balance from the committed
response.

Registered vehicles appear as compact RFID chips containing registration number,
vehicle class, tag ID, and `ACTIVE`/`BLOCKED` status. The transaction section is
an append-oriented financial ledger with journey ID, timestamp, tag, plaza and
highway, deduction, payment status, and failure reason.

```javascript
async function recharge(amount) {
  const response = await fetch('/api/wallet/recharge', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({user_id: USER_ID, amount})
  });
  const data = await response.json();
  if (data.success) document.getElementById('wallet-val').innerText =
    Number(data.new_balance).toFixed(2);
}
```

Every 2.5 seconds the page polls `/api/portal/<username>/history`, refreshing
the balance, record count, and transaction rows. The server-side route is the
actual privacy boundary: the application should additionally enforce that the
requested username matches the authenticated session for production use.
