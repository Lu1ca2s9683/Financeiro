from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from ninja.testing import TestClient

from financeiro_core.app.api.endpoints import router
from financeiro_core.app.services.ofx_parser import OfxParserService

from .helpers import create_test_token


VALID_OFX = """OFXHEADER:100
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260829120000[-3:BRT]
<TRNAMT>125.45
<MEMO>Recebimento PIX
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260830120000[-3:BRT]
<TRNAMT>-40.10
<NAME>Tarifa bancaria
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


class OfxParserServiceTest(TestCase):
    def test_parse_valid_transactions_with_dates_values_and_classification(self):
        transactions = OfxParserService.parse(VALID_OFX)

        self.assertEqual(len(transactions), 2)
        self.assertEqual(
            transactions[0],
            {
                "data_transacao": date(2026, 8, 29),
                "descricao_original": "Recebimento PIX",
                "valor": Decimal("125.45"),
                "tipo": "ENTRADA",
            },
        )
        self.assertEqual(transactions[1]["data_transacao"], date(2026, 8, 30))
        self.assertEqual(transactions[1]["descricao_original"], "Tarifa bancaria")
        self.assertEqual(transactions[1]["valor"], Decimal("40.10"))
        self.assertEqual(transactions[1]["tipo"], "SAIDA")

    def test_malformed_input_fails_cleanly_without_capture_group_error(self):
        malformed = "<OFX><STMTTRN><DTPOSTED>not-a-date<TRNAMT>invalid<MEMO>broken"

        self.assertEqual(OfxParserService.parse(malformed), [])


class OfxImportApiTest(TestCase):
    databases = {"default", "vendas"}

    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.using("vendas").create(username="ofx-user")
        self.loja_id = 15
        self.headers = {
            "Authorization": f"Bearer {create_test_token(self.user.id, self.loja_id)}"
        }

    def _upload(self, content=VALID_OFX):
        return SimpleUploadedFile(
            "extrato.ofx",
            content.encode("utf-8"),
            content_type="application/x-ofx",
        )

    def test_import_endpoint_matches_frontend_contract(self):
        response = self.client.post(
            f"/extrato/importar-despesas/{self.loja_id}/",
            FILES={"file": self._upload()},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(
            set(data[0]),
            {"data_transacao", "descricao_original", "valor", "tipo", "categoria_sugerida_id"},
        )

    def test_import_rejects_store_outside_authenticated_context(self):
        response = self.client.post(
            f"/extrato/importar-despesas/{self.loja_id + 1}/",
            FILES={"file": self._upload()},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 403)

    def test_import_rejects_malformed_file_cleanly(self):
        response = self.client.post(
            f"/extrato/importar-despesas/{self.loja_id}/",
            FILES={"file": self._upload("not an OFX or OFC statement")},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_import_requires_authentication(self):
        response = self.client.post(
            f"/extrato/importar-despesas/{self.loja_id}/",
            FILES={"file": self._upload()},
        )

        self.assertEqual(response.status_code, 401)
