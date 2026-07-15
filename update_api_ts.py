import sys

filepath = './financeiro-frontend/src/services/api.ts'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if "importExtrato: async (file: File): Promise<ExtratoItem[]> => {" in line:
        new_lines.append("""
  importarExtratoDespesas: async (lojaId: number | string, file: File): Promise<any[]> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiConfig.post(`/financeiro/extrato/importar-despesas/${lojaId}/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },
""")

with open(filepath, 'w') as f:
    f.writelines(new_lines)
