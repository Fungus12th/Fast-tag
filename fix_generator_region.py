with open('generator.py', 'r') as f:
    content = f.read()

# Replace the choices with type=str.upper
old_arg = """parser.add_argument('--region', '-r', choices=['DELHI', 'CHENNAI', 'MUMBAI', 'OTHER'], default='NORTH',"""
new_arg = """parser.add_argument('--region', '-r', type=str.upper, choices=['DELHI', 'CHENNAI', 'MUMBAI', 'OTHER'], default='DELHI',"""
content = content.replace(old_arg, new_arg)

with open('generator.py', 'w') as f:
    f.write(content)
