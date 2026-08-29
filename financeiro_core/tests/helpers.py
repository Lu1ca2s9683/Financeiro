import datetime
import jwt
from django.conf import settings

# Must match settings.SECRET_KEY or what security.py expects. In settings_test.py we set it.
def create_test_token(user_id, active_loja_id):
    payload = {
        "user_id": user_id,
        "active_loja_id": active_loja_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
