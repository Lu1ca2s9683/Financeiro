import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "class DespesaIn(Schema):" in line:
        new_lines.append(line)
    elif "    data_vencimento: date" in line and "DespesaIn" in "".join(lines[lines.index(line)-10:lines.index(line)]):
        new_lines.append("    data_transacao: date\n")
        new_lines.append("    rateios: List[RateioIn] = []\n")
    elif "status: str" in line and "DespesaOut" in "".join(lines[lines.index(line)-10:lines.index(line)]):
        new_lines.append("    data_transacao: Optional[date] = None\n")
    elif "    dias_para_vencimento: Optional[int] = None" in line:
        pass
    elif "    is_vencendo: bool = False" in line:
        pass
    elif "    is_atrasado: bool = False" in line:
        pass
    elif "    @staticmethod" in line and "resolve_dias_para_vencimento" in "".join(lines[lines.index(line):lines.index(line)+2]):
        pass
    elif "    def resolve_dias_para_vencimento(obj):" in line:
        pass
    elif "        if obj.status == 'PAGO':" in line and "resolve_dias_para_vencimento" in "".join(lines[lines.index(line)-3:lines.index(line)]):
        pass
    elif "            return None" in line and "resolve_dias_para_vencimento" in "".join(lines[lines.index(line)-5:lines.index(line)]):
        pass
    elif "        return (obj.data_vencimento - date.today()).days" in line and "resolve_dias_para_vencimento" in "".join(lines[lines.index(line)-6:lines.index(line)]):
        pass
    elif "    @staticmethod" in line and "resolve_is_vencendo" in "".join(lines[lines.index(line):lines.index(line)+2]):
        pass
    elif "    def resolve_is_vencendo(obj):" in line:
        pass
    elif "        if obj.status == 'PAGO':" in line and "resolve_is_vencendo" in "".join(lines[lines.index(line)-3:lines.index(line)]):
        pass
    elif "            return False" in line and "resolve_is_vencendo" in "".join(lines[lines.index(line)-5:lines.index(line)]):
        pass
    elif "        dias = (obj.data_vencimento - date.today()).days" in line and "resolve_is_vencendo" in "".join(lines[lines.index(line)-6:lines.index(line)]):
        pass
    elif "        return 0 <= dias <= 7" in line and "resolve_is_vencendo" in "".join(lines[lines.index(line)-7:lines.index(line)]):
        pass
    elif "    @staticmethod" in line and "resolve_is_atrasado" in "".join(lines[lines.index(line):lines.index(line)+2]):
        pass
    elif "    def resolve_is_atrasado(obj):" in line:
        pass
    elif "        if obj.status == 'PAGO':" in line and "resolve_is_atrasado" in "".join(lines[lines.index(line)-3:lines.index(line)]):
        pass
    elif "            return False" in line and "resolve_is_atrasado" in "".join(lines[lines.index(line)-5:lines.index(line)]):
        pass
    elif "        return obj.status == 'ATRASADO' or (obj.data_vencimento < date.today())" in line and "resolve_is_atrasado" in "".join(lines[lines.index(line)-6:lines.index(line)]):
        pass
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
