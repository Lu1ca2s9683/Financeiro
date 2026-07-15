import sys
import re

filepath = './financeiro-frontend/src/app/despesas/page.tsx'
with open(filepath, 'r') as f:
    content = f.read()

# Replace href="/despesas/nova" with href={`/despesas/nova?mes=${mes}&ano=${ano}`}
content = re.sub(r'href="/despesas/nova"', r'href={`/despesas/nova?mes=${mes}&ano=${ano}`}', content)

with open(filepath, 'w') as f:
    f.write(content)

print("Nova Despesa link updated to pass mes and ano")
