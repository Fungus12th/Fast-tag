"""
FASTag DA-2 — Cassandra Schema Setup Script
Run this standalone to create/verify the keyspace and table in Cassandra.

Usage:
    python3 setup_cassandra.py [--host 127.0.0.1] [--port 9042]
"""

import argparse
import sys

try:
    from cassandra.cluster import Cluster
except ImportError:
    print("ERROR: cassandra-driver is not installed.")
    print("       pip install cassandra-driver")
    sys.exit(1)

import config


def setup(contact_points: list[str], port: int):
    """Create the FASTag_Telemetry keyspace and Raw_RFID_Pings table."""
    print(f"Connecting to Cassandra at {contact_points}:{port} ...")
    cluster = Cluster(contact_points=contact_points, port=port)
    session = cluster.connect()

    # ─── Create Keyspace ────────────────────────────────────────────────────
    print(f"Creating keyspace '{config.CASSANDRA_KEYSPACE}' ...")
    session.execute(f"""
        CREATE KEYSPACE IF NOT EXISTS {config.CASSANDRA_KEYSPACE}
        WITH replication = {{
            'class': 'SimpleStrategy',
            'replication_factor': 1
        }}
    """)
    session.set_keyspace(config.CASSANDRA_KEYSPACE)

    # ─── Create Table ───────────────────────────────────────────────────────
    print(f"Creating table '{config.CASSANDRA_TABLE}' ...")
    session.execute(f"""
        CREATE TABLE IF NOT EXISTS {config.CASSANDRA_TABLE} (
            plaza_id             text,
            ping_timestamp       timestamp,
            ping_id              uuid,
            tag_id               text,
            rssi_signal_strength double,
            lane_id              text,
            region               text,
            PRIMARY KEY (plaza_id, ping_timestamp, ping_id)
        ) WITH CLUSTERING ORDER BY (ping_timestamp DESC, ping_id ASC)
    """)

    # ─── Verify ─────────────────────────────────────────────────────────────
    print("\nSchema verification:")
    rows = session.execute(f"""
        SELECT keyspace_name, table_name
        FROM system_schema.tables
        WHERE keyspace_name = '{config.CASSANDRA_KEYSPACE}'
    """)
    for row in rows:
        print(f"  ✓ {row.keyspace_name}.{row.table_name}")

    cols = session.execute(f"""
        SELECT column_name, type, kind
        FROM system_schema.columns
        WHERE keyspace_name = '{config.CASSANDRA_KEYSPACE}'
          AND table_name = '{config.CASSANDRA_TABLE}'
    """)
    print(f"\n  Columns in {config.CASSANDRA_TABLE}:")
    for col in cols:
        print(f"    {col.column_name:30s} {col.type:15s} ({col.kind})")

    cluster.shutdown()
    print("\n✅ Cassandra schema setup complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FASTag Cassandra Schema Setup")
    parser.add_argument("--host", default=",".join(config.CASSANDRA_CONTACT_POINTS),
                        help="Cassandra contact points (comma-separated)")
    parser.add_argument("--port", type=int, default=config.CASSANDRA_PORT,
                        help="Cassandra native transport port")
    args = parser.parse_args()

    contact_points = [h.strip() for h in args.host.split(",")]
    setup(contact_points, args.port)
