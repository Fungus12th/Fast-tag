# FASTag Backend Architecture

## System scope

FASTag is a layered Flask application for high-frequency RFID telemetry, batch
deduplication, toll charging, and distributed-database demonstrations. The
runtime path is:

```text
generator.py -> POST /api/ingest -> db.py storage
                                      |
                                      v
                         BatchDeduplicator (timer/window)
                                      |
                                      v
                         sql_ledger.process_toll_batch()
                                      |
                 +--------------------+--------------------+
                 v                                         v
       fastag_ledger.db (central)             data/nodes/*_node.db (regional)
```

`app.py` owns process initialization and HTTP policy. `db.py` stores raw
telemetry, `deduplicator.py` produces one billable candidate per spatial/tag
group, `sql_ledger.py` is the financial system of record, and
`ddbms_manager.py` mirrors regional operational fragments and federates
read-only queries.

## 1. Ingestion Layer (`db.py`)

### Responsibilities

The ingestion layer accepts JSON batches and normalizes each ping into a stable
schema. The Flask endpoint rejects missing, non-array, and empty `pings`
payloads, then delegates the entire batch to the selected storage backend.

Each normalized record contains:

| Field | Purpose |
|---|---|
| `ping_id` | UUID used to distinguish repeated reads |
| `plaza_id` | Spatial partitioning/grouping key |
| `tag_id` | RFID identity |
| `rssi_signal_strength` | Signal strength in dBm; higher is closer/better |
| `ping_timestamp` | Sensor event timestamp |
| `lane_id` | Toll lane identity |
| `region` | City/region label |
| `ingested_at` | Server-side arrival time used for retention windows |

### In-memory high-throughput path

`InMemoryStorage` uses a bounded `collections.deque` as a ring buffer. Its
`maxlen` is `MAX_RAW_PINGS_IN_MEMORY` (500,000 by default), so old records are
evicted automatically instead of allowing unbounded process memory growth.
All mutation and snapshot operations are protected by one `threading.Lock`.
The lock is intentionally held while appending a batch and incrementing the
authoritative total, which makes concurrent Flask worker requests consistent.

```python
class InMemoryStorage:
    def __init__(self):
        self._lock = threading.Lock()
        self._pings = deque(maxlen=config.MAX_RAW_PINGS_IN_MEMORY)
        self._total_ingested = 0
        self._throughput_log = deque(maxlen=10_000)

    def insert_pings(self, pings):
        now = time.time()
        with self._lock:
            for ping in pings:
                self._pings.append(normalize(ping, now))
            self._total_ingested += len(pings)
            self._throughput_log.append((now, len(pings)))
        return len(pings)
```

The actual normalizer supplies UUID/default values, converts RSSI to `float`,
and records one arrival time for the batch. `get_recent_pings()` copies the
deque under the lock and filters outside the lock using
`ingested_at >= time.time() - window_seconds`. This keeps reader work from
blocking ingestion longer than necessary.

### Sliding-window throughput

The throughput log stores `(arrival_epoch_seconds, batch_count)` tuples. PPS is
calculated over `THROUGHPUT_WINDOW_SECONDS` (five seconds by default), not over
the lifetime total:

```python
cutoff = time.time() - config.THROUGHPUT_WINDOW_SECONDS
with self._lock:
    total = sum(n for ts, n in self._throughput_log if ts >= cutoff)
pps = round(total / config.THROUGHPUT_WINDOW_SECONDS, 1)
```

The history endpoint bins recent entries into one-second buckets, enabling the
dashboard to render a rolling 30-point line chart. Plaza statistics use a
five-minute view and derive total pings, unique tags, and an approximate
duplicate count (`total_pings - unique_tags`).

### Cassandra driver and fallback

When the Python Cassandra driver is installed, `CassandraStorage` creates the
`fastag_telemetry.raw_rfid_pings` schema with partition key `plaza_id` and
clustering columns `(ping_timestamp, ping_id)`. Inserts use prepared
statements and unlogged batches, flushed every 500 records. Recent reads are
issued per known plaza because the schema is intentionally plaza-partitioned.

`create_storage()` supports three modes:

* `memory`: deterministic local ring buffer.
* `cassandra`: require Cassandra and fail fast if the driver is unavailable.
* `auto` (default): attempt a Cassandra connection, then log the failure and
  fall back to `InMemoryStorage`.

