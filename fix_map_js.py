import re

with open('templates/index.html', 'r') as f:
    html = f.read()

new_map_js = """
    const mapDiv = document.getElementById('map');
    mapDiv.style.position = 'relative';
    mapDiv.style.backgroundImage = "url('/static/india_map_transparent.png')";
    mapDiv.style.backgroundSize = 'contain';
    mapDiv.style.backgroundRepeat = 'no-repeat';
    mapDiv.style.backgroundPosition = 'center';
    mapDiv.style.backgroundColor = 'transparent';
    
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
        text.style.color = '#0b4a22';
        text.style.fontWeight = 'bold';
        text.style.textShadow = '0 0 3px #fff';
        m.appendChild(text);
        
        mapDiv.appendChild(m);
        markers[id] = m;
    }
    
    function initMap() {
        createMarker('PLAZA_NH44_DELHI', '32%', '39%', 'DELHI');
        createMarker('PLAZA_NH48_MUMBAI', '63%', '28%', 'MUMBAI');
        createMarker('PLAZA_NH44_CHENNAI', '84%', '42%', 'CHENNAI');
    }
    
    function updateMapMarkers(plazasData) {
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
                markers[id].style.backgroundColor = '#913c32'; // Reddish when active
            }
        }
    }
"""

html = re.sub(r'function initMap\(\) \{.*?\}\s*(?=function updateMapMarkers)', '', html, flags=re.DOTALL)
html = re.sub(r'function updateMapMarkers\(plazas\) \{.*?\}\s*(?=function tickCounters)', new_map_js + '\n    ', html, flags=re.DOTALL)

with open('templates/index.html', 'w') as f:
    f.write(html)

