import re
with open('templates/index.html', 'r') as f:
    html = f.read()

# Remove feed section
html = re.sub(
    r'<!-- LIVE EVENT FEED -->.*?</section>',
    '',
    html,
    flags=re.DOTALL
)

with open('templates/index.html', 'w') as f:
    f.write(html)
