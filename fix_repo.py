import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "            data_competencia__month=mes," in line and "DjangoRepositorioDespesas" in "".join(lines[lines.index(line)-10:lines.index(line)]):
        new_lines.append("            data_transacao__month=mes, \n")
    elif "            data_competencia__year=ano" in line and "DjangoRepositorioDespesas" in "".join(lines[lines.index(line)-10:lines.index(line)]):
        new_lines.append("            data_transacao__year=ano\n")
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)

print("DjangoRepositorioDespesas updated to use data_transacao")
