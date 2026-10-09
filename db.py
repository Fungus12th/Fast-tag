"""
FASTag DA-2 — Database / Storage Layer
Provides a unified StorageBackend that transparently uses Cassandra or in-memory storage.
"""

import time
import threading
import uuid
from collections import deque, defaultdict
from datetime import datetime, timezone

import config

# ─── Try importing Cassandra driver ────────────────────────────────────────────
try:
    from cassandra.cluster import Cluster
    from cassandra.query import BatchStatement, BatchType, SimpleStatement
    CASSANDRA_AVAILABLE = True
except ImportError:
    CASSANDRA_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────────
# In-Memory Storage (for dev / when Cassandra is not installed)
# ─────────────────────────────────────────────────────────────────────────────────
class InMemoryStorage:
    """Thread-safe in-memory storage that mimics the Cassandra schema."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pings = deque(maxlen=config.MAX_RAW_PINGS_IN_MEMORY)
        self._total_ingested = 0
        # Throughput tracking: list of (timestamp, count) tuples
        self._throughput_log = deque(maxlen=10_000)
        print("[DB] Using IN-MEMORY storage backend")


    def insert_pings(self, pings: list[dict]) -> int:
        """Insert a batch of pings. Returns number inserted."""
        now = time.time()
        count = 0
        with self._lock:
            for ping in pings:
                # Ensure required fields
                record = {
                    "ping_id":              ping.get("ping_id", str(uuid.uuid4())),
                    "plaza_id":             ping.get("plaza_id", "UNKNOWN"),
                    "tag_id":               ping.get("tag_id", "UNKNOWN"),
                    "rssi_signal_strength": float(ping.get("rssi_signal_strength", -50.0)),
                    "ping_timestamp":       ping.get("ping_timestamp", datetime.now(timezone.utc).isoformat()),
                    "lane_id":              ping.get("lane_id", "LANE_1"),
                    "region":               ping.get("region", "UNKNOWN"),
                    "ingested_at":          now,
                }
                self._pings.append(record)
                count += 1
            self._total_ingested += count
            self._throughput_log.append((now, count))
        return count

    def get_recent_pings(self, window_seconds: int = None) -> list[dict]:
        """Get pings within the last `window_seconds`."""
        if window_seconds is None:
            window_seconds = config.DEDUP_TIME_WINDOW_SECONDS
        cutoff = time.time() - window_seconds
        with self._lock:
            snapshot = list(self._pings)
        return [p for p in snapshot if p["ingested_at"] >= cutoff]

    def get_total_ingested(self) -> int:
        with self._lock:
            return self._total_ingested

    def get_throughput_pps(self) -> float:
        """Calculate pings per second over the sliding window."""
        now = time.time()
        window = config.THROUGHPUT_WINDOW_SECONDS
        cutoff = now - window
        with self._lock:
            total = sum(count for ts, count in self._throughput_log if ts >= cutoff)
        return round(total / window, 1) if window > 0 else 0.0

    def get_plaza_stats(self) -> dict:
        """Get per-plaza breakdown from recent pings."""
        recent = self.get_recent_pings(window_seconds=300)  # last 5 minutes
        stats = defaultdict(lambda: {"total_pings": 0, "unique_tags": set(), "region": "UNKNOWN"})
        for p in recent:
            plaza = p["plaza_id"]
            stats[plaza]["total_pings"] += 1
            stats[plaza]["unique_tags"].add(p["tag_id"])
            stats[plaza]["region"] = p.get("region", "UNKNOWN")
        # Convert sets to counts for JSON serialization
        result = {}
        for plaza, data in stats.items():
            result[plaza] = {
                "plaza_id":     plaza,
                "total_pings":  data["total_pings"],
                "unique_tags":  len(data["unique_tags"]),
                "duplicates":   data["total_pings"] - len(data["unique_tags"]),
                "region":       data["region"],
            }
        return result

    def get_all_raw_count(self) -> int:
        """Get total number of raw pings currently held in memory."""
        with self._lock:
            return len(self._pings)

    def get_throughput_history(self, buckets: int = 30) -> list[dict]:
        now = time.time()
        bucket_size = 1
        bucket_totals = [0] * buckets
        cutoff = now - (buckets * bucket_size)
        
        with self._lock:
            for ts, count in reversed(self._throughput_log):
                if ts < cutoff:
                    break
                idx = buckets - 1 - int((now - ts) / bucket_size)
                if 0 <= idx < buckets:
                    bucket_totals[idx] += count

        result = []
        for i in range(buckets):
            bucket_start = now - ((buckets - i) * bucket_size)
            result.append({
                "timestamp": datetime.fromtimestamp(bucket_start, tz=timezone.utc).isoformat(),
                "pps": bucket_totals[i],
            })
        return result


# ─────────────────────────────────────────────────────────────────────────────────
# Cassandra Storage
# ─────────────────────────────────────────────────────────────────────────────────
class CassandraStorage:
    """Cassandra-backed storage using the FASTag_Telemetry schema."""

    def __init__(self):
        self._cluster = Cluster(
            contact_points=config.CASSANDRA_CONTACT_POINTS,
            port=config.CASSANDRA_PORT,
        )
        self._session = self._cluster.connect()
        self._ensure_schema()
        self._session.set_keyspace(config.CASSANDRA_KEYSPACE)
        self._total_ingested = 0
        self._lock = threading.Lock()
        self._throughput_log = deque(maxlen=10_000)
        self._known_plazas_set = set()  # Track plazas in-memory to avoid full table scans
        print(f"[DB] Connected to Cassandra at {config.CASSANDRA_CONTACT_POINTS}")

        # Prepare statements for performance
        self._insert_stmt = self._session.prepare(f"""
            INSERT INTO {config.CASSANDRA_TABLE}
                (plaza_id, ping_timestamp, ping_id, tag_id, rssi_signal_strength, lane_id, region)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """)
        self._recent_stmt = self._session.prepare(f"""
            SELECT * FROM {config.CASSANDRA_TABLE}
            WHERE plaza_id = ? AND ping_timestamp >= ?
        """)

    def _ensure_schema(self):
        """Create keyspace and table if they don't exist."""
        self._session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {config.CASSANDRA_KEYSPACE}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
        """)
        self._session.set_keyspace(config.CASSANDRA_KEYSPACE)
        self._session.execute(f"""
            CREATE TABLE IF NOT EXISTS {config.CASSANDRA_TABLE} (
                plaza_id            text,
                ping_timestamp      timestamp,
                ping_id             uuid,
                tag_id              text,
                rssi_signal_strength double,
                lane_id             text,
                region              text,
                PRIMARY KEY (plaza_id, ping_timestamp, ping_id)
            ) WITH CLUSTERING ORDER BY (ping_timestamp DESC, ping_id ASC)
        """)
        print("[DB] Cassandra schema verified/created")

    def insert_pings(self, pings: list[dict]) -> int:
        """Insert a batch of pings using Cassandra BatchStatement."""
        if not pings:
            return 0
        now = time.time()
        batch = BatchStatement(batch_type=BatchType.UNLOGGED)
        count = 0
        new_plazas = set()
        for ping in pings:
            ts_str = ping.get("ping_timestamp", datetime.now(timezone.utc).isoformat())
            if isinstance(ts_str, str):
                # Parse ISO timestamp
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            else:
                ts = ts_str
            ping_id = uuid.UUID(ping["ping_id"]) if "ping_id" in ping else uuid.uuid4()
            plaza_id = ping.get("plaza_id", "UNKNOWN")
            new_plazas.add(plaza_id)
            batch.add(self._insert_stmt, (
                plaza_id,
                ts,
                ping_id,
                ping.get("tag_id", "UNKNOWN"),
                float(ping.get("rssi_signal_strength", -50.0)),
                ping.get("lane_id", "LANE_1"),
                ping.get("region", "UNKNOWN"),
            ))
            count += 1
            # Cassandra batches shouldn't be too large
            if count % 500 == 0:
                self._session.execute(batch)
                batch = BatchStatement(batch_type=BatchType.UNLOGGED)
        if count % 500 != 0:
            self._session.execute(batch)
        with self._lock:
            self._total_ingested += count
            self._throughput_log.append((now, count))
            self._known_plazas_set.update(new_plazas)
        return count

    def get_recent_pings(self, window_seconds: int = None) -> list[dict]:
        """Get pings from all plazas within the time window."""
        if window_seconds is None:
            window_seconds = config.DEDUP_TIME_WINDOW_SECONDS
        cutoff = datetime.now(timezone.utc).timestamp() - window_seconds
        cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
        # We need to query per plaza; get known plazas from system
        # For simplicity, query a set of known plazas
        known_plazas = self._get_known_plazas()
        results = []
        for plaza_id in known_plazas:
            rows = self._session.execute(self._recent_stmt, (plaza_id, cutoff_dt))
            for row in rows:
                results.append({
                    "ping_id":              str(row.ping_id),
                    "plaza_id":             row.plaza_id,
                    "tag_id":               row.tag_id,
                    "rssi_signal_strength": row.rssi_signal_strength,
                    "ping_timestamp":       row.ping_timestamp.isoformat(),
                    "lane_id":              row.lane_id,
                    "region":               row.region,
                })
        return results

    def _get_known_plazas(self) -> list[str]:
        """Get distinct plaza IDs tracked in-memory."""
        with self._lock:
            return list(self._known_plazas_set)

    def get_total_ingested(self) -> int:
        with self._lock:
            return self._total_ingested

    def get_throughput_pps(self) -> float:
        now = time.time()
        window = config.THROUGHPUT_WINDOW_SECONDS
        cutoff = now - window
        with self._lock:
            total = sum(count for ts, count in self._throughput_log if ts >= cutoff)
        return round(total / window, 1) if window > 0 else 0.0

    def get_plaza_stats(self) -> dict:
        recent = self.get_recent_pings(window_seconds=300)
        stats = defaultdict(lambda: {"total_pings": 0, "unique_tags": set(), "region": "UNKNOWN"})
        for p in recent:
            plaza = p["plaza_id"]
            stats[plaza]["total_pings"] += 1
            stats[plaza]["unique_tags"].add(p["tag_id"])
            stats[plaza]["region"] = p.get("region", "UNKNOWN")
        result = {}
        for plaza, data in stats.items():
            result[plaza] = {
                "plaza_id":     plaza,
                "total_pings":  data["total_pings"],
                "unique_tags":  len(data["unique_tags"]),
                "duplicates":   data["total_pings"] - len(data["unique_tags"]),
                "region":       data["region"],
            }
        return result

    def get_all_raw_count(self) -> int:
        return self.get_total_ingested()

    def get_throughput_history(self, buckets: int = 30) -> list[dict]:
        now = time.time()
        bucket_size = 1
        bucket_totals = [0] * buckets
        cutoff = now - (buckets * bucket_size)
        
        with self._lock:
            for ts, count in reversed(self._throughput_log):
                if ts < cutoff:
                    break
                idx = buckets - 1 - int((now - ts) / bucket_size)
                if 0 <= idx < buckets:
                    bucket_totals[idx] += count

        result = []
        for i in range(buckets):
            bucket_start = now - ((buckets - i) * bucket_size)
            result.append({
                "timestamp": datetime.fromtimestamp(bucket_start, tz=timezone.utc).isoformat(),
                "pps": bucket_totals[i],
            })
        return result

    def shutdown(self):
        """Cleanly close the Cassandra connection."""
        self._cluster.shutdown()
        print("[DB] Cassandra connection closed")


# ─────────────────────────────────────────────────────────────────────────────────
# Factory: Create the right backend based on config
# ─────────────────────────────────────────────────────────────────────────────────
def create_storage():
    """Create and return the appropriate storage backend."""
    mode = config.STORAGE_MODE.lower()

    if mode == "memory":
        return InMemoryStorage()

    if mode == "cassandra":
        if not CASSANDRA_AVAILABLE:
            raise RuntimeError("cassandra-driver is not installed but STORAGE_MODE='cassandra'")
        return CassandraStorage()

    # mode == "auto": try Cassandra, fall back to memory
    if CASSANDRA_AVAILABLE:
        try:
            return CassandraStorage()
        except Exception as e:
            print(f"[DB] Cassandra not reachable ({e}), falling back to in-memory storage")
    else:
        print("[DB] cassandra-driver not installed, using in-memory storage")

    return InMemoryStorage()
