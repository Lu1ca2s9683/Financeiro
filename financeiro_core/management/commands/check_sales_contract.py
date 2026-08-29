from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "Checks whether the external Sales database satisfies Financeiro's read contract."

    def handle(self, *args, **options):
        auth_user_table = User._meta.db_table
        required_schema = {
            auth_user_table: [field.column for field in User._meta.concrete_fields],
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
        }

        try:
            connection = connections["vendas"]
            with connection.cursor() as cursor:
                introspection = connection.introspection
                tables = set(introspection.table_names(cursor))

                missing_tables = [table for table in required_schema if table not in tables]
                missing_columns = {}

                for table, columns in required_schema.items():
                    if table not in tables:
                        continue
                    description = introspection.get_table_description(cursor, table)
                    actual_columns = {column.name for column in description}
                    missing = [column for column in columns if column not in actual_columns]
                    if missing:
                        missing_columns[table] = missing

                if missing_tables or missing_columns:
                    messages = []
                    if missing_tables:
                        messages.append(
                            "Missing required tables in vendas DB: " + ", ".join(missing_tables)
                        )
                    for table, columns in missing_columns.items():
                        messages.append(
                            f"Missing required columns in {table}: {', '.join(columns)}"
                        )
                    raise CommandError(" | ".join(messages))

        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"Database introspection failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Sales database contract is valid."))
