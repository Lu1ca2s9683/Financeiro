import sys

filepath = './financeiro-frontend/src/app/despesas/page.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "alert('Importação recebida. (Mock visual para teste) ' + file.name);" in line:
        # replace with real api call setup
        new_lines.append("""                        try {
                            const formData = new FormData();
                            formData.append('file', file);

                            const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
                            const lojaId = typeof window !== 'undefined' ? localStorage.getItem('active_loja_id') || '1' : '1';

                            const res = await fetch(`http://localhost:8000/api/financeiro/extrato/importar/${lojaId}`, {
                                method: 'POST',
                                headers: {
                                    'Authorization': `Bearer ${token}`
                                },
                                body: formData
                            });

                            if (res.ok) {
                                alert('Extrato importado com sucesso!');
                                window.location.reload();
                            } else {
                                const errorData = await res.json();
                                alert('Erro ao importar extrato: ' + (errorData.detail || 'Erro desconhecido'));
                            }
                        } catch (error) {
                            console.error('Erro na importação:', error);
                            alert('Erro de conexão ao tentar importar extrato.');
                        }
""")
    elif "// await api.importExtrato(file);" in line:
        pass # remove this line
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)

print("Frontend import mock removed and replaced with real call")
