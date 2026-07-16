import sys

filepath = './financeiro-frontend/src/app/relatorios/dre/page.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "import { Download } from 'lucide-react';" in line:
        new_lines.append(line)
        new_lines.append("import { PeriodSelector } from '@/components/PeriodSelector';\n")
    elif '<div className="flex justify-between items-end border-b-2 border-slate-900 pb-4">' in line:
        new_lines.append("""            <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b-2 border-slate-900 pb-4 gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight uppercase">Demonstrativo do Resultado do Exercício</h1>
                    <p className="text-slate-500 mt-1 font-medium">DRE Gerencial Consolidado (Regime de Caixa)</p>
                </div>
                <div className="flex items-center gap-4">
                    <PeriodSelector />
                    <button className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors border border-slate-300 px-4 py-2 rounded-md shadow-sm h-[40px]">
                        <Download size={16} /> PDF
                    </button>
                </div>
            </div>
""")
    elif "                <div>" in line and "Demonstrativo do Resultado do Exercício" in "".join(lines[lines.index(line):lines.index(line)+5]):
        pass
    elif "                    <h1 className=\"text-3xl font-bold text-slate-900 tracking-tight uppercase\">Demonstrativo do Resultado do Exercício</h1>" in line and "DRE Gerencial Consolidado" in "".join(lines[lines.index(line):lines.index(line)+2]):
        pass
    elif "                    <p className=\"text-slate-500 mt-1 font-medium\">DRE Gerencial Consolidado (Regime de Caixa) - {mes}/{ano}</p>" in line:
        pass
    elif "                </div>" in line and "Demonstrativo do Resultado do Exercício" in "".join(lines[lines.index(line)-3:lines.index(line)]):
        pass
    elif "                <button className=\"flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors border border-slate-300 px-4 py-2 rounded-md shadow-sm\">" in line and "Exportar PDF" in "".join(lines[lines.index(line):lines.index(line)+2]):
        pass
    elif "                    <Download size={16} /> Exportar PDF" in line:
        pass
    elif "                </button>" in line and "Exportar PDF" in "".join(lines[lines.index(line)-2:lines.index(line)]):
        pass
    elif "            </div>" in line and "Exportar PDF" in "".join(lines[lines.index(line)-4:lines.index(line)]):
        pass
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
