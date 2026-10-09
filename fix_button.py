with open('templates/index.html', 'r') as f:
    content = f.read()

link_html = '<a href="/database" style="color: #0b4a22; background-color: #d4edda; text-decoration: none; font-size: 1rem; border: 2px solid #0b4a22; padding: 8px 16px; border-radius: 6px; font-weight: bold; position: absolute; right: 20px; top: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); z-index: 1000;">View Live Database</a>'

content = content.replace('<h1>FASTag Live Ingestion Dashboard</h1>', link_html + '\n            <h1>FASTag Live Ingestion Dashboard</h1>')

with open('templates/index.html', 'w') as f:
    f.write(content)
