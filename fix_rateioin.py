import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "class CategoriaOut(Schema):" in line:
        new_lines.append("""class RateioIn(Schema):
    descricao: str
    valor: Decimal
    categoria_id: Optional[int] = None

""")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
