from datetime import date
from decimal import Decimal

from django.test import TestCase

from financeiro_core.app.services.dre_repositories import DjangoRepositorioTaxas
from financeiro_core.models import PerfilTaxaCartao, TaxaMaquininha


class DeterministicCardFeeSelectionTest(TestCase):
    def _perfil(self, nome, inicio):
        return PerfilTaxaCartao.objects.create(
            nome=nome,
            loja_id_externo=5,
            data_inicio_vigencia=inicio,
            ativo=True,
        )

    @staticmethod
    def _taxa(
        perfil,
        bandeira,
        percentual,
        parcela_inicial=1,
        parcela_final=1,
        tipo="CREDITO_AVISTA",
    ):
        return TaxaMaquininha.objects.create(
            perfil=perfil,
            tipo=tipo,
            bandeira=bandeira,
            parcela_inicial=parcela_inicial,
            parcela_final=parcela_final,
            taxa_percentual=Decimal(percentual),
            taxa_fixa=Decimal("0.10"),
        )

    def test_exact_brand_precedes_general_fallback(self):
        perfil = self._perfil("Atual", date(2026, 1, 1))
        self._taxa(perfil, "GERAL", "3.00")
        self._taxa(perfil, "VISA", "1.50")

        taxa = DjangoRepositorioTaxas().buscar_taxa(
            5, "CREDITO_AVISTA", "visa", 1
        )

        self.assertEqual(taxa.percentual, Decimal("1.50"))

    def test_general_is_used_only_as_fallback(self):
        perfil = self._perfil("Atual", date(2026, 1, 1))
        self._taxa(perfil, "GERAL", "3.00")

        taxa = DjangoRepositorioTaxas().buscar_taxa(
            5, "CREDITO_AVISTA", "MASTER", 1
        )

        self.assertEqual(taxa.percentual, Decimal("3.00"))

    def test_installment_range_is_respected(self):
        perfil = self._perfil("Atual", date(2026, 1, 1))
        self._taxa(
            perfil,
            "VISA",
            "4.25",
            parcela_inicial=2,
            parcela_final=6,
            tipo="CREDITO_PARCELADO",
        )

        repo = DjangoRepositorioTaxas()
        taxa = repo.buscar_taxa(5, "CREDITO_PARCELADO", "VISA", 4)

        self.assertEqual(taxa.percentual, Decimal("4.25"))
        self.assertIsNone(repo.buscar_taxa(5, "CREDITO_PARCELADO", "VISA", 1))

    def test_no_matching_fee_returns_none(self):
        self.assertIsNone(
            DjangoRepositorioTaxas().buscar_taxa(5, "DEBITO", "VISA", 1)
        )

    def test_multiple_active_profiles_choose_latest_start_deterministically(self):
        antigo = self._perfil("Antigo", date(2025, 1, 1))
        atual = self._perfil("Atual", date(2026, 1, 1))
        self._taxa(antigo, "VISA", "1.00")
        self._taxa(atual, "VISA", "2.00")

        taxa = DjangoRepositorioTaxas().buscar_taxa(
            5, "CREDITO_AVISTA", "VISA", 1
        )

        self.assertEqual(taxa.percentual, Decimal("2.00"))

    def test_newer_profile_general_beats_older_profile_exact_brand(self):
        antigo = self._perfil("Perfil 2025", date(2025, 1, 1))
        atual = self._perfil("Perfil 2026", date(2026, 1, 1))
        self._taxa(antigo, "VISA", "1.00")
        self._taxa(atual, "GERAL", "2.00")

        taxa = DjangoRepositorioTaxas().buscar_taxa(
            5, "CREDITO_AVISTA", "VISA", 1
        )

        self.assertEqual(taxa.percentual, Decimal("2.00"))

    def test_newer_profile_exact_beats_older_profile_general(self):
        antigo = self._perfil("Perfil 2025", date(2025, 1, 1))
        atual = self._perfil("Perfil 2026", date(2026, 1, 1))
        self._taxa(antigo, "GERAL", "3.00")
        self._taxa(atual, "VISA", "1.50")

        taxa = DjangoRepositorioTaxas().buscar_taxa(
            5, "CREDITO_AVISTA", "VISA", 1
        )

        self.assertEqual(taxa.percentual, Decimal("1.50"))

    def test_same_start_date_uses_highest_profile_id(self):
        primeiro = self._perfil("Primeiro", date(2026, 1, 1))
        segundo = self._perfil("Segundo", date(2026, 1, 1))
        self._taxa(primeiro, "VISA", "1.00")
        self._taxa(segundo, "GERAL", "2.00")

        taxa = DjangoRepositorioTaxas().buscar_taxa(
            5, "CREDITO_AVISTA", "VISA", 1
        )

        self.assertEqual(taxa.percentual, Decimal("2.00"))

    def test_rate_from_another_store_is_not_applicable(self):
        perfil_outra_loja = PerfilTaxaCartao.objects.create(
            nome="Outra loja",
            loja_id_externo=6,
            data_inicio_vigencia=date(2027, 1, 1),
            ativo=True,
        )
        self._taxa(perfil_outra_loja, "VISA", "0.50")

        self.assertIsNone(
            DjangoRepositorioTaxas().buscar_taxa(
                5, "CREDITO_AVISTA", "VISA", 1
            )
        )
