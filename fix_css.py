import re
with open('templates/index.html', 'r') as f:
    html = f.read()

# We want to change the dark blue boxes to light green.
# The dark blue comes from var(--color-2) which is #162a3f, 
# or var(--color-1) which is #0a1726.
# Actually, the user wants the solid color to be the same as the button (light green #d4edda)
# Frame (border) same as button (#0b4a22)
# Text color same as button (#0b4a22)

# Let's override the CSS variables directly instead of changing every class!
# In the :root {} section:
html = re.sub(r'--color-2:\s*#162a3f;', '--color-2: #d4edda;', html) # Panels background
html = re.sub(r'--color-4:\s*#ead3b5;', '--color-4: #0b4a22;', html) # Primary text (was beige, now dark green)
html = re.sub(r'--color-3:\s*#9cc3e6;', '--color-3: #0b4a22;', html) # Highlight text (was light blue, now dark green)

# We also need to add the dark green border to panels/cards.
# Let's find .stat-card and .panel and add border.
html = re.sub(r'(\.stat-card\s*\{.*?)(\})', r'\1 border: 2px solid #0b4a22; \2', html, flags=re.DOTALL)
html = re.sub(r'(\.panel\s*\{.*?)(\})', r'\1 border: 2px solid #0b4a22; \2', html, flags=re.DOTALL)

with open('templates/index.html', 'w') as f:
    f.write(html)