The fallback preserves the storage interface used by Flask and the worker, so
the rest of the pipeline is backend-independent. Cassandra totals and
throughput are still tracked in process memory for the live dashboard.

## 2. Deduplication Engine (`deduplicator.py`)

### Windowed two-stage interpretation

The worker runs every `DEDUP_INTERVAL_SECONDS` (30 seconds by default), while
looking back `DEDUP_TIME_WINDOW_SECONDS` (60 seconds by default). Operationally
this is a two-stage windowed pipeline:

1. **Temporal admission:** obtain only records whose server arrival time falls
   inside the sliding look-back window.
2. **Spatial/signal reduction:** group admitted records by `(plaza_id, tag_id)`
   and select the strongest signal as the representative journey.

There is no separate durable second-stage cache: each run recomputes the
window and writes its output to `batch_output.json` plus the relational ledger.
Because adjacent windows overlap, the SQL idempotency index is the final guard
against charging the same `(tag_id, plaza_id, timestamp)` twice.

```python
recent = storage.get_recent_pings(window_seconds=config.DEDUP_TIME_WINDOW_SECONDS)
groups = defaultdict(list)
for ping in recent:
    groups[(ping["plaza_id"], ping["tag_id"])].append(ping)

for (plaza_id, tag_id), pings in groups.items():
    winner = max(pings, key=lambda p: p["rssi_signal_strength"])
    journeys.append({
        "plaza_id": plaza_id,
        "tag_id": tag_id,
        "rssi_signal_strength": winner["rssi_signal_strength"],
        "ping_timestamp": winner.get("ping_timestamp", ""),
        "duplicate_count": len(pings),
    })
```

### Spatial and temporal semantics

The plaza is the spatial boundary and the storage lookup window is the temporal
boundary. A tag observed repeatedly at the same plaza is one candidate, while
the same tag at two plazas remains two candidates. The winner rule treats RSSI
as a signal-quality filter: because RSSI values are negative, `-25 dBm` wins
over `-60 dBm`; the strongest reading is assumed closest to the antenna.
The generator supplies jittered RSSI values to make this selection meaningful.

The result retains lane, region, event timestamp, and `duplicate_count` for
audit/display. `dedup_ratio` is:

```text
((raw_count - journey_count) / raw_count) * 100
```

The worker serializes execution with `_run_lock`, protects published metrics
with `_lock`, and uses a daemon `threading.Timer` for periodic scheduling.
Manual `/api/dedup/trigger` calls use the same serialized path. Cumulative
processed raw count comes from the storage backend’s authoritative ingest
counter; journey totals are cumulative worker-run outputs.

### Ledger handoff

After publishing the batch result, the worker calls
`sql_ledger.process_toll_batch(tag_id, plaza_id, ping_timestamp)` once per
winner. Failures in one call are logged at the handoff boundary rather than
crashing the timer thread. The ledger itself decides whether the candidate is
billable, rejected, fraud-suspect, or insufficient-funds.

## 3. Relational 3NF ACID Ledger (`sql_ledger.py`)

### Schema and constraints

`fastag_ledger.db` contains six normalized relations:

1. `Users` — owner identity and credentials.
2. `Wallet_Ledgers` — one wallet per owner (`user_id UNIQUE`).
3. `Vehicles` — registration and vehicle class.
4. `RFID_Tags` — one tag per vehicle, with `ACTIVE`, `BLOCKED`, or `REPLACED`.
5. `Toll_Plazas` — plaza metadata and base rate.
6. `Journeys` — append-only payment/audit events.

Foreign keys connect every dependent entity to its parent, `CHECK` constraints
prevent negative wallets and invalid statuses, and a unique index on
`(tag_id, plaza_id, timestamp)` provides application-level idempotency.

Every connection enables foreign keys and WAL mode:

```python
conn = sqlite3.connect(DB_PATH, timeout=10.0)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON;")
conn.execute("PRAGMA journal_mode = WAL;")
```

WAL allows readers to proceed while a writer appends, while each call obtains
its own connection and closes it in `finally`.

### Atomic `process_toll_batch()` procedure

The procedure starts with `BEGIN IMMEDIATE`, acquiring the write reservation
before the read/decide/write sequence. It then resolves the plaza, joins tag →
vehicle → owner → wallet, and evaluates checks in a deterministic order:

