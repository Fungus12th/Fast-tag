import re
with open('db.py', 'r') as f:
    content = f.read()

mem_func = """    def get_recent_pings(self, limit=50) -> list[dict]:
        with self._lock:
            pings = list(self._pings)
            return pings[-limit:][::-1]
"""
content = re.sub(
    r'(class InMemoryStorage:.*?)(    def insert_pings)',
    r'\1' + mem_func + r'\n\2',
    content,
    flags=re.DOTALL
)

cass_func = """    def get_recent_pings(self, limit=50) -> list[dict]:
        return [] # Not implemented for Cassandra in this demo
"""
content = re.sub(
    r'(class CassandraStorage:.*?)(    def insert_pings)',
    r'\1' + cass_func + r'\n\2',
    content,
    flags=re.DOTALL
)

with open('db.py', 'w') as f:
    f.write(content)
