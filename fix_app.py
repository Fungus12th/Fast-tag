with open('app.py', 'r') as f:
    content = f.read()

# Replace the wrong call in app.py
content = content.replace('pings = storage.get_recent_pings(limit=100)', 'pings = storage.get_recent_pings(window_seconds=60)[:100]')

with open('app.py', 'w') as f:
    f.write(content)
