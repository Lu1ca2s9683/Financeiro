import sys

filepath = './financeiro-frontend/src/app/despesas/page.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "valor: item.valor," in line and "salvarImportada" in "".join(lines[lines.index(line)-10:lines.index(line)]):
        new_lines.append("              valor: Math.abs(Number(item.valor)),\n")
    elif "categoria_id: item.categoria_sugerida_id," in line and "salvarImportada" in "".join(lines[lines.index(line)-10:lines.index(line)]):
        new_lines.append(line)
        new_lines.append("              loja_id: activeLoja?.id || Number(localStorage.getItem('active_loja_id')) || 1,\n")
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
