import sys

filepath = './financeiro-frontend/src/components/PeriodSelector.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "import { useFinanceiro } from '@/contexts/FinanceiroContext';" in line:
        new_lines.append("import { useDateFilter } from '@/contexts/DateFilterContext';\n")
    elif "  const { mes, setMes, ano, setAno, periodoFormatado } = useFinanceiro();" in line:
        new_lines.append("  const { mes, setMes, ano, setAno } = useDateFilter();\n")
        new_lines.append("  const nomeMeses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];\n")
        new_lines.append("  const periodoFormatado = `${nomeMeses[mes - 1]} de ${ano}`;\n")
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)

print("PeriodSelector refactored to use DateFilterContext instead of FinanceiroContext")
