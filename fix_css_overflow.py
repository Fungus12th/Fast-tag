import re
with open('templates/index.html', 'r') as f:
    html = f.read()

# Make sure map tooltip z-index is super high just in case
html = html.replace("tooltip.style.zIndex = '1000';", "tooltip.style.zIndex = '9999';")

with open('templates/index.html', 'w') as f:
    f.write(html)
