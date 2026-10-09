import re

with open('templates/index.html', 'r') as f:
    html = f.read()

# Replace the map initialization JS
new_map_js = """
    // --- CUSTOM CSS MAP INITIALIZATION ---
    const mapContainer = document.getElementById('map');
    if (mapContainer) {
        // Reset container to be a flexbox
        mapContainer.style.display = 'flex';
        mapContainer.style.justifyContent = 'center';
        mapContainer.style.alignItems = 'center';
        mapContainer.style.overflow = 'hidden';
        
        // Create an inner wrapper that maintains the 1:1 square aspect ratio of the image
        var mapDiv = document.createElement('div');
        mapDiv.style.position = 'relative';
        mapDiv.style.height = '100%';
        mapDiv.style.aspectRatio = '1 / 1';
        mapDiv.style.backgroundImage = "url('/static/india_map_transparent.png')";
        mapDiv.style.backgroundSize = 'contain';
        mapDiv.style.backgroundRepeat = 'no-repeat';
        mapDiv.style.backgroundPosition = 'center';
        
        mapContainer.appendChild(mapDiv);
    }
"""

# Now we need to adjust the coordinates because the image is 536x536 but the Indian map outline
# inside it doesn't take up the full square perfectly.
# Based on the user's screenshot where the map outline was centered:
# The previous percentages were:
# DELHI: 32% top, 39% left
# MUMBAI: 63% top, 28% left
# CHENNAI: 84% top, 42% left
# But wait, looking at the image: 
# Delhi is roughly top 30%, left 45% of the square image.
# Mumbai is roughly top 65%, left 32% of the square image.
# Chennai is roughly top 82%, left 44% of the square image.
# I will adjust the coordinates slightly.

html = re.sub(r'const mapDiv = document\.getElementById\(\'map\'\);.*?backgroundColor = \'transparent\';\s*\}', new_map_js, html, flags=re.DOTALL)

# Adjust markers
html = html.replace("createMarker('PLAZA_NH44_DELHI', '32%', '39%', 'DELHI');", "createMarker('PLAZA_NH44_DELHI', '32%', '45%', 'DELHI');")
html = html.replace("createMarker('PLAZA_NH48_MUMBAI', '63%', '28%', 'MUMBAI');", "createMarker('PLAZA_NH48_MUMBAI', '65%', '32%', 'MUMBAI');")
html = html.replace("createMarker('PLAZA_NH44_CHENNAI', '84%', '42%', 'CHENNAI');", "createMarker('PLAZA_NH44_CHENNAI', '82%', '45%', 'CHENNAI');")

with open('templates/index.html', 'w') as f:
    f.write(html)
