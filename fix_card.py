import re
with open('templates/index.html', 'r') as f:
    html = f.read()

# Make absolutely sure .card is styled right
html = re.sub(
    r'\.card\s*\{.*?\}',
    '.card {\n    background: #d4edda;\n    border: 3px solid #0b4a22;\n    border-radius: 12px;\n    padding: 1.5rem;\n    transition: border-color 0.3s, background-color 0.3s;\n}',
    html,
    flags=re.DOTALL
)

html = re.sub(
    r'\.card-title\s*\{.*?\}',
    '.card-title {\n    color: #0b4a22;\n    font-family: var(--font-mono);\n    font-size: 0.9rem;\n    font-weight: 500;\n    text-transform: uppercase;\n    letter-spacing: 0.05em;\n    margin-bottom: 0.75rem;\n}',
    html,
    flags=re.DOTALL
)

html = re.sub(
    r'\.hero-value\.primary\s*\{.*?\}',
    '.hero-value.primary {\n    color: #0b4a22;\n}',
    html,
    flags=re.DOTALL
)

html = re.sub(
    r'\.hero-value\.secondary\s*\{.*?\}',
    '.hero-value.secondary {\n    color: #0b4a22;\n}',
    html,
    flags=re.DOTALL
)

# Text inside table
html = re.sub(
    r'\.table th\s*\{.*?\}',
    '.table th {\n    text-align: left;\n    padding: 12px 16px;\n    font-family: var(--font-mono);\n    color: #0b4a22;\n    font-size: 0.85rem;\n    border-bottom: 2px solid #0b4a22;\n}',
    html,
    flags=re.DOTALL
)

html = re.sub(
    r'\.table td\s*\{.*?\}',
    '.table td {\n    padding: 14px 16px;\n    border-bottom: 1px solid #0b4a22;\n    font-weight: 500;\n    color: #0b4a22;\n}',
    html,
    flags=re.DOTALL
)

html = re.sub(
    r'\.event-row\s*\{.*?\}',
    '.event-row {\n    padding: 12px;\n    border-bottom: 1px solid #0b4a22;\n    display: flex;\n    gap: 16px;\n    align-items: center;\n    color: #0b4a22;\n}',
    html,
    flags=re.DOTALL
)

# Make map div transparent border if any
html = re.sub(r'border:\s*1px\s*solid\s*rgba.*?156.*?0\.4\);', 'border: 2px solid #0b4a22;', html)

with open('templates/index.html', 'w') as f:
    f.write(html)
