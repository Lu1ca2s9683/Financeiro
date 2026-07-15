import sys

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

out_lines = []
in_dashboard_func = False
dashboard_start = -1
dashboard_end = -1

for i, line in enumerate(lines):
    if line.startswith('def obter_resumo_dashboard('):
        in_dashboard_func = True
        dashboard_start = i

    if in_dashboard_func and line.startswith('def ') and not line.startswith('def obter_resumo_dashboard('):
        in_dashboard_func = False
        dashboard_end = i
        break

if in_dashboard_func and dashboard_end == -1:
    dashboard_end = len(lines)

new_func = """def obter_resumo_dashboard(request, loja_id: int, mes: int, ano: int):
    \"\"\"Retorna dados agregados para o dashboard usando Regime de Caixa (data_transacao).\"\"\"
    print(f"DEBUG: Endpoint Dashboard acessado pelo usuário {request.auth}")
    check_permission(request, loja_id)

    despesas = ContaPagar.objects.filter(
        loja_id_externo=loja_id,
        data_transacao__month=mes,
        data_transacao__year=ano
    ).prefetch_related('splits')

    total = despesas.count()
    if total == 0:
        return {
            "percentual_pago": 100.0,
            "percentual_atrasado": 0.0,
            "percentual_previsto": 0.0,
            "total_despesas_mes": 0,
            "despesas_vencendo_semana": 0,
            "despesas_atrasadas": 0,
            "saude_financeira": "SAUDAVEL",
            "mensagem_assistente": "Nenhuma despesa lançada no regime de caixa para este período."
        }

    total_despesas_mes = 0

    for d in despesas:
        if d.splits.exists():
            for split in d.splits.all():
                total_despesas_mes += float(split.valor)
        else:
            total_despesas_mes += float(d.valor_liquido)

    # Como filtramos por data_transacao, consideramos tudo como pago/caixa.
    perc_pago = 100.0
    perc_atrasado = 0.0
    perc_previsto = 0.0

    return {
        "percentual_pago": round(perc_pago, 1),
        "percentual_atrasado": round(perc_atrasado, 1),
        "percentual_previsto": round(perc_previsto, 1),
        "total_despesas_mes": round(total_despesas_mes, 2),
        "despesas_vencendo_semana": 0,
        "despesas_atrasadas": 0,
        "saude_financeira": "SAUDAVEL",
        "mensagem_assistente": "Resumo calculado em regime de caixa com sucesso."
    }
"""

with open(filepath, 'w') as f:
    f.writelines(lines[:dashboard_start])
    f.write(new_func)
    f.writelines(lines[dashboard_end:])

print("Dashboard endpoint updated")
