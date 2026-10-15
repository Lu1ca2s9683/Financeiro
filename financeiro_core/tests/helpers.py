import datetime
import jwt
from django.conf import settings
from django.db import connections


def seed_financial_access_test_store(user_id, active_loja_id):
    """Fixture de vinculo REAL em tabelas SQLite de teste, nunca em producao.

    O test router so migra auth/contenttypes no alias vendas. O esquema minimo
    dessas duas tabelas espelha as consultas do ERP no contrato financeiro.
    """
    if active_loja_id is None or connections['vendas'].vendor != 'sqlite':
        return
    with connections['vendas'].cursor() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vendas_loja (
                id INTEGER PRIMARY KEY, nome TEXT NOT NULL,
                ativa BOOLEAN NOT NULL DEFAULT 1, grupo_id INTEGER NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vendas_grupolojas_super_usuarios_grupo (
                user_id INTEGER NOT NULL, grupolojas_id INTEGER NOT NULL,
                UNIQUE (user_id, grupolojas_id)
            )
        ''')
        cursor.execute(
            "INSERT OR IGNORE INTO vendas_loja (id, nome, ativa, grupo_id) VALUES (%s, %s, 1, %s)",
            [active_loja_id, f"Loja teste {active_loja_id}", active_loja_id],
        )
        cursor.execute(
            "INSERT OR IGNORE INTO vendas_grupolojas_super_usuarios_grupo (user_id, grupolojas_id) "
            "VALUES (%s, %s)", [user_id, active_loja_id],
        )

# Must match settings.SECRET_KEY or what security.py expects. In settings_test.py we set it.
def create_test_token(user_id, active_loja_id):
    seed_financial_access_test_store(user_id, active_loja_id)
    payload = {
        "user_id": user_id,
        "active_loja_id": active_loja_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
