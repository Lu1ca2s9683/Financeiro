import sys

filepath = './financeiro-frontend/src/app/despesas/page.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "const formData = new FormData();" in line and "try {" in "".join(lines[i-5:i]):
        new_lines.append("""                            const lojaId = activeLoja?.id || (typeof window !== 'undefined' ? localStorage.getItem('active_loja_id') : '1') || '1';
                            const extratoTransacoes = await api.importarExtratoDespesas(lojaId, file);
                            setImportedDespesas(extratoTransacoes.map((t: any, idx: number) => ({ ...t, _tempId: idx, expanded: false, rateios: [] })));
                            alert(`Extrato lido com sucesso! ${extratoTransacoes.length} saídas aguardam categorização.`);
""")
        skip = True
    elif skip and "} catch (error) {" in line:
        skip = False
        new_lines.append(line)
    elif not skip:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
