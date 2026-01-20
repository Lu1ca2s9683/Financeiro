import pytest
from decimal import Decimal
from financeiro_core.domain.services import (
    CalculadoraFinanceira, ProcessadorFechamento,
    FaturamentoBruto, TaxasCalculadas
)


class TestCalculadoraFinanceira:
    def test_calcular_taxas_cartao(self):
        calculadora = CalculadoraFinanceira()

        faturamento = FaturamentoBruto(
            debito=Decimal('1000.00'),
            credito_vista=Decimal('2000.00'),
            credito_parcelado=Decimal('1500.00')
        )

        taxas = {
            'debito': {'percentual': Decimal('1.5'), 'fixo': Decimal('0.10')},
            'credito_vista': {'percentual': Decimal('2.5'), 'fixo': Decimal('0.20')},
            'credito_parcelado': {'percentual': Decimal('3.5'), 'fixo': Decimal('0.30')},
        }

        resultado = calculadora.calcular_taxas_cartao(faturamento, taxas)

        assert isinstance(resultado, TaxasCalculadas)
        assert resultado.taxa_debito == Decimal('15.10')  # 1000 * 0.015 + 0.10
        assert resultado.taxa_credito_vista == Decimal('50.20')  # 2000 * 0.025 + 0.20
        assert resultado.taxa_credito_parcelado == Decimal('52.80')  # 1500 * 0.035 + 0.30
        assert resultado.total_taxas == Decimal('118.10')

    def test_calcular_taxas_cartao_taxas_incompletas(self):
        calculadora = CalculadoraFinanceira()

        faturamento = FaturamentoBruto(
            debito=Decimal('1000.00'),
            credito_vista=Decimal('2000.00'),
            credito_parcelado=Decimal('1500.00')
        )

        taxas_incompletas = {
            'debito': {'percentual': Decimal('1.5'), 'fixo': Decimal('0.10')},
            # Faltando credito_vista e credito_parcelado
        }

        with pytest.raises(ValueError, match="Taxas para todos os tipos de cartão devem ser fornecidas"):
            calculadora.calcular_taxas_cartao(faturamento, taxas_incompletas)


class MockVendasClient:
    def obter_faturamento(self, loja_id, mes, ano):
        return FaturamentoBruto(
            debito=Decimal('1000.00'),
            credito_vista=Decimal('2000.00'),
            credito_parcelado=Decimal('1500.00')
        )


class MockRepositorioPerfilTaxa:
    def obter_taxas_por_loja(self, loja_id):
        return {
            'debito': {'percentual': Decimal('1.5'), 'fixo': Decimal('0.10')},
            'credito_vista': {'percentual': Decimal('2.5'), 'fixo': Decimal('0.20')},
            'credito_parcelado': {'percentual': Decimal('3.5'), 'fixo': Decimal('0.30')},
        }


class MockRepositorioFechamento:
    def __init__(self):
        self.fechamentos_salvos = []

    def salvar_fechamento(self, fechamento_data):
        self.fechamentos_salvos.append(fechamento_data)


class TestProcessadorFechamento:
    def test_processar_fechamento_previa(self):
        vendas_client = MockVendasClient()
        calculadora = CalculadoraFinanceira()
        repo_perfil = MockRepositorioPerfilTaxa()
        repo_fechamento = MockRepositorioFechamento()

        processador = ProcessadorFechamento(
            vendas_client, calculadora, repo_perfil, repo_fechamento
        )

        previa = processador.processar_fechamento_previa(1, 1, 2024)

        assert previa['faturamento_bruto'] == Decimal('4500.00')
        assert previa['total_taxas_cartao'] == Decimal('118.10')
        assert previa['total_despesas'] == Decimal('5000.00')  # Valor mock
        assert previa['lucro_liquido'] == Decimal('4500.00') - Decimal('118.10') - Decimal('5000.00')

    def test_processar_fechamento_definitivo(self):
        vendas_client = MockVendasClient()
        calculadora = CalculadoraFinanceira()
        repo_perfil = MockRepositorioPerfilTaxa()
        repo_fechamento = MockRepositorioFechamento()

        processador = ProcessadorFechamento(
            vendas_client, calculadora, repo_perfil, repo_fechamento
        )

        processador.processar_fechamento_definitivo(1, 1, 2024)

        assert len(repo_fechamento.fechamentos_salvos) == 1
        fechamento = repo_fechamento.fechamentos_salvos[0]
        assert fechamento['loja_id_externo'] == 1
        assert fechamento['mes'] == 1
        assert fechamento['ano'] == 2024