import re

with open('templates/index.html', 'r') as f:
    html = f.read()

# Remove pollEvents function
html = re.sub(r'async function pollEvents\(\) \{.*?\n    \}', '', html, flags=re.DOTALL)

# Remove (function loopEvents() { pollEvents().finally(() => setTimeout(loopEvents, POLL_EVENTS_MS)); })();
html = re.sub(r'\(function loopEvents\(\).*?POLL_EVENTS_MS\)\); \}\)\(\);', '', html)

with open('templates/index.html', 'w') as f:
    f.write(html)

print("pollEvents removed")
