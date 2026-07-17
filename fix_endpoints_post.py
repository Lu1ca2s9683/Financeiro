import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "        try:" in line and "vendas_client = VendasClientSQL()" in "".join(lines[lines.index(line):lines.index(line)+5]) and "calcular_fechamento" in "".join(lines[lines.index(line)-10:lines.index(line)]):
        skip = True
        new_lines.append("""        from financeiro_core.app.services.dre_service import DREService
        service = DREService()
        dre_data = service.gerar(target_loja, mes, ano, f"Loja {target_loja}", "Sistema")
        resumo = dre_data['resumo']

        with transaction.atomic():
            fechamento, created = FechamentoMensal.objects.update_or_create(
                loja_id_externo=target_loja,
                mes=mes,
                ano=ano,
                defaults={
                    'faturamento_bruto': resumo['receita_bruta'],
                    'total_taxas': resumo['taxas_cartao'],
                    'receita_liquida': resumo['receita_liquida'],
                    'total_despesas': resumo['despesas_operacionais'],
                    'resultado_operacional': resumo['resultado_operacional'],
                    'dados_auditoria_snapshot': dre_data
                }
            )
            # Preserva status se ja existia, a menos que especificado

        return {
            "loja_id_externo": fechamento.loja_id_externo,
            "mes": fechamento.mes,
            "ano": fechamento.ano,
            "receita_bruta": fechamento.faturamento_bruto,
            "total_dinheiro": Decimal('0.00'),
            "total_cartao": Decimal('0.00'),
            "total_pix": Decimal('0.00'),
            "impostos": resumo['impostos'],
            "receita_liquida": fechamento.receita_liquida,
            "custos_produtos": resumo['custos_produtos'],
            "lucro_bruto": resumo['lucro_bruto'],
            "despesas_operacionais": fechamento.total_despesas,
            "resultado_operacional": fechamento.resultado_operacional,
            "despesas_financeiras": resumo['despesas_financeiras_total'],
            "lucro_liquido": resumo['lucro_liquido']
        }
""")
    elif skip and "return {" in line and "lucro_liquido" in "".join(lines[lines.index(line):lines.index(line)+15]):
        skip = False # we just bypassed all the old calculation
        pass
    elif skip and "}" in line and "lucro_liquido" in "".join(lines[lines.index(line)-15:lines.index(line)]):
        skip = False
    elif not skip:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
