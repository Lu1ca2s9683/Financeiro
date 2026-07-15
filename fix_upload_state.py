import sys

filepath = './financeiro-frontend/src/app/despesas/page.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "const [totalMes, setTotalMes] = useState(0);" in line:
        new_lines.append(line)
        new_lines.append("  // Estado para extrato importado pendente de categorização\n")
        new_lines.append("  const [importedDespesas, setImportedDespesas] = useState<any[]>([]);\n")
        new_lines.append("  const [categoriasPendentes, setCategoriasPendentes] = useState<any[]>([]);\n")
        new_lines.append("  \n")
        new_lines.append("  useEffect(() => {\n")
        new_lines.append("      api.getCategorias().then(setCategoriasPendentes).catch(console.error);\n")
        new_lines.append("  }, []);\n")
    elif "const res = await fetch(`http://localhost:8000/api/financeiro/extrato/importar/${lojaId}`" in line:
        new_lines.append(line.replace('/extrato/importar/', '/extrato/importar-despesas/'))
    elif "const saidas = extratoTransacoes.filter((t: any) => t.tipo === 'SAIDA');" in line:
        pass # don't filter again, it's already filtered in the backend
    elif "const extratoTransacoes = await res.json();" in line:
        new_lines.append("                                const extratoTransacoes = await res.json();\n")
        new_lines.append("                                setImportedDespesas(extratoTransacoes.map((t: any, idx: number) => ({ ...t, _tempId: idx, expanded: false, rateios: [] })));\n")
    elif "alert(`Extrato importado com sucesso! Encontradas" in line:
        new_lines.append("                                alert(`Extrato lido com sucesso! ${extratoTransacoes.length} saídas aguardam categorização.`);\n")
    elif "// window.location.reload();" in line or "window.location.reload();" in line:
        pass # don't reload
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)

print("Frontend state updated to handle pending imported expenses")
