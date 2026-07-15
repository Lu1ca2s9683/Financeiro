import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if "def importar_extrato(request, file: UploadedFile = File(...)):" in line:
        pass # keep the old one, but we'll add a new one at the end of the file

new_endpoint = """
@router.post("/extrato/importar-despesas/{loja_id}")
def importar_extrato_despesas(request, loja_id: int, file: UploadedFile = File(...)):
    \"\"\"Importa um arquivo OFX/OFC filtrando estritamente para SAIDAS.\"\"\"
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id or int(active_loja_id) != loja_id:
        raise HttpError(400, "Loja inválida no contexto")

    check_permission(request, loja_id)

    content = file.read().decode('utf-8', errors='ignore')
    transactions = OfxParserService.parse(content)

    saidas = []
    for t in transactions:
        if t['tipo'] == 'SAIDA':
            t['categoria_sugerida_id'] = OfxParserService.adivinhar_categoria(t['descricao_original'], active_loja_id)
            saidas.append(t)

    return saidas
"""

with open(filepath, 'a') as f:
    f.write(new_endpoint)

print("Backend endpoint /extrato/importar-despesas added")
