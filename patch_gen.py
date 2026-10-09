import re
with open('generator.py', 'r') as f:
    content = f.read()

content = content.replace('"NORTH"', '"DELHI"')
content = content.replace('"SOUTH"', '"CHENNAI"')
content = content.replace('"WEST"', '"MUMBAI"')
content = content.replace('"EAST"', '"OTHER"')

with open('generator.py', 'w') as f:
    f.write(content)
