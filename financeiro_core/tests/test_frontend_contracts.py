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
