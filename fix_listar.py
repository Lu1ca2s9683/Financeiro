import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "qs = qs.filter(data_competencia__month=mes, data_competencia__year=ano)" in line:
        new_lines.append("        qs = qs.filter(data_transacao__month=mes, data_transacao__year=ano)\n")
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
