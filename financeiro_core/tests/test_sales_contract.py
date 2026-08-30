from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class CheckSalesContractCommandTest(TestCase):
    databases = {"default", "vendas"}

    @staticmethod
    def _schema():
        return {
            User._meta.db_table: [field.column for field in User._meta.concrete_fields],
            "vendas_loja": ["id", "nome", "ativa", "grupo_id"],
            "vendas_grupolojas_super_usuarios_grupo": ["grupolojas_id", "user_id"],
            "vendas_loja_gestores": ["loja_id", "user_id"],
            "vendas_userprofile": ["id", "user_id", "loja_id"],
            "vendas_userprofile_lojas_conferencia": ["loja_id", "userprofile_id"],
            "vendas_venda": [
                "id",
                "caixa_id",
                "loja_id",
                "ignorar_faturamento",
                "forma_pagamento",
                "subtipo_pagamento_1",
                "valor_pagamento_1",
                "forma_pagamento_2",
                "subtipo_pagamento_2",
                "valor_pagamento_2",
            ],
            "vendas_caixadiario": ["id", "data"],
            "vendas_estorno": ["id", "venda_id"],
            "vendas_vendedor": ["id", "loja_id", "nome", "ativo"],
        }

    def _configure_introspection(self, mock_connections, schema):
        mock_connection = mock_connections.__getitem__.return_value
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_introspection = MagicMock()
        mock_connection.introspection = mock_introspection
        mock_introspection.table_names.return_value = list(schema)

        def get_table_description(cursor, table):
            return [type("MockColumn", (), {"name": column}) for column in schema[table]]

        mock_introspection.get_table_description.side_effect = get_table_description
        return mock_cursor

    @patch("financeiro_core.management.commands.check_sales_contract.connections")
    def test_compatible_schema(self, mock_connections):
        mock_cursor = self._configure_introspection(mock_connections, self._schema())
        out = StringIO()

        call_command("check_sales_contract", stdout=out)

        self.assertIn("Sales database contract is valid.", out.getvalue())
        mock_cursor.execute.assert_not_called()

    @patch("financeiro_core.management.commands.check_sales_contract.connections")
    def test_missing_required_table(self, mock_connections):
        schema = self._schema()
        del schema["vendas_venda"]
        mock_cursor = self._configure_introspection(mock_connections, schema)

        with self.assertRaises(CommandError) as context:
            call_command("check_sales_contract")

        self.assertIn("Missing required tables in vendas DB: vendas_venda", str(context.exception))
        mock_cursor.execute.assert_not_called()

    @patch("financeiro_core.management.commands.check_sales_contract.connections")
    def test_missing_revenue_column(self, mock_connections):
        schema = self._schema()
        schema["vendas_venda"].remove("forma_pagamento")
        mock_cursor = self._configure_introspection(mock_connections, schema)

        with self.assertRaises(CommandError) as context:
            call_command("check_sales_contract")

        self.assertIn(
            "Missing required columns in vendas_venda: forma_pagamento",
            str(context.exception),
        )
        mock_cursor.execute.assert_not_called()

    @patch("financeiro_core.management.commands.check_sales_contract.connections")
    def test_missing_seller_column(self, mock_connections):
        schema = self._schema()
        schema["vendas_vendedor"].remove("ativo")
        mock_cursor = self._configure_introspection(mock_connections, schema)

        with self.assertRaises(CommandError) as context:
            call_command("check_sales_contract")

        self.assertIn(
            "Missing required columns in vendas_vendedor: ativo",
            str(context.exception),
        )
        mock_cursor.execute.assert_not_called()

    @patch("financeiro_core.management.commands.check_sales_contract.connections")
    def test_missing_auth_user_column(self, mock_connections):
        schema = self._schema()
        schema[User._meta.db_table].remove("email")
        mock_cursor = self._configure_introspection(mock_connections, schema)

        with self.assertRaises(CommandError) as context:
            call_command("check_sales_contract")

        self.assertIn(
            f"Missing required columns in {User._meta.db_table}: email",
            str(context.exception),
        )
        mock_cursor.execute.assert_not_called()

    @patch("financeiro_core.management.commands.check_sales_contract.connections")
    def test_database_unavailable(self, mock_connections):
        mock_connections.__getitem__.side_effect = RuntimeError("Connection refused")

        with self.assertRaises(CommandError) as context:
            call_command("check_sales_contract")

        self.assertIn("Database introspection failed: Connection refused", str(context.exception))
