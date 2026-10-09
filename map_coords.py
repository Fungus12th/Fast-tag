from PIL import Image

img = Image.open('static/india_map_transparent.png').convert("RGBA")
w, h = img.size
print(f"Image size: {w}x{h}")
bbox = img.getbbox()
if bbox:
    min_x, min_y, max_x, max_y = bbox
    print(f"Bounding box: X:{min_x}-{max_x}, Y:{min_y}-{max_y}")

    def print_city(name, rx, ry):
        cx = min_x + (max_x - min_x) * rx
        cy = min_y + (max_y - min_y) * ry
        print(f"{name}: left={cx/w*100:.1f}%, top={cy/h*100:.1f}%")

    # Real world map approx relative to bounding box
    print_city("Delhi", 0.38, 0.28)
    print_city("Mumbai", 0.15, 0.65)
    print_city("Chennai", 0.45, 0.82)
else:
    print("No bounding box found (empty image)")
