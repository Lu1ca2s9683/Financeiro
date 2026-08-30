from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class FrontendPhase1ContractTest(SimpleTestCase):
    @classmethod
    def _read_frontend(cls, relative_path):
        path = Path(settings.BASE_DIR) / "financeiro-frontend" / "src" / relative_path
        return path.read_text(encoding="utf-8")

    def test_dashboard_keeps_fechamento_when_auxiliary_summary_fails(self):
        source = self._read_frontend(Path("app") / "page.tsx")

        self.assertIn("Promise.allSettled", source)
        self.assertNotIn("Promise.all([", source)

    def test_dashboard_reads_frozen_closing_before_calculating_open_period(self):
        api_source = self._read_frontend(Path("services") / "api.ts")
        dashboard_source = self._read_frontend(Path("app") / "page.tsx")

        self.assertIn("getFechamentoPersistido", api_source)
        self.assertIn("method: 'GET'", api_source)
        self.assertIn("persisted?.status === 'CONCLUIDO'", api_source)
        self.assertIn("return persisted", api_source)
        self.assertIn("api.getFechamento(lojaId, mes, ano)", dashboard_source)
        self.assertNotIn("api.calcularFechamento", dashboard_source)

    def test_dashboard_does_not_render_unknown_legacy_breakdown_as_zero(self):
        source = self._read_frontend(Path("app") / "page.tsx")

        self.assertIn('value={dados.total_dinheiro}', source)
        self.assertIn('value={dados.total_cartao}', source)
        self.assertIn('value={dados.total_pix}', source)
        self.assertNotIn('dados.total_dinheiro ?? 0', source)
        self.assertNotIn('dados.total_cartao ?? 0', source)
        self.assertNotIn('dados.total_pix ?? 0', source)
        self.assertIn("value == null ? '—'", source)

    def test_conferencia_uses_central_api_store_context_and_no_mock_sales(self):
        source = self._read_frontend(Path("app") / "relatorios" / "conferencia" / "page.tsx")

        self.assertIn("useFinanceiro", source)
        self.assertIn("api.importarExtratoDespesas", source)
        self.assertIn("Dados de vendas não disponíveis", source)
        self.assertNotIn("vendasMock", source)
        self.assertNotIn("localhost:8000", source)
        self.assertNotIn("localStorage.getItem('token')", source)
        self.assertNotIn("active_loja_id", source)

    def test_ofx_callers_share_the_registered_route_and_token_helper(self):
        api_source = self._read_frontend(Path("services") / "api.ts")
        despesas_source = self._read_frontend(Path("app") / "despesas" / "page.tsx")

        self.assertIn("/extrato/importar-despesas/${lojaId}/", api_source)
        self.assertNotIn("/import-statement/", api_source)
        self.assertIn("api.importarExtratoDespesas(activeLoja.id, file)", despesas_source)
        self.assertNotIn("onrender.com/api/financeiro", despesas_source)

    def test_transfer_frontend_uses_canonical_data_field(self):
        source = self._read_frontend(Path("app") / "tesouraria" / "page.tsx")

        self.assertIn("data: new Date()", source)
        self.assertNotIn("data_ocorrencia", source)

    def test_dre_types_expose_payment_composition_and_quality(self):
        source = self._read_frontend(Path("services") / "api.ts")

        self.assertIn("composicao_recebimentos", source)
        self.assertIn("qualidade_recebimentos", source)
        self.assertIn("credito_nao_identificado", source)
        self.assertIn("valor_pagamentos_sem_taxa_configurada", source)

    def test_dre_page_explains_payment_composition_without_dashboard_changes(self):
        source = self._read_frontend(Path("app") / "relatorios" / "dre" / "page.tsx")
        dashboard = self._read_frontend(Path("app") / "page.tsx")

        self.assertIn("COMPOSIÇÃO DOS RECEBIMENTOS", source)
        self.assertIn("Pix em Conta", source)
        self.assertIn("Pix via Maquininha", source)
        self.assertIn("Crédito — parcelamento não informado", source)
        self.assertIn("Taxa não configurada", source)
        self.assertNotIn("COMPOSIÇÃO DOS RECEBIMENTOS", dashboard)

    def test_reporting_hub_describes_only_current_capabilities(self):
        source = self._read_frontend(Path("app") / "relatorios" / "page.tsx")
        normalized = source.lower()

        self.assertIn("regime de caixa", normalized)
        self.assertIn('href="/relatorios/dre"', source)
        self.assertIn(">Abrir DRE<", source)
        self.assertIn('href="/despesas"', source)
        self.assertIn(">Consultar despesas<", source)
        self.assertNotIn("Baixar Excel", source)
        self.assertNotIn("detalhado por competência", normalized)
        self.assertNotIn("centro de custo", normalized)