```python
conn.execute("BEGIN IMMEDIATE;")
record = lookup_tag_vehicle_owner_wallet(cur, tag_id)

if record["status"] != "ACTIVE":
    insert_failed_journey(cur, tag_id, plaza_id, "Tag BLOCKED")
    conn.commit()
    return failed_result()

if balance < toll_rate:
    insert_failed_journey(cur, tag_id, plaza_id, "Insufficient Balance")
    conn.commit()
    return failed_result()

cur.execute("UPDATE Wallet_Ledgers SET current_balance=current_balance-? ...", ...)
cur.execute("INSERT OR IGNORE INTO Journeys (...) VALUES (...)", ...)
conn.commit()
```

Unknown tags are recorded as `SKIPPED`; unknown plazas currently fall back to
the seeded Delhi plaza for demo continuity. Any exception rolls the transaction
back and returns an `ERROR` result.

### Vehicle-class pricing

The base toll is multiplied before the balance check and deduction:

| Class | Multiplier |
|---|---:|
| Car | 1.0× |
| Bus | 2.0× |
| Truck | 3.0× |

```python
multiplier = {"Car": 1.0, "Bus": 2.0, "Truck": 3.0}.get(vehicle_class, 1.0)
toll_rate = round(base_toll_rate * multiplier, 2)
```

### Impossible travel / cloned-tag detection

Before charging, the procedure retrieves the most recent successful journey for
the tag. It extracts the city suffix from plaza names such as
`Place1Chennai`. If the current and previous cities differ, it parses both ISO
timestamps and computes the absolute gap. A cross-city transition under two
hours is rejected as a suspected cloned tag:

```python
if last_city != current_city:
    gap_hours = abs((current_time - last_time).total_seconds()) / 3600
    if gap_hours < 2.0:
        reason = f"Suspected Tag Cloning: {last_city}→{current_city} in {gap_hours:.1f}h"
        insert_failed_journey(cur, tag_id, plaza_id, reason)
        conn.commit()
        return failed_result(reason)
```

The failed event is retained with zero deduction, making fraud and operational
failures visible in the ledger. Timestamp parse errors are ignored by this
check so that malformed telemetry does not prevent normal processing.

### Regional synchronization

After each committed success or failure, a best-effort callback resolves the
plaza city and writes the same passage to that city’s `Journeys_Local` table.
The central transaction is authoritative; regional replication errors are
logged/ignored so a node outage does not undo an already committed financial
charge.

## 4. Distributed Database Management System Core (`ddbms_manager.py`)

### Physical topology

The coordinator is `fastag_ledger.db`. Ten regional SQLite WAL databases are
created under `data/nodes/`:

```text
data/nodes/<city>_node.db
```

The cities are Delhi, Kolkata, Mumbai, Bengaluru, Chennai, Hyderabad,
Ahmedabad, Surat, Pune, and Jaipur. Each node is initialized with WAL and
`synchronous=NORMAL`, local plaza metadata, operational tag cache, and node
metadata.

### Primary horizontal fragmentation

The logical `Journeys` relation is horizontally fragmented by city:

```text
Journeys_CITY = σ(region = 'CITY')(Journeys)
Journeys = ⋃ CITY Journeys_CITY
Journeys_i ∩ Journeys_j = ∅ for i ≠ j
```

The physical relation is `Journeys_Local`, carrying `journey_id`, tag/plaza
identifiers, region, timestamp, amount, status, and failure reason. `Toll_Plazas`
is similarly materialized as `Toll_Plazas_Local`. Plaza ID/name maps resolve a
passage to exactly one regional node; initialization also backfills existing
central journeys.

### Vertical fragmentation and privacy boundary

`Edge_Tags_Cache` is the operational edge fragment:

```text
π(tag_id, registration_no, vehicle_class, status, home_region)
```

It excludes wallet balances, phone numbers, and owner PII, allowing local gate
authorization without exposing financial data. The central fragment is formed
from `Users` and `Wallet_Ledgers`:

```text
π(user_id, full_name, phone_number, current_balance)
```

The conceptual lossless reconstruction is:

```text
Vehicle_Full_Profile = Edge_Tags_Cache ⨝ Central_Financial_Fragment
```

The shared vehicle identity is registration-related: the live demonstration
fetches edge rows and joins central `Vehicles` on `registration_no` to retrieve
the owner financial fragment. The API exposes this as
`/api/ddbms/reconstruct` and labels the result as a verified lossless join.

