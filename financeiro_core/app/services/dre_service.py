from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from typing import Dict, Any

# Imports das regras de domínio e infraestrutura existentes
from financeiro_core.domain.services import CalculadoraFinanceira
from financeiro_core.infrastructure.vendas_client import VendasClientSQL
from financeiro_core.app.services.dre_repositories import DjangoRepositorioTaxas
from financeiro_core.app.models.entidades import ContaPagar

class DREService:
    def __init__(self, vendas_client=None, repositorio_taxas=None):
        self.vendas_client = vendas_client or VendasClientSQL()

        self.repositorio_taxas = repositorio_taxas or DjangoRepositorioTaxas()

    @staticmethod
    def _round(val: Decimal) -> Decimal:
        if val is None:
            return Decimal('0.00')
        return Decimal(str(val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def gerar(self, loja_id: int, mes: int, ano: int, loja_nome: str, gerado_por: str) -> Dict[str, Any]:
        """
        Gera a estrutura consolidada do DRE sem nenhum efeito colateral.
        - Filtra estritamente por regime de caixa (data_transacao)
        - Distribui despesas aplicando a regra de splits (rateio válido/inválido)
        - Aplica taxas de cartão separadamente.
        """
        # 1. Consulta Vendas Base e Taxas de Cartão
        try:
            dados_vendas_api = self.vendas_client.get_faturamento_por_loja(loja_id, mes, ano)
        except Exception as e:
            raise Exception(f"Falha ao obter faturamento. O banco de vendas está indisponível. Detalhe: {str(e)}")

        vendas = CalculadoraFinanceira.calcular_liquido_vendas(
            dados_vendas_api, self.repositorio_taxas, loja_id
        )

        faturamento_bruto = vendas['total_bruto']
        taxas_cartao = vendas['total_taxas']

        # 2. Obter e Processar Despesas com lógica de Splits
        despesas_qs = ContaPagar.objects.filter(
            loja_id_externo=loja_id,
            data_transacao__month=mes,
            data_transacao__year=ano,
            data_transacao__isnull=False
        ).select_related('categoria', 'fornecedor').prefetch_related('splits', 'splits__categoria')

        grupos_totais = {
            'IMPOSTOS': Decimal('0.00'),
            'CUSTOS': Decimal('0.00'),
            'PESSOAL': Decimal('0.00'),
            'ADMINISTRATIVA': Decimal('0.00'),
            'MARKETING': Decimal('0.00'),
            'FINANCEIRA': Decimal('0.00'),
        }

        # Dicionário aninhado: grupo -> categoria_id -> lancamentos[]
        estrutura_analitica = {}

        qtd_consideradas = 0
        qtd_sem_rateio = 0
        qtd_rateio_valido = 0
        qtd_rateio_invalido = 0
        qtd_rateio_ajustado = 0
        valor_rateio_invalido = Decimal('0.00')
        valor_absoluto_ajustes_rateio = Decimal('0.00')
        valor_total_consideradas = Decimal('0.00')
        pessoal_individualizado = {}
        pessoal_nao_individualizado = Decimal('0.00')

        def registrar_pessoal(grupo, valor, vendedor_id, vendedor_nome):
            nonlocal pessoal_nao_individualizado
            if grupo != 'PESSOAL':
                return
            if vendedor_id is not None and vendedor_nome:
                chave = (vendedor_id, vendedor_nome)
                pessoal_individualizado[chave] = (
                    pessoal_individualizado.get(chave, Decimal('0.00')) + valor
                )
            else:
                pessoal_nao_individualizado += valor

        for despesa in despesas_qs:
            valor_liq = despesa.valor_liquido
            splits = sorted(despesa.splits.all(), key=lambda split: split.id)

            qtd_consideradas += 1
            valor_total_consideradas += valor_liq

            if not splits:
                # Regra A: Sem splits
                qtd_sem_rateio += 1
                grupo = despesa.categoria.grupo_contabil
                cat_id = despesa.categoria.id
                cat_nome = despesa.categoria.nome

                grupos_totais[grupo] = grupos_totais.get(grupo, Decimal('0.00')) + valor_liq
                registrar_pessoal(
                    grupo,
                    valor_liq,
                    despesa.vendedor_id_externo,
                    despesa.vendedor_nome_snapshot,
                )

                self._adicionar_lancamento(
                    estrutura_analitica, grupo, cat_id, cat_nome,
                    {
                        "despesa_id": despesa.id,
                        "rateio_id": None,
                        "tipo_origem": "DESPESA",
                        "data_transacao": str(despesa.data_transacao),
                        "descricao": despesa.descricao,
                        "fornecedor_nome": despesa.fornecedor.razao_social if despesa.fornecedor else None,
                        "valor": valor_liq,
                        "vendedor_id_externo": (
                            despesa.vendedor_id_externo
                            if grupo == 'PESSOAL'
                            else None
                        ),
                        "vendedor_nome": (
                            despesa.vendedor_nome_snapshot
                            if grupo == 'PESSOAL'
                            else None
                        ),
                    },
                    valor_liq
                )
            else:
                soma_splits = sum((s.valor for s in splits), Decimal('0.00'))
                residual = valor_liq - soma_splits

                if abs(residual) <= Decimal('0.01'):
                    # Regra B: Splits Válidos
                    qtd_rateio_valido += 1
                    if residual:
                        qtd_rateio_ajustado += 1
                        valor_absoluto_ajustes_rateio += abs(residual)

                    for indice, split in enumerate(splits):
                        ajuste = residual if indice == len(splits) - 1 else Decimal('0.00')
                        v_split = split.valor + ajuste

                        # Fallback seguro para categoria
                        cat = split.categoria if split.categoria else despesa.categoria
                        grupo = cat.grupo_contabil
                        cat_id = cat.id
                        cat_nome = cat.nome

                        grupos_totais[grupo] = grupos_totais.get(grupo, Decimal('0.00')) + v_split
                        registrar_pessoal(
                            grupo,
                            v_split,
                            split.vendedor_id_externo,
                            split.vendedor_nome_snapshot,
                        )

                        self._adicionar_lancamento(
                            estrutura_analitica, grupo, cat_id, cat_nome,
                            {
                                "despesa_id": despesa.id,
                                "rateio_id": split.id,
                                "tipo_origem": "RATEIO",
                                "data_transacao": str(despesa.data_transacao),
                                "descricao": split.descricao or despesa.descricao,
                                "fornecedor_nome": despesa.fornecedor.razao_social if despesa.fornecedor else None,
                                "valor": v_split,
                                "ajuste_conservacao": ajuste,
                                "vendedor_id_externo": (
                                    split.vendedor_id_externo
                                    if grupo == 'PESSOAL'
                                    else None
                                ),
                                "vendedor_nome": (
                                    split.vendedor_nome_snapshot
                                    if grupo == 'PESSOAL'
                                    else None
                                ),
                            },
                            v_split
                        )
                else:
                    # Regra D: Splits Inválidos
                    qtd_rateio_invalido += 1
                    valor_rateio_invalido += valor_liq

                    grupo = despesa.categoria.grupo_contabil
                    cat_id = despesa.categoria.id
                    cat_nome = despesa.categoria.nome

                    grupos_totais[grupo] = grupos_totais.get(grupo, Decimal('0.00')) + valor_liq
                    registrar_pessoal(
                        grupo,
                        valor_liq,
                        despesa.vendedor_id_externo,
                        despesa.vendedor_nome_snapshot,
                    )

                    self._adicionar_lancamento(
                        estrutura_analitica, grupo, cat_id, cat_nome,
                        {
                            "despesa_id": despesa.id,
                            "rateio_id": None,
                            "tipo_origem": "DESPESA",
                            "data_transacao": str(despesa.data_transacao),
                            "descricao": f"[RATEIO INVÁLIDO] {despesa.descricao}",
                            "fornecedor_nome": despesa.fornecedor.razao_social if despesa.fornecedor else None,
                            "valor": valor_liq,
                            "vendedor_id_externo": (
                                despesa.vendedor_id_externo
                                if grupo == 'PESSOAL'
                                else None
                            ),
                            "vendedor_nome": (
                                despesa.vendedor_nome_snapshot
                                if grupo == 'PESSOAL'
                                else None
                            ),
                        },
                        valor_liq
                    )

        # 3. Cascata DRE
        impostos = grupos_totais.get('IMPOSTOS', Decimal('0.00'))
        receita_liquida = faturamento_bruto - impostos

        custos_produtos = grupos_totais.get('CUSTOS', Decimal('0.00'))
        lucro_bruto = receita_liquida - custos_produtos

        despesas_pessoal = grupos_totais.get('PESSOAL', Decimal('0.00'))
        vendedores_pessoal = [
            {
                "vendedor_id_externo": vendedor_id,
                "vendedor_nome": vendedor_nome,
                "valor": valor,
            }
            for (vendedor_id, vendedor_nome), valor in sorted(
                pessoal_individualizado.items(),
                key=lambda item: (item[0][1].casefold(), item[0][0]),
            )
        ]
        total_pessoal_individualizado = sum(
            (item["valor"] for item in vendedores_pessoal),
            Decimal('0.00'),
        )
        pessoal_por_vendedor = {
            "total_pessoal": despesas_pessoal,
            "total_individualizado": total_pessoal_individualizado,
            "total_nao_individualizado": pessoal_nao_individualizado,
            "vendedores": vendedores_pessoal,
        }
        despesas_administrativas = grupos_totais.get('ADMINISTRATIVA', Decimal('0.00'))
        despesas_marketing = grupos_totais.get('MARKETING', Decimal('0.00'))

        despesas_operacionais = despesas_pessoal + despesas_administrativas + despesas_marketing
        resultado_operacional = lucro_bruto - despesas_operacionais

        outras_despesas_financeiras = grupos_totais.get('FINANCEIRA', Decimal('0.00'))
        despesas_financeiras_total = taxas_cartao + outras_despesas_financeiras

        lucro_liquido = resultado_operacional - despesas_financeiras_total
        valor_total_classificado = sum(grupos_totais.values(), Decimal('0.00'))

        # Funções para Margens
        def calc_margem(valor: Decimal) -> Decimal:
            if receita_liquida == 0:
                return Decimal('0.00')
            return self._round((valor / receita_liquida) * 100)

        def calc_perc(valor: Decimal) -> Decimal:
            if faturamento_bruto == 0:
                return Decimal('0.00')
            return self._round((valor / faturamento_bruto) * 100)

        # Mapeamento do Período
        nome_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        periodo_descricao = f"{nome_meses[mes-1]} de {ano}"

        composicao_recebimentos = {
            "dinheiro": {
                "total": vendas['total_dinheiro'],
            },
            "pix": {
                "total": vendas['total_pix'],
                "conta": vendas['total_pix_conta'],
                "maquina": vendas['total_pix_maquina'],
                "nao_detalhado": vendas['total_pix_nao_detalhado'],
            },
            "cartao": {
                "total": vendas['total_cartao'],
                "debito": vendas['total_debito'],
                "credito_avista": vendas['total_credito_avista'],
                "credito_parcelado": vendas['total_credito_parcelado'],
                "credito_nao_identificado": vendas[
                    'total_credito_nao_identificado'
                ],
                "nao_identificado": vendas['total_cartao_nao_identificado'],
            },
            "outros": {
                "total": vendas['total_outros'],
                "voucher": vendas['total_voucher'],
                "nao_identificado": vendas['total_outros_nao_identificados'],
            },
        }
        total_composicao = (
            vendas['total_dinheiro']
            + vendas['total_pix']
            + vendas['total_cartao']
            + vendas['total_outros']
        )
        diferenca_conservacao_receita = self._round(
            total_composicao - faturamento_bruto
        )
        qualidade_recebimentos = {
            "receita_conservada": diferenca_conservacao_receita == Decimal('0.00'),
            "diferenca_conservacao": diferenca_conservacao_receita,
            "valor_credito_sem_detalhe": vendas[
                'total_credito_nao_identificado'
            ],
            "valor_cartao_sem_subtipo": vendas[
                'total_cartao_nao_identificado'
            ],
            "valor_pagamentos_elegiveis_taxa": vendas[
                'valor_pagamentos_elegiveis_taxa'
            ],
            "valor_pagamentos_com_taxa_configurada": vendas[
                'valor_pagamentos_com_taxa_configurada'
            ],
            "valor_pagamentos_sem_taxa_configurada": vendas[
                'valor_pagamentos_sem_taxa_configurada'
            ],
            "possui_credito_sem_detalhe": (
                vendas['total_credito_nao_identificado'] > 0
            ),
            "possui_cartao_sem_subtipo": (
                vendas['total_cartao_nao_identificado'] > 0
            ),
            "possui_pagamentos_elegiveis_sem_taxa": (
                vendas['valor_pagamentos_sem_taxa_configurada'] > 0
            ),
        }

        # Montagem do Contrato Central
        contrato = {
            "identificacao": {
                "loja_id": loja_id,
                "loja_nome": loja_nome,
                "mes": mes,
                "ano": ano,
                "periodo_descricao": periodo_descricao,
                "regime": "CAIXA",
                "gerado_em": timezone.now().isoformat(),
                "gerado_por": gerado_por
            },
            "resumo": {
                "receita_bruta": faturamento_bruto,
                "total_dinheiro": vendas['total_dinheiro'],
                "total_cartao": vendas['total_cartao'],
                "total_pix": vendas['total_pix'],
                "total_outros": vendas['total_outros'],
                "impostos": impostos,
                "receita_liquida": receita_liquida,
                "custos_produtos": custos_produtos,
                "lucro_bruto": lucro_bruto,
                "despesas_pessoal": despesas_pessoal,
                "despesas_administrativas": despesas_administrativas,
                "despesas_marketing": despesas_marketing,
                "despesas_operacionais": despesas_operacionais,
                "resultado_operacional": resultado_operacional,
                "taxas_cartao": taxas_cartao,
                "outras_despesas_financeiras": outras_despesas_financeiras,
                "despesas_financeiras_total": despesas_financeiras_total,
                "lucro_liquido": lucro_liquido,
                "margem_bruta_percentual": calc_margem(lucro_bruto),
                "margem_operacional_percentual": calc_margem(resultado_operacional),
                "margem_liquida_percentual": calc_margem(lucro_liquido)
            },
            "composicao_recebimentos": composicao_recebimentos,
            "qualidade_recebimentos": qualidade_recebimentos,
            "pessoal_por_vendedor": pessoal_por_vendedor,
            "linhas": [
                {"codigo": "1", "descricao": "Receita Bruta Operacional", "tipo": "TOTAL", "nivel": 0, "ordem": 1, "valor": faturamento_bruto, "percentual_receita": calc_perc(faturamento_bruto)},
                {"codigo": "2", "descricao": "(-) Deduções e Impostos sobre Vendas", "tipo": "SUBTRACAO", "nivel": 1, "ordem": 2, "valor": impostos, "percentual_receita": calc_perc(impostos)},
                {"codigo": "3", "descricao": "Receita Líquida Operacional", "tipo": "TOTAL", "nivel": 0, "ordem": 3, "valor": receita_liquida, "percentual_receita": calc_perc(receita_liquida)},
                {"codigo": "4", "descricao": "(-) Custos de Produtos Vendidos / Serviços Prestados", "tipo": "SUBTRACAO", "nivel": 1, "ordem": 4, "valor": custos_produtos, "percentual_receita": calc_perc(custos_produtos)},
                {"codigo": "5", "descricao": "Lucro Bruto", "tipo": "TOTAL", "nivel": 0, "ordem": 5, "valor": lucro_bruto, "percentual_receita": calc_perc(lucro_bruto)},
                {"codigo": "6", "descricao": "(-) Despesas com Pessoal", "tipo": "SUBTRACAO", "nivel": 1, "ordem": 6, "valor": despesas_pessoal, "percentual_receita": calc_perc(despesas_pessoal)},
                {"codigo": "7", "descricao": "(-) Despesas Administrativas", "tipo": "SUBTRACAO", "nivel": 1, "ordem": 7, "valor": despesas_administrativas, "percentual_receita": calc_perc(despesas_administrativas)},
                {"codigo": "8", "descricao": "(-) Despesas de Vendas e Marketing", "tipo": "SUBTRACAO", "nivel": 1, "ordem": 8, "valor": despesas_marketing, "percentual_receita": calc_perc(despesas_marketing)},
                {"codigo": "9", "descricao": "Total de Despesas Operacionais", "tipo": "TOTAL", "nivel": 1, "ordem": 9, "valor": despesas_operacionais, "percentual_receita": calc_perc(despesas_operacionais)},
                {"codigo": "10", "descricao": "Resultado Operacional antes do Resultado Financeiro", "tipo": "TOTAL", "nivel": 0, "ordem": 10, "valor": resultado_operacional, "percentual_receita": calc_perc(resultado_operacional)},
                {"codigo": "11", "descricao": "(-) Taxas de Meios de Pagamento", "tipo": "SUBTRACAO", "nivel": 1, "ordem": 11, "valor": taxas_cartao, "percentual_receita": calc_perc(taxas_cartao)},
                {"codigo": "12", "descricao": "(-) Outras Despesas Financeiras", "tipo": "SUBTRACAO", "nivel": 1, "ordem": 12, "valor": outras_despesas_financeiras, "percentual_receita": calc_perc(outras_despesas_financeiras)},
                {"codigo": "13", "descricao": "Total de Despesas Financeiras", "tipo": "TOTAL", "nivel": 1, "ordem": 13, "valor": despesas_financeiras_total, "percentual_receita": calc_perc(despesas_financeiras_total)},
                {"codigo": "14", "descricao": "Resultado Líquido do Exercício", "tipo": "TOTAL", "nivel": 0, "ordem": 14, "valor": lucro_liquido, "percentual_receita": calc_perc(lucro_liquido)}
            ],
            "grupos_detalhados": self._formatar_grupos_detalhados(estrutura_analitica, calc_perc),
            "qualidade_dados": {
                "quantidade_despesas_consideradas": qtd_consideradas,
                "quantidade_despesas_sem_rateio": qtd_sem_rateio,
                "quantidade_despesas_com_rateio_valido": qtd_rateio_valido,
                "quantidade_despesas_com_rateio_invalido": qtd_rateio_invalido,
                "quantidade_rateios_com_ajuste_tolerado": qtd_rateio_ajustado,
                "valor_despesas_com_rateio_invalido": valor_rateio_invalido,
                "valor_absoluto_ajustes_rateio": valor_absoluto_ajustes_rateio,
                "valor_total_despesas_consideradas": valor_total_consideradas,
                "valor_total_despesas_classificadas": valor_total_classificado,
                "diferenca_conservacao_despesas": (
                    valor_total_classificado - valor_total_consideradas
                ),
                "possui_rateios_invalidos": qtd_rateio_invalido > 0
            }
        }
        return contrato

    def _adicionar_lancamento(self, estrutura, grupo, cat_id, cat_nome, lancamento, valor):
        if grupo not in estrutura:
            estrutura[grupo] = {"descricao": self._obter_nome_grupo(grupo), "categorias": {}}

        if cat_id not in estrutura[grupo]["categorias"]:
            estrutura[grupo]["categorias"][cat_id] = {
                "categoria_id": cat_id,
                "categoria_nome": cat_nome,
                "lancamentos": [],
                "total": Decimal('0.00')
            }

        estrutura[grupo]["categorias"][cat_id]["lancamentos"].append(lancamento)
        estrutura[grupo]["categorias"][cat_id]["total"] += valor

    def _formatar_grupos_detalhados(self, estrutura, calc_perc_func):
        retorno = []
        for grupo, data in estrutura.items():
            categorias_list = []
            grupo_total = Decimal('0.00')

            for cat_id, cat_data in data["categorias"].items():
                grupo_total += cat_data["total"]
                categorias_list.append({
                    "categoria_id": cat_data["categoria_id"],
                    "categoria_nome": cat_data["categoria_nome"],
                    "total": cat_data["total"],
                    "quantidade_lancamentos": len(cat_data["lancamentos"]),
                    "lancamentos": sorted(cat_data["lancamentos"], key=lambda x: x["data_transacao"])
                })

            retorno.append({
                "grupo_contabil": grupo,
                "descricao": data["descricao"],
                "total": grupo_total,
                "percentual_receita": calc_perc_func(grupo_total),
                "categorias": sorted(categorias_list, key=lambda x: x["categoria_nome"])
            })

        # Ordenar os grupos pela ordem contábil clássica para a listagem analítica
        ordem_grupos = {'IMPOSTOS': 1, 'CUSTOS': 2, 'PESSOAL': 3, 'ADMINISTRATIVA': 4, 'MARKETING': 5, 'FINANCEIRA': 6}
        retorno.sort(key=lambda x: ordem_grupos.get(x["grupo_contabil"], 99))

        return retorno

    def _obter_nome_grupo(self, grupo: str) -> str:
        mapa = {
            'IMPOSTOS': 'Impostos e Deduções da Receita',
            'CUSTOS': 'Custos de Serviço/Produto',
            'PESSOAL': 'Despesas com Pessoal',
            'ADMINISTRATIVA': 'Despesas Administrativas',
            'MARKETING': 'Vendas e Marketing',
            'FINANCEIRA': 'Outras Despesas Financeiras'
        }
        return mapa.get(grupo, grupo)
