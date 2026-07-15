import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "def importar_extrato_despesas(" in line:
        skip = True
        new_lines.append(line)
        new_lines.append("""    \"\"\"Importa um arquivo OFX/OFC filtrando estritamente para SAIDAS.\"\"\"
    import re

    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id or int(active_loja_id) != loja_id:
        raise HttpError(400, "Loja inválida no contexto")

    check_permission(request, loja_id)

    try:
        conteudo = file.read().decode('latin-1', errors='ignore')
    except Exception as e:
        raise HttpError(400, "Erro ao ler a codificação do ficheiro.")

    transacoes_negativas = []

    blocos = conteudo.split('<STMTTRN>')

    for bloco in blocos[1:]:
        try:
            dt_match = re.search(r'<DTPOSTED>(\d{8})', bloco)
            amt_match = re.search(r'<TRNAMT>([\-\d\.]+)', bloco)
            memo_match = re.search(r'<MEMO>(.*)', bloco)

            if dt_match and amt_match and memo_match:
                valor = float(amt_match.group(1))

                if valor < 0:
                    data_str = dt_match.group(1)
                    data_formatada = f"{data_str[0:4]}-{data_str[4:6]}-{data_str[6:8]}"

                    descricao = memo_match.group(1).strip()

                    categoria_sug = OfxParserService.adivinhar_categoria(descricao, active_loja_id)

                    transacoes_negativas.append({
                        "data_transacao": data_formatada,
                        "descricao_original": descricao,
                        "valor": valor,
                        "tipo": "SAIDA",
                        "categoria_sugerida_id": categoria_sug
                    })
        except Exception:
            continue

    return transacoes_negativas
""")
    elif skip and "return saidas" in line:
        skip = False
    elif skip and "return transacoes_negativas" in line:
        skip = False
    elif not skip:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
