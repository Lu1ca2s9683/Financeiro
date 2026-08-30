from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from ninja.testing import TestClient

from financeiro_core.app.api.endpoints import router
from financeiro_core.app.services.ofx_parser import OfxParserService
from financeiro_core.models import CategoriaDespesa, ContaBancaria, ContaPagar

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
<FITID>credit-1
<MEMO>Recebimento PIX
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260830120000[-3:BRT]
<TRNAMT>-40.10
<FITID>debit-1
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
        self.assertEqual(transactions[0]["data_transacao"], date(2026, 8, 29))
        self.assertEqual(transactions[0]["descricao_original"], "Recebimento PIX")
        self.assertEqual(transactions[0]["valor"], Decimal("125.45"))
        self.assertEqual(transactions[0]["tipo"], "ENTRADA")
        self.assertEqual(transactions[0]["fitid"], "credit-1")
        self.assertEqual(len(transactions[0]["fingerprint"]), 64)
        self.assertEqual(transactions[1]["data_transacao"], date(2026, 8, 30))
        self.assertEqual(transactions[1]["descricao_original"], "Tarifa bancaria")
        self.assertEqual(transactions[1]["valor"], Decimal("40.10"))
        self.assertEqual(transactions[1]["tipo"], "SAIDA")
        self.assertEqual(transactions[1]["fitid"], "debit-1")

    def test_missing_fitid_uses_stable_distinct_occurrence_fingerprints(self):
        repeated = """<OFX><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260830120000<TRNAMT>-10.00<NAME>TARIFA</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260830120000<TRNAMT>-10.00<NAME>TARIFA</STMTTRN>
</BANKTRANLIST></OFX>"""

        first = OfxParserService.parse(repeated)
        second = OfxParserService.parse(repeated)

        self.assertEqual([item["fitid"] for item in first], [None, None])
        self.assertNotEqual(first[0]["fingerprint"], first[1]["fingerprint"])
        self.assertEqual(
            [item["fingerprint"] for item in first],
            [item["fingerprint"] for item in second],
        )
        self.assertIsInstance(first[0]["valor"], Decimal)

    def test_malformed_block_is_skipped_without_losing_valid_transaction(self):
        content = """<OFX>
<STMTTRN><DTPOSTED>invalid<TRNAMT>broken<MEMO>Inválida</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260830120000<TRNAMT>-12.34<REFNUM>R-9<MEMO>Válida</STMTTRN>
</OFX>"""

        transactions = OfxParserService.parse(content)

        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]["descricao_original"], "Válida")
        self.assertEqual(transactions[0]["refnum"], "R-9")

    def test_malformed_input_fails_cleanly_without_capture_group_error(self):
        malformed = "<OFX><STMTTRN><DTPOSTED>not-a-date<TRNAMT>invalid<MEMO>broken"

        self.assertEqual(OfxParserService.parse(malformed), [])


class OfxImportApiTest(TestCase):
    databases = {"default", "vendas"}

    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.using("vendas").create(username="ofx-user")
        self.loja_id = 15
        self.conta = ContaBancaria.objects.create(
            nome="Banco",
            loja_id_externo=self.loja_id,
            ativo=True,
        )
        self.categoria = CategoriaDespesa.objects.create(nome="Tarifas")
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
            f"/extrato/importar-despesas/{self.loja_id}/?conta_origem_id={self.conta.id}",
            FILES={"file": self._upload()},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(
            set(data[0]),
            {
                "data_transacao",
                "descricao_original",
                "valor",
                "tipo",
                "fitid",
                "fingerprint",
                "trntype",
                "checknum",
                "refnum",
                "name",
                "memo",
                "categoria_sugerida_id",
                "ja_importada",
                "duplicate_reason",
                "ofx_import_token",
            },
        )
        credit, debit = data
        self.assertIsNone(credit["ofx_import_token"])
        self.assertTrue(debit["ofx_import_token"])
        self.assertFalse(data[1]["ja_importada"])

    def test_valid_preview_token_creates_authoritative_ofx_expense(self):
        preview = self.client.post(
            f"/extrato/importar-despesas/{self.loja_id}/?conta_origem_id={self.conta.id}",
            FILES={"file": self._upload()},
            headers=self.headers,
        )
        debit = next(
            item for item in preview.json() if item["tipo"] == "SAIDA"
        )

        response = self.client.post(
            "/despesas/",
            json={
                "descricao": "Tarifa categorizada",
                "categoria_id": self.categoria.id,
                "valor": debit["valor"],
                "data_competencia": debit["data_transacao"],
                "data_transacao": debit["data_transacao"],
                "conta_origem_id": self.conta.id,
                "origem_lancamento": "OFX",
                "ofx_fitid": debit["fitid"],
                "ofx_fingerprint": debit["fingerprint"],
                "descricao_original_extrato": debit["descricao_original"],
                "ofx_import_token": debit["ofx_import_token"],
                "rateios": [],
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        expense = ContaPagar.objects.get()
        self.assertEqual(expense.ofx_fitid, debit["fitid"])
        self.assertEqual(expense.ofx_fingerprint, debit["fingerprint"])

    def test_preview_marks_existing_fitid_for_selected_account(self):
        ContaPagar.objects.create(
            descricao="Descrição local alterada",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal("40.10"),
            data_competencia=date(2026, 8, 1),
            data_transacao=date(2026, 8, 30),
            conta_origem=self.conta,
            origem_lancamento="OFX",
            ofx_fitid="debit-1",
            ofx_fingerprint="a" * 64,
            descricao_original_extrato="Tarifa bancaria",
        )

        response = self.client.post(
            f"/extrato/importar-despesas/{self.loja_id}/?conta_origem_id={self.conta.id}",
            FILES={"file": self._upload()},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        debit = next(item for item in response.json() if item["tipo"] == "SAIDA")
        self.assertTrue(debit["ja_importada"])
        self.assertEqual(debit["duplicate_reason"], "FITID")

    def test_preview_rejects_account_from_another_store_or_inactive(self):
        other = ContaBancaria.objects.create(
            nome="Outra loja",
            loja_id_externo=self.loja_id + 1,
            ativo=True,
        )
        inactive = ContaBancaria.objects.create(
            nome="Inativa",
            loja_id_externo=self.loja_id,
            ativo=False,
        )

        for conta in (other, inactive):
            with self.subTest(conta=conta.id):
                response = self.client.post(
                    f"/extrato/importar-despesas/{self.loja_id}/?conta_origem_id={conta.id}",
                    FILES={"file": self._upload()},
                    headers=self.headers,
                )
                self.assertEqual(response.status_code, 400)

    def test_import_rejects_store_outside_authenticated_context(self):
        response = self.client.post(
            f"/extrato/importar-despesas/{self.loja_id + 1}/?conta_origem_id={self.conta.id}",
            FILES={"file": self._upload()},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 403)

    def test_import_rejects_malformed_file_cleanly(self):
        response = self.client.post(
            f"/extrato/importar-despesas/{self.loja_id}/?conta_origem_id={self.conta.id}",
            FILES={"file": self._upload("not an OFX or OFC statement")},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_import_requires_authentication(self):
        response = self.client.post(
            f"/extrato/importar-despesas/{self.loja_id}/?conta_origem_id={self.conta.id}",
            FILES={"file": self._upload()},
        )

        self.assertEqual(response.status_code, 401)
