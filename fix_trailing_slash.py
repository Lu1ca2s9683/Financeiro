import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if '@router.post("/extrato/importar-despesas/{loja_id}")' in line:
        new_lines.append(line)
        # Add a trailing slash variant just in case
        new_lines.append('@router.post("/extrato/importar-despesas/{loja_id}/")\n')
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
