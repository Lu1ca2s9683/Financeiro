import sys

filepath = './financeiro-frontend/src/services/api.ts'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "  getFechamento: async (lojaId: number, mes: number, ano: number): Promise<Fechamento> => {" in line:
        new_lines.append("""  getDre: async (lojaId: number, mes: number, ano: number): Promise<any> => {
    const res = await fetch(`${API_BASE_URL}/dre/${lojaId}/${mes}/${ano}`, {
      method: 'GET',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Falha ao carregar DRE');
    return res.json();
  },

  downloadDrePdf: async (lojaId: number, mes: number, ano: number): Promise<void> => {
    const res = await fetch(`${API_BASE_URL}/dre/${lojaId}/${mes}/${ano}/pdf`, {
      method: 'GET',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Falha ao baixar PDF');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `DRE_${lojaId}_${mes}_${ano}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  downloadDreXml: async (lojaId: number, mes: number, ano: number): Promise<void> => {
    const res = await fetch(`${API_BASE_URL}/dre/${lojaId}/${mes}/${ano}/xml`, {
      method: 'GET',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Falha ao baixar XML');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `DRE_${lojaId}_${mes}_${ano}.xml`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

""")
    new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
