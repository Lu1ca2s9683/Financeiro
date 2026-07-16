import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "total_despesas_mes: int" in line and "DashboardResumoOut" in "".join(lines[lines.index(line)-10:lines.index(line)]):
        new_lines.append("    total_despesas_mes: float\n")
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
