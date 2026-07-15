import sys

filepath = './financeiro-frontend/src/app/despesas/page.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "const excluir = async (id: number) => {" in line:
        # Add a save function for imported expenses
        new_lines.append("""
  const salvarImportada = async (index: number) => {
      const item = importedDespesas[index];
      if (!item.categoria_sugerida_id) {
          alert('Por favor, selecione uma categoria para a despesa.');
          return;
      }
      try {
          const payload = {
              descricao: item.descricao_original,
              valor: item.valor,
              categoria_id: item.categoria_sugerida_id,
              data_competencia: item.data_transacao,
              data_transacao: item.data_transacao,
              rateios: item.rateios.map((r: any) => ({
                  descricao: r.descricao,
                  valor: parseFloat(r.valor.replace(',', '.')),
                  categoria_id: r.categoria_id ? Number(r.categoria_id) : undefined
              }))
          };
          await api.createDespesa(payload);
          const newImported = [...importedDespesas];
          newImported.splice(index, 1);
          setImportedDespesas(newImported);
          carregar(); // Recarrega a tabela principal
      } catch (error) {
          console.error(error);
          alert('Erro ao salvar despesa importada.');
      }
  };

  const toggleImportedExpanded = (index: number) => {
      const newImported = [...importedDespesas];
      newImported[index].expanded = !newImported[index].expanded;
      setImportedDespesas(newImported);
  };

  const updateImportedRateio = (index: number, rateioIndex: number, field: string, value: string) => {
      const newImported = [...importedDespesas];
      newImported[index].rateios[rateioIndex][field] = value;
      setImportedDespesas(newImported);
  };

  const addImportedRateio = (index: number) => {
      const newImported = [...importedDespesas];
      newImported[index].rateios.push({ descricao: '', valor: '', categoria_id: '' });
      newImported[index].expanded = true;
      setImportedDespesas(newImported);
  };
""")
        new_lines.append(line)
    elif "return (" in line and "main" in "".join(lines[lines.index(line):lines.index(line)+5]):
        # We need to insert the rendering block just after the Header
        pass
    else:
        new_lines.append(line)

# Let's read the file again to find exactly where to insert the UI
with open(filepath, 'w') as f:
    f.writelines(new_lines)
