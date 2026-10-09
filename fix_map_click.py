import re

with open('templates/index.html', 'r') as f:
    html = f.read()

# Add a tooltip div to the map container
new_js = """
    const tooltip = document.createElement('div');
    tooltip.style.position = 'absolute';
    tooltip.style.display = 'none';
    tooltip.style.backgroundColor = '#d4edda';
    tooltip.style.border = '2px solid #0b4a22';
    tooltip.style.padding = '10px';
    tooltip.style.borderRadius = '5px';
    tooltip.style.color = '#0b4a22';
    tooltip.style.fontWeight = 'bold';
    tooltip.style.zIndex = '1000';
    tooltip.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
    tooltip.style.pointerEvents = 'none';
    
    if (mapDiv) {
        mapDiv.appendChild(tooltip);
    }

    const markersData = {};
"""

html = html.replace('const markers = {};', new_js + '\n    const markers = {};')

# In createMarker, add onclick
marker_click_js = """
        m.style.cursor = 'pointer';
        
        m.onclick = function(e) {
            const data = markersData[id];
            if (data) {
                tooltip.innerHTML = `
                    <div style="font-size: 1.1em; border-bottom: 1px solid #0b4a22; margin-bottom: 5px; padding-bottom: 5px;">${label}</div>
                    Total Pings: ${data.total_pings.toLocaleString()}<br>
                    Unique Tags: ${data.unique_tags.toLocaleString()}<br>
                    Duplicates: ${data.duplicates.toLocaleString()}
                `;
                tooltip.style.display = 'block';
                
                // Position tooltip near the marker
                const rect = m.getBoundingClientRect();
                const mapRect = mapDiv.getBoundingClientRect();
                tooltip.style.left = (rect.left - mapRect.left + 25) + 'px';
                tooltip.style.top = (rect.top - mapRect.top - 20) + 'px';
                
                // Hide after 3 seconds
                setTimeout(() => { tooltip.style.display = 'none'; }, 3000);
            } else {
                tooltip.innerHTML = label + "<br>No data yet";
                tooltip.style.display = 'block';
                const rect = m.getBoundingClientRect();
                const mapRect = mapDiv.getBoundingClientRect();
                tooltip.style.left = (rect.left - mapRect.left + 25) + 'px';
                tooltip.style.top = (rect.top - mapRect.top - 20) + 'px';
                setTimeout(() => { tooltip.style.display = 'none'; }, 3000);
            }
            e.stopPropagation();
        };
        
        mapDiv.onclick = function() {
            tooltip.style.display = 'none';
        };
"""

html = html.replace('markers[id] = m;', marker_click_js + '\n        markers[id] = m;')

# In updateMapMarkers, update markersData
update_data_js = """
        for (const id in plazasData) {
            const data = plazasData[id];
            markersData[id] = data;
"""

html = html.replace('for (const id in plazasData) {\n            const data = plazasData[id];', update_data_js)

with open('templates/index.html', 'w') as f:
    f.write(html)
