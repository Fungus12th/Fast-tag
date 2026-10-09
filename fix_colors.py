import re

with open('templates/index.html', 'r') as f:
    html = f.read()

# Fix playKaChing by checking typeof
html = html.replace(
    'if (!soundEnabled || !audioCtx) return;',
    'if (typeof soundEnabled === "undefined" || typeof audioCtx === "undefined" || !soundEnabled || !audioCtx) return;'
)

# Fix map coordinates
html = html.replace("createMarker('PLAZA_NH44_DELHI', '32%', '45%', 'DELHI');", "createMarker('PLAZA_NH44_DELHI', '31.7%', '41.1%', 'DELHI');")
html = html.replace("createMarker('PLAZA_NH48_MUMBAI', '65%', '32%', 'MUMBAI');", "createMarker('PLAZA_NH48_MUMBAI', '62.5%', '24.1%', 'MUMBAI');")
html = html.replace("createMarker('PLAZA_NH44_CHENNAI', '82%', '45%', 'CHENNAI');", "createMarker('PLAZA_NH44_CHENNAI', '76.6%', '46.3%', 'CHENNAI');")

# Fix button styles in CSS
button_css_old = """        #trigger-dedup-btn {
            font-family: var(--font-body);
            font-weight: 600;
            letter-spacing: 0.5px;
            padding: 0.7rem 1.4rem;
            
            font-size: 1rem;
            
            background: var(--color-1);
            color: var(--color-4);
            border: 2px solid var(--color-3);"""
button_css_new = """        #trigger-dedup-btn {
            font-family: var(--font-body);
            font-weight: 600;
            letter-spacing: 0.5px;
            padding: 0.7rem 1.4rem;
            font-size: 1rem;
            background: #d4edda;
            color: #0b4a22;
            border: 2px solid #0b4a22;"""
html = html.replace(button_css_old, button_css_new)

button_hover_old = """        #trigger-dedup-btn:hover {
            background: var(--color-3);
            color: var(--color-1);
        }"""
button_hover_new = """        #trigger-dedup-btn:hover {
            background: #c3e6cb;
            color: #0b4a22;
        }"""
html = html.replace(button_hover_old, button_hover_new)

# Fix Chart.js colors
html = html.replace("'#ead3b5'", "'#0b4a22'")
html = html.replace("'rgba(156, 195, 230, 0.4)'", "'#0b4a22'")
html = html.replace("'#9cc3e6'", "'#0b4a22'")
html = html.replace("'rgba(156, 195, 230, 0.15)'", "'#d4edda'")
html = html.replace("'rgba(156, 195, 230, 0.2)'", "'#c3e6cb'")
html = html.replace("'#16304a'", "'#d4edda'")
html = html.replace("'#f3efe6'", "'#0b4a22'")

html = html.replace("['#0a1726', '#16304a']", "['#0b4a22', '#d4edda']")
html = html.replace("['#ead3b5', '#9cc3e6']", "['#0b4a22', '#d4edda']")

# Fix slider colors
html = html.replace("background: var(--color-1);", "background: #0b4a22;")

# Fix :root colors just in case
html = html.replace("--color-1: #0a1726;", "--color-1: #0b4a22;")
html = html.replace("--color-2: #d4edda;", "--color-2: #d4edda;")
html = html.replace("--color-3: #0b4a22;", "--color-3: #0b4a22;")
html = html.replace("--color-4: #0b4a22;", "--color-4: #0b4a22;")
html = html.replace("--color-5: #0b4a22;", "--color-5: #0b4a22;")

# Fix body background
body_old = """        body {
    background-color: #e0f2e9;
    background-image: radial-gradient(#9acbb3 2px, transparent 2px);
    background-size: 30px 30px;
    color: var(--color-4);
}"""
body_new = """        body {
    background-color: #d4edda;
    background-image: radial-gradient(#a3c9ae 2px, transparent 2px);
    background-size: 30px 30px;
    color: #0b4a22;
}"""
html = html.replace(body_old, body_new)


with open('templates/index.html', 'w') as f:
    f.write(html)

print("Colors and map coordinates fixed.")
