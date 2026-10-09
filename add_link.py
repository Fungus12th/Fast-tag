with open('templates/index.html', 'r') as f:
    content = f.read()
    
link_html = '<a href="/database" style="color: var(--color-4); text-decoration: none; font-size: 1rem; border: 1px solid var(--color-4); padding: 5px 10px; border-radius: 4px;">View Live Database</a>'

content = content.replace('<h1>FASTag DA-2 | High-Frequency Ingestion</h1>', '<h1>FASTag DA-2 | High-Frequency Ingestion</h1>\n            ' + link_html)

with open('templates/index.html', 'w') as f:
    f.write(content)