### Distributed Query Processor (DQP)

`execute_distributed_federated_query()` performs four phases:

1. **Decompose/localize:** rewrite logical `Journeys` and `Toll_Plazas` names to
   `Journeys_Local` and `Toll_Plazas_Local`.
2. **Predicate pushdown/pruning:** inspect `region = ...` and
   `plaza_name LIKE ...` predicates and select only matching city nodes.
3. **Parallel scatter:** execute the localized read-only query on active nodes
   with `ThreadPoolExecutor` (up to ten workers).
4. **Gather/merge:** collect columns, union rows (preview capped at 100),
   record per-node latency, and return a transparent execution plan.

```python
local_query = re.sub(r"\bJourneys\b", "Journeys_Local", query,
                     flags=re.IGNORECASE)

with ThreadPoolExecutor(max_workers=min(10, len(active_nodes))) as pool:
    futures = {pool.submit(query_node, city): city for city in active_nodes}
    for future in as_completed(futures):
        city, columns, rows, latency, error = future.result()
        gathered_rows.extend(rows)
```

Targeting one city skips federation. `COORDINATOR` executes against the master
database. All node and federated paths accept only `SELECT`, `PRAGMA`,
`EXPLAIN`, or `WITH` prefixes. The plan reports active/pruned nodes, strategy,
pipeline steps, total latency, and individual node latency.

## 5. API Gateway and Multi-Tier RBAC (`app.py`)

### Session and route guards

Flask sessions store username, role, full name, city, and user ID. The unified
login accepts:

* `admin` / `admin123` → global Operations Admin.
* `<city>` / `<city>123` → that city’s Station Officer.
* seeded owner accounts → Vehicle Owner.

`redirect_for_role()` routes these tiers to `/dashboard`, `/city/<city>`, and
`/portal/<user>` respectively. Owners are restricted to their own portal;
city officers are restricted to their own city; admin has global UI access.

### Important routes

| Route | Policy and purpose |
|---|---|
| `POST /api/ingest` | Batch raw pings into selected telemetry storage |
| `GET /api/stats*` | Live totals, plaza breakdown, and throughput history |
| `POST /api/dedup/trigger` | Manual serialized dedup run |
| `POST /api/city/<city>/sql` | Read-only SQL against one authorized regional node; admin or matching city officer |
| `POST /api/ddbms/query` | Coordinator or federated read-only DQP; admin/city only |
| `GET /api/ddbms/reconstruct` | Demonstrate edge/central lossless reconstruction |
| `POST /api/wallet/recharge` | Add funds to the authenticated/posted owner wallet |
| `GET /api/portal/<user>/history` | Wallet, vehicles, and latest journey ledger |
| `GET /api/health` | Backend, totals, and worker liveness |

The city SQL endpoint delegates to `execute_node_query()`, which rejects write
prefixes. The DDBMS endpoint supports `COORDINATOR`, a named city, or
`FEDERATED`; the coordinator path uses the central SQL reader while regional
paths use DQP. The wallet endpoint calls `recharge_wallet()` and returns the
new balance after commit.

### Security boundary

The project is a demonstration application: credentials are seeded in plain
text and the Flask secret is development-grade. Read-only SQL guards are
prefix-based rather than a full SQL parser, and the recharge endpoint should be
strengthened with strict ownership checks, CSRF protection, rate limiting, and
production authentication before deployment.

## 6. Synthetic Load Generator (`generator.py`)

The generator is a `requests`-based multi-threaded client. Its registry contains
10 cities and three plazas per city (30 plazas total). Each `IngestWorker`
generates a batch, POSTs it to `/api/ingest`, maintains shared counters under a
lock, and backs off after failures. Defaults are three workers, 500 pings per
batch, and 0.1 seconds between batches.

The generator selects active tags in deterministic 45-second buckets, chooses
plazas with per-tag imbalance, emits RSSI between roughly -65 and -25 dBm plus
jitter, and assigns one of four lanes. `--region ALL` exercises all 30 plazas;
otherwise a comma-separated city list limits the simulation.

Chaos mode is monitored by a daemon thread polling `/api/chaos/status` every
second. When active, each worker increases its batch size and reduces delay
(capped at a fivefold client-side adjustment, while the server advertises the
default tenfold multiplier). A separate stats printer reports sent pings,
batches, errors, and observed PPS. Shutdown uses stop events for workers,
monitor, and printer.
