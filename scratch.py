from PIL import Image

img = Image.open('static/india_map.png').convert("RGBA")
datas = img.getdata()

new_data = []
for item in datas:
    # change all white (also shades of white)
    # to transparent
    if item[0] > 200 and item[1] > 200 and item[2] > 200:
        new_data.append((255, 255, 255, 0))
    else:
        new_data.append(item)

img.putdata(new_data)
img.save('static/india_map_transparent.png', "PNG")
