import sys

filepath = './financeiro-frontend/src/components/DespesaForm.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "data_competencia: new Date().toISOString().slice(0, 10)," in line:
        # Check if we have context in URL
        new_lines.append("    data_competencia: (() => {\n")
        new_lines.append("      if (typeof window !== 'undefined') {\n")
        new_lines.append("        const urlParams = new URLSearchParams(window.location.search);\n")
        new_lines.append("        const mes = urlParams.get('mes');\n")
        new_lines.append("        const ano = urlParams.get('ano');\n")
        new_lines.append("        if (mes && ano) {\n")
        new_lines.append("          const m = mes.padStart(2, '0');\n")
        new_lines.append("          return `${ano}-${m}-01`;\n")
        new_lines.append("        }\n")
        new_lines.append("      }\n")
        new_lines.append("      return new Date().toISOString().slice(0, 10);\n")
        new_lines.append("    })(),\n")
    elif "data_transacao: new Date().toISOString().slice(0, 10)" in line and "form" in ''.join(new_lines[-10:]):
        new_lines.append("    data_transacao: (() => {\n")
        new_lines.append("      if (typeof window !== 'undefined') {\n")
        new_lines.append("        const urlParams = new URLSearchParams(window.location.search);\n")
        new_lines.append("        const mes = urlParams.get('mes');\n")
        new_lines.append("        const ano = urlParams.get('ano');\n")
        new_lines.append("        if (mes && ano) {\n")
        new_lines.append("          const m = mes.padStart(2, '0');\n")
        new_lines.append("          return `${ano}-${m}-01`;\n")
        new_lines.append("        }\n")
        new_lines.append("      }\n")
        new_lines.append("      return new Date().toISOString().slice(0, 10);\n")
        new_lines.append("    })()\n")
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)

print("DespesaForm updated to inherit dates from URL params")
