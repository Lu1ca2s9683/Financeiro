import sys

filepath = './financeiro-frontend/src/services/api.ts'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "    });" in line and i >= len(lines) - 4:
        continue
    new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
