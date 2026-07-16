import sys

filepath = './financeiro-frontend/src/app/relatorios/dre/page.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "            ) : (" in line and "</div>" not in lines[lines.index(line)-1]:
        new_lines.append("                </div>\n")
        new_lines.append(line)
    elif "            )}" in line and "</div>" not in lines[lines.index(line)-1]:
        new_lines.append("                </div>\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
