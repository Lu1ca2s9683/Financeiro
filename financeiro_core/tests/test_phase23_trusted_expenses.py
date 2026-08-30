from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core import signing
from django.test import SimpleTestCase, TestCase
from ninja.testing import TestClient

from financeiro_core.app.api.endpoints import router
from financeiro_core.app.services.dre_service import DREService
from financeiro_core.infrastructure.vendas_client import VendasClientSQL
from financeiro_core.models import (
    CategoriaDespesa,
    ContaBancaria,
    ContaPagar,
    FechamentoMensal,
    RateioDespesa,
)

from .helpers import create_test_token


class TrustedExpenseWriteTest(TestCase):
    databases = {"default", "vendas"}

    def setUp(self):
        self.client = TestClient(router)
        self.loja_id = 41
        user = User.objects.using("vendas").create(username="phase23")
        self.headers = {
            "Authorization": f"Bearer {create_test_token(user.id, self.loja_id)}"
        }
        self.pessoal = CategoriaDespesa.objects.create(
            nome="Salários", grupo_contabil="PESSOAL"
        )
        self.administrativa = CategoriaDespesa.objects.create(
            nome="Administrativa", grupo_contabil="ADMINISTRATIVA"
        )
        self.conta_a = ContaBancaria.objects.create(
            nome="Conta A", loja_id_externo=self.loja_id, ativo=True
        )
        self.conta_b = ContaBancaria.objects.create(
            nome="Conta B", loja_id_externo=self.loja_id, ativo=True
        )

    def _payload(self, **overrides):
        payload = {
            "descricao": "Despesa",
            "categoria_id": self.administrativa.id,
            "valor": "100.00",
            "data_competencia": "2026-08-01",
            "data_transacao": "2026-08-20",
            "rateios": [],
        }
        payload.update(overrides)
        return payload

    def _ofx_payload(self, **overrides):
        payload = self._payload(
            origem_lancamento="OFX",
            conta_origem_id=self.conta_a.id,
            ofx_fitid="fit-1",
            ofx_fingerprint="1" * 64,
            descricao_original_extrato="DESCRIÇÃO ORIGINAL",
        )
        payload.update(overrides)
        if "ofx_import_token" not in overrides:
            payload["ofx_import_token"] = signing.dumps(
                {
                    "loja_id": self.loja_id,
                    "conta_origem_id": payload.get("conta_origem_id"),
                    "fitid": payload.get("ofx_fitid"),
                    "fingerprint": payload.get("ofx_fingerprint"),
                    "data_transacao": payload["data_transacao"],
                    "valor": f"{Decimal(str(payload['valor'])):.2f}",
                    "descricao_original_extrato": payload.get(
                        "descricao_original_extrato"
                    ),
                    "tipo": "SAIDA",
                },
                salt="financeiro.ofx.import.v1",
            )
        return payload

    def _existing_ofx(self):
        return ContaPagar.objects.create(
            descricao="Descrição contábil",
            loja_id_externo=self.loja_id,
            categoria=self.administrativa,
            valor_bruto=Decimal("100.00"),
            data_competencia=date(2026, 8, 1),
            data_transacao=date(2026, 8, 20),
            conta_origem=self.conta_a,
            origem_lancamento="OFX",
            ofx_fitid="fit-immutable",
            ofx_fingerprint="a" * 64,
            descricao_original_extrato="BANCO ORIGINAL",
        )

    def test_same_fitid_same_account_is_controlled_conflict(self):
        first = self.client.post(
            "/despesas/", json=self._ofx_payload(), headers=self.headers
        )
        second = self.client.post(
            "/despesas/",
            json=self._ofx_payload(descricao="Descrição local diferente"),
            headers=self.headers,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(ContaPagar.objects.count(), 1)

    def test_same_fitid_different_account_is_allowed(self):
        first = self.client.post(
            "/despesas/", json=self._ofx_payload(), headers=self.headers
        )
        second = self.client.post(
            "/despesas/",
            json=self._ofx_payload(
                conta_origem_id=self.conta_b.id,
                ofx_fingerprint="2" * 64,
            ),
            headers=self.headers,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ContaPagar.objects.count(), 2)

    def test_same_date_description_with_different_fitid_is_allowed(self):
        first = self.client.post(
            "/despesas/", json=self._ofx_payload(), headers=self.headers
        )
        second = self.client.post(
            "/despesas/",
            json=self._ofx_payload(
                ofx_fitid="fit-2",
                ofx_fingerprint="2" * 64,
            ),
            headers=self.headers,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

    def test_same_fingerprint_without_fitid_is_controlled_conflict(self):
        payload = self._ofx_payload(ofx_fitid=None, ofx_fingerprint="f" * 64)

        first = self.client.post("/despesas/", json=payload, headers=self.headers)
        second = self.client.post("/despesas/", json=payload, headers=self.headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_manual_expenses_remain_unaffected_by_ofx_uniqueness(self):
        first = self.client.post(
            "/despesas/", json=self._payload(), headers=self.headers
        )
        second = self.client.post(
            "/despesas/", json=self._payload(), headers=self.headers
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ContaPagar.objects.count(), 2)
        self.assertEqual(
            set(ContaPagar.objects.values_list("origem_lancamento", flat=True)),
            {"MANUAL"},
        )

    def test_missing_token_for_ofx_is_rejected(self):
        response = self.client.post(
            "/despesas/",
            json=self._ofx_payload(ofx_import_token=None),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("token", response.json()["detail"].lower())

    def test_signed_ofx_token_rejects_every_bound_field_tampering(self):
        cases = {
            "ofx_fingerprint": "b" * 64,
            "ofx_fitid": "fit-adulterado",
            "conta_origem_id": self.conta_b.id,
            "data_transacao": "2026-08-21",
            "valor": "100.01",
            "descricao_original_extrato": "DESCRIÇÃO ADULTERADA",
        }

        for field, value in cases.items():
            with self.subTest(field=field):
                payload = self._ofx_payload()
                payload[field] = value
                response = self.client.post(
                    "/despesas/", json=payload, headers=self.headers
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("token", response.json()["detail"].lower())

        self.assertFalse(ContaPagar.objects.exists())

    def test_ofx_amount_and_transaction_date_are_immutable(self):
        expense = self._existing_ofx()

        amount = self.client.put(
            f"/despesas/{expense.id}",
            json=self._payload(valor="100.01"),
            headers=self.headers,
        )
        transaction_date = self.client.put(
            f"/despesas/{expense.id}",
            json=self._payload(data_transacao="2026-08-21"),
            headers=self.headers,
        )

        self.assertEqual(amount.status_code, 400)
        self.assertEqual(transaction_date.status_code, 400)
        self.assertIn("OFX", amount.json()["detail"])
        self.assertIn("OFX", transaction_date.json()["detail"])
        expense.refresh_from_db()
        self.assertEqual(expense.valor_bruto, Decimal("100.00"))
        self.assertEqual(expense.data_transacao, date(2026, 8, 20))

    def test_ofx_accounting_edit_preserves_all_bank_facts(self):
        expense = self._existing_ofx()
        bank_facts = {
            "conta_origem_id": expense.conta_origem_id,
            "valor_bruto": expense.valor_bruto,
            "data_transacao": expense.data_transacao,
            "ofx_fitid": expense.ofx_fitid,
            "ofx_fingerprint": expense.ofx_fingerprint,
            "descricao_original_extrato": expense.descricao_original_extrato,
            "origem_lancamento": expense.origem_lancamento,
        }

        response = self.client.put(
            f"/despesas/{expense.id}",
            json=self._payload(
                descricao="Descrição contábil corrigida",
                categoria_id=self.pessoal.id,
            ),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        expense.refresh_from_db()
        self.assertEqual(expense.descricao, "Descrição contábil corrigida")
        self.assertEqual(expense.categoria, self.pessoal)
        for field, expected in bank_facts.items():
            self.assertEqual(getattr(expense, field), expected)

    def test_ofx_requires_active_account_from_active_store(self):
        wrong_store = ContaBancaria.objects.create(
            nome="Outra", loja_id_externo=99, ativo=True
        )
        inactive = ContaBancaria.objects.create(
            nome="Inativa", loja_id_externo=self.loja_id, ativo=False
        )

        for conta in (wrong_store, inactive):
            with self.subTest(conta=conta.id):
                response = self.client.post(
                    "/despesas/",
                    json=self._ofx_payload(conta_origem_id=conta.id),
                    headers=self.headers,
                )
                self.assertEqual(response.status_code, 400)

        missing = self.client.post(
            "/despesas/",
            json=self._ofx_payload(conta_origem_id=None),
            headers=self.headers,
        )
        self.assertEqual(missing.status_code, 400)

    def test_ofx_creation_in_closed_cash_period_remains_blocked(self):
        FechamentoMensal.objects.create(
            loja_id_externo=self.loja_id,
            mes=8,
            ano=2026,
            faturamento_bruto=Decimal("0.00"),
            total_taxas=Decimal("0.00"),
            receita_liquida=Decimal("0.00"),
            total_despesas=Decimal("0.00"),
            resultado_operacional=Decimal("0.00"),
            status="CONCLUIDO",
        )

        response = self.client.post(
            "/despesas/", json=self._ofx_payload(), headers=self.headers
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(ContaPagar.objects.exists())

    def test_exact_rateio_is_accepted(self):
        response = self.client.post(
            "/despesas/",
            json=self._payload(
                rateios=[
                    {"descricao": "A", "valor": "60.00"},
                    {"descricao": "B", "valor": "40.00"},
                ]
            ),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sum(RateioDespesa.objects.values_list("valor", flat=True)),
            Decimal("100.00"),
        )

    def test_edit_rateio_conserves_prospective_liquid_value_with_discount(self):
        expense = ContaPagar.objects.create(
            descricao="Com desconto",
            loja_id_externo=self.loja_id,
            categoria=self.administrativa,
            valor_bruto=Decimal("100.00"),
            valor_desconto=Decimal("10.00"),
            data_competencia=date(2026, 8, 1),
            data_transacao=date(2026, 8, 20),
        )
        accepted = self.client.put(
            f"/despesas/{expense.id}",
            json=self._payload(
                rateios=[
                    {"descricao": "A", "valor": "60.00"},
                    {"descricao": "B", "valor": "30.00"},
                ]
            ),
            headers=self.headers,
        )

        self.assertEqual(accepted.status_code, 200)
        expense.refresh_from_db()
        self.assertEqual(expense.valor_liquido, Decimal("90.00"))
        self.assertEqual(
            sum(expense.splits.values_list("valor", flat=True)),
            Decimal("90.00"),
        )
        vendas = MagicMock()
        vendas.get_faturamento_por_loja.return_value = []
        dre = DREService(vendas_client=vendas).gerar(
            self.loja_id, 8, 2026, "Loja", "teste"
        )
        self.assertEqual(
            dre["qualidade_dados"]["quantidade_despesas_com_rateio_valido"],
            1,
        )

        rejected = self.client.put(
            f"/despesas/{expense.id}",
            json=self._payload(
                rateios=[
                    {"descricao": "A", "valor": "60.00"},
                    {"descricao": "B", "valor": "40.00"},
                ]
            ),
            headers=self.headers,
        )
        self.assertEqual(rejected.status_code, 400)

    def test_edit_rateio_conserves_prospective_liquid_value_with_surcharge(self):
        expense = ContaPagar.objects.create(
            descricao="Com acréscimo",
            loja_id_externo=self.loja_id,
            categoria=self.administrativa,
            valor_bruto=Decimal("100.00"),
            valor_acrescimo=Decimal("10.00"),
            data_competencia=date(2026, 8, 1),
            data_transacao=date(2026, 8, 20),
        )

        accepted = self.client.put(
            f"/despesas/{expense.id}",
            json=self._payload(
                rateios=[
                    {"descricao": "A", "valor": "60.00"},
                    {"descricao": "B", "valor": "50.00"},
                ]
            ),
            headers=self.headers,
        )

        self.assertEqual(accepted.status_code, 200)
        expense.refresh_from_db()
        self.assertEqual(expense.valor_liquido, Decimal("110.00"))
        self.assertEqual(
            sum(expense.splits.values_list("valor", flat=True)),
            Decimal("110.00"),
        )

    def test_under_over_zero_and_negative_rateios_are_rejected(self):
        cases = (
            (["60.00", "39.00"], "Saldo"),
            (["60.00", "41.00"], "Saldo"),
            (["100.00", "0.00"], "maior que zero"),
            (["101.00", "-1.00"], "maior que zero"),
        )

        for values, message in cases:
            with self.subTest(values=values):
                response = self.client.post(
                    "/despesas/",
                    json=self._payload(
                        rateios=[
                            {"descricao": str(index), "valor": value}
                            for index, value in enumerate(values)
                        ]
                    ),
                    headers=self.headers,
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(message, response.json()["detail"])

        self.assertFalse(ContaPagar.objects.exists())

    def test_parent_seller_and_rateios_are_rejected(self):
        response = self.client.post(
            "/despesas/",
            json=self._payload(
                categoria_id=self.pessoal.id,
                vendedor_id_externo=10,
                rateios=[{"descricao": "Tudo", "valor": "100.00"}],
            ),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("vendedor", response.json()["detail"].lower())

    @patch(
        "financeiro_core.app.api.endpoints.VendasClientSQL.get_vendedores_ativos_por_loja"
    )
    def test_personnel_split_uses_sales_snapshot_not_frontend_name(self, sellers):
        sellers.return_value = [{"id": 10, "nome": "Lucas", "loja_id": self.loja_id}]
        response = self.client.post(
            "/despesas/",
            json=self._payload(
                categoria_id=self.pessoal.id,
                rateios=[
                    {
                        "descricao": "Lucas",
                        "valor": "100.00",
                        "vendedor_id_externo": 10,
                        "vendedor_nome_snapshot": "Nome forjado",
                    }
                ],
            ),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        split = RateioDespesa.objects.get()
        self.assertEqual(split.vendedor_id_externo, 10)
        self.assertEqual(split.vendedor_nome_snapshot, "Lucas")

    @patch(
        "financeiro_core.app.api.endpoints.VendasClientSQL.get_vendedores_ativos_por_loja"
    )
    def test_direct_personnel_payment_uses_sales_snapshot(self, sellers):
        sellers.return_value = [{"id": 10, "nome": "Lucas", "loja_id": self.loja_id}]

        response = self.client.post(
            "/despesas/",
            json=self._payload(
                descricao="Pix Lucas",
                categoria_id=self.pessoal.id,
                vendedor_id_externo=10,
            ),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        despesa = ContaPagar.objects.get()
        self.assertEqual(despesa.vendedor_id_externo, 10)
        self.assertEqual(despesa.vendedor_nome_snapshot, "Lucas")
        self.assertFalse(despesa.splits.exists())

    @patch(
        "financeiro_core.app.api.endpoints.VendasClientSQL.get_vendedores_ativos_por_loja"
    )
    def test_seller_from_another_store_is_rejected(self, sellers):
        sellers.return_value = [{"id": 10, "nome": "Outro", "loja_id": 999}]

        response = self.client.post(
            "/despesas/",
            json=self._payload(
                categoria_id=self.pessoal.id,
                vendedor_id_externo=10,
            ),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("loja atual", response.json()["detail"])

    @patch(
        "financeiro_core.app.api.endpoints.VendasClientSQL.get_vendedores_ativos_por_loja",
        side_effect=AssertionError("historical seller must not be revalidated"),
    )
    def test_edit_preserves_historical_snapshot_without_sales_lookup(self, sellers):
        despesa = ContaPagar.objects.create(
            descricao="Pix Lucas",
            loja_id_externo=self.loja_id,
            categoria=self.pessoal,
            valor_bruto=Decimal("100.00"),
            data_competencia=date(2026, 8, 1),
            data_transacao=date(2026, 8, 20),
            vendedor_id_externo=10,
            vendedor_nome_snapshot="Lucas",
        )

        response = self.client.put(
            f"/despesas/{despesa.id}",
            json=self._payload(
                descricao="Pix Lucas corrigido",
                categoria_id=self.pessoal.id,
                vendedor_id_externo=10,
            ),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        despesa.refresh_from_db()
        self.assertEqual(despesa.vendedor_nome_snapshot, "Lucas")
        sellers.assert_not_called()

    @patch(
        "financeiro_core.app.api.endpoints.VendasClientSQL.get_vendedores_ativos_por_loja"
    )
    def test_non_personnel_seller_is_rejected(self, sellers):
        sellers.return_value = [{"id": 10, "nome": "Lucas", "loja_id": self.loja_id}]
        response = self.client.post(
            "/despesas/",
            json=self._payload(vendedor_id_externo=10),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("PESSOAL", response.json()["detail"])

    @patch(
        "financeiro_core.app.api.endpoints.VendasClientSQL.get_vendedores_ativos_por_loja"
    )
    def test_missing_active_seller_is_rejected(self, sellers):
        sellers.return_value = []
        response = self.client.post(
            "/despesas/",
            json=self._payload(
                categoria_id=self.pessoal.id,
                vendedor_id_externo=10,
            ),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ativo", response.json()["detail"].lower())

    @patch(
        "financeiro_core.app.api.endpoints.VendasClientSQL.get_vendedores_ativos_por_loja"
    )
    def test_sales_unavailable_fails_closed_only_when_seller_is_required(
        self, sellers
    ):
        sellers.side_effect = RuntimeError("Sales indisponível")

        associated = self.client.post(
            "/despesas/",
            json=self._payload(
                categoria_id=self.pessoal.id,
                vendedor_id_externo=10,
            ),
            headers=self.headers,
        )
        plain = self.client.post(
            "/despesas/", json=self._payload(), headers=self.headers
        )

        self.assertEqual(associated.status_code, 503)
        self.assertEqual(plain.status_code, 200)
        self.assertEqual(sellers.call_count, 1)


class ActiveSellerEndpointTest(TestCase):
    databases = {"default", "vendas"}

    def setUp(self):
        self.client = TestClient(router)
        self.loja_id = 51
        user = User.objects.using("vendas").create(username="seller-endpoint")
        self.headers = {
            "Authorization": f"Bearer {create_test_token(user.id, self.loja_id)}"
        }

    @patch(
        "financeiro_core.app.api.endpoints.VendasClientSQL.get_vendedores_ativos_por_loja"
    )
    def test_returns_only_public_active_seller_contract(self, sellers):
        sellers.return_value = [
            {"id": 10, "nome": "Lucas", "loja_id": self.loja_id}
        ]

        response = self.client.get(
            f"/vendedores/ativos/{self.loja_id}", headers=self.headers
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [{"id": 10, "nome": "Lucas", "loja_id": self.loja_id}],
        )
        sellers.assert_called_once_with(self.loja_id)

    @patch(
        "financeiro_core.app.api.endpoints.VendasClientSQL.get_vendedores_ativos_por_loja",
        side_effect=RuntimeError("offline"),
    )
    def test_sales_unavailable_returns_controlled_503(self, sellers):
        response = self.client.get(
            f"/vendedores/ativos/{self.loja_id}", headers=self.headers
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("indisponível", response.json()["detail"])

    def test_active_store_must_match_requested_store(self):
        response = self.client.get(
            f"/vendedores/ativos/{self.loja_id + 1}", headers=self.headers
        )

        self.assertEqual(response.status_code, 403)


class VendasSellerQueryTest(SimpleTestCase):
    @patch("financeiro_core.infrastructure.vendas_client.connections")
    def test_active_sellers_query_is_read_only_scoped_and_deterministic(
        self, connections
    ):
        cursor = MagicMock()
        connections.__getitem__.return_value.cursor.return_value.__enter__.return_value = (
            cursor
        )
        cursor.fetchall.return_value = [(10, "Lucas", 7), (11, "Maria", 7)]

        result = VendasClientSQL().get_vendedores_ativos_por_loja(7)

        query, params = cursor.execute.call_args.args
        self.assertIn("FROM vendas_vendedor", query)
        self.assertIn("loja_id = %s", query)
        self.assertIn("ativo = TRUE", query)
        self.assertIn("ORDER BY nome, id", query)
        self.assertEqual(params, [7])
        self.assertEqual(
            result,
            [
                {"id": 10, "nome": "Lucas", "loja_id": 7},
                {"id": 11, "nome": "Maria", "loja_id": 7},
            ],
        )
