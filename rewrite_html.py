import re

with open('templates/index.html', 'r') as f:
    html = f.read()

# 1. Background style
html = re.sub(
    r'body \{.*?\}',
    r'body {\n    background-color: #e0f2e9;\n    background-image: radial-gradient(#9acbb3 2px, transparent 2px);\n    background-size: 30px 30px;\n    color: var(--color-4);\n}',
    html,
    flags=re.DOTALL
)

# 2. Remove chaos mode button
html = re.sub(r'<div class="chaos-panel">.*?</div>', '', html, flags=re.DOTALL)
html = re.sub(r'const btn = document\.getElementById\(\'chaos-btn\'\);.*?\}', '', html, flags=re.DOTALL)
html = re.sub(r'document\.getElementById\(\'chaos-btn\'\)\.addEventListener.*?\}\);', '', html, flags=re.DOTALL)

# 3. Remove leaflet map and replace with our image map
leaflet_css = r'<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css".*?>'
html = re.sub(leaflet_css, '', html)
leaflet_js = r'<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js".*?></script>'
html = re.sub(leaflet_js, '', html)

# The map container is <div id="map"></div>
# Let's replace the leaflet overrides css
html = re.sub(r'/\* Leaflet Overrides \*/.*?/\* Animations \*/', '/* Animations */', html, flags=re.DOTALL)

# Let's update KNOWN_PLAZAS and map logic
# Instead of full leaflet script, we will just manage DOM elements in the map div.

new_map_js = """
    // ─── CUSTOM CSS MAP INITIALIZATION ───
    const mapDiv = document.getElementById('map');
    mapDiv.style.position = 'relative';
    mapDiv.style.backgroundImage = "url('/static/india_map_transparent.png')";
    mapDiv.style.backgroundSize = 'contain';
    mapDiv.style.backgroundRepeat = 'no-repeat';
    mapDiv.style.backgroundPosition = 'center';
    mapDiv.style.backgroundColor = 'transparent';
    
    // Create markers for the 3 cities
    const markers = {};
    
    function createMarker(id, top, left, label) {
        const m = document.createElement('div');
        m.style.position = 'absolute';
        m.style.top = top;
        m.style.left = left;
        m.style.width = '15px';
        m.style.height = '15px';
        m.style.backgroundColor = 'var(--color-3)';
        m.style.borderRadius = '50%';
        m.style.transform = 'translate(-50%, -50%)';
        m.style.transition = 'all 0.3s ease';
        m.style.boxShadow = '0 0 10px var(--color-3)';
        
        const text = document.createElement('div');
        text.textContent = label;
        text.style.position = 'absolute';
        text.style.top = '20px';
        text.style.left = '50%';
        text.style.transform = 'translateX(-50%)';
        text.style.color = '#000';
        text.style.fontWeight = 'bold';
        text.style.textShadow = '0 0 3px #fff';
        m.appendChild(text);
        
        mapDiv.appendChild(m);
        markers[id] = m;
    }
    
    // Approximate positions on the square map image
    createMarker('PLAZA_NH44_DELHI', '32%', '39%', 'DELHI');
    createMarker('PLAZA_NH48_MUMBAI', '63%', '28%', 'MUMBAI');
    createMarker('PLAZA_NH44_CHENNAI', '84%', '42%', 'CHENNAI');
    
    function updateMapData(plazasData) {
        // Reset all
        Object.values(markers).forEach(m => {
            m.style.width = '15px';
            m.style.height = '15px';
            m.style.backgroundColor = 'var(--color-3)';
        });
        
        for (const [id, data] of Object.entries(plazasData)) {
            if (markers[id]) {
                const scale = Math.min(3, 1 + (data.total_pings / 5000));
                markers[id].style.width = (15 * scale) + 'px';
                markers[id].style.height = (15 * scale) + 'px';
                markers[id].style.backgroundColor = 'var(--color-6)'; // Reddish when active
            }
        }
    }
"""

html = re.sub(
    r'// ─── MAP INITIALIZATION \(Leaflet\) ───.*?// ─── API POLLING ───', 
    new_map_js + '\n    // ─── API POLLING ───', 
    html, 
    flags=re.DOTALL
)

# Update KNOWN_PLAZAS
new_plazas = """
    const KNOWN_PLAZAS = {
        'PLAZA_NH44_DELHI':     { region: 'DELHI', name: 'Delhi Border (NH-44)' },
        'PLAZA_NH48_MUMBAI':    { region: 'MUMBAI',  name: 'Bandra-Worli (Mumbai)' },
        'PLAZA_NH44_CHENNAI':   { region: 'CHENNAI', name: 'Paranur (Chennai)' }
    };
"""
html = re.sub(r'const KNOWN_PLAZAS = \{.*?\};', new_plazas, html, flags=re.DOTALL)

# In the updatePlazaTable, it uses map logic which we removed, let's fix it
html = re.sub(r'updateMapData\(plazas\);', '', html) # we'll call our new one
html = html.replace('renderTable();', 'renderTable();\n        updateMapData(plazas);')

# Also fix the map popups in updateMapData - we already replaced the whole map block.

with open('templates/index.html', 'w') as f:
    f.write(html)

