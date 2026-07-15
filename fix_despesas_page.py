import sys

filepath = './financeiro-frontend/src/app/despesas/page.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "if (res.ok) {" in line:
        new_lines.append(line)
        new_lines.append("                                const extratoTransacoes = await res.json();\n")
        new_lines.append("                                const saidas = extratoTransacoes.filter((t: any) => t.tipo === 'SAIDA');\n")
        new_lines.append("                                alert(`Extrato importado com sucesso! Encontradas ${saidas.length} saídas.`);\n")
        new_lines.append("                                // Idealmente preencher um modal ou estado, mas como a página não tem visual para extratos...\n")
        new_lines.append("                                // window.location.reload();\n")
    elif "alert('Extrato importado com sucesso!');" in line:
        pass # replace this line
    elif "window.location.reload();" in line and "if (res.ok) {" in "".join(new_lines[-5:]):
        pass # replace this line
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)

print("Despesas import handler fixed to process only SAIDAS")
