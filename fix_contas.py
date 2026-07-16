import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "@router.post(\"/contas/\", response=ContaBancariaOut, auth=AuthBearer())" in line:
        new_lines.append("""@router.get("/contas/", response=List[ContaBancariaOut])
def listar_contas(request):
    \"\"\"Lista as contas bancárias da loja ativa.\"\"\"
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")
    return ContaBancaria.objects.filter(loja_id_externo=active_loja_id, ativo=True)

""")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
