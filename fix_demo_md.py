import re

with open('demo.md', 'r') as f:
    content = f.read()

old_instructions = """1. Install the required dependency if you haven't already:
   ```bash
   pip install requests
   ```
2. Run the generator, replacing `<MAIN_IP>` with the IP address you found in Phase 1:
   ```bash
   python generator.py --server <MAIN_IP> --region DELHI --workers 2
   ```"""

new_instructions = """1. Set up a virtual environment and install the required dependency:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install requests
   ```
2. Run the generator, replacing `<MAIN_IP>` with the IP address you found in Phase 1:
   ```bash
   python generator.py --server <MAIN_IP> --region DELHI --workers 2
   ```"""

content = content.replace(old_instructions, new_instructions)

with open('demo.md', 'w') as f:
    f.write(content)

