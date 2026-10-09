import re
with open('templates/index.html', 'r') as f:
    html = f.read()

# Change --color-2 from #16304a to #d4edda
html = re.sub(r'--color-2:\s*#16304a;', '--color-2: #d4edda;', html)

# Change header text colors
html = re.sub(r'--color-5:\s*#f3efe6;', '--color-5: #0b4a22;', html) # Make off-white text dark green too

# Make sure all borders are dark green
html = re.sub(r'--border-light:\s*rgba\(156, 195, 230, 0\.4\);', '--border-light: #0b4a22;', html)
html = re.sub(r'--bg-card-hover:\s*#3b7396;', '--bg-card-hover: #c3e6cb;', html)

with open('templates/index.html', 'w') as f:
    f.write(html)
